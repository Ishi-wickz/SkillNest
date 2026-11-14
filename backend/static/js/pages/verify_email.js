import { api } from "../api.js";

const token = new URLSearchParams(location.search).get("token");
history.replaceState(null, "", location.pathname); // keep the token out of the address bar

const msg = document.getElementById("msg");
const next = document.getElementById("next");

if (!token) {
  msg.textContent = "This verification link is incomplete. Log in and use the resend button.";
} else {
  try {
    await api("/auth/verify-email/confirm/", { method: "POST", body: { token } });
    msg.textContent = "Your email is verified. You can now post jobs, send proposals and message people.";
  } catch (err) {
    msg.textContent = err.status === 429
      ? "Too many attempts. Please wait a minute and reload the link."
      : err.message || "Something went wrong.";
  }
  next.hidden = false;
}