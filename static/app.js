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

async function send(text, fromVoice = false) {
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
  let reply = "";

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
          if (state.conversationId !== event.conversation_id) {
            state.conversationId = event.conversation_id;
            els.title.textContent = text.length > 50 ? text.slice(0, 47) + "..." : text;
          }
        } else if (event.type === "token") {
          reply += event.text;
          bubble.innerHTML = renderMarkdown(reply);
          scrollToBottom();
        } else if (event.type === "error") {
          throw new Error(event.message);
        }
      }
    }
    if (reply && (els.speak.checked || fromVoice)) speak(reply);
  } catch (err) {
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

let recorder = null;

els.mic.addEventListener("click", async () => {
  if (recorder && recorder.state === "recording") {
    recorder.stop();
    return;
  }
  stopSpeaking();
  let stream;
  try {
    stream = await navigator.mediaDevices.getUserMedia({ audio: true });
  } catch {
    setStatus("Mikrofona erişilemedi. Tarayıcının mikrofon iznini kontrol et.", true);
    return;
  }
  const chunks = [];
  recorder = new MediaRecorder(stream);
  recorder.ondataavailable = (e) => e.data.size && chunks.push(e.data);
  recorder.onstop = async () => {
    stream.getTracks().forEach((t) => t.stop());
    els.mic.classList.remove("recording");
    const blob = new Blob(chunks, { type: recorder.mimeType });
    if (!blob.size) return setStatus("");
    setStatus("Ses yazıya çevriliyor... (ilk seferde model indirildiği için birkaç dakika sürebilir)");
    setBusy(true);
    try {
      const form = new FormData();
      form.append("audio", blob, "kayit.webm");
      const { text } = await api("/api/transcribe", { method: "POST", body: form });
      setBusy(false);
      if (!text) return setStatus("Bir şey duyamadım, tekrar dener misin?", true);
      send(text, true);
    } catch (err) {
      setBusy(false);
      setStatus(err.message, true);
    }
  };
  recorder.start();
  els.mic.classList.add("recording");
  setStatus("🎙️ Dinliyorum... Bitirince 🎤 butonuna tekrar bas.");
});

// Voice output: only offline voices installed on Windows, so no text leaves the computer.

function pickVoice() {
  const lang = (state.settings.language || "tr").toLowerCase();
  const local = speechSynthesis.getVoices().filter((v) => v.localService);
  return local.find((v) => v.lang.toLowerCase().startsWith(lang)) || null;
}

function speak(text) {
  if (!("speechSynthesis" in window)) return;
  const voice = pickVoice();
  if (!voice) {
    setStatus("Bu dilde yüklü bir Windows sesi bulunamadı. Ayarlar > Zaman ve dil > Konuşma bölümünden ses ekleyebilirsin.", true);
    return;
  }
  const utterance = new SpeechSynthesisUtterance(plainText(text));
  utterance.voice = voice;
  utterance.lang = voice.lang;
  speechSynthesis.speak(utterance);
}

function stopSpeaking() {
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
  els.memoryDialog.showModal();
  await loadMemories();
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

async function loadSettings() {
  state.settings = await api("/api/settings");
  els.greeting.textContent = `Merhaba, ben ${state.settings.assistant_name}!`;
  document.title = state.settings.assistant_name;
}

$("#open-settings").onclick = async () => {
  const form = els.settingsForm;
  form.assistant_name.value = state.settings.assistant_name;
  form.whisper_model.value = state.settings.whisper_model;
  form.language.value = state.settings.language;

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

  els.settingsDialog.showModal();
};

els.settingsForm.addEventListener("submit", async (e) => {
  e.preventDefault();
  const data = Object.fromEntries(new FormData(els.settingsForm));
  await api("/api/settings", { method: "PUT", body: JSON.stringify(data) });
  await loadSettings();
  els.settingsDialog.close();
});

document.querySelectorAll("[data-close]").forEach((btn) => {
  btn.onclick = () => btn.closest("dialog").close();
});

// Layout

$("#new-chat").onclick = newConversation;
$("#toggle-sidebar").onclick = () => els.sidebar.classList.toggle("open");

loadSettings().catch((err) => setStatus(err.message, true));
loadConversations().catch((err) => setStatus(err.message, true));
