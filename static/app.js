const $ = (sel) => document.querySelector(sel);

const els = {
  sidebar: $("#sidebar"),
  conversations: $("#conversations"),
  messages: $("#messages"),
  empty: $("#empty"),
  greeting: $("#greeting"),
  title: $("#chat-title"),
  input: $("#input"),
  send: $("#send"),
  mic: $("#mic"),
  composer: $("#composer"),
  status: $("#status"),
  speak: $("#speak-toggle"),
  memoryDialog: $("#memory-dialog"),
  memoryList: $("#memory-list"),
  memoryForm: $("#memory-form"),
  memoryInput: $("#memory-input"),
  settingsDialog: $("#settings-dialog"),
  settingsForm: $("#settings-form"),
  modelsHint: $("#models-hint"),
};

const state = { conversationId: null, busy: false, settings: {} };

// Helpers

async function api(path, options = {}) {
  const res = await fetch(path, {
    headers: options.body && !(options.body instanceof FormData) ? { "Content-Type": "application/json" } : {},
    ...options,
  });
  if (!res.ok) {
    let detail = res.statusText;
    try { detail = (await res.json()).detail || detail; } catch {}
    throw new Error(detail);
  }
  return res.json();
}

function setStatus(text, isError = false) {
  els.status.hidden = !text;
  els.status.textContent = text || "";
  els.status.classList.toggle("error", isError);
}

function escapeHtml(s) {
  return s.replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
}

