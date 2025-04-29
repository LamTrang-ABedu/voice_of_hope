from flask import Flask, request, jsonify
from utils.tts_manager import generate_audio
from utils.gemini_helper import polish_text

app = Flask(__name__)

@app.route("/generate-voice", methods=["POST"])
def generate_voice():
    data = request.json
    text = data.get("text")
    language = data.get("language", "vi")
    use_gemini = data.get("use_gemini", False)

    if use_gemini:
        text = polish_text(text)

    audio_url = generate_audio(text, language)
    return jsonify({"audio_url": audio_url})

@app.route("/healthcheck")
def health():
    return "OK", 200

if __name__ == "__main__":
    app.run(debug=True)
