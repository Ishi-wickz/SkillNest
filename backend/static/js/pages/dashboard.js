import { api, ensureCsrf, getMe } from "../api.js";
import { budgetLabel, el, money, timeAgo } from "../format.js";

const PAGE_SIZE = 12; // matches PAGE_SIZE in settings.py
const root = document.getElementById("dash");
const statusEl = document.getElementById("status");
const title = document.getElementById("dash-title");

let clientPage = 1;
let freelancerPage = 1;

const pretty = (s) => s.replace("_", " ");
const badge = (s) => el("span", `badge s-${s}`, pretty(s));

function emptyMessage(text, linkText, href) {
  const p = el("p", "note", text + " ");
  if (href) { const a = el("a", "", linkText); a.href = href; p.append(a); }
  return p;
}

// Previous / Page X of Y / Next. Returns null when everything fits on one page.
function pager(count, page, go) {
  const pages = Math.ceil(count / PAGE_SIZE);
  if (pages <= 1) return null;
  const nav = el("nav", "pager");
  nav.setAttribute("aria-label", "Pagination");
  const link = (label, target, off) => {
    if (off) return el("span", "off", label);
    const a = el("a", "", label);
    a.href = "#";
    a.addEventListener("click", (e) => { e.preventDefault(); go(target); window.scrollTo(0, 0); });
    return a;
  };
  nav.append(link("Previous", page - 1, page <= 1),
             el("span", "current", `Page ${page} of ${pages}`),
             link("Next", page + 1, page >= pages));
  return nav;
}

// Opens (or finds) the chat for a job, then jumps to the inbox
async function openChat(body, button) {
  button.disabled = true;
  try {
    await ensureCsrf();
    const conv = await api("/conversations/", { method: "POST", body });
    location.href = `/messages/?c=${conv.id}`;
  } catch (err) {
    alert(err.message || "Could not open the conversation.");
    button.disabled = false;
  }
}

/* ---------------- Client ---------------- */
const reloadClient = () => clientView(clientPage);

function proposalRow(job, p) {
  const row = el("div", "proposal");
  const head = el("div", "proposal-head");
  head.append(
    el("strong", "", p.freelancer.full_name || "Freelancer"),
    el("span", "note", `${money(p.bid_amount, job.currency)} · ${p.delivery_days} days`),
    badge(p.status)
  );
  row.append(head, el("p", "cover", p.cover_letter));

  const actions = el("div", "actions");
  if (p.status === "pending" && job.status === "open") {
    const accept = el("button", "btn-green", "Accept");
    const reject = el("button", "btn-outline", "Reject");
    accept.addEventListener("click", () => decide(p.id, "accept", accept, reject));
    reject.addEventListener("click", () => decide(p.id, "reject", accept, reject));
    actions.append(accept, reject);
  }
  const message = el("button", "btn-outline", "Message");
  message.addEventListener("click", () =>
    openChat({ job_id: job.id, freelancer_id: p.freelancer.id }, message));
  actions.append(message);
  row.append(actions);
  return row;
}

// Page 1 replaces the panel, later pages are appended under a "Show more" button
async function loadProposals(job, panel, page = 1) {
  if (page === 1) panel.replaceChildren(el("p", "note", "Loading proposals…"));
  try {
    const data = await api(`/jobs/${job.id}/proposals/?page=${page}`);
    if (page === 1) panel.replaceChildren();
    panel.querySelector(".more")?.remove();
    if (!data.results.length && page === 1) { panel.append(el("p", "note", "No proposals yet.")); return; }
    data.results.forEach((p) => panel.append(proposalRow(job, p)));
    if (data.next) {
      const more = el("button", "btn-outline more", "Show more");
      more.addEventListener("click", () => { more.disabled = true; loadProposals(job, panel, page + 1); });
      panel.append(more);
    }
  } catch {
    const msg = el("p", "form-error", "Could not load proposals.");
    if (page === 1) panel.replaceChildren(msg); else panel.append(msg);
  }
}

async function decide(id, action, ...buttons) {
  if (action === "accept" &&
      !confirm("Accept this proposal? All other pending proposals will be rejected.")) return;
  buttons.forEach((b) => (b.disabled = true));
  try {
    await api(`/proposals/${id}/${action}/`, { method: "POST" });
    await reloadClient();
  } catch (err) {
    alert(err.message || "Something went wrong.");
    buttons.forEach((b) => (b.disabled = false));
  }
}