// Small Markdown subset: code blocks, inline code, bold, lists, line breaks.
function renderMarkdown(src) {
  return src.split("```").map((part, i) => {
    if (i % 2 === 1) {
      const nl = part.indexOf("\n");
      return `<pre><code>${escapeHtml(nl >= 0 ? part.slice(nl + 1) : part)}</code></pre>`;
    }
    return escapeHtml(part)
      .replace(/`([^`\n]+)`/g, "<code>$1</code>")
      .replace(/\*\*([^*\n]+)\*\*/g, "<strong>$1</strong>")
      .replace(/^\s*[-*] (.+)$/gm, "• $1")
      .replace(/^#{1,6} (.+)$/gm, "<strong>$1</strong>")
      .replace(/\n/g, "<br>");
  }).join("");
}

function plainText(src) {
  return src.replace(/```[\s\S]*?```/g, " ").replace(/[*_`#>]/g, "").replace(/\s+/g, " ").trim();
}

function autoGrow() {
  els.input.style.height = "auto";
  els.input.style.height = Math.min(els.input.scrollHeight, 200) + "px";
}

function scrollToBottom() {
  els.messages.scrollTop = els.messages.scrollHeight;
}

function addMessage(role, text) {
  els.empty.hidden = true;
  const wrap = document.createElement("div");
  wrap.className = `msg ${role}`;
  const bubble = document.createElement("div");
  bubble.className = "bubble";
  bubble.innerHTML = role === "user" ? escapeHtml(text).replace(/\n/g, "<br>") : renderMarkdown(text);
  wrap.appendChild(bubble);
  els.messages.appendChild(wrap);
  scrollToBottom();
  return bubble;
}

function setBusy(busy) {
  state.busy = busy;
  els.send.disabled = busy;
  els.mic.disabled = busy;
}

// Conversations

async function loadConversations() {
  const list = await api("/api/conversations");
  els.conversations.innerHTML = "";
  for (const c of list) {
    const item = document.createElement("div");
    item.className = "conv" + (c.id === state.conversationId ? " active" : "");
    item.innerHTML = `<span></span><button title="Sil">🗑</button>`;
    item.querySelector("span").textContent = c.title;
    item.onclick = () => openConversation(c.id, c.title);
    item.querySelector("button").onclick = async (e) => {
      e.stopPropagation();
      if (!confirm(`"${c.title}" sohbeti silinsin mi?`)) return;
      await api(`/api/conversations/${c.id}`, { method: "DELETE" });
      if (c.id === state.conversationId) newConversation();
      loadConversations();
    };
    els.conversations.appendChild(item);
  }
}

function clearMessages() {
  els.messages.querySelectorAll(".msg").forEach((m) => m.remove());
  els.empty.hidden = false;
}

function newConversation() {
  state.conversationId = null;
  els.title.textContent = "Yeni sohbet";
  clearMessages();
  setStatus("");
  loadConversations();
  els.sidebar.classList.remove("open");
  els.input.focus();
}

async function openConversation(id, title) {
  if (state.busy) return;
  state.conversationId = id;
  els.title.textContent = title;
  clearMessages();
  setStatus("");
  for (const m of await api(`/api/conversations/${id}/messages`)) addMessage(m.role, m.content);
  loadConversations();
  els.sidebar.classList.remove("open");
}

// Chat

const seconds = (ms) => (ms / 1000).toFixed(1).replace(".", ",") + " sn";

// Live stopwatch under a reply, then a summary so different computers/models can be compared.
function replyTimer(bubble, sttMs) {
  const el = document.createElement("div");
  el.className = "timing";
  bubble.parentElement.appendChild(el);
  const start = performance.now();
  let firstMs = null;
  const tick = () => { el.textContent = "⏱ " + seconds(performance.now() - start); };
  tick();
  const interval = setInterval(tick, 100);
  return {
    instant: false, // answered from the clock, no model involved
    firstToken() { if (firstMs === null) firstMs = performance.now() - start; },
    finish(ok) {
      clearInterval(interval);
      if (!ok) return el.remove();
      const parts = [];
      if (sttMs != null) parts.push(`ses→yazı ${seconds(sttMs)}`);
      parts.push(`ilk kelime ${seconds(firstMs ?? performance.now() - start)}`);
      parts.push(`toplam ${seconds(performance.now() - start)}`);
      parts.push(this.instant ? "bilgisayar saatinden" : state.settings.model);
      el.textContent = "⏱ " + parts.join(" · ");
    },
  };
}

async function send(text, fromVoice = false, sttMs = null) {
  text = text.trim();
  if (!text || state.busy) return;
  els.input.value = "";
  autoGrow();
  setStatus("");
  setBusy(true);
  stopSpeaking();

  addMessage("user", text);
  const bubble = addMessage("assistant", "");
  bubble.classList.add("typing");
  const timer = replyTimer(bubble, sttMs);
  let reply = "";
  const speaker = (els.speak.checked || fromVoice) ? sentenceSpeaker() : null;
  const round = (state.voiceRound = (state.voiceRound || 0) + 1);

  try {
    const res = await fetch("/api/chat", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ message: text, conversation_id: state.conversationId }),
    });
    if (!res.ok) throw new Error((await res.json()).detail || res.statusText);

    const reader = res.body.getReader();
    const decoder = new TextDecoder();
    let buffer = "";
    for (;;) {
      const { value, done } = await reader.read();
      if (done) break;
      buffer += decoder.decode(value, { stream: true });
      const lines = buffer.split("\n");
      buffer = lines.pop();
      for (const line of lines) {
        if (!line.trim()) continue;
        const event = JSON.parse(line);
        if (event.type === "meta") {
          timer.instant = !!event.instant;
          if (state.conversationId !== event.conversation_id) {
            state.conversationId = event.conversation_id;
            els.title.textContent = text.length > 50 ? text.slice(0, 47) + "..." : text;
          }
        } else if (event.type === "token") {
          timer.firstToken();
          reply += event.text;
          bubble.innerHTML = renderMarkdown(reply);
          scrollToBottom();
          if (speaker) speaker.feed(reply);
        } else if (event.type === "error") {
          throw new Error(event.message);
        }
      }
    }
    if (speaker) speaker.feed(reply, true);
    if (fromVoice && reply) listenAgainAfterReply(round);
    timer.finish(true);
  } catch (err) {
    timer.finish(false);
    bubble.parentElement.classList.add("error");
    bubble.textContent = "⚠️ " + err.message;
  } finally {
    bubble.classList.remove("typing");
    setBusy(false);
    loadConversations();
    els.input.focus();
  }
}

els.composer.addEventListener("submit", (e) => {
  e.preventDefault();
  send(els.input.value);
});

els.input.addEventListener("keydown", (e) => {
  if (e.key === "Enter" && !e.shiftKey) {
    e.preventDefault();
    send(els.input.value);
  }
});
els.input.addEventListener("input", autoGrow);

// Voice input: record in the browser, transcribe locally with Whisper on the server.
// Recording stops by itself once the user has spoken and then stayed quiet for a moment.
// In voice conversations the microphone reopens after the reply has been read aloud.

const SILENCE_MS = 1300;       // quiet time after speech that ends the recording
const MIN_SPEECH_MS = 250;     // this much sound counts as speech (ignores clicks and coughs)
const WAIT_MANUAL_MS = 10000;  // give up if nothing is said after pressing the button...
const WAIT_AUTO_MS = 8000;     // ...or after the microphone reopened by itself
const MAX_RECORDING_MS = 60000;

let recorder = null;

const sleep = (ms) => new Promise((r) => setTimeout(r, ms));

