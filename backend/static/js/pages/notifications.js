import { api, ensureCsrf, getMe } from "../api.js";
import { el, timeAgo } from "../format.js";
import { safePath } from "../notify.js";

const PAGE_SIZE = 20; // matches NotificationPagination
const gate = document.getElementById("gate");
const box = document.getElementById("box");
const list = document.getElementById("note-list");
const pagerEl = document.getElementById("pager");
const statusEl = document.getElementById("status");
const saved = document.getElementById("saved");
const toggle = document.getElementById("email-toggle");
let page = 1;

const refreshBell = () => window.dispatchEvent(new CustomEvent("skillnest:refresh-unread"));

function item(n) {
  const a = el("a", "note-item" + (n.read ? "" : " unread"));
  a.href = safePath(n.url);
  const dot = el("span", "note-dot");
  dot.setAttribute("aria-hidden", "true");
  const body = el("span");
  body.append(document.createTextNode(n.message),
              el("small", "", timeAgo(n.created_at) + (n.read ? "" : " · new")));
  a.append(dot, body);
  a.addEventListener("click", async (e) => {
    if (n.read) return; // already read: follow the link normally
    e.preventDefault();
    try {
      await ensureCsrf();
      await api(`/notifications/${n.id}/read/`, { method: "POST" });
    } catch { /* go to the page anyway */ }
    location.href = a.href;
  });
  return a;
}

function renderPager(count) {
  pagerEl.replaceChildren();
  const pages = Math.ceil(count / PAGE_SIZE);
  if (pages <= 1) return;
  const link = (label, target, off) => {
    if (off) return el("span", "off", label);
    const a = el("a", "", label);
    a.href = "#";
    a.addEventListener("click", (e) => { e.preventDefault(); page = target; load(); window.scrollTo(0, 0); });
    return a;
  };
  pagerEl.append(link("Previous", page - 1, page <= 1),
                 el("span", "current", `Page ${page} of ${pages}`),
                 link("Next", page + 1, page >= pages));
}

async function load() {
  try {
    const data = await api(`/notifications/?page=${page}`);
    list.replaceChildren(...data.results.map(item));
    list.hidden = data.results.length === 0;
    statusEl.textContent = data.count === 0 ? "You have no notifications yet." : "";
    renderPager(data.count);
  } catch (err) {
    if (err.status === 404 && page > 1) { page -= 1; return load(); }
    statusEl.textContent = "Could not load notifications. Please try again.";
  }
}

const me = await getMe();
if (!me) {
  location.replace("/login/");
} else if (me.role !== "client" && me.role !== "freelancer") {
  gate.textContent = "Administrators don't have notifications.";
} else {
  try {
    await ensureCsrf();
    const settings = await api("/notifications/settings/");
    toggle.checked = settings.email_enabled;
    await load();
    gate.remove();
    box.hidden = false;
  } catch {
    gate.textContent = "Could not load your notifications. Please try again.";
  }

  toggle.addEventListener("change", async () => {
    const wanted = toggle.checked;
    saved.textContent = "";
    try {
      await ensureCsrf();
      await api("/notifications/settings/", { method: "PATCH", body: { email_enabled: wanted } });
      saved.textContent = wanted ? "Email notifications are on." : "Email notifications are off.";
    } catch {
      toggle.checked = !wanted; // put it back if saving failed
      saved.textContent = "Could not save that setting.";
    }
  });

  document.getElementById("read-all").addEventListener("click", async () => {
    try {
      await ensureCsrf();
      await api("/notifications/read-all/", { method: "POST" });
      await load();
      refreshBell();
    } catch {
      saved.textContent = "Could not mark them as read.";
    }
  });

  // A live notification arrived: refresh the list
  window.addEventListener("skillnest:notification", () => load());
}