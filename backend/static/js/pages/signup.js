import { api, ensureCsrf } from "../api.js";
import { setBusy, showErrors, wirePasswordToggle } from "../forms.js";

// Only the wording differs between roles
const COPY = {
  freelancer: { title: "Create your freelancer account", button: "Join as a freelancer",
                note: "Signing up as a freelancer. " },
  client:     { title: "Create your client account", button: "Join as a client",
                note: "Signing up as a client. " },
};

const role = new URLSearchParams(location.search).get("role");

if (!Object.hasOwn(COPY, role)) {
  location.replace("/signup/"); // no valid role: go pick one first
} else {
  const c = COPY[role];
  document.getElementById("form-title").textContent = c.title;
  document.getElementById("submit-btn").textContent = c.button;

  const note = document.getElementById("role-note");
  note.append(c.note);
  const change = document.createElement("a");
  change.href = "/signup/";
  change.textContent = "Change";
  note.append(change);

  wirePasswordToggle();
  const form = document.getElementById("signup-form");
  form.elements.role.value = role;

  form.addEventListener("submit", async (e) => {
    e.preventDefault();
    setBusy(form, true);
    try {
      await ensureCsrf();
      await api("/auth/signup/", {
        method: "POST",
        body: {
          role: form.elements.role.value,
          full_name: form.elements.full_name.value.trim(),
          email: form.elements.email.value.trim(),
          password: form.elements.password.value,
        },
      });
      location.href = "/";
    } catch (err) {
      showErrors(form, err);
      setBusy(form, false);
    }
  });
}