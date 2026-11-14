import { api, ensureCsrf } from "../api.js";
import { setBusy, showErrors } from "../forms.js";

const form = document.getElementById("forgot-form");
const done = document.getElementById("done");

form.addEventListener("submit", async (e) => {
  e.preventDefault();
  setBusy(form, true);
  try {
    await ensureCsrf();
    const r = await api("/auth/password-reset/", {
      method: "POST",
      body: { email: form.elements.email.value.trim() },
    });
    form.hidden = true;
    document.getElementById("form-error").textContent = "";
    done.textContent = r.detail; // the same message whether or not the account exists
    done.hidden = false;
  } catch (err) {
    if (err.status === 429) {
      document.getElementById("form-error").textContent = "Too many requests. Please try again in a while.";
    } else {
      showErrors(form, err);
    }
    setBusy(form, false);
  }
});