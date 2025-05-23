# tts_microservice/app.py

from flask import Flask, request, jsonify, send_file, Response, render_template
import requests
import os
import uuid
from io import BytesIO
from dotenv import load_dotenv
from flask_cors import CORS
import json
from gtts import gTTS
from pydub import AudioSegment
from gtts.lang import tts_langs

load_dotenv()

app = Flask(__name__)
CORS(app)

ELEVENLABS_API_KEY = os.getenv("ELEVENLABS_API_KEY")
AZURE_TTS_KEY = os.getenv("AZURE_TTS_KEY")
AZURE_TTS_REGION = os.getenv("AZURE_TTS_REGION")

@app.route("/api/voices", methods=["GET"])
def get_voices():
    result = {"default": None, "providers": {}}

    # Try Azure first
    try:
        headers = {"Ocp-Apim-Subscription-Key": AZURE_TTS_KEY}
        url = f"https://{AZURE_TTS_REGION}.tts.speech.microsoft.com/cognitiveservices/voices/list"
        r = requests.get(url, headers=headers)
        print("Azure voice status:", r.status_code)
        if r.status_code == 200:
            print("Azure TTS voices fetched successfully")
            voices = r.json()
            result["providers"]["azure"] = voices
            result["default"] = "azure"
            print("providers default:", result["default"])
    except Exception:
        pass

    # Then ElevenLabs
    try:
        headers = {"xi-api-key": ELEVENLABS_API_KEY}
        r = requests.get("https://api.elevenlabs.io/v1/voices", headers=headers)
        if r.status_code == 200:
            voices = r.json()
            result["providers"]["elevenlabs"] = voices
            if not result["default"]:
                result["default"] = "elevenlabs"
                print("providers default:", result["default"])
    except Exception:
        pass

    # Then gTTS
    try:
        voices = tts_langs()
        result["providers"]["gtts"] = voices
        if not result["default"]:
            result["default"] = "gtts"
    except Exception:
        result["providers"]["gtts"] = {}
        if not result["default"]:
            result["default"] = "gtts"

    return jsonify(result)

@app.route("/api/tts", methods=["POST"])
def tts_api():
    data = request.get_json()
    text = data.get("text")
    voice = data.get("voice")
    language = data.get("language", "en-US")
    provider = data.get("provider", "azure")

    if not text:
        return jsonify({"error": "Missing 'text' field"}), 400

    if provider == "azure" and AZURE_TTS_KEY:
        try:
            token_url = f"https://{AZURE_TTS_REGION}.api.cognitive.microsoft.com/sts/v1.0/issueToken"
            headers = {"Ocp-Apim-Subscription-Key": AZURE_TTS_KEY}
            token = requests.post(token_url, headers=headers).text

            ssml = f"""
            <speak version='1.0' xml:lang='{language}'>
              <voice name='{voice}'>
                {text}
              </voice>
            </speak>
            """

            # get speech marks (streaming JSONL)
            marks_headers = {
                "Authorization": f"Bearer {token}",
                "Content-Type": "application/ssml+xml",
                "X-Microsoft-OutputFormat": "json"
            }
            marks_url = f"https://{AZURE_TTS_REGION}.tts.speech.microsoft.com/cognitiveservices/voices/streaming"
            marks_response = requests.post(marks_url, headers=marks_headers, data=ssml.encode("utf-8"))

            word_timings = []
            if marks_response.status_code == 200:
                for line in marks_response.text.strip().split("\n"):
                    try:
                        item = json.loads(line)
                        if item.get("type") == "Word":
                            word_timings.append(item)
                    except:
                        continue
            print("Word timings:", word_timings)
            # generate mp3
            synth_url = f"https://{AZURE_TTS_REGION}.tts.speech.microsoft.com/cognitiveservices/v1"
            audio_headers = {
                "Authorization": f"Bearer {token}",
                "Content-Type": "application/ssml+xml",
                "X-Microsoft-OutputFormat": "audio-16khz-32kbitrate-mono-mp3"
            }
            audio_response = requests.post(synth_url, headers=audio_headers, data=ssml.encode("utf-8"))

            if audio_response.status_code != 200:
                raise Exception("Azure audio failed")

            def generate():
                yield b"--ttsboundary\r\n"
                yield b"Content-Type: application/json\r\n\r\n"
                yield json.dumps(word_timings).encode("utf-8")
                yield b"\r\n--ttsboundary\r\n"
                yield b"Content-Type: audio/mpeg\r\n\r\n"
                yield audio_response.content
                yield b"\r\n--ttsboundary--"

            return Response(generate(), mimetype="multipart/mixed; boundary=ttsboundary")

        except Exception as e:
            return jsonify({"error": str(e)}), 500

    if provider == "elevenlabs" and ELEVENLABS_API_KEY:
        try:
            url = f"https://api.elevenlabs.io/v1/text-to-speech/{voice}"
            headers = {
                "xi-api-key": ELEVENLABS_API_KEY,
                "Content-Type": "application/json"
            }
            payload = {
                "text": text,
                "voice_settings": {
                    "stability": 0.5,
                    "similarity_boost": 0.5,
                    "style": 0.0,
                    "use_speaker_boost": True
                }
            }
            r = requests.post(url, headers=headers, json=payload, stream=True)
            if r.status_code == 200:
                return Response(r.iter_content(chunk_size=1024), mimetype="audio/mpeg")
        except Exception:
            pass

    # fallback gTTS
    tts = gTTS(text=text, lang=language.split("-")[0])
    audio_stream = BytesIO()
    tts.write_to_fp(audio_stream)
    audio_stream.seek(0)
    return send_file(audio_stream, mimetype="audio/mpeg")


@app.route('/')
def voice_of_hope():
    return render_template('index.html')

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5001)
