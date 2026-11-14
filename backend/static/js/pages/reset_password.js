import { api, ensureCsrf } from "../api.js";
import { setBusy, showErrors, wirePasswordToggle } from "../forms.js";

const params = new URLSearchParams(location.search);
const uid = params.get("uid") || "";
const token = params.get("token") || "";
// Keep the token out of the address bar and the browser history
history.replaceState(null, "", location.pathname);

const form = document.getElementById("reset-form");
const done = document.getElementById("done");
const topError = document.getElementById("form-error");

if (!uid || !token) {
  form.hidden = true;
  topError.textContent = "This reset link is incomplete. Please request a new one.";
} else {
  wirePasswordToggle();
  form.addEventListener("submit", async (e) => {
    e.preventDefault();
    if (form.elements.password.value !== form.elements.password2.value) {
      topError.textContent = "The two passwords don't match.";
      return;
    }
    setBusy(form, true);
    try {
      await ensureCsrf();
      const r = await api("/auth/password-reset/confirm/", {
        method: "POST",
        body: { uid, token, password: form.elements.password.value },
      });
      form.hidden = true;
      topError.textContent = "";
      done.textContent = r.detail + " ";
      const a = document.createElement("a");
      a.href = "/login/";
      a.textContent = "Log in";
      done.append(a);
      done.hidden = false;
    } catch (err) {
      showErrors(form, err);
      setBusy(form, false);
    }
  });
}