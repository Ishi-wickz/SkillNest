import { api, ensureCsrf, getMe } from "./api.js";

function link(href, text, cls) {
  const a = document.createElement("a");
  a.href = href;
  a.textContent = text;
  if (cls) a.className = cls;
  return a;
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