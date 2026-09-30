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
      .replace(/\[([^\]\n]+)\]\((https?:\/\/[^\s)]+)\)/g, '<a href="$2" target="_blank" rel="noopener noreferrer">$1</a>')
      .replace(/^\s*[-*] (.+)$/gm, "• $1")
      .replace(/^#{1,6} (.+)$/gm, "<strong>$1</strong>")
      .replace(/\n/g, "<br>");
  }).join("");
}

function plainText(src) {
  return src.replace(/```[\s\S]*?```/g, " ").replace(/\[([^\]\n]+)\]\([^)\s]+\)/g, "$1").replace(/[*_`#>]/g, "").replace(/\s+/g, " ").trim();
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
    item.innerHTML = `<span></span><button class="rename" title="Adını değiştir">✏️</button><button class="delete" title="Sil">🗑</button>`;
    item.querySelector("span").textContent = c.title;
    item.onclick = () => openConversation(c.id, c.title);
    item.querySelector(".rename").onclick = (e) => {
      e.stopPropagation();
      renameConversation(c.id, c.title);
    };
    item.querySelector(".delete").onclick = async (e) => {
      e.stopPropagation();
      if (!confirm(`"${c.title}" sohbeti silinsin mi?`)) return;
      await api(`/api/conversations/${c.id}`, { method: "DELETE" });
      if (c.id === state.conversationId) newConversation();
      loadConversations();
    };
    els.conversations.appendChild(item);
  }
}

// 3.25: conversations are named "202609301324 Merhaba" by the server; the name can be changed here or on the title.
async function renameConversation(id, current) {
  const title = prompt("Sohbetin yeni adı:", current);
  if (title === null || !title.trim() || title.trim() === current) return;
  try {
    const result = await api(`/api/conversations/${id}`, { method: "PUT", body: JSON.stringify({ title }) });
    if (id === state.conversationId) els.title.textContent = result.title;
  } catch (err) {
    setStatus(err.message, true);
  }
  loadConversations();
}

els.title.title = "Adını değiştirmek için tıkla";
els.title.onclick = () => { if (state.conversationId) renameConversation(state.conversationId, els.title.textContent); };

function clearMessages() {
  els.messages.querySelectorAll(".msg").forEach((m) => m.remove());
  els.empty.hidden = false;
}

function newConversation() {
  state.conversationId = null;
  els.title.textContent = "Yeni sohbet";
  clearMessages();
  loadDocs();
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
  loadDocs();
  loadConversations();
  els.sidebar.classList.remove("open");
}

// Chat

const seconds = (ms) => (ms / 1000).toFixed(1).replace(".", ",") + " sn";

// Live stopwatch under a reply, then a summary so different computers/models can be compared.
function replyTimer(bubble, sttMs, sttDevice) {
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
      if (sttMs != null) parts.push(`ses→yazı ${seconds(sttMs)}${sttDevice ? ` (${sttDevice.toUpperCase()})` : ""}`);
      parts.push(`ilk kelime ${seconds(firstMs ?? performance.now() - start)}`);
      parts.push(`toplam ${seconds(performance.now() - start)}`);
      parts.push(this.instant ? "hazır cevap (yapay zekâ kullanılmadı)" : state.settings.model);
      el.textContent = "⏱ " + parts.join(" · ");
    },
  };
}

async function send(text, fromVoice = false, sttMs = null, sttDevice = null) {
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
  const timer = replyTimer(bubble, sttMs, sttDevice);
  let reply = "";
  let notice = false; // lock/switch notice: shown briefly, not part of the conversation
  let newIdentity = null;
  const speaker = (els.speak.checked || fromVoice) ? sentenceSpeaker() : null;
  const round = (state.voiceRound = (state.voiceRound || 0) + 1);

  try {
    const res = await fetch("/api/chat", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ message: text, conversation_id: state.conversationId, via: fromVoice ? "ses" : "yazı" }),
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
          notice = !!event.notice;
          newIdentity = event.identity || null;
          if (notice) continue;
          if (state.conversationId !== event.conversation_id) {
            state.conversationId = event.conversation_id;
            els.title.textContent = event.title || text;
          }
        } else if (event.type === "progress") { // a long document is being read part by part
          if (!reply) bubble.textContent = event.text;
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
    if (notice) {
      timer.finish(false);
      bubble.parentElement.previousElementSibling?.remove(); // the typed code itself
      bubble.parentElement.remove();
      applyIdentity(newIdentity);
      setStatus(reply);
      return;
    }
    applyIdentity(newIdentity);
    loadAgenda(); // "yarın 9'da ... hatırlat" shows up on the right at once
    if ($("#notes-dialog").open) loadNotes();
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

// The microphone, through the calibrated gain (Ayarlar > Mikrofon). Everything records from here:
// chat, voice commands, voice enrollment. The analyser measures the level after the gain.
async function openMic({ gainDb = Number(state.settings.mic_gain) || 0, agc = !state.settings.mic_calibrated } = {}) {
  const raw = await navigator.mediaDevices.getUserMedia({
    audio: { echoCancellation: true, noiseSuppression: true, autoGainControl: agc },
  });
  const ctx = new AudioContext();
  const source = ctx.createMediaStreamSource(raw);
  const gain = ctx.createGain();
  gain.gain.value = Math.pow(10, gainDb / 20);
  const out = ctx.createMediaStreamDestination();
  const analyser = ctx.createAnalyser();
  analyser.fftSize = 2048;
  source.connect(gain);
  gain.connect(out);
  gain.connect(analyser);
  const samples = new Float32Array(analyser.fftSize);
  return {
    stream: out.stream,
    level() { // RMS and peak of the last ~40 ms, after the gain
      analyser.getFloatTimeDomainData(samples);
      let sum = 0, peak = 0;
      for (const v of samples) { sum += v * v; peak = Math.max(peak, Math.abs(v)); }
      return { rms: Math.sqrt(sum / samples.length), peak };
    },
    ctx, node: gain, // the wake listener reads the raw samples from here
    close() { raw.getTracks().forEach((t) => t.stop()); ctx.close(); },
  };
}

// auto: reopened after a spoken reply; handsFree: nobody pressed the button (auto or after the wake word), so song
// lyrics heard from music are dropped by the server.
async function startListening(auto, handsFree = auto) {
  if (state.busy || (recorder && recorder.state === "recording")) return;
  fetch("/api/transcribe/warmup", { method: "POST" }).catch(() => {}); // load the speech model while the user talks
  let mic;
  try {
    mic = await openMic();
  } catch {
    setStatus("Mikrofona erişilemedi. Tarayıcının mikrofon iznini kontrol et.", true);
    return;
  }
  const loudness = () => mic.level().rms; // used to notice the end of speech

  const chunks = [];
  const rec = new MediaRecorder(mic.stream);
  recorder = rec;
  let heardSpeech = false;
  rec.ondataavailable = (e) => e.data.size && chunks.push(e.data);
  rec.onstop = async () => {
    clearInterval(meter);
    mic.close();
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
      if (handsFree) form.append("hands_free", "true");
      const sttStart = performance.now();
      const { text, device, identity, voice_too_short: tooShort, echo, music } = await api("/api/transcribe", { method: "POST", body: form });
      state.voiceTooShort = !!tooShort; // guest bar asks for a longer sentence
      const sttMs = performance.now() - sttStart;
      showSttDevice(device);
      applyIdentity(identity); // a different voice starts its own conversation
      setBusy(false);
      if (echo) return setStatus("🔇 Hoparlörden kendi okuduğum cevabı duydum; mesaj olarak almadım.");
      if (music) return setStatus("🎵 Müzik ya da yabancı dilde şarkı sözü duydum; mesaj olarak almadım. Sesli sohbet bitti.");
      if (!text) return handsFree ? setStatus("Sesli sohbet bitti. Devam etmek için 🎤'a bas ya da adımla seslen.")
        : setStatus("Bir şey duyamadım, tekrar dener misin?", true);
      send(text, true, sttMs, device);
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
  const guest = !!state.identity?.guest;
  els.memoryForm.hidden = guest;
  els.memoryList.innerHTML = "";
  if (guest) {
    els.memoryList.innerHTML = `<li class="none">Misafir modunda hafıza gösterilmez. Kendi hafızanı görmek için konuş.</li>`;
    return;
  }
  const list = await api("/api/memories");
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
  status.textContent = "";
  await loadMemories();
  if (state.identity?.guest) return;
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

// Voice identification: who is talking (shown under the message box), voice profiles, security log.

function identityKey(id) {
  return id ? (id.name || (id.guest ? "misafir" : "herkes")) : null;
}

function applyIdentity(id) {
  if (!id) return;
  const before = identityKey(state.identity);
  state.identity = id;
  const bar = $("#identity-bar");
  bar.hidden = !id.active;
  bar.classList.toggle("guest", !!id.guest);
  bar.textContent = id.guest
    ? (state.voiceTooShort
      ? "👤 Misafir — çok kısa konuştun, sesinden tanıyamadım. Bir cümle daha söyle."
      : "👤 Misafir — tanınmıyor. Kendi oturumun için konuş.")
    : `👤 ${id.name}${id.admin ? " · yönetici" : ""}`;
  $("#open-security").hidden = !(id.active && id.admin);
  $("#open-reminders").hidden = !!id.guest; // reminders are personal
  $("#open-notes").hidden = !!id.guest;
  if (id.guest) $("#notes-dialog").close();
  showAgenda(!id.guest);
  if (id.guest) $("#agenda-weather").hidden = true;
  else if (before !== identityKey(id)) loadAgendaWeather(true);
  if (id.guest) $("#reminders-dialog").close();
  // Only the admin reaches Settings (enrolling voices, models); everyone else uses the admin's settings.
  const locked = !!(id.active && !id.admin);
  $("#open-settings").hidden = locked;
  $("#config-summary").disabled = locked;
  if (locked) els.settingsDialog.close();
  if (before !== null && before !== identityKey(id)) {
    // Another person: their own conversations and a fresh chat.
    state.conversationId = null;
    els.title.textContent = "Yeni sohbet";
    clearMessages();
    loadConversations();
  }
}

// Chosen to cover every Turkish vowel and consonant (ç ğ ı ö ş ü j f h v z ...) so the voiceprint
// hears the whole range of the voice, not just a few sounds.
const ENROLL_SENTENCES = [
  "Şu köşedeki büyük ağacın gölgesinde oturup çay içmeyi, kuşları dinlemeyi çok severim.",
  "Pazartesi sabahı fırından taze poğaça, zeytin, bal ve beyaz peynir alıp eve döndüm.",
  "Jale, dokuz yüz altmış yedi numaralı vapura binip hızla Üsküdar'a geçti.",
]
const ENROLL_MS = 7000;

async function recordFor(ms, onTick) {
  const mic = await openMic();
  const rec = new MediaRecorder(mic.stream);
  const chunks = [];
  rec.ondataavailable = (e) => e.data.size && chunks.push(e.data);
  const stopped = new Promise((r) => (rec.onstop = r));
  const start = Date.now();
  const tick = setInterval(() => onTick(Math.max(0, ms - (Date.now() - start))), 200);
  rec.start();
  await sleep(ms);
  rec.stop();
  await stopped;
  clearInterval(tick);
  mic.close();
  return new Blob(chunks, { type: rec.mimeType });
}

$("#enroll-open").onclick = () => {
  const first = !state.identity?.active;
  $("#enroll-intro").textContent = first
    ? "İlk tanıtılan kişi yönetici olur ve şimdiye kadarki sohbetler ve hafıza onun olur. Sessiz bir yerde, normal sesinle 3 kısa cümle okuyacaksın."
    : "Tanıtılacak kişi (ör. Sezin) 3 kısa cümleyi kendi sesiyle, normal konuşur gibi okusun. Aynı adla tekrar kaydedersen o kişinin sesi yenilenir.";
  $("#enroll-sentence").textContent = "Okunacak cümleler (önceden bir göz at):\n"
    + ENROLL_SENTENCES.map((t, i) => `${i + 1}. ${t}`).join("\n")
    + "\n\nAdı yazıp \"Kaydı başlat\"a bas. Her cümle sırayla burada büyük yazılacak.";
  $("#enroll-status").textContent = "";
  $("#enroll-record").disabled = false;
  $("#enroll-dialog").showModal();
};

$("#enroll-record").onclick = async () => {
  const name = $("#enroll-name").value.trim();
  const status = $("#enroll-status");
  if (!name || /\s/.test(name)) return (status.textContent = "⚠️ Tek kelimelik bir ad yaz.");
  stopSpeaking();
  const button = $("#enroll-record");
  button.disabled = true;
  const form = new FormData();
  form.append("name", name);
  try {
    for (let i = 0; i < ENROLL_SENTENCES.length; i++) {
      $("#enroll-sentence").textContent = `${i + 1}/${ENROLL_SENTENCES.length}: "${ENROLL_SENTENCES[i]}"`;
      for (let n = 3; n > 0; n--) { status.textContent = `${n}... hazırlan`; await sleep(700); }
      const blob = await recordFor(ENROLL_MS, (left) => {
        status.textContent = `🔴 Oku! (${Math.ceil(left / 1000)} sn)`;
      });
      form.append("audio", blob, `ornek${i + 1}.webm`);
    }
    $("#enroll-sentence").textContent = "Kayıtlar tamam.";
    status.textContent = "⏳ Ses parmak izi çıkarılıyor... (ilk seferde model indirilir, biraz sürebilir)";
    const result = await api("/api/voice/enroll", { method: "POST", body: form });
    const weak = result.consistency < 0.5;
    status.textContent = weak
      ? `⚠️ ${name} kaydedildi ama örnekler birbirine az benziyor (${result.consistency}). Daha sessiz bir yerde tekrar kaydetmen iyi olur.`
      : `✅ ${name} kaydedildi. (örnek tutarlılığı ${result.consistency})`;
    applyIdentity(result.identity);
    loadProfiles();
  } catch (err) {
    status.textContent = "⚠️ " + err.message;
  } finally {
    button.disabled = false;
  }
};

async function loadProfiles() {
  const list = $("#profile-list");
  const hint = $("#profiles-hint");
  list.innerHTML = "";
  const id = state.identity || {};
  $("#enroll-open").hidden = !!(id.active && !id.admin);
  $("#profiles").hidden = !!(id.active && !id.admin);
  $("#settings-tabs [data-tab=\"profiles\"]").hidden = $("#profiles").hidden;
  if (!id.active) {
    hint.textContent = "Henüz ses tanıtılmadı. İlk tanıtılan kişi yönetici olur; o andan itibaren asistan konuşanı sesinden tanır, tanımadıklarını misafir sayar.";
    return;
  }
  if (!id.admin) {
    hint.textContent = "Ses profillerini yalnızca yönetici görebilir ve değiştirebilir.";
    return;
  }
  hint.textContent = "Kilitlemek için 1234 yaz. Yönetici olarak başka birinin oturumuna geçmek için adını ve 1234 yaz (ör. Sezin1234). 🔑 ile kişiye şifre verirsen, sesi tanınmadığında (ör. hastayken) şifresini yazarak kendi oturumuna girebilir.";
  for (const p of await api("/api/voice/profiles")) {
    const li = document.createElement("li");
    li.className = "profile";
    li.innerHTML = `<span></span><span class="profile-actions"><button class="key" title="Şifre">🔑</button><button class="del" title="Sil">✕</button></span>
      <form class="passcode-form" hidden>
        <input type="password" autocomplete="new-password" placeholder="Yeni şifre: harf + rakam, en az 6">
        <button class="primary">Kaydet</button>
        <button type="button" class="ghost remove">Şifreyi kaldır</button>
      </form>`;
    li.querySelector("span").textContent = `${p.name}${p.admin ? " · yönetici" : ""}${p.has_passcode ? " · 🔑 şifreli" : ""}`;
    const pform = li.querySelector(".passcode-form");
    pform.querySelector(".remove").hidden = !p.has_passcode;
    li.querySelector(".key").onclick = () => {
      pform.hidden = !pform.hidden;
      if (!pform.hidden) pform.querySelector("input").focus();
    };
    const savePasscode = async (passcode) => {
      try {
        await api(`/api/voice/profiles/${p.id}/passcode`, { method: "PUT", body: JSON.stringify({ passcode }) });
        hint.textContent = passcode ? `✅ ${p.name} için şifre kaydedildi.` : `${p.name} için şifre kaldırıldı.`;
        loadProfiles();
      } catch (err) {
        hint.textContent = "⚠️ " + err.message;
      }
    };
    pform.onsubmit = (e) => {
      e.preventDefault();
      const code = pform.querySelector("input").value.trim();
      if (code) savePasscode(code);
    };
    pform.querySelector(".remove").onclick = () => {
      if (confirm(`${p.name} şifresi kaldırılsın mı?`)) savePasscode("");
    };
    li.querySelector(".del").onclick = async () => {
      if (!confirm(`${p.name} ses profili silinsin mi?`)) return;
      try {
        const res = await api(`/api/voice/profiles/${p.id}`, { method: "DELETE" });
        applyIdentity(res.identity);
        loadProfiles();
      } catch (err) {
        hint.textContent = "⚠️ " + err.message;
      }
    };
    list.appendChild(li);
  }
}

// Security log: a table (search, filter by event, sort by column, export for Excel).
let securityRows = [];
const securitySort = { key: "date", desc: true };

function securityClass(event) {
  if (/Tanınmayan|Yanlış şifre|Çok fazla|engellendi/.test(event)) return "bad";
  if (/tanındı|doğrulandı|Şifre ile girildi/.test(event)) return "good";
  if (/Misafir|Kilitlendi/.test(event)) return "warn";
  return "info";
}

function securityView() {
  const q = $("#security-search").value.trim().toLocaleLowerCase("tr");
  const only = $("#security-filter").value;
  const rows = securityRows.filter((r) => (!only || r.event === only)
    && (!q || `${r.created_at} ${r.event} ${r.detail} ${r.score ?? ""}`.toLocaleLowerCase("tr").includes(q)));
  const { key, desc } = securitySort;
  const value = (r) => key === "score" ? (r.score ?? -1) : key === "event" ? r.event : key === "detail" ? r.detail
    : key === "time" ? r.created_at.slice(11) : r.created_at;
  rows.sort((x, y) => {
    const a = value(x), b = value(y);
    const c = typeof a === "number" ? a - b : String(a).localeCompare(String(b), "tr");
    return (desc ? -c : c) || (desc ? y.id - x.id : x.id - y.id);
  });
  return rows;
}

function renderSecurity() {
  const rows = securityView();
  const body = $("#security-table tbody");
  body.innerHTML = "";
  for (const r of rows) {
    const tr = document.createElement("tr");
    const [date, time] = (r.created_at || " ").split(" ");
    tr.innerHTML = `<td class="nowrap"></td><td class="nowrap"></td><td><span class="badge"></span></td><td></td><td class="num"></td>`;
    const cells = tr.children;
    cells[0].textContent = date ? date.split("-").reverse().join(".") : "";
    cells[1].textContent = time || "";
    cells[2].firstChild.textContent = r.event;
    cells[2].firstChild.classList.add(securityClass(r.event));
    cells[3].textContent = r.detail;
    cells[4].textContent = r.score != null ? Number(r.score).toFixed(3).replace(".", ",") : "";
    body.appendChild(tr);
  }
  if (!rows.length) body.innerHTML = `<tr><td colspan="5" class="agenda-empty">Kayıt yok.</td></tr>`;
  $("#security-count").textContent = `${rows.length} / ${securityRows.length} kayıt`;
  document.querySelectorAll("#security-table th").forEach((th) => {
    th.classList.toggle("sorted", th.dataset.key === securitySort.key);
    th.classList.toggle("desc", th.dataset.key === securitySort.key && securitySort.desc);
  });
}

$("#open-security").onclick = async () => {
  $("#security-search").value = "";
  $("#security-dialog").showModal();
  try {
    securityRows = await api("/api/security-log");
  } catch (err) {
    securityRows = [{ id: 0, created_at: "", event: "⚠️ " + err.message, detail: "", score: null }];
  }
  const filter = $("#security-filter");
  filter.innerHTML = `<option value="">Tüm olaylar</option>`;
  for (const ev of [...new Set(securityRows.map((r) => r.event))].sort((a, b) => a.localeCompare(b, "tr"))) {
    filter.add(new Option(ev, ev));
  }
  renderSecurity();
};
$("#security-clear").onclick = async () => {
  if (!confirm("Güvenlik kaydındaki tüm satırlar silinsin mi? (Önce \"Excel'e aktar\" ile saklayabilirsin.)")) return;
  try {
    await api("/api/security-log", { method: "DELETE" });
  } catch (err) {
    return setStatus(err.message, true);
  }
  $("#open-security").onclick(); // reload: only the "temizlendi" line is left
};
$("#security-search").addEventListener("input", renderSecurity);
$("#security-filter").addEventListener("change", renderSecurity);
document.querySelectorAll("#security-table th").forEach((th) => {
  th.onclick = () => {
    securitySort.desc = securitySort.key === th.dataset.key ? !securitySort.desc : th.dataset.key !== "event";
    securitySort.key = th.dataset.key;
    renderSecurity();
  };
});

// CSV with ";" and a BOM: Turkish Excel opens it with the right columns and letters.
$("#security-export").onclick = () => {
  const cell = (v) => `"${String(v ?? "").replace(/"/g, '""')}"`;
  const lines = [["Tarih", "Saat", "Olay", "Ayrıntı", "Benzerlik"].map(cell).join(";")];
  for (const r of securityView()) {
    const [date, time] = (r.created_at || " ").split(" ");
    lines.push([date.split("-").reverse().join("."), time, r.event, r.detail,
      r.score != null ? String(r.score).replace(".", ",") : ""].map(cell).join(";"));
  }
  const blob = new Blob(["\ufeff" + lines.join("\r\n")], { type: "text/csv;charset=utf-8" });
  const link = document.createElement("a");
  link.href = URL.createObjectURL(blob);
  link.download = `guvenlik-kaydi-${new Date().toISOString().slice(0, 10)}.csv`;
  link.click();
  setTimeout(() => URL.revokeObjectURL(link.href), 1000);
};

