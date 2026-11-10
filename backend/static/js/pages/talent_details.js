import { api } from "../api.js";
import { el, money, skillChips } from "../format.js";

const id = location.pathname.split("/").filter(Boolean).pop();
const statusEl = document.getElementById("status");
const box = document.getElementById("profile");

function initials(name) {
  return (name || "?").split(/\s+/).slice(0, 2).map((w) => w[0]).join("").toUpperCase();
}

try {
  const t = await api(`/talent/${encodeURIComponent(id)}/`);
  statusEl.remove();

  const head = el("div", "talent-main");
  head.append(el("div", "avatar-lg", initials(t.full_name)));
  const who = el("div");
  who.append(
    el("h1", "", t.full_name),
    el("div", "note", t.avg_rating ? `★ ${t.avg_rating} (${t.review_count} reviews)` : "No reviews yet")
  );
  head.append(who);

  const meta = el("div", "detail-meta");
  const rate = el("div");
  rate.append(el("b", "", t.hourly_rate ? money(t.hourly_rate, "USD") + "/hr" : "Not set"), el("small", "", "Hourly rate"));
  meta.append(rate);

  box.append(head, meta, el("h2", "", "About"), el("p", "detail-desc", t.bio || "This freelancer hasn't written a bio yet."));
  if (t.skills.length) box.append(el("h2", "", "Skills"), skillChips(t.skills));

  const cta = el("p", "note");
  cta.append("Want to work with " + t.full_name + "? ");
  const a = el("a", "", "Post a job");
  a.href = "/jobs/new/";
  cta.append(a, ".");
  box.append(cta);

  box.hidden = false;
  document.title = t.full_name + " - SkillNest";
} catch (err) {
  statusEl.textContent = err.status === 404 ? "This freelancer doesn't exist."
                                            : "Could not load this profile. Please try again.";
}