els.mic.addEventListener("click", () => {
  state.voiceRound = (state.voiceRound || 0) + 1; // cancels a pending automatic reopen
  if (recorder && recorder.state === "recording") {
    recorder.stop();
    return;
  }
  stopSpeaking();
  startListening(false);
});

async function startListening(auto) {
  if (state.busy || (recorder && recorder.state === "recording")) return;
  fetch("/api/transcribe/warmup", { method: "POST" }).catch(() => {}); // load the speech model while the user talks
  let stream;
  try {
    stream = await navigator.mediaDevices.getUserMedia({ audio: { echoCancellation: true, noiseSuppression: true } });
  } catch {
    setStatus("Mikrofona erişilemedi. Tarayıcının mikrofon iznini kontrol et.", true);
    return;
  }

  // Loudness meter used to notice the end of speech.
  const audioCtx = new AudioContext();
  const analyser = audioCtx.createAnalyser();
  analyser.fftSize = 2048;
  audioCtx.createMediaStreamSource(stream).connect(analyser);
  const samples = new Float32Array(analyser.fftSize);
  const loudness = () => {
    analyser.getFloatTimeDomainData(samples);
    let sum = 0;
    for (const v of samples) sum += v * v;
    return Math.sqrt(sum / samples.length);
  };

  const chunks = [];
  const rec = new MediaRecorder(stream);
  recorder = rec;
  let heardSpeech = false;
  rec.ondataavailable = (e) => e.data.size && chunks.push(e.data);
  rec.onstop = async () => {
    clearInterval(meter);
    stream.getTracks().forEach((t) => t.stop());
    audioCtx.close();
    els.mic.classList.remove("recording");
    if (!heardSpeech) {
      setStatus(auto ? "Sesli sohbet bitti. Devam etmek için 🎤'a bas." : "Bir şey duyamadım, tekrar dener misin?", !auto);
      return;
    }
    const blob = new Blob(chunks, { type: rec.mimeType });
    setStatus("Ses yazıya çevriliyor... (ilk seferde model indirildiği için birkaç dakika sürebilir)");
    setBusy(true);
    try {
      const form = new FormData();
      form.append("audio", blob, "kayit.webm");
      const sttStart = performance.now();
      const { text } = await api("/api/transcribe", { method: "POST", body: form });
      const sttMs = performance.now() - sttStart;
      setBusy(false);
      if (!text) return setStatus("Bir şey duyamadım, tekrar dener misin?", true);
      send(text, true, sttMs);
    } catch (err) {
      setBusy(false);
      setStatus(err.message, true);
    }
  };

  const started = Date.now();
  let noiseFloor = null;
  let loudMs = 0;
  let quietSince = null;
  const meter = setInterval(() => {
    const now = Date.now();
    const level = loudness();
    if (now - started < 300) {           // first moment: measure the room's background noise
      noiseFloor = Math.max(noiseFloor || 0, level);
      return;
    }
    const loud = level > Math.max(0.02, noiseFloor * 2.5);
    if (loud) {
      loudMs += 100;
      quietSince = null;
      if (loudMs >= MIN_SPEECH_MS) heardSpeech = true;
    } else if (quietSince === null) {
      quietSince = now;
    }
    const waited = now - started;
    if ((heardSpeech && quietSince && now - quietSince >= SILENCE_MS) ||
        (!heardSpeech && waited >= (auto ? WAIT_AUTO_MS : WAIT_MANUAL_MS)) ||
        waited >= MAX_RECORDING_MS) {
      if (rec.state === "recording") rec.stop();
    }
  }, 100);

  rec.start();
  els.mic.classList.add("recording");
  setStatus("🎙️ Dinliyorum... Sustuğunda kendiliğinden gönderilir.");
}

// After a spoken question, reopen the microphone once the reply has been read aloud.
async function listenAgainAfterReply(round) {
  if (!state.settings.auto_listen) return;
  let chain;
  do { chain = playback; await chain; } while (chain !== playback); // online voice queue
  while ("speechSynthesis" in window && (speechSynthesis.speaking || speechSynthesis.pending)) await sleep(200);
  await sleep(300);
  if (round === state.voiceRound && !state.busy) startListening(true);
}

// Voice output: either an online Microsoft neural voice rendered by the server (/api/tts),
// or an offline Windows voice in the browser, so that no text leaves the computer.

function pickVoice() {
  const lang = (state.settings.language || "tr").toLowerCase();
  const local = speechSynthesis.getVoices().filter((v) => v.localService);
  return local.find((v) => v.lang.toLowerCase().startsWith(lang)) || null;
}

function speak(text) {
  if (!text) return;
  if ((state.settings.tts_voice || "windows") === "windows") speakLocal(text);
  else speakOnline(text);
}

function speakLocal(text) {
  if (!("speechSynthesis" in window)) return;
  const voice = pickVoice();
  if (!voice) {
    setStatus("Bu dilde yüklü bir Windows sesi bulunamadı. Ayarlar > Zaman ve dil > Konuşma bölümünden ses ekleyebilirsin.", true);
    return;
  }
  const utterance = new SpeechSynthesisUtterance(text);
  utterance.voice = voice;
  utterance.lang = voice.lang;
  speechSynthesis.speak(utterance); // queued after anything already being spoken
}

// Speaks a streaming reply sentence by sentence, so speech starts with the first sentence
// instead of waiting for the whole answer.
function sentenceSpeaker() {
  let spoken = 0; // characters of the reply already handed to the voice
  return {
    feed(reply, final = false) {
      const rest = reply.slice(spoken);
      let end = rest.length;
      if (!final) {
        end = 0;
        for (const m of rest.matchAll(/[.!?…:]\s|\n/g)) end = m.index + m[0].length;
        // Never cut inside a code block; those are skipped anyway.
        if (reply.slice(0, spoken + end).split("```").length % 2 === 0) return;
      }
      if (end <= 0) return;
      spoken += end;
      speak(plainText(rest.slice(0, end)));
    },
  };
}

// Online voice: every sentence is fetched right away (so the next one is ready in time)
// and played strictly in order.
let playback = Promise.resolve();
let speechRound = 0; // bumped by stopSpeaking() to drop everything still queued
let stopCurrentAudio = null;

function speakOnline(text) {
  const round = speechRound;
  const audio = fetch("/api/tts", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ text }),
  }).then(async (res) => {
    if (!res.ok) throw new Error((await res.json().catch(() => ({}))).detail || res.statusText);
    return res.blob();
  });
  audio.catch(() => {}); // handled below, in order
  playback = playback.then(async () => {
    if (round !== speechRound) return;
    let blob;
    try {
      blob = await audio;
    } catch (err) {
      if (round !== speechRound) return;
      setStatus(`${err.message}. Bu cümle Windows sesiyle okunuyor.`, true);
      return speakLocal(text);
    }
    if (round === speechRound) await playBlob(blob);
  });
}

function playBlob(blob) {
  return new Promise((resolve) => {
    const url = URL.createObjectURL(blob);
    const player = new Audio(url);
    const finish = () => {
      URL.revokeObjectURL(url);
      if (stopCurrentAudio === stop) stopCurrentAudio = null;
      resolve();
    };
    const stop = () => { player.pause(); finish(); };
    stopCurrentAudio = stop;
    player.onended = finish;
    player.onerror = finish;
    player.play().catch(finish);
  });
}

function stopSpeaking() {
  speechRound++;
  playback = Promise.resolve();
  if (stopCurrentAudio) stopCurrentAudio();
  if ("speechSynthesis" in window) speechSynthesis.cancel();
}

if ("speechSynthesis" in window) speechSynthesis.getVoices(); // warms up the voice list

try { els.speak.checked = localStorage.getItem("speak") === "1"; } catch {}
els.speak.addEventListener("change", () => {
  try { localStorage.setItem("speak", els.speak.checked ? "1" : "0"); } catch {}
  if (!els.speak.checked) stopSpeaking();
});

// Memory dialog

async function loadMemories() {
  const list = await api("/api/memories");
  els.memoryList.innerHTML = "";
  if (!list.length) {
    els.memoryList.innerHTML = `<li class="none">Henüz kayıtlı bilgi yok.</li>`;
    return;
  }
  for (const m of list.slice().reverse()) {
    const li = document.createElement("li");
    li.innerHTML = `<span></span><button title="Sil">✕</button>`;
    li.querySelector("span").textContent = m.content;
    li.querySelector("button").onclick = async () => {
      await api(`/api/memories/${m.id}`, { method: "DELETE" });
      loadMemories();
    };
    els.memoryList.appendChild(li);
  }
}

$("#open-memory").onclick = async () => {
  const status = $("#memory-status");
  els.memoryDialog.showModal();
  await loadMemories();
  // Learn from the latest messages right away instead of waiting for the idle timer.
  status.textContent = "⏳ Son konuşmalar taranıyor...";
  try {
    const { added } = await api("/api/memories/learn", { method: "POST" });
    status.textContent = added ? `✅ ${added} yeni bilgi eklendi.` : "Son konuşmalarda yeni bilgi bulunamadı.";
    if (added) await loadMemories();
  } catch (err) {
    status.textContent = "⚠️ " + err.message;
  }
};

els.memoryForm.addEventListener("submit", async (e) => {
  e.preventDefault();
  const content = els.memoryInput.value.trim();
  if (!content) return;
  await api("/api/memories", { method: "POST", body: JSON.stringify({ content }) });
  els.memoryInput.value = "";
  loadMemories();
});

// Settings dialog

const WHISPER_LABELS = { tiny: "en hızlı", base: "hızlı", small: "dengeli", medium: "en iyi" };
const VOICE_LABELS = { "tr-TR-EmelNeural": "Emel", "tr-TR-AhmetNeural": "Ahmet", windows: "Windows sesi" };

async function loadSettings() {
  state.settings = await api("/api/settings");
  const s = state.settings;
  els.greeting.textContent = `Merhaba, ben ${s.assistant_name}!`;
  document.title = s.assistant_name;

  // Sidebar summary of the settings that matter most when comparing speed.
  const lines = [`🤖 Model: ${s.model}`];
  if (s.memory_model && s.memory_model !== s.model) lines.push(`🧠 Hafıza: ${s.memory_model}`);
  lines.push(`🎤 Ses tanıma: ${WHISPER_LABELS[s.whisper_model] || s.whisper_model} (${s.whisper_model})`);
  lines.push(`🔊 Ses: ${VOICE_LABELS[s.tts_voice] || s.tts_voice}`);
  const summary = $("#config-summary");
  summary.innerHTML = "";
  for (const line of lines) {
    const span = document.createElement("span");
    span.textContent = line;
    summary.appendChild(span);
  }
}

$("#open-settings").onclick = async () => {
  const form = els.settingsForm;
  form.assistant_name.value = state.settings.assistant_name;
  form.whisper_model.value = state.settings.whisper_model;
  form.language.value = state.settings.language;
  form.tts_voice.value = state.settings.tts_voice;
  form.auto_listen.checked = !!state.settings.auto_listen;

  const select = form.model;
  select.innerHTML = "";
  let models = [];
  try {
    models = (await api("/api/models")).models;
    els.modelsHint.textContent = models.length ? "" : "Yüklü model yok. Komut isteminde: ollama pull gemma3:4b";
  } catch (err) {
    els.modelsHint.textContent = err.message;
  }
  if (!models.includes(state.settings.model)) models.unshift(state.settings.model);
  for (const name of models) select.add(new Option(name, name));
  select.value = state.settings.model;

  const memSelect = form.memory_model;
  memSelect.innerHTML = "";
  memSelect.add(new Option("Sohbet modeliyle aynı", ""));
  const memModels = models.filter((m) => m !== state.settings.model || m === state.settings.memory_model);
  if (state.settings.memory_model && !memModels.includes(state.settings.memory_model)) memModels.push(state.settings.memory_model);
  for (const name of memModels) memSelect.add(new Option(name, name));
  memSelect.value = state.settings.memory_model || "";

  els.settingsDialog.showModal();
};

els.settingsForm.addEventListener("submit", async (e) => {
  e.preventDefault();
  const data = Object.fromEntries(new FormData(els.settingsForm));
  data.auto_listen = els.settingsForm.auto_listen.checked;
  await api("/api/settings", { method: "PUT", body: JSON.stringify(data) });
  await loadSettings();
  els.settingsDialog.close();
});

document.querySelectorAll("[data-close]").forEach((btn) => {
  btn.onclick = () => btn.closest("dialog").close();
});

// Layout

$("#new-chat").onclick = newConversation;
$("#config-summary").onclick = () => $("#open-settings").click();
$("#toggle-sidebar").onclick = () => els.sidebar.classList.toggle("open");

// Updates: the server restarts itself with new code; tell the user when the open page is older.

const pageVersion = document.querySelector('meta[name="version"]').content;

async function checkVersion() {
  if (state.busy) return;
  try {
    const { version, other_computer: other } = await api("/api/version");
    if (other) {
      setStatus(`⚠️ Asistan şu anda "${other}" bilgisayarında da açık. Sohbetler iki bilgisayarda ortak olduğu için aynı anda kullanmak kayıtları bozabilir; birini kapat.`, true);
    } else if (version !== pageVersion) {
      setStatus(`Yeni sürüm (${version}) yüklendi. Sayfayı yenilemek için F5'e bas.`);
    }
  } catch {
    if (pageVersion.includes("{{")) {
      setStatus("Güncelleme yarım kaldı: baslat.bat penceresini kapatıp yeniden aç.", true);
    }
  }
}

checkVersion();
setInterval(checkVersion, 60000);
window.addEventListener("focus", checkVersion);

loadSettings().catch((err) => setStatus(err.message, true));
loadConversations().catch((err) => setStatus(err.message, true));
