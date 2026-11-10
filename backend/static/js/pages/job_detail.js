import { api, ensureCsrf, getMe } from "../api.js";
import { budgetLabel, el, skillChips, timeAgo } from "../format.js";
import { setBusy, showErrors } from "../forms.js";

const id = location.pathname.split("/").filter(Boolean).pop(); // "/jobs/5/" -> "5"
const statusEl = document.getElementById("status");
const jobBox = document.getElementById("job");
const note = document.getElementById("apply-note");
const applyBox = document.getElementById("apply");

function stat(value, label) {
  const d = el("div");
  d.append(el("b", "", value), el("small", "", label));
  return d;
}

function renderJob(job) {
  const b = budgetLabel(job);
  const meta = el("div", "detail-meta");
  meta.append(stat(b.price, b.kind), stat(String(job.proposal_count), "Proposals"),
              stat(timeAgo(job.created_at), "Posted"));
  jobBox.append(el("h1", "", job.title),
                el("div", "note", [job.category?.name, job.client_name].filter(Boolean).join(" · ")),
                meta, el("p", "detail-desc", job.description), skillChips(job.skills));
  jobBox.hidden = false;
  document.title = job.title + " - SkillNest";
}

async function setupApply(job) {
  const me = await getMe();
  if (job.status !== "open") { note.textContent = "This job is no longer open for proposals."; return; }
  if (!me) {
    note.append("Want to apply? ");
    const a = el("a", "", "Log in or sign up as a freelancer");
    a.href = "/login/";
    note.append(a, ".");
    return;
  }
  if (me.role !== "freelancer") return; // clients and admins don't see the form
  applyBox.hidden = false;

  const form = document.getElementById("proposal-form");
  form.addEventListener("submit", async (e) => {
    e.preventDefault();
    setBusy(form, true);
    try {
      await ensureCsrf();
      await api(`/jobs/${encodeURIComponent(id)}/proposals/`, {
        method: "POST",
        body: {
          bid_amount: form.elements.bid_amount.value,
          delivery_days: Number(form.elements.delivery_days.value),
          cover_letter: form.elements.cover_letter.value.trim(),
        },
      });
      applyBox.replaceChildren(el("p", "ok", "Proposal sent! The client will review it."));
    } catch (err) {
      showErrors(form, err);
      setBusy(form, false);
    }
  });
}

try {
  const job = await api(`/jobs/${encodeURIComponent(id)}/`);
  statusEl.remove();
  renderJob(job);
  await setupApply(job);
} catch (err) {
  statusEl.textContent = err.status === 404 ? "This job doesn't exist or is no longer available."
                                            : "Could not load this job. Please try again.";
}