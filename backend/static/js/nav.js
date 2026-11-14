import { api, ensureCsrf, getMe } from "./api.js";

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
    const messages = link("/messages/", "Messages");
    const badge = document.createElement("span");
    badge.className = "nav-badge";
    badge.hidden = true;
    messages.append(badge);
    box.append(link("/dashboard/", "Dashboard"), messages, link("/profile/", "Profile"));

    const refresh = async () => {
      try {
        const { count } = await api("/messages/unread/");
        badge.textContent = String(count);
        badge.hidden = count === 0;
      } catch { /* ignore: the badge is a convenience */ }
    };
    refresh();
    setInterval(refresh, 30000);

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