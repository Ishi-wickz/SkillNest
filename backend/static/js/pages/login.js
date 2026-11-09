import { api, ensureCsrf } from "../api.js";
import { setBusy, showErrors, wirePasswordToggle } from "../forms.js";

wirePasswordToggle();
const form = document.getElementById("login-form");
form.addEventListener("submit", async (e) => {
  e.preventDefault();
  setBusy(form, true);
  try {
    await ensureCsrf();
    await api("/auth/login/", {
      method: "POST",
      body: { email: form.elements.email.value, password: form.elements.password.value },
    });
    location.href = "/";
  } catch (err) {
    showErrors(form, err);
    setBusy(form, false);
  }
});