// Settings dialog

const WHISPER_LABELS = { tiny: "en hızlı", base: "hızlı", small: "dengeli", medium: "iyi", "large-v3-turbo": "en iyi" };
const VOICE_LABELS = { "tr-TR-EmelNeural": "Emel", "tr-TR-AhmetNeural": "Ahmet", windows: "Windows sesi" };

async function loadSettings() {
  state.settings = await api("/api/settings");
  const s = state.settings;
  els.greeting.textContent = `Merhaba, ben ${s.assistant_name}!`;
  document.title = s.assistant_name;

  // Sidebar summary of the settings that matter most when comparing speed.
  const lines = [`🤖 Model: ${s.model}`];
  if (s.memory_model && s.memory_model !== s.model) lines.push(`🧠 Hafıza: ${s.memory_model}`);
  const hardware = state.sttDevice ? ` · ${state.sttDevice.toUpperCase()}` : "";
  lines.push(`🎤 Ses tanıma: ${WHISPER_LABELS[s.whisper_model] || s.whisper_model} (${s.whisper_model})${hardware}`);
  lines.push(`🔊 Ses: ${VOICE_LABELS[s.tts_voice] || s.tts_voice}`);
  const summary = $("#config-summary");
  summary.innerHTML = "";
  for (const line of lines) {
    const span = document.createElement("span");
    span.textContent = line;
    summary.appendChild(span);
  }
  wakeListener.update();
}

