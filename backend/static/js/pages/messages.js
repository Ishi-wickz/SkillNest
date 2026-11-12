import { api, ensureCsrf, getMe } from "../api.js";
import { el } from "../format.js";

const gate = document.getElementById("gate");
const layout = document.getElementById("chat-layout");
const listEl = document.getElementById("conv-list");
const head = document.getElementById("chat-head");
const log = document.getElementById("chat-log");
const statusEl = document.getElementById("chat-status");
const form = document.getElementById("chat-form");
const input = document.getElementById("chat-input");

let me = null;
let current = null; // state of the open conversation

const timeLabel = (iso) =>
  new Date(iso).toLocaleString([], { day: "numeric", month: "short", hour: "2-digit", minute: "2-digit" });

async function loadList() {
  const data = await api("/conversations/");
  listEl.replaceChildren();
  if (!data.results.length) {
    listEl.append(el("p", "note pad", "No conversations yet. Open a job's proposals (or your proposal) and click Message."));
    return data.results;
  }
  data.results.forEach((c) => {
    const a = el("a", "conv-item" + (current && current.id === c.id ? " active" : ""));
    a.href = `/messages/?c=${c.id}`;
    const top = el("strong");
    top.append(el("span", "", c.other.full_name || "User"));
    if (c.unread_count) top.append(el("span", "unread", String(c.unread_count)));
    a.append(top, el("small", "", c.job_title), el("small", "", c.last_message ? c.last_message.body : "No messages yet"));
    a.addEventListener("click", (e) => { e.preventDefault(); openConversation(c); });
    listEl.append(a);
  });
  return data.results;
}

function stop() {
  if (!current) return;
  current.closed = true;
  clearInterval(current.poll);
  clearTimeout(current.retry);
  if (current.ws) current.ws.close();
  current = null;
}

function addMessages(state, items) {
  const wasEmpty = state.seen.size === 0;
  const nearBottom = log.scrollHeight - log.scrollTop - log.clientHeight < 80;
  let added = false, lastMine = false;
  items.forEach((m) => {
    if (state.seen.has(m.id)) return;
    state.seen.add(m.id);
    state.lastId = Math.max(state.lastId, m.id);
    if (!added) log.querySelectorAll(".empty-pane").forEach((n) => n.remove());
    added = true;
    lastMine = m.sender_id === me.id;
    const bubble = el("div", `msg ${lastMine ? "mine" : "theirs"}`);
    bubble.append(document.createTextNode(m.body), el("time", "", timeLabel(m.created_at))); // text only, never HTML
    log.append(bubble);
  });
  if (added && (wasEmpty || nearBottom || lastMine)) log.scrollTop = log.scrollHeight;
}

// REST is the source of truth: always ask for "everything after the last id I have"
async function fetchMessages(state) {
  try {
    const qs = state.lastId ? `?after=${state.lastId}` : "";
    const data = await api(`/conversations/${state.id}/messages/${qs}`);
    if (state.closed) return;
    addMessages(state, data.results);
    if (!state.seen.size && !log.querySelector(".empty-pane")) {
      log.append(el("p", "empty-pane", "No messages yet. Say hello!"));
    }
    statusEl.textContent = "";
  } catch {
    if (!state.closed) statusEl.textContent = "Connection problem. Retrying…";
  }
}

function connect(state) {
  if (state.closed) return;
  const proto = location.protocol === "https:" ? "wss" : "ws";
  const ws = new WebSocket(`${proto}://${location.host}/ws/chat/${state.id}/`);
  state.ws = ws;
  ws.onopen = () => fetchMessages(state); // catch up on anything missed while disconnected
  ws.onmessage = () => { fetchMessages(state); loadList().catch(() => {}); }; // the socket is a doorbell
  ws.onclose = () => { if (!state.closed) state.retry = setTimeout(() => connect(state), 10000); };
}

async function openConversation(c) {
  stop();
  const state = { id: c.id, seen: new Set(), lastId: 0, ws: null, poll: null, retry: null, closed: false };
  current = state;
  history.replaceState(null, "", `/messages/?c=${c.id}`);

  const title = el("h2", "", c.other.full_name || "User");
  const jobLink = el("a", "", c.job_title);
  jobLink.href = `/jobs/${c.job}/`;
  head.replaceChildren(title, jobLink);
  log.replaceChildren();
  statusEl.textContent = "";
  form.hidden = false;

  await fetchMessages(state);
  connect(state);
  // Fallback: while the socket is down, poll every 4 seconds
  state.poll = setInterval(() => {
    if (!state.ws || state.ws.readyState !== WebSocket.OPEN) fetchMessages(state);
  }, 4000);
  input.focus();
  loadList().catch(() => {});
}

form.addEventListener("submit", async (e) => {
  e.preventDefault();
  const state = current;
  const body = input.value.trim();
  if (!state || !body) return;
  const btn = form.querySelector("button");
  btn.disabled = true;
  statusEl.textContent = "";
  try {
    await ensureCsrf();
    await api(`/conversations/${state.id}/messages/`, { method: "POST", body: { body } });
    input.value = "";
    await fetchMessages(state); // shows my message and anything I missed
    loadList().catch(() => {});
  } catch (err) {
    statusEl.textContent = err.status === 429
      ? "You're sending messages too fast. Please wait a moment."
      : err.data && err.data.body ? [].concat(err.data.body).join(" ") : err.message;
  }
  btn.disabled = false;
  input.focus();
});

input.addEventListener("keydown", (e) => {
  if (e.key === "Enter" && !e.shiftKey) { e.preventDefault(); form.requestSubmit(); }
});

me = await getMe();
if (!me) {
  location.replace("/login/");
} else if (me.role !== "client" && me.role !== "freelancer") {
  gate.textContent = "Administrators don't have an inbox.";
} else {
  try {
    await ensureCsrf();
    const convs = await loadList();
    gate.remove();
    layout.hidden = false;
    const wanted = Number(new URLSearchParams(location.search).get("c"));
    const first = convs.find((c) => c.id === wanted);
    if (first) openConversation(first);
    else log.append(el("p", "empty-pane", "Select a conversation."));
    setInterval(() => loadList().catch(() => {}), 15000);
  } catch {
    gate.textContent = "Could not load your messages. Please try again.";
  }
}