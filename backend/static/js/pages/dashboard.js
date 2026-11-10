import { api, ensureCsrf, getMe } from "../api.js";
import { budgetLabel, el, money, timeAgo } from "../format.js";

const root = document.getElementById("dash");
const statusEl = document.getElementById("status");
const title = document.getElementById("dash-title");

const pretty = (s) => s.replace("_", " ");
const badge = (s) => el("span", `badge s-${s}`, pretty(s));

function emptyMessage(text, linkText, href) {
  const p = el("p", "note", text + " ");
  if (href) { const a = el("a", "", linkText); a.href = href; p.append(a); }
  return p;
}

/* ---------------- Client ---------------- */
async function loadProposals(job, panel) {
  panel.replaceChildren(el("p", "note", "Loading proposals…"));
  try {
    const data = await api(`/jobs/${job.id}/proposals/`);
    panel.replaceChildren();
    if (!data.results.length) { panel.append(el("p", "note", "No proposals yet.")); return; }
    data.results.forEach((p) => {
      const row = el("div", "proposal");
      const head = el("div", "proposal-head");
      head.append(
        el("strong", "", p.freelancer.full_name || "Freelancer"),
        el("span", "note", `${money(p.bid_amount, job.currency)} · ${p.delivery_days} days`),
        badge(p.status)
      );
      row.append(head, el("p", "cover", p.cover_letter));

      if (p.status === "pending" && job.status === "open") {
        const actions = el("div", "actions");
        const accept = el("button", "btn-green", "Accept");
        const reject = el("button", "btn-outline", "Reject");
        accept.addEventListener("click", () => decide(p.id, "accept", accept, reject));
        reject.addEventListener("click", () => decide(p.id, "reject", accept, reject));
        actions.append(accept, reject);
        row.append(actions);
      }
      panel.append(row);
    });
  } catch {
    panel.replaceChildren(el("p", "form-error", "Could not load proposals."));
  }
}

async function decide(id, action, ...buttons) {
  if (action === "accept" &&
      !confirm("Accept this proposal? All other pending proposals will be rejected.")) return;
  buttons.forEach((b) => (b.disabled = true)); // stops double clicks
  try {
    await api(`/proposals/${id}/${action}/`, { method: "POST" });
    await clientView();
  } catch (err) {
    alert(err.message || "Something went wrong.");
    buttons.forEach((b) => (b.disabled = false));
  }
}

function jobItem(job) {
  const item = el("div", "dash-item");
  const card = el("article", "job-card");

  const left = el("div");
  const h2 = el("h2");
  const a = el("a", "", job.title);
  a.href = `/jobs/${job.id}/`;
  h2.append(a);
  left.append(h2, el("div", "meta", [job.category?.name, `Posted ${timeAgo(job.created_at)}`].filter(Boolean).join(" · ")));

  const actions = el("div", "actions");
  const view = el("button", "btn-navy small", `Proposals (${job.proposal_count})`);
  actions.append(view);
  if (job.status === "open") {
    const cancel = el("button", "btn-outline", "Cancel job");
    cancel.addEventListener("click", async () => {
      if (!confirm("Cancel this job? Freelancers will no longer see it.")) return;
      cancel.disabled = true;
      try { await api(`/jobs/${job.id}/`, { method: "DELETE" }); await clientView(); }
      catch (err) { alert(err.message || "Could not cancel."); cancel.disabled = false; }
    });
    actions.append(cancel);
  }
  left.append(actions);

  const b = budgetLabel(job);
  const side = el("div", "job-side");
  side.append(el("div", "price", b.price), badge(job.status));
  card.append(left, side);

  const panel = el("div", "proposals");
  panel.hidden = true;
  view.addEventListener("click", () => {
    panel.hidden = !panel.hidden;
    if (!panel.hidden) loadProposals(job, panel);
  });

  item.append(card, panel);
  return item;
}

async function clientView() {
  title.textContent = "My jobs";
  const data = await api("/jobs/mine/");
  statusEl.textContent = "";
  root.replaceChildren(
    ...(data.results.length
      ? data.results.map(jobItem)
      : [emptyMessage("You haven't posted any jobs yet.", "Post your first job", "/jobs/new/")])
  );
}

/* ---------------- Freelancer ---------------- */
async function freelancerView() {
  title.textContent = "My proposals";
  const data = await api("/proposals/mine/");
  statusEl.textContent = "";
  if (!data.results.length) {
    root.replaceChildren(emptyMessage("You haven't sent any proposals yet.", "Browse jobs", "/jobs/"));
    return;
  }
  root.replaceChildren(...data.results.map((p) => {
    const card = el("article", "job-card");
    const left = el("div");
    const h2 = el("h2");
    const a = el("a", "", p.job_title);
    a.href = `/jobs/${p.job}/`;
    h2.append(a);
    left.append(h2,
      el("div", "meta", `Sent ${timeAgo(p.created_at)} · delivery in ${p.delivery_days} days`),
      el("p", "desc", p.cover_letter.length > 200 ? p.cover_letter.slice(0, 200) + "…" : p.cover_letter));
    const side = el("div", "job-side");
    side.append(el("div", "price", Number(p.bid_amount).toFixed(2)), el("small", "", "Your bid"), badge(p.status));
    card.append(left, side);
    return card;
  }));
}

/* ---------------- Start ---------------- */
const me = await getMe();
if (!me) {
  location.replace("/login/");
} else {
  await ensureCsrf();
  try {
    if (me.role === "client") await clientView();
    else if (me.role === "freelancer") await freelancerView();
    else statusEl.textContent = "Administrators use the admin site.";
  } catch {
    statusEl.textContent = "Could not load your dashboard. Please try again.";
  }
}