// "gpu" / "cpu": where speech recognition actually runs; shown in the sidebar summary.
function showSttDevice(device) {
  if (!device || device === state.sttDevice) return;
  state.sttDevice = device;
  loadSettings().catch(() => {});
}

$("#open-settings").onclick = async () => {
  const form = els.settingsForm;
  form.assistant_name.value = state.settings.assistant_name;
  form.whisper_model.value = state.settings.whisper_model;
  form.whisper_device.value = state.settings.whisper_device || "auto";
  form.language.value = state.settings.language;
  form.tts_voice.value = state.settings.tts_voice;
  form.auto_listen.checked = !!state.settings.auto_listen;
  form.wake_word.checked = !!state.settings.wake_word;
  form.wake_phrase.value = state.settings.wake_phrase || "";
  form.outlook_sync.checked = !!state.settings.outlook_sync;
  form.weather_city.value = state.settings.weather_city || "";
  form.analysis_folder.value = state.settings.analysis_folder || "";
  form.mic_gain.value = Number(state.settings.mic_gain) || 0;
  $("#mic-gain-label").textContent = `+${form.mic_gain.value} dB`;
  $("#mic-result").textContent = state.settings.mic_calibrated ? "" : "Henüz ayarlanmadı.";
  $("#mic-meter-bar").style.width = "0";
  $("#mic-play").hidden = !calibrationTake;

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
  loadProfiles();

  showSettingsTab(settingsTab());
  els.settingsDialog.showModal();
};

