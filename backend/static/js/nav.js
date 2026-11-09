import { api, ensureCsrf, getMe } from "./api.js";

async function initNav() {
  await ensureCsrf();
  const me = await getMe();
  const box = document.getElementById("nav-auth");
  box.replaceChildren();

  if (!me) {
    box.append(link("/login/", "Login", "btn"), link("/signup/", "Sign Up", "btn"));
    return;
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

function link(href, text, cls) {
  const a = document.createElement("a");
  a.href = href;
  a.textContent = text;
  a.className = cls;
  return a;
}

initNav();