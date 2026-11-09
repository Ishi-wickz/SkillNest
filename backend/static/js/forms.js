// Shows API errors under the matching field. Uses textContent, so error text can't inject HTML.
export function showErrors(form, error) {
  form.querySelectorAll(".field-error").forEach((el) => el.remove());
  const top = document.getElementById("form-error");
  top.textContent = "";

  const data = error.data || {};
  let shownAny = false;
  for (const [field, messages] of Object.entries(data)) {
    const input = form.elements[field];
    if (!input || field === "detail") continue;
    const p = document.createElement("div");
    p.className = "field-error";
    p.textContent = [].concat(messages).join(" ");
    input.closest(".field")?.append(p);
    shownAny = true;
  }
  if (!shownAny) {
    top.textContent = error.status === 429
      ? "Too many attempts. Please wait a minute and try again."
      : error.message || "Something went wrong.";
  }
}

export function setBusy(form, busy) {
  form.querySelector('button[type="submit"]').disabled = busy; // stops double submits
}

// Show/hide password. A real <button>, so it works with keyboard and screen readers.
export function wirePasswordToggle() {
  document.querySelectorAll(".pw-toggle").forEach((btn) => {
    const input = btn.parentElement.querySelector("input");
    btn.addEventListener("click", () => {
      const show = input.type === "password";
      input.type = show ? "text" : "password";
      btn.textContent = show ? "Hide" : "Show";
      btn.setAttribute("aria-pressed", String(show));
      btn.setAttribute("aria-label", show ? "Hide password" : "Show password");
    });
  });
}