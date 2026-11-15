import { api } from "./api.js";

// Only ever follow paths on our own site, even though the server made them
export function safePath(url) {
  return typeof url === "string" && url.startsWith("/") && !url.startsWith("//") ? url : "/notifications/";
}

function toast(n) {
  document.querySelector(".toast")?.remove();
  const box = document.createElement("a");
  box.className = "toast";
  box.href = safePath(n.url);
  box.setAttribute("role", "status");
  box.textContent = n.message; // text only, never HTML
  document.body.append(box);
  setTimeout(() => box.remove(), 6000);
}

export function startNotifications(badge) {
  const show = (count) => {
    badge.textContent = count > 99 ? "99+" : String(count);
    badge.hidden = count === 0;
  };
  const refresh = async () => {
    try {
      const { count } = await api("/notifications/unread/");
      show(count);
    } catch { /* the badge is a convenience */ }
  };
  refresh();
  setInterval(refresh, 30000); // the fallback when the socket is down
  window.addEventListener("skillnest:refresh-unread", refresh);

  let delay = 5000;
  const connect = () => {
    let ws;
    try {
      ws = new WebSocket(`${location.protocol === "https:" ? "wss" : "ws"}://${location.host}/ws/notifications/`);
    } catch { return; }
    ws.onopen = () => { delay = 5000; };
    ws.onmessage = (e) => {
      let n;
      try { n = JSON.parse(e.data); } catch { return; }
      show(Number(n.unread) || 0);
      window.dispatchEvent(new CustomEvent("skillnest:notification", { detail: n }));
      const inChat = n.kind === "new_message" && location.pathname.startsWith("/messages/");
      if (inChat) setTimeout(refresh, 1500); // the open chat marks it read a moment later
      else toast(n);
    };
    ws.onclose = () => {
      setTimeout(connect, delay);
      delay = Math.min(delay * 2, 120000); // back off, for hosts that don't support WebSockets
    };
  };
  connect();
}