function reviewForm(job) {
  const form = el("form", "review-form");
  form.noValidate = true;

  const rLabel = el("label", "", "Rating");
  const select = document.createElement("select");
  [5, 4, 3, 2, 1].forEach((n) => {
    const o = el("option", "", `${n} star${n > 1 ? "s" : ""}`);
    o.value = n;
    select.append(o);
  });
  rLabel.append(select);

  const cLabel = el("label", "", "Comment (optional)");
  const comment = document.createElement("textarea");
  comment.maxLength = 2000;
  cLabel.append(comment);

  const error = el("div", "form-error");
  error.setAttribute("role", "alert");
  const submit = el("button", "btn-navy small", "Submit review");
  submit.type = "submit";

  form.append(rLabel, cLabel, error, submit);
  form.addEventListener("submit", async (e) => {
    e.preventDefault();
    submit.disabled = true;
    error.textContent = "";
    try {
      await ensureCsrf();
      await api(`/jobs/${job.id}/reviews/`, {
        method: "POST",
        body: { rating: Number(select.value), comment: comment.value.trim() },
      });
      await reloadClient();
    } catch (err) {
      error.textContent = err.message || "Could not save your review.";
      submit.disabled = false;
    }
  });
  return form;
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

  let reviewPanel = null;
  if (job.status === "open") {
    const cancel = el("button", "btn-outline", "Cancel job");
    cancel.addEventListener("click", async () => {
      if (!confirm("Cancel this job? Freelancers will no longer see it.")) return;
      cancel.disabled = true;
      try { await api(`/jobs/${job.id}/`, { method: "DELETE" }); await reloadClient(); }
      catch (err) { alert(err.message || "Could not cancel."); cancel.disabled = false; }
    });
    actions.append(cancel);
  } else if (job.status === "in_progress") {
    const done = el("button", "btn-green", "Mark complete");
    done.addEventListener("click", async () => {
      if (!confirm("Mark this job as complete? You can then review the freelancer.")) return;
      done.disabled = true;
      try { await api(`/jobs/${job.id}/complete/`, { method: "POST" }); await reloadClient(); }
      catch (err) { alert(err.message || "Could not complete the job."); done.disabled = false; }
    });
    actions.append(done);
  } else if (job.status === "completed") {
    if (job.reviewed) {
      actions.append(el("span", "note", "You reviewed this freelancer ✓"));
    } else {
      const review = el("button", "btn-green", "Leave a review");
      reviewPanel = reviewForm(job);
      reviewPanel.hidden = true;
      review.addEventListener("click", () => { reviewPanel.hidden = !reviewPanel.hidden; });
      actions.append(review);
    }
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

  item.append(card);
  if (reviewPanel) item.append(reviewPanel);
  item.append(panel);
  return item;
}

async function clientView(page = 1) {
  title.textContent = "My jobs";
  let data;
  try {
    data = await api(`/jobs/mine/?page=${page}`);
  } catch (err) {
    if (err.status === 404 && page > 1) return clientView(page - 1); // the last page just emptied
    throw err;
  }
  clientPage = page;
  statusEl.textContent = "";
  if (!data.results.length) {
    root.replaceChildren(emptyMessage("You haven't posted any jobs yet.", "Post your first job", "/jobs/new/"));
    return;
  }
  root.replaceChildren(...[...data.results.map(jobItem), pager(data.count, page, clientView)].filter(Boolean));
}

/* ---------------- Freelancer ---------------- */
const reloadFreelancer = () => freelancerView(freelancerPage);

function proposalCard(p) {
  const card = el("article", "job-card");
  const left = el("div");
  const h2 = el("h2");
  const a = el("a", "", p.job_title);
  a.href = `/jobs/${p.job}/`;
  h2.append(a);
  left.append(h2,
    el("div", "meta", `Sent ${timeAgo(p.created_at)} · delivery in ${p.delivery_days} days`),
    el("p", "desc", p.cover_letter.length > 200 ? p.cover_letter.slice(0, 200) + "…" : p.cover_letter));

  const actions = el("div", "actions");
  const message = el("button", "btn-outline", "Message client");
  message.addEventListener("click", () => openChat({ job_id: p.job }, message));
  actions.append(message);

  if (p.status === "pending") {
    const withdraw = el("button", "btn-outline", "Withdraw");
    withdraw.addEventListener("click", async () => {
      if (!confirm("Withdraw this proposal? You can't send another one for the same job.")) return;
      withdraw.disabled = true;
      try {
        await ensureCsrf();
        await api(`/proposals/${p.id}/withdraw/`, { method: "POST" });
        await reloadFreelancer();
      } catch (err) {
        alert(err.message || "Could not withdraw the proposal.");
        withdraw.disabled = false;
      }
    });
    actions.append(withdraw);
  }
  left.append(actions);

  const side = el("div", "job-side");
  side.append(el("div", "price", Number(p.bid_amount).toFixed(2)), el("small", "", "Your bid"), badge(p.status));
  if (p.status === "accepted") side.append(el("small", "", `Job ${pretty(p.job_status)}`));
  card.append(left, side);
  return card;
}

async function freelancerView(page = 1) {
  title.textContent = "My proposals";
  let data;
  try {
    data = await api(`/proposals/mine/?page=${page}`);
  } catch (err) {
    if (err.status === 404 && page > 1) return freelancerView(page - 1);
    throw err;
  }
  freelancerPage = page;
  statusEl.textContent = "";
  if (!data.results.length) {
    root.replaceChildren(emptyMessage("You haven't sent any proposals yet.", "Browse jobs", "/jobs/"));
    return;
  }
  root.replaceChildren(...[...data.results.map(proposalCard), pager(data.count, page, freelancerView)].filter(Boolean));
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