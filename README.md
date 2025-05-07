# README.md

# TTS Microservice API

Chuyển văn bản thành giọng nói (Text-to-Speech) hỗ trợ:
- ✅ ElevenLabs (giọng thật)
- ✅ Azure TTS (giọng neural)
- ✅ gTTS (miễn phí)

## 🛠 Triển khai trên Render
```bash
pip install -r requirements.txt
python app.py
```

## 🌐 API
### `GET /api/voices`
Trả về danh sách giọng đọc từ ElevenLabs → Azure → gTTS

### `POST /api/tts`
Input JSON:
```json
{
  "text": "Xin chào HopeHub",
  "language": "vi",
  "voice": "default",
  "speed": 1.2,
  "provider": "elevenlabs"
}
```
Output: Stream MP3 file

## 🧪 Môi trường (`.env`)
```env
ELEVENLABS_API_KEY=...
AZURE_TTS_KEY=...
AZURE_TTS_REGION=southeastasia
```

---

> Maintained for HopeHub integration.