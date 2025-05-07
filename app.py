# tts_microservice/app.py

from flask import Flask, request, jsonify, send_file
import requests
from gtts import gTTS
from pydub import AudioSegment
import os
import uuid
import tempfile
from io import BytesIO
from dotenv import load_dotenv
from flask_cors import CORS

app = Flask(__name__)
CORS(app)  # Cho phép tất cả origin gọi API này
load_dotenv()

app = Flask(__name__)

# Load API keys from .env
ELEVENLABS_API_KEY = os.getenv("ELEVENLABS_API_KEY")
AZURE_TTS_KEY = os.getenv("AZURE_TTS_KEY")
AZURE_TTS_REGION = os.getenv("AZURE_TTS_REGION")


@app.route("/api/voices", methods=["GET"])
def get_voices():
    # 1. Try ElevenLabs
    try:
        headers = {"xi-api-key": ELEVENLABS_API_KEY}
        r = requests.get("https://api.elevenlabs.io/v1/voices", headers=headers)
        if r.status_code == 200:
            voices = r.json()
            return jsonify({"provider": "elevenlabs", "voices": voices})
    except Exception:
        pass

    # 2. Try Azure
    try:
        headers = {
            "Ocp-Apim-Subscription-Key": AZURE_TTS_KEY
        }
        url = f"https://{AZURE_TTS_REGION}.tts.speech.microsoft.com/cognitiveservices/voices/list"
        r = requests.get(url, headers=headers)
        if r.status_code == 200:
            voices = r.json()
            return jsonify({"provider": "azure", "voices": voices})
    except Exception:
        pass

    # 3. Fallback: gTTS static list
    from gtts.lang import tts_langs
    voices = tts_langs()
    return jsonify({"provider": "gtts", "voices": voices})


@app.route("/api/tts", methods=["POST"])
def tts_api():
    data = request.get_json()
    text = data.get("text")
    voice = data.get("voice", "default")
    language = data.get("language", "en")
    speed = float(data.get("speed", 1.0))
    provider = data.get("provider", "elevenlabs")

    if not text:
        return jsonify({"error": "Missing 'text' field"}), 400

    audio_stream = BytesIO()

    try:
        if provider == "elevenlabs" and ELEVENLABS_API_KEY:
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
                for chunk in r.iter_content(chunk_size=1024):
                    if chunk:
                        audio_stream.write(chunk)
                audio_stream.seek(0)
            else:
                raise Exception("ElevenLabs TTS failed")

        elif provider == "azure" and AZURE_TTS_KEY:
            token_url = f"https://{AZURE_TTS_REGION}.api.cognitive.microsoft.com/sts/v1.0/issueToken"
            headers = {"Ocp-Apim-Subscription-Key": AZURE_TTS_KEY}
            token = requests.post(token_url, headers=headers).text
            synth_url = f"https://{AZURE_TTS_REGION}.tts.speech.microsoft.com/cognitiveservices/v1"
            headers = {
                "Authorization": f"Bearer {token}",
                "Content-Type": "application/ssml+xml",
                "X-Microsoft-OutputFormat": "audio-16khz-32kbitrate-mono-mp3"
            }
            ssml = f"""
            <speak version='1.0' xml:lang='{language}'>
                <voice name='{voice}'>
                    <prosody rate='{(speed - 1) * 100:+.0f}%'>
                        {text}
                    </prosody>
                </voice>
            </speak>
            """
            r = requests.post(synth_url, headers=headers, data=ssml.encode('utf-8'))
            if r.status_code == 200:
                audio_stream.write(r.content)
                audio_stream.seek(0)
            else:
                raise Exception("Azure TTS failed")

        else:
            tts = gTTS(text=text, lang=language)
            tts_fp = BytesIO()
            tts.write_to_fp(tts_fp)
            tts_fp.seek(0)

            if speed != 1.0:
                sound = AudioSegment.from_file(tts_fp, format="mp3")
                adjusted = sound._spawn(sound.raw_data, overrides={
                    "frame_rate": int(sound.frame_rate * speed)
                }).set_frame_rate(sound.frame_rate)
                adjusted.export(audio_stream, format="mp3")
            else:
                audio_stream = tts_fp

        return send_file(audio_stream, mimetype="audio/mpeg")

    except Exception as e:
        return jsonify({"error": str(e)}), 500


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=10000)