// Settings tabs (3.24), remembered for the next time the window opens.
function settingsTab() {
  try { return localStorage.getItem("settingsTab") || "ai"; } catch { return "ai"; }
}

function showSettingsTab(name) {
  const tabs = [...document.querySelectorAll("#settings-tabs button")];
  const visible = tabs.filter((b) => !b.hidden);
  if (!visible.some((b) => b.dataset.tab === name)) name = visible[0]?.dataset.tab || "ai";
  tabs.forEach((b) => b.classList.toggle("active", b.dataset.tab === name));
  document.querySelectorAll(".settings-dialog .card[data-tab]").forEach((c) => c.classList.toggle("shown", c.dataset.tab === name));
  try { localStorage.setItem("settingsTab", name); } catch {}
}

document.querySelectorAll("#settings-tabs button").forEach((b) => { b.onclick = () => showSettingsTab(b.dataset.tab); });

els.settingsForm.addEventListener("submit", async (e) => {
  e.preventDefault();
  const data = Object.fromEntries(new FormData(els.settingsForm));
  data.auto_listen = els.settingsForm.auto_listen.checked;
  data.wake_word = els.settingsForm.wake_word.checked;
  data.outlook_sync = els.settingsForm.outlook_sync.checked;
  data.mic_gain = Number(data.mic_gain) || 0;
  data.mic_calibrated = data.mic_gain > 0 || !!state.settings.mic_calibrated;
  await api("/api/settings", { method: "PUT", body: JSON.stringify(data) });
  await loadSettings();
  loadAgendaWeather(true);
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
    const { version, other_computer: other, stt_device: sttDevice, identity } = await api("/api/version");
    showSttDevice(sttDevice);
    applyIdentity(identity);
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

// Reminders, alarms and timers: the server fires them; this page rings, speaks and shows running timers.

const REPEAT_LABELS = { daily: "her gün", weekly: "her hafta", monthly: "her ay", yearly: "her yıl" };
const alertQueue = [];
const alertSeen = new Set();
let alertShowing = null;
let timers = []; // [{id, text, endsAt}]

function fmtLeft(ms) {
  const total = Math.max(0, Math.round(ms / 1000));
  const h = Math.floor(total / 3600), m = Math.floor((total % 3600) / 60), sec = total % 60;
  const two = (n) => String(n).padStart(2, "0");
  return h ? `${h}:${two(m)}:${two(sec)}` : `${two(m)}:${two(sec)}`;
}

function renderTimers() {
  renderAgendaTimers();
  const bar = $("#timer-bar");
  bar.hidden = !timers.length;
  bar.innerHTML = "";
  for (const t of timers) {
    const chip = document.createElement("span");
    chip.className = "timer-chip";
    chip.innerHTML = `⏳ <b></b><span></span><button title="İptal et">✕</button>`;
    chip.querySelector("b").textContent = fmtLeft(t.endsAt - Date.now());
    chip.querySelector("span").textContent = t.text;
    chip.querySelector("button").onclick = async () => {
      await api(`/api/reminders/${t.id}`, { method: "DELETE" }).catch(() => {});
      timers = timers.filter((x) => x.id !== t.id);
      renderTimers();
    };
    bar.appendChild(chip);
  }
}
setInterval(() => { if (timers.length) renderTimers(); }, 1000);

// A two-tone chime made in the browser (no sound file needed), repeated until "Tamam".
let chimeTimer = null;
let audioCtx = null;
function chime() {
  try {
    audioCtx = audioCtx || new (window.AudioContext || window.webkitAudioContext)();
    audioCtx.resume();
    [880, 660].forEach((freq, i) => {
      const osc = audioCtx.createOscillator();
      const gain = audioCtx.createGain();
      const t0 = audioCtx.currentTime + i * 0.25;
      osc.frequency.value = freq;
      gain.gain.setValueAtTime(0.0001, t0);
      gain.gain.exponentialRampToValueAtTime(0.3, t0 + 0.02);
      gain.gain.exponentialRampToValueAtTime(0.0001, t0 + 0.22);
      osc.connect(gain).connect(audioCtx.destination);
      osc.start(t0);
      osc.stop(t0 + 0.25);
    });
  } catch {}
}

function showNextAlert() {
  if (alertShowing || !alertQueue.length) return;
  alertShowing = alertQueue.shift();
  const a = alertShowing;
  $("#alert-icon").textContent = a.kind === "timer" ? "⏳" : a.kind === "alarm" ? "⏰" : "🔔";
  $("#alert-text").textContent = a.text;
  $("#alert-when").textContent = a.missed ? `Kaçırılan hatırlatma (${a.due}). Asistan o sırada kapalıydı.` : a.due;
  $("#alert-dialog").showModal();
  let rings = 0;
  chime();
  chimeTimer = setInterval(() => { if (++rings < 40) chime(); }, 1500); // at most one minute
  const spoken = a.kind === "timer" ? `Süre doldu. ${a.text}` : `Hatırlatma: ${a.text}`;
  speak(a.missed ? `Kaçırılan hatırlatma. ${a.text}` : spoken);
}

$("#alert-ok").onclick = async () => {
  clearInterval(chimeTimer);
  $("#alert-dialog").close();
  const done = alertShowing;
  alertShowing = null;
  if (done) await api(`/api/alerts/${done.id}/ack`, { method: "POST" }).catch(() => {});
  showNextAlert();
};
$("#alert-dialog").addEventListener("cancel", (e) => { e.preventDefault(); $("#alert-ok").click(); });

async function pollAlerts() {
  try {
    const res = await api("/api/alerts");
    const now = Date.now();
    timers = res.timers.map((t) => ({ id: t.id, text: t.text, endsAt: now + t.left * 1000 }));
    renderTimers();
    for (const a of res.alerts) {
      if (alertSeen.has(a.id)) continue;
      alertSeen.add(a.id);
      alertQueue.push(a);
    }
    showNextAlert();
  } catch {}
}
setInterval(pollAlerts, 3000);
pollAlerts();

async function loadReminders() {
  const list = $("#reminder-list");
  list.innerHTML = "";
  const items = await api("/api/reminders");
  if (!items.length) {
    list.innerHTML = `<li class="none">Kurulu hatırlatma yok.</li>`;
    return;
  }
  for (const r of items) {
    const li = document.createElement("li");
    li.innerHTML = `<div><span></span><small></small></div><button title="İptal et">✕</button>`;
    const icon = r.kind === "timer" ? "⏳" : r.kind === "alarm" ? "⏰" : "🔔";
    li.querySelector("span").textContent = `${icon} ${r.text}`;
    li.querySelector("small").textContent = r.when + (r.repeat ? ` · ${REPEAT_LABELS[r.repeat]}` : "")
      + (r.calendar ? " · 📅 Outlook'ta" : "") + (r.calendar_note ? ` · ⚠️ ${r.calendar_note}` : "");
    li.querySelector("button").onclick = async () => {
      await api(`/api/reminders/${r.id}`, { method: "DELETE" });
      loadReminders();
      pollAlerts();
      loadAgenda();
    };
    list.appendChild(li);
  }
}

$("#open-reminders").onclick = async () => {
  $("#reminder-status").textContent = "";
  const soon = new Date(Date.now() + 60 * 60 * 1000);
  soon.setMinutes(0, 0, 0);
  const local = new Date(soon.getTime() - soon.getTimezoneOffset() * 60000);
  $("#reminder-when").value = local.toISOString().slice(0, 16);
  $("#reminders-dialog").showModal();
  loadReminders().catch((err) => { $("#reminder-status").textContent = "⚠️ " + err.message; });
};

$("#reminder-form").addEventListener("submit", async (e) => {
  e.preventDefault();
  try {
    await api("/api/reminders", {
      method: "POST",
      body: JSON.stringify({
        text: $("#reminder-text").value,
        due_at: $("#reminder-when").value,
        repeat: $("#reminder-repeat").value || null,
      }),
    });
    $("#reminder-text").value = "";
    $("#reminder-status").textContent = "✅ Eklendi.";
    loadReminders();
    loadAgenda();
  } catch (err) {
    $("#reminder-status").textContent = "⚠️ " + err.message;
  }
});

// Help: NELER_YAPABILIR.md, the list of things the assistant can do with example commands.
$("#open-help").onclick = async () => {
  const body = $("#help-body");
  body.textContent = "Yükleniyor...";
  $("#help-dialog").showModal();
  try {
    const { markdown } = await api("/api/help");
    // Join wrapped lines of a paragraph/list item, drop the title and rules, then use the chat's Markdown renderer.
    const text = markdown
      .replace(/^# .*\n/, "")
      .replace(/^---$/gm, "")
      .replace(/\n(?=[ ]{2,}\S)/g, "")
      .replace(/([^\n])\n(?=[^\n\-*#\s])/g, "$1 ")
      .replace(/\n{3,}/g, "\n\n")
      .trim();
    body.innerHTML = renderMarkdown(text);
  } catch (err) {
    body.textContent = "⚠️ " + err.message;
  }
};

$("#outlook-test").onclick = async () => {
  const status = $("#outlook-status");
  status.textContent = "⏳ Outlook'a bağlanılıyor (Outlook kapalıysa açılması biraz sürebilir)...";
  try {
    status.textContent = (await api("/api/outlook/test", { method: "POST" })).message;
  } catch (err) {
    status.textContent = "⚠️ " + err.message;
  }
};

// Agenda: the right-hand panel with a month calendar and the person's upcoming reminders (3.9).

const MONTHS = ["Ocak", "Şubat", "Mart", "Nisan", "Mayıs", "Haziran", "Temmuz", "Ağustos", "Eylül", "Ekim", "Kasım", "Aralık"];
const DAYS = ["Pazar", "Pazartesi", "Salı", "Çarşamba", "Perşembe", "Cuma", "Cumartesi"];
const agenda = { items: [], outlook: [], outlookError: "", month: new Date(new Date().getFullYear(), new Date().getMonth(), 1),
  selected: null, allowed: false, loadedAt: 0 };

function agendaPref() {
  try { return localStorage.getItem("agenda") !== "hidden"; } catch { return true; }
}

function showAgenda(allowed) {
  agenda.allowed = allowed;
  $("#toggle-agenda").hidden = !allowed;
  $("#agenda").hidden = !(allowed && agendaPref());
  if (!$("#agenda").hidden) loadAgenda();
}

$("#toggle-agenda").onclick = () => {
  const show = $("#agenda").hidden;
  try { localStorage.setItem("agenda", show ? "shown" : "hidden"); } catch {}
  showAgenda(agenda.allowed);
};

const dayKey = (d) => `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, "0")}-${String(d.getDate()).padStart(2, "0")}`;
const dueDate = (r) => new Date(r.due_at.replace(" ", "T"));

function occursOn(r, day) {
  if (r.kind === "outlook") {
    // An appointment covers every day from its start to its end (an all-day event ends at midnight).
    const start = dueDate(r);
    const end = new Date(new Date(r.end_at.replace(" ", "T")).getTime() - 60000);
    const first = new Date(start.getFullYear(), start.getMonth(), start.getDate());
    return day >= first && day <= end;
  }
  const due = dueDate(r);
  const start = new Date(due.getFullYear(), due.getMonth(), due.getDate());
  if (day < start) return false;
  switch (r.repeat) {
    case "daily": return true;
    case "weekly": return day.getDay() === due.getDay();
    case "monthly": return day.getDate() === due.getDate();
    case "yearly": return day.getDate() === due.getDate() && day.getMonth() === due.getMonth();
    default: return dayKey(day) === dayKey(due);
  }
}

function dayLabel(d) {
  const today = new Date();
  const tomorrow = new Date(today.getFullYear(), today.getMonth(), today.getDate() + 1);
  if (dayKey(d) === dayKey(today)) return "Bugün";
  if (dayKey(d) === dayKey(tomorrow)) return "Yarın";
  const year = d.getFullYear() !== today.getFullYear() ? ` ${d.getFullYear()}` : "";
  return `${d.getDate()} ${MONTHS[d.getMonth()]}${year} ${DAYS[d.getDay()]}`;
}

async function loadAgenda() {
  if ($("#agenda").hidden) return;
  agenda.loadedAt = Date.now();
  let own = [];
  try {
    own = (await api("/api/reminders")).filter((r) => r.kind !== "timer");
  } catch {}
  agenda.items = own.concat(agenda.outlook);
  renderMonth();
  renderAgendaList();
  loadOutlookEvents(own); // slower (Outlook may need to start): added when it arrives
  loadAgendaWeather();
}

// Weather line at the top of the agenda (the city from Settings), refreshed at most every 15 minutes.
let weatherLoadedAt = 0;
async function loadAgendaWeather(force = false) {
  const box = $("#agenda-weather");
  if (!force && Date.now() - weatherLoadedAt < 15 * 60 * 1000) return;
  weatherLoadedAt = Date.now();
  try {
    const { weather: w } = await api("/api/weather");
    box.hidden = !w;
    if (!w) return;
    box.innerHTML = `<span class="w-icon"></span><div><b></b><small></small></div>`;
    box.querySelector(".w-icon").textContent = w.icon;
    box.querySelector("b").textContent = `${w.place} ${w.temp}`;
    box.querySelector("small").textContent = `${w.words} · en yüksek ${w.max}, en düşük ${w.min}`
      + (w.rain != null ? ` · yağış %${w.rain}` : "");
    box.title = "Hava durumu (Open-Meteo)";
  } catch {
    box.hidden = true;
  }
}

// The admin's Outlook appointments, read-only, for the shown month and the next 30 days (3.10).
async function loadOutlookEvents(own) {
  const m = agenda.month;
  const first = new Date(m.getFullYear(), m.getMonth(), 1 - (m.getDay() + 6) % 7);
  const today = new Date();
  const start = first < today ? first : new Date(today.getFullYear(), today.getMonth(), today.getDate());
  const gridEnd = new Date(first.getFullYear(), first.getMonth(), first.getDate() + 42);
  const soon = new Date(today.getFullYear(), today.getMonth(), today.getDate() + 31);
  const end = gridEnd > soon ? gridEnd : soon;
  try {
    const res = await api(`/api/outlook/events?start=${dayKey(start)}T00:00&end=${dayKey(end)}T00:00`);
    agenda.outlook = res.events;
    agenda.outlookError = res.error || "";
  } catch (err) {
    agenda.outlook = [];
    agenda.outlookError = err.message;
  }
  agenda.items = own.concat(agenda.outlook);
  renderMonth();
  renderAgendaList();
}

function renderMonth() {
  const m = agenda.month;
  $("#month-title").textContent = `${MONTHS[m.getMonth()]} ${m.getFullYear()}`;
  const grid = $("#month-grid");
  grid.innerHTML = ["Pzt", "Sal", "Çar", "Per", "Cum", "Cmt", "Paz"].map((d) => `<span class="dow">${d}</span>`).join("");
  const offset = (m.getDay() + 6) % 7; // Monday first
  const today = dayKey(new Date());
  for (let i = 0; i < 42; i++) {
    const day = new Date(m.getFullYear(), m.getMonth(), 1 - offset + i);
    const key = dayKey(day);
    const btn = document.createElement("button");
    btn.type = "button";
    btn.textContent = day.getDate();
    btn.classList.toggle("other", day.getMonth() !== m.getMonth());
    btn.classList.toggle("today", key === today);
    btn.classList.toggle("selected", key === agenda.selected);
    const count = agenda.items.filter((r) => occursOn(r, day)).length;
    btn.classList.toggle("has", count > 0);
    btn.title = count ? `${count} hatırlatma` : "";
    btn.onclick = () => {
      agenda.selected = agenda.selected === key ? null : key;
      renderMonth();
      renderAgendaList();
    };
    grid.appendChild(btn);
  }
}

function agendaItem(r, showDay) {
  const div = document.createElement("div");
  div.className = "agenda-item";
  if (r.kind === "outlook") return outlookItem(r, div);
  const icon = r.kind === "alarm" ? "⏰" : "🔔";
  div.innerHTML = `<span class="time"></span><span class="what"><span></span><small></small></span><button title="İptal et">✕</button>`;
  const due = dueDate(r);
  div.querySelector(".time").textContent = `${String(due.getHours()).padStart(2, "0")}:${String(due.getMinutes()).padStart(2, "0")}`;
  div.querySelector(".what span").textContent = `${icon} ${r.text}`;
  const notes = [];
  if (showDay) notes.push(dayLabel(due));
  if (r.repeat) notes.push(REPEAT_LABELS[r.repeat]);
  if (r.calendar) notes.push("📅 Outlook'ta");
  if (r.calendar_note) notes.push("⚠️ " + r.calendar_note);
  div.querySelector("small").textContent = notes.join(" · ");
  div.querySelector("button").onclick = async () => {
    if (!confirm(`"${r.text}" iptal edilsin mi?`)) return;
    await api(`/api/reminders/${r.id}`, { method: "DELETE" }).catch(() => {});
    loadAgenda();
  };
  return div;
}

function outlookItem(r, div) {
  div.classList.add("outlook");
  div.innerHTML = `<span class="time"></span><span class="what"><span></span><small></small></span>`;
  const due = dueDate(r);
  div.querySelector(".time").textContent = r.all_day ? "Tüm gün"
    : `${String(due.getHours()).padStart(2, "0")}:${String(due.getMinutes()).padStart(2, "0")}`;
  div.querySelector(".what span").textContent = `📆 ${r.text}`;
  div.querySelector("small").textContent = ["Outlook", r.location, r.recurring ? "tekrarlanan" : ""].filter(Boolean).join(" · ");
  div.title = "Outlook takviminden (buradan değiştirilemez)";
  return div;
}

function renderAgendaList() {
  const list = $("#agenda-list");
  list.innerHTML = "";
  $("#agenda-all").hidden = !agenda.selected;
  if (agenda.selected) {
    const day = new Date(agenda.selected + "T00:00");
    $("#agenda-list-title").textContent = dayLabel(day);
    const items = agenda.items.filter((r) => occursOn(r, day))
      .sort((a, b) => a.due_at.slice(11).localeCompare(b.due_at.slice(11)));
    if (!items.length) list.innerHTML = `<div class="agenda-empty">Bu gün için hatırlatma yok.</div>`;
    for (const r of items) list.appendChild(agendaItem(r, false));
    return;
  }
  $("#agenda-list-title").textContent = "Yaklaşanlar";
  if (!agenda.items.length && !agenda.outlookError) {
    list.innerHTML = `<div class="agenda-empty">Kurulu hatırlatma yok. Sohbette "yarın 9'da doktoru aramamı hatırlat" yazabilirsin.</div>`;
    return;
  }
  const now = new Date();
  const upcoming = agenda.items.filter((r) => r.kind !== "outlook" || new Date(r.end_at.replace(" ", "T")) > now);
  if (agenda.outlookError) {
    const warn = document.createElement("div");
    warn.className = "agenda-empty";
    warn.textContent = "⚠️ " + agenda.outlookError;
    list.appendChild(warn);
  }
  let last = "";
  for (const r of upcoming.sort((a, b) => a.due_at.localeCompare(b.due_at)).slice(0, 40)) {
    const label = dayLabel(dueDate(r));
    if (label !== last) {
      const h = document.createElement("div");
      h.className = "agenda-day";
      h.textContent = label;
      list.appendChild(h);
      last = label;
    }
    list.appendChild(agendaItem(r, false));
  }
}

function renderAgendaTimers() {
  const box = $("#agenda-timers");
  box.hidden = !timers.length;
  box.innerHTML = timers.length ? `<div class="agenda-subhead"><span>Sayaçlar</span></div>` : "";
  for (const t of timers) {
    const div = document.createElement("div");
    div.className = "agenda-item";
    div.innerHTML = `<span class="time"></span><span class="what"></span>`;
    div.querySelector(".time").textContent = fmtLeft(t.endsAt - Date.now());
    div.querySelector(".what").textContent = `⏳ ${t.text}`;
    box.appendChild(div);
  }
}

$("#month-prev").onclick = () => { agenda.month = new Date(agenda.month.getFullYear(), agenda.month.getMonth() - 1, 1); loadAgenda(); };
$("#month-next").onclick = () => { agenda.month = new Date(agenda.month.getFullYear(), agenda.month.getMonth() + 1, 1); loadAgenda(); };
$("#agenda-all").onclick = () => { agenda.selected = null; renderMonth(); renderAgendaList(); };

// "+ Ekle" opens the reminder window, set to the selected day at 09:00 (or the next full hour).
$("#agenda-add").onclick = () => {
  $("#open-reminders").click();
  if (agenda.selected) $("#reminder-when").value = `${agenda.selected}T09:00`;
  $("#reminder-text").focus();
};

setInterval(() => { if (Date.now() - agenda.loadedAt > 20000) loadAgenda(); }, 5000);
showAgenda(true);

// Microphone calibration (3.15): 5 s of normal speech from where the person sits, measured without any gain
// and without the browser's automatic gain; the gain is chosen so speech lands near -20 dBFS without clipping.
const TARGET_DB = -20;
const MAX_GAIN_DB = 30;
let calibrationTake = null; // the last test recording, to listen to it with the chosen gain
const toDb = (v) => 20 * Math.log10(Math.max(v, 1e-6));

$("#mic-gain").addEventListener("input", (e) => { $("#mic-gain-label").textContent = `+${e.target.value} dB`; });

$("#mic-test").onclick = async () => {
  const button = $("#mic-test");
  const result = $("#mic-result");
  const bar = $("#mic-meter-bar");
  let mic;
  try {
    mic = await openMic({ gainDb: 0, agc: false });
  } catch {
    result.textContent = "⚠️ Mikrofona erişilemedi. Tarayıcının mikrofon iznini kontrol et.";
    return;
  }
  button.disabled = true;
  for (let n = 3; n > 0; n--) { result.textContent = `${n}... Her zamanki yerinden, normal sesinle konuşmaya hazırlan.`; await sleep(700); }
  const chunks = [];
  const rec = new MediaRecorder(mic.stream);
  rec.ondataavailable = (e) => e.data.size && chunks.push(e.data);
  const stopped = new Promise((r) => (rec.onstop = r));
  rec.start();
  const frames = [];
  let peak = 0;
  const started = Date.now();
  result.textContent = "🔴 Konuş: \"Merhaba, mikrofonumu ayarlıyorum. Bugün hava çok güzel.\"";
  while (Date.now() - started < 5000) {
    const { rms, peak: p } = mic.level();
    frames.push(rms);
    peak = Math.max(peak, p);
    bar.style.width = `${Math.min(100, Math.max(0, (toDb(rms) + 60) / 60 * 100))}%`;
    await sleep(50);
  }
  rec.stop();
  await stopped;
  mic.close();
  bar.style.width = "0";
  button.disabled = false;
  calibrationTake = new Blob(chunks, { type: rec.mimeType });

  const sorted = [...frames].sort((a, b) => a - b);
  const noise = sorted[Math.floor(sorted.length * 0.1)];
  const speech = frames.filter((v) => v > Math.max(noise * 3, 0.0005)).sort((a, b) => a - b);
  if (speech.length < 10) {
    result.textContent = "⚠️ Konuşma duyamadım. Mikrofon kapalı ya da sesi çok kısık olabilir (Windows'ta doğru mikrofon seçili mi, "
      + "mikrofonun kendi ses/kazanç ayarı açık mı?). Tekrar dene.";
    $("#mic-play").hidden = true;
    return;
  }
  const speechDb = toDb(speech[Math.floor(speech.length / 2)]);
  const peakDb = toDb(peak);
  let gainDb = Math.round(Math.min(MAX_GAIN_DB, Math.max(0, TARGET_DB - speechDb), -1 - peakDb));
  gainDb = Math.max(0, gainDb);
  const noiseAfter = toDb(noise) + gainDb;
  const lines = [
    `Konuşma seviyen: ${speechDb.toFixed(0)} dB ${speechDb < -40 ? "(çok kısık)" : speechDb < -28 ? "(biraz kısık)" : "(iyi)"}, en yüksek nokta ${peakDb.toFixed(0)} dB.`,
    gainDb > 0 ? `✅ Asistan sesini +${gainDb} dB yükseltecek.` : "✅ Yükseltmeye gerek yok.",
    `Arka plan gürültüsü (yükseltmeden sonra): ${noiseAfter.toFixed(0)} dB ${noiseAfter > -45 ? "⚠️ yüksek — fan, klima ya da uğultu var mı?" : "(iyi)"}`,
  ];
  if (peakDb > -1) lines.push("⚠️ Ses yer yer kırpılıyor (çok yüksek). Mikrofonun kendi kazancını biraz kıs.");
  if (TARGET_DB - speechDb > MAX_GAIN_DB) lines.push("⚠️ Ses çok kısık: mikrofona yaklaş ya da mikrofonun kendi kazanç düğmesini aç, sonra tekrar dene.");
  else if (gainDb >= 20) lines.push("💡 Mikrofonun kendi kazanç düğmesini açarsan daha az gürültüyle daha temiz ses alırsın.");
  result.textContent = lines.join("\n");
  $("#mic-gain").value = gainDb;
  $("#mic-gain-label").textContent = `+${gainDb} dB`;
  $("#mic-play").hidden = false;
  try { // saved right away: the next recording already uses it
    await api("/api/settings", { method: "PUT", body: JSON.stringify({ mic_gain: gainDb, mic_calibrated: true }) });
    state.settings.mic_gain = gainDb;
    state.settings.mic_calibrated = true;
  } catch (err) {
    result.textContent += "\n⚠️ Kaydedilemedi: " + err.message;
  }
};

// Listen to the test recording with the gain currently on the slider.
$("#mic-play").onclick = async () => {
  if (!calibrationTake) return;
  const ctx = new AudioContext();
  const audio = await ctx.decodeAudioData(await calibrationTake.arrayBuffer());
  const source = ctx.createBufferSource();
  const gain = ctx.createGain();
  gain.gain.value = Math.pow(10, (Number($("#mic-gain").value) || 0) / 20);
  source.buffer = audio;
  source.connect(gain).connect(ctx.destination);
  source.onended = () => ctx.close();
  source.start();
};

// Notes and lists (3.16): one tab per list; tick = bought/done, ✕ = delete.
const DEFAULT_LISTS = ["alışveriş", "yapılacaklar", "notlar"];
let notesTab = "alışveriş";
const listTitle = (n) => (n === "notlar" ? "📝 Notlar" : n === "alışveriş" ? "🛒 Alışveriş" : n === "yapılacaklar" ? "✅ Yapılacaklar"
  : `📋 ${n.charAt(0).toLocaleUpperCase("tr") + n.slice(1)}`);

async function loadNotes() {
  let lists = [];
  try { lists = (await api("/api/notes")).lists; } catch {}
  const names = [...new Set([...DEFAULT_LISTS, ...lists.map((l) => l.name)])];
  if (!names.includes(notesTab)) notesTab = names[0];
  const tabs = $("#note-tabs");
  tabs.innerHTML = "";
  for (const name of names) {
    const count = (lists.find((l) => l.name === name)?.items || []).filter((i) => !i.done).length;
    const b = document.createElement("button");
    b.type = "button";
    b.textContent = listTitle(name) + (count ? ` (${count})` : "");
    b.classList.toggle("active", name === notesTab);
    b.onclick = () => { notesTab = name; loadNotes(); };
    tabs.appendChild(b);
  }
  const items = lists.find((l) => l.name === notesTab)?.items || [];
  const ul = $("#note-list");
  ul.innerHTML = items.length ? "" : `<li class="none">Bu liste boş.</li>`;
  for (const item of items) {
    const li = document.createElement("li");
    li.classList.toggle("done", !!item.done);
    li.innerHTML = `<label><input type="checkbox"><span></span></label><button title="Sil">✕</button>`;
    li.querySelector("span").textContent = item.text;
    const box = li.querySelector("input");
    box.checked = !!item.done;
    box.onchange = async () => {
      await api(`/api/notes/${item.id}`, { method: "PUT", body: JSON.stringify({ done: box.checked }) }).catch(() => {});
      loadNotes();
    };
    li.querySelector("button").onclick = async () => {
      await api(`/api/notes/${item.id}`, { method: "DELETE" }).catch(() => {});
      loadNotes();
    };
    ul.appendChild(li);
  }
  $("#note-input").placeholder = notesTab === "notlar" ? "Not yaz…" : "Eklenecek şey (virgülle birden fazla: süt, ekmek)";
}

$("#open-notes").onclick = () => {
  $("#notes-dialog").showModal();
  loadNotes();
  $("#note-input").focus();
};

$("#note-form").addEventListener("submit", async (e) => {
  e.preventDefault();
  const input = $("#note-input");
  const texts = notesTab === "notlar" ? [input.value.trim()] : input.value.split(",").map((t) => t.trim());
  for (const text of texts.filter(Boolean)) {
    await api("/api/notes", { method: "POST", body: JSON.stringify({ list_name: notesTab, text }) }).catch(() => {});
  }
  input.value = "";
  loadNotes();
});


// Wake word (3.19): the microphone stays open; every burst of speech is checked by the local Whisper for the wake
// phrase ("Asiye, saat kaç?"). Bursts without it are dropped by the server without being saved or logged.
const wakeListener = (() => {
  const TARGET_RATE = 16000;
  const PRE_ROLL_MS = 500;   // keep a little sound from before the voice got loud, so the first syllable is not cut
  const END_SILENCE_MS = 700;
  const MIN_SPEECH_MS = 250;
  const MAX_BURST_MS = 6000;
  const OVERLAP_MS = 2000;   // music never goes quiet: long sound is checked in 6 s windows that overlap by 2 s,
                             // so a wake phrase cut by one window is whole in the next
  const button = $("#wake-toggle");
  let mic = null, processor = null, starting = false, sending = false, waiting = null, restUntil = 0;
  let paused = false;
  try { paused = localStorage.getItem("wakePaused") === "1"; } catch {}

  const wanted = () => !!state.settings.wake_word && !paused;
  const speaking = () => !!stopCurrentAudio || ("speechSynthesis" in window && speechSynthesis.speaking);
  const deaf = () => Date.now() < restUntil || state.busy || (recorder && recorder.state === "recording") || speaking()
    || document.querySelector("dialog[open]");

  function show() {
    button.hidden = !state.settings.wake_word;
    button.classList.toggle("on", !!mic && !paused);
    const phrase = state.settings.wake_phrase || state.settings.assistant_name;
    button.title = paused ? `Duraklatıldı. "${phrase}" diye seslenmeyi yeniden dinlemek için bas.`
      : `"${phrase}" diye seslenmeni bekliyorum (mikrofona basmadan). Duraklatmak için bas.`;
  }

  async function start() {
    if (mic || starting) return;
    starting = true;
    try {
      mic = await openMic();
    } catch {
      starting = false;
      setStatus("Adınla seslenme için mikrofona erişilemedi. Tarayıcının mikrofon iznini kontrol et.", true);
      return;
    }
    starting = false;
    if (!wanted()) return stop();
    const { ctx } = mic;
    // A page that was not clicked yet may not be allowed to process sound; start on the first click or key.
    if (ctx.state === "suspended") {
      const resume = () => ctx.resume();
      document.addEventListener("click", resume, { once: true });
      document.addEventListener("keydown", resume, { once: true });
      ctx.resume().catch(() => {});
    }
    const rate = ctx.sampleRate;
    processor = ctx.createScriptProcessor(4096, 1, 1);
    const chunkMs = 4096 / rate * 1000;
    let preRoll = [], burst = null, loudMs = 0, quietMs = 0, floor = 0.004;
    processor.onaudioprocess = (e) => {
      const input = new Float32Array(e.inputBuffer.getChannelData(0));
      let sum = 0;
      for (const v of input) sum += v * v;
      const rms = Math.sqrt(sum / input.length);
      if (deaf()) { burst = null; preRoll = []; return; }
      const loud = rms > Math.max(0.015, floor * 3);
      if (!burst) {
        if (!loud) floor = floor * 0.95 + rms * 0.05; // follows the room's background noise
        preRoll.push(input);
        if (preRoll.length * chunkMs > PRE_ROLL_MS) preRoll.shift();
        if (loud) { burst = preRoll; preRoll = []; loudMs = chunkMs; quietMs = 0; }
        return;
      }
      burst.push(input);
      if (loud) { loudMs += chunkMs; quietMs = 0; } else quietMs += chunkMs;
      const length = burst.length * chunkMs;
      if (quietMs >= END_SILENCE_MS) {
        const done = burst;
        burst = null;
        if (loudMs >= MIN_SPEECH_MS) check(done, rate, false);
      } else if (length >= MAX_BURST_MS) { // still loud: music, TV or a long sentence
        const done = burst;
        burst = burst.slice(-Math.round(OVERLAP_MS / chunkMs));
        loudMs = OVERLAP_MS;
        check(done, rate, true);
      }
    };
    mic.node.connect(processor);
    processor.connect(ctx.destination); // outputs silence; needed so the processor runs
    show();
  }

  function stop() {
    if (processor) { processor.disconnect(); processor.onaudioprocess = null; processor = null; }
    if (mic) { mic.close(); mic = null; }
    show();
  }

  async function check(chunks, rate, noisy) {
    if (sending) { waiting = [chunks, rate, noisy]; return; } // keep only the newest while one is being checked
    sending = true;
    try {
      const form = new FormData();
      form.append("audio", toWav(chunks, rate), "uyandirma.wav");
      form.append("wake_check", "true");
      if (noisy) form.append("noisy", "true");
      const started = performance.now();
      const result = await api("/api/transcribe", { method: "POST", body: form });
      if (!result.wake || result.echo) return;
      const sttMs = performance.now() - started;
      showSttDevice(result.device);
      applyIdentity(result.identity);
      state.voiceTooShort = !!result.voice_too_short;
      restUntil = Date.now() + 3000; // the overlapping window still holds the same phrase
      button.classList.add("heard");
      setTimeout(() => button.classList.remove("heard"), 1500);
      state.voiceRound++;
      if (result.text) send(result.text, true, sttMs, result.device);
      else {
        chime();
        await sleep(600); // the chime is not recorded as speech
        startListening(false, true);
      }
      waiting = null; // woken: sound heard meanwhile belonged to this
    } catch {
      // a failed check is not worth a message; the next burst is checked again
    } finally {
      sending = false;
      if (waiting && !deaf()) check(...waiting.splice(0));
      waiting = null;
    }
  }

  // 16 kHz mono 16-bit WAV: small to send, and exactly what Whisper uses.
  function toWav(chunks, rate) {
    const total = chunks.reduce((n, c) => n + c.length, 0);
    const ratio = rate / TARGET_RATE;
    const count = Math.floor(total / ratio);
    const all = new Float32Array(total);
    let offset = 0;
    for (const c of chunks) { all.set(c, offset); offset += c.length; }
    const buffer = new ArrayBuffer(44 + count * 2);
    const view = new DataView(buffer);
    const text = (at, s) => [...s].forEach((ch, i) => view.setUint8(at + i, ch.charCodeAt(0)));
    text(0, "RIFF"); view.setUint32(4, 36 + count * 2, true); text(8, "WAVE"); text(12, "fmt ");
    view.setUint32(16, 16, true); view.setUint16(20, 1, true); view.setUint16(22, 1, true);
    view.setUint32(24, TARGET_RATE, true); view.setUint32(28, TARGET_RATE * 2, true);
    view.setUint16(32, 2, true); view.setUint16(34, 16, true); text(36, "data"); view.setUint32(40, count * 2, true);
    for (let i = 0; i < count; i++) {
      const from = Math.floor(i * ratio), to = Math.max(from + 1, Math.floor((i + 1) * ratio));
      let sum = 0;
      for (let j = from; j < to && j < total; j++) sum += all[j];
      const v = Math.max(-1, Math.min(1, sum / (to - from)));
      view.setInt16(44 + i * 2, v < 0 ? v * 0x8000 : v * 0x7fff, true);
    }
    return new Blob([buffer], { type: "audio/wav" });
  }

  button.onclick = () => {
    paused = !paused;
    try { localStorage.setItem("wakePaused", paused ? "1" : "0"); } catch {}
    update();
    if (paused) setStatus("👂 Adınla seslenme duraklatıldı. Yeniden açmak için 👂'a bas.");
  };

  function update() {
    if (wanted()) start(); else stop();
    show();
  }
  return { update };
})();

// Documents (3.23): PDF / Word / text files added to the current conversation.
async function loadDocs() {
  const bar = $("#doc-bar");
  const id = state.conversationId;
  if (!id) { bar.hidden = true; bar.innerHTML = ""; return; }
  let docs = [];
  try { docs = await api(`/api/conversations/${id}/documents`); } catch {}
  if (id !== state.conversationId) return;
  bar.innerHTML = "";
  bar.hidden = !docs.length;
  for (const doc of docs) {
    const chip = document.createElement("span");
    chip.className = "doc-chip";
    chip.title = doc.long ? "Uzun belge: her soruda ilgili bölümlerine bakılır." : "Belgenin tamamı her soruda okunur.";
    chip.innerHTML = `📄 <span></span> <small></small><button type="button" title="Belgeyi bu sohbetten çıkar">✕</button>`;
    chip.querySelector("span").textContent = doc.name;
    chip.querySelector("small").textContent = doc.about;
    chip.querySelector("button").onclick = async () => {
      if (!confirm(`"${doc.name}" bu sohbetten çıkarılsın mı?`)) return;
      await api(`/api/documents/${doc.id}`, { method: "DELETE" }).catch(() => {});
      loadDocs();
    };
    bar.appendChild(chip);
  }
}

async function uploadDocs(files) {
  if (state.busy || !files.length) return;
  setBusy(true);
  let added = null;
  for (const file of files) {
    setStatus(`📄 "${file.name}" okunuyor…`);
    try {
      const form = new FormData();
      form.append("file", file, file.name);
      if (state.conversationId) form.append("conversation_id", state.conversationId);
      const result = await api("/api/documents", { method: "POST", body: form });
      state.conversationId = result.conversation_id;
      added = result;
      setStatus("");
    } catch (err) {
      setStatus(`"${file.name}": ${err.message}`, true);
    }
  }
  setBusy(false);
  if (added) {
    const conv = (await api("/api/conversations").catch(() => [])).find((c) => c.id === state.conversationId);
    await openConversation(state.conversationId, conv ? conv.title : added.document.name);
    els.input.focus();
  }
}

$("#attach").onclick = () => $("#attach-file").click();
$("#attach-file").onchange = (e) => {
  uploadDocs([...e.target.files]);
  e.target.value = "";
};

// Drag a file from Explorer onto the chat.
let dragDepth = 0;
const hasFiles = (e) => [...(e.dataTransfer?.types || [])].includes("Files");
document.addEventListener("dragenter", (e) => { if (hasFiles(e)) { dragDepth++; document.body.classList.add("dropping"); } });
document.addEventListener("dragleave", (e) => { if (hasFiles(e) && --dragDepth <= 0) { dragDepth = 0; document.body.classList.remove("dropping"); } });
document.addEventListener("dragover", (e) => { if (hasFiles(e)) e.preventDefault(); });
document.addEventListener("drop", (e) => {
  if (!hasFiles(e)) return;
  e.preventDefault();
  dragDepth = 0;
  document.body.classList.remove("dropping");
  uploadDocs([...e.dataTransfer.files]);
});
