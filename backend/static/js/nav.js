import { api, ensureCsrf, getMe } from "./api.js";
import { startNotifications } from "./notify.js";

function link(href, text, cls) {
  const a = document.createElement("a");
  a.href = href;
  a.textContent = text;
  if (cls) a.className = cls;
  return a;
}

function verifyBanner() {
  const bar = document.createElement("div");
  bar.className = "verify-bar";
  bar.setAttribute("role", "status");
  const text = document.createElement("span");
  text.textContent = "Please verify your email to post jobs, send proposals and message people. ";
  const btn = document.createElement("button");
  btn.type = "button";
  btn.className = "link-btn";
  btn.textContent = "Resend verification email";
  btn.addEventListener("click", async () => {
    btn.disabled = true;
    try {
      await ensureCsrf();
      const r = await api("/auth/verify-email/send/", { method: "POST" });
      text.textContent = r.detail + " ";
      btn.remove();
    } catch (err) {
      text.textContent = (err.status === 429 ? "Too many requests. Please try again later." : err.message) + " ";
      btn.disabled = false;
    }
  });
  bar.append(text, btn);
  return bar;
}

async function initNav() {
  await ensureCsrf();
  const me = await getMe();
  const box = document.getElementById("nav-auth");
  box.replaceChildren();

  if (!me) {
    box.append(link("/login/", "Login", "btn"), link("/signup/", "Sign Up", "btn"));
    return;
  }
  if (me.role === "client") box.append(link("/jobs/new/", "Post a job"));
  if (me.role === "client" || me.role === "freelancer") {
    const messages = link("/messages/", "\u2709\uFE0F");
    messages.title = "Messages";
    messages.setAttribute("aria-label", "Messages");
    const msgBadge = document.createElement("span");
    msgBadge.className = "nav-badge";
    msgBadge.hidden = true;
    messages.append(msgBadge);

    const bell = link("/notifications/", "\u{1F514}");
    bell.title = "Notifications";
    bell.setAttribute("aria-label", "Notifications");
    const bellBadge = document.createElement("span");
    bellBadge.className = "nav-badge";
    bellBadge.hidden = true;
    bell.append(bellBadge);

    box.append(link("/dashboard/", "Dashboard"), messages, bell, link("/profile/", "Profile"));

    const refreshMessages = async () => {
      try {
        const { count } = await api("/messages/unread/");
        msgBadge.textContent = String(count);
        msgBadge.hidden = count === 0;
      } catch { /* ignore: the badge is a convenience */ }
    };
    refreshMessages();
    setInterval(refreshMessages, 30000);
    startNotifications(bellBadge);

    if (me.email_verified === false) document.querySelector(".nav").after(verifyBanner());
  }

  const who = document.createElement("span");
  who.textContent = me.full_name || me.email;
  const out = document.createElement("button");
  out.className = "btn";
  out.textContent = "Log out";
  out.addEventListener("click", async () => {
    await api("/auth/logout/", { method: "POST" });
    location.href = "/";
  });
  box.append(who, out);
}

initNav();