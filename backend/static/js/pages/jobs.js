import { api } from "../api.js";
import { budgetLabel, el, skillChips, timeAgo } from "../format.js";

const PAGE_SIZE = 12; // matches PAGE_SIZE in settings.py
const params = new URLSearchParams(location.search);
const form = document.getElementById("filters");
const list = document.getElementById("job-list");
const statusEl = document.getElementById("status");
const pager = document.getElementById("pager");
const FILTERS = ["q", "category", "min", "max"];

function card(job) {
  const left = el("div");
  const h2 = el("h2");
  const a = el("a", "", job.title);
  a.href = `/jobs/${job.id}/`; // id is a number from our own API
  h2.append(a);
  const bits = [job.category?.name, `Posted ${timeAgo(job.created_at)}`, job.client_name].filter(Boolean);
  const text = job.description.length > 220 ? job.description.slice(0, 220) + "…" : job.description;
  left.append(h2, el("div", "meta", bits.join(" · ")), el("p", "desc", text), skillChips(job.skills));

  const b = budgetLabel(job);
  const side = el("div", "job-side");
  side.append(el("div", "price", b.price), el("small", "", b.kind),
              el("small", "", `${job.proposal_count} proposal${job.proposal_count === 1 ? "" : "s"}`));

  const article = el("article", "job-card");
  article.append(left, side);
  return article;
}

function pageUrl(n) {
  const p = new URLSearchParams(params);
  p.set("page", n);
  return "/jobs/?" + p.toString();
}

function renderPager(count, current) {
  pager.replaceChildren();
  const pages = Math.ceil(count / PAGE_SIZE);
  if (pages <= 1) return;
  const link = (label, n, off) => {
    if (off) return el("span", "off", label);
    const a = el("a", n === current ? "current" : "", label);
    a.href = pageUrl(n);
    if (n === current) a.setAttribute("aria-current", "page");
    return a;
  };
  pager.append(link("Previous", current - 1, current <= 1));
  for (let n = Math.max(1, current - 2); n <= Math.min(pages, current + 2); n++) pager.append(link(String(n), n));
  pager.append(link("Next", current + 1, current >= pages));
}

async function load() {
  statusEl.textContent = "Loading jobs…";
  const qs = new URLSearchParams();
  [...FILTERS, "page"].forEach((k) => params.get(k) && qs.set(k, params.get(k)));
  try {
    const data = await api("/jobs/?" + qs.toString());
    list.replaceChildren(...data.results.map(card));
    statusEl.textContent = data.count === 0
      ? "No jobs match your search. Try fewer filters."
      : `${data.count} job${data.count === 1 ? "" : "s"} found`;
    renderPager(data.count, Number(params.get("page") || 1));
  } catch (err) {
    list.replaceChildren();
    pager.replaceChildren();
    statusEl.textContent = err.status === 404 ? "That page doesn't exist. Go back to page 1."
      : err.status === 400 ? "Please check your filter values."
      : "Could not load jobs. Please try again.";
  }
}

async function init() {
  try {
    const cats = await api("/categories/");
    cats.forEach((c) => {
      const o = el("option", "", c.name);
      o.value = c.slug;
      form.elements.category.append(o);
    });
  } catch { /* the feed still works without the category list */ }
  FILTERS.forEach((k) => { form.elements[k].value = params.get(k) || ""; });
  load();
}

init();