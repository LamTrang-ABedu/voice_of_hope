const TTS_API = "https://voice-of-hope.onrender.com";
let audio = null;
let lastAudioUrl = null;
const ttsCache = new Map();

window.onload = loadVoices;

async function loadVoices() {
  const loading = document.getElementById("loadingStatus");
  if (loading) loading.style.display = "inline";
  try {
    const res = await fetch(`${TTS_API}/api/voices`);
    const data = await res.json();
    const provider = data.default;
    const providers = data.providers;

    document.getElementById("providerSelect").innerHTML = Object.keys(providers).map(p =>
      `<option value="${p}" ${p === provider ? 'selected' : ''}>${p}</option>`
    ).join('');

    const langSelect = document.getElementById("languageSelect");
    const voiceSelect = document.getElementById("voiceSelect");
    langSelect.innerHTML = '';
    voiceSelect.innerHTML = '';

    const azureVoices = (providers.azure || []).filter(v =>
      ["en-US", "vi-VN"].includes(v.Locale));

    const langMap = {};
    azureVoices.forEach(v => {
      const lang = v.Locale;
      if (!langMap[lang]) langMap[lang] = [];
      langMap[lang].push(v);
    });

    for (const lang in langMap) {
      const langLabelMap = {
        "vi-VN": "Tiếng Việt",
        "en-US": "Tiếng Anh"
      };
      langSelect.innerHTML += `<option value="${lang}">${langLabelMap[lang] || lang}</option>`;
    }

    const updateVoices = () => {
      const selectedLang = langSelect.value;
      const voices = langMap[selectedLang] || [];
      voiceSelect.innerHTML = voices.map(v => {
        const val = v.ShortName;
        const label = v.DisplayName || val;
        return `<option value="${val}">${label}</option>`;
      }).join('');
    };

    langSelect.onchange = updateVoices;
    updateVoices();

  } catch (e) {
    alert("❌ Lỗi tải danh sách voices.");
  } finally {
    if (loading) loading.style.display = "none";
  }
}

async function speakText() {
  const text = document.getElementById("ttsInput").value.trim();
  const provider = document.getElementById("providerSelect").value;
  const language = document.getElementById("languageSelect").value;
  const voice = document.getElementById("voiceSelect").value;
  const speed = parseFloat(document.getElementById("speedSelect").value);

  const cacheKey = JSON.stringify({ text, provider, language, voice });
  const cached = ttsCache.get(cacheKey);
  if (cached) return playFromCache(cached.audioUrl, cached.wordTimings, speed);

  const loading = document.getElementById("loadingStatus");
  if (loading) loading.style.display = "inline";

  try {
    const res = await fetch(`${TTS_API}/api/tts`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ text, provider, language, voice })
    });

    const contentType = res.headers.get("Content-Type");
    if (contentType.startsWith("multipart/mixed")) {
      const boundary = contentType.split("boundary=")[1];
      const buffer = await res.arrayBuffer();
      const { jsonData, audioBlob } = await parseMultipartMixedArrayBuffer(buffer, boundary);
      const wordTimings = jsonData.filter(w => w.type === "Word").map(w => ({
        word: w.text,
        start: w.offset / 1_000_000,
        end: (w.offset + w.duration) / 1_000_000
      }));
      const url = URL.createObjectURL(audioBlob);
      ttsCache.set(cacheKey, { audioUrl: url, wordTimings });
      playFromCache(url, wordTimings, speed);
    } else {
      const blob = await res.blob();
      const url = URL.createObjectURL(blob);
      ttsCache.set(cacheKey, { audioUrl: url });
      playFromCache(url, null, speed);
    }
  } catch (e) {
    alert("❌ Lỗi xử lý audio.");
  } finally {
    if (loading) loading.style.display = "none";
  }
}

function parseMultipartMixedArrayBuffer(buffer, boundary) {
  const text = new TextDecoder().decode(buffer);
  const boundaryMarker = `--${boundary}`;
  const parts = text.split(boundaryMarker).filter(Boolean);
  let jsonPart = null;
  let audioStartIndex = -1;

  for (const part of parts) {
    if (part.includes("application/json")) {
      const jsonMatch = /\r\n\r\n([\s\S]+?)\r\n--/.exec(part + '--');
      if (jsonMatch) jsonPart = JSON.parse(jsonMatch[1]);
    }
    if (part.includes("audio/mpeg")) {
      const partOffset = text.indexOf(part);
      const bodyOffset = text.indexOf("\r\n\r\n", partOffset) + 4;
      const bodyText = text.slice(0, bodyOffset);
      audioStartIndex = bodyText.length;
    }
  }
  const audioBytes = buffer.slice(audioStartIndex);
  const audioBlob = new Blob([audioBytes], { type: 'audio/mpeg' });
  return { jsonData: jsonPart, audioBlob };
}

function estimateTimingsBySentence(text, duration) {
  const sentences = text.match(/[^.!?,;:–—]+[.!?,;:–—\s]*/g) || [text];
  const total = sentences.join('').length;
  let acc = 0;
  return sentences.map(s => {
    const start = acc / total * duration;
    acc += s.length;
    const end = acc / total * duration;
    return { text: s.trim(), start, end };
  });
}

function highlightBySentence(audio, timings) {
  const textarea = document.getElementById("ttsInput");
  const text = textarea.value;
  const sentences = text.match(/[^.!?,;:–—]+[.!?,;:–—\s]*/g) || [text];

  const render = () => {
    const t = audio.currentTime;
    const idx = timings.findIndex((w, i) => t >= w.start && t < w.end);
    if (idx !== -1) {
      let start = 0;
      for (let i = 0; i < idx; i++) start += sentences[i].length;
      const end = start + sentences[idx].length;
      textarea.focus();
      textarea.setSelectionRange(start, end);
    }
    if (!audio.paused && !audio.ended) requestAnimationFrame(render);
  };
  audio.onplay = () => requestAnimationFrame(render);
}

function playFromCache(audioUrl, timings, speed) {
  lastAudioUrl = audioUrl;
  if (audio) audio.pause();
  audio = new Audio(audioUrl);
  audio.playbackRate = speed;

  const text = document.getElementById("ttsInput").value.trim();

  if (timings && timings.length > 0) {
    highlightWithTimestamps(audio, text, timings);
  } else {
    audio.onloadedmetadata = () => {
      const est = estimateTimingsBySentence(text, audio.duration);
      highlightBySentence(audio, est);
      audio.play();
    };
    return;
  }

  audio.play();
}

function togglePlayPause(btn) {
  if (audio) {
    if (audio.paused) {
      audio.play();
      btn.innerHTML = `
        <svg width="20" height="20" fill="currentColor" viewBox="0 0 24 24" xmlns="http://www.w3.org/2000/svg">
          <path d="M6 4h4v16H6V4zm8 0h4v16h-4V4z"/>
        </svg>
        <span style="display:inline-block; width:88px">Tạm dừng</span>`;
    } else {
      audio.pause();
      btn.innerHTML = `
        <svg width="20" height="20" fill="currentColor" viewBox="0 0 24 24" xmlns="http://www.w3.org/2000/svg">
          <path d="M8 5v14l11-7z"/>
        </svg>
        <span style="display:inline-block; width:88px">Tiếp tục</span>`;
    }
  }
}

function downloadAudio() {
  if (lastAudioUrl) {
    const link = document.createElement("a");
    link.href = lastAudioUrl;
    link.download = "tts_output.mp3";
    link.click();
  } else {
    alert("❌ Không có file nào để tải.");
  }
}
