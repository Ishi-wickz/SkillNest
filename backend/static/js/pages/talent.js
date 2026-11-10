import { api } from "../api.js";
import { el, money, skillChips } from "../format.js";

const PAGE_SIZE = 12; // matches PAGE_SIZE in settings.py
const params = new URLSearchParams(location.search);
const form = document.getElementById("filters");
const list = document.getElementById("talent-list");
const statusEl = document.getElementById("status");
const pager = document.getElementById("pager");
const FILTERS = ["q", "skill", "min", "max"];

function initials(name) {
  return (name || "?").split(/\s+/).slice(0, 2).map((w) => w[0]).join("").toUpperCase();
}

function card(t) {
  const left = el("div", "talent-main");
  left.append(el("div", "avatar-lg", initials(t.full_name)));

  const body = el("div");
  const h2 = el("h2");
  const a = el("a", "", t.full_name);
  a.href = `/talent/${t.id}/`;
  h2.append(a);
  const bio = t.bio.length > 180 ? t.bio.slice(0, 180) + "…" : t.bio;
  body.append(h2, el("p", "desc", bio || "No bio yet."), skillChips(t.skills));
  left.append(body);

  const side = el("div", "job-side");
  side.append(
    el("div", "price", t.hourly_rate ? money(t.hourly_rate, "USD") + "/hr" : "Rate not set"),
    el("small", "", t.avg_rating ? `★ ${t.avg_rating} (${t.review_count})` : "No reviews yet")
  );

  const article = el("article", "job-card");
  article.append(left, side);
  return article;
}

function pageUrl(n) {
  const p = new URLSearchParams(params);
  p.set("page", n);
  return "/talent/?" + p.toString();
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
  statusEl.textContent = "Loading…";
  const qs = new URLSearchParams();
  [...FILTERS, "page"].forEach((k) => params.get(k) && qs.set(k, params.get(k)));
  try {
    const data = await api("/talent/?" + qs.toString());
    list.replaceChildren(...data.results.map(card));
    statusEl.textContent = data.count === 0
      ? "No freelancers match your search. Try fewer filters."
      : `${data.count} freelancer${data.count === 1 ? "" : "s"} found`;
    renderPager(data.count, Number(params.get("page") || 1));
  } catch (err) {
    list.replaceChildren();
    pager.replaceChildren();
    statusEl.textContent = err.status === 404 ? "That page doesn't exist. Go back to page 1."
      : err.status === 400 ? "Please check your filter values."
      : "Could not load freelancers. Please try again.";
  }
}

async function init() {
  try {
    const skills = await api("/skills/");
    skills.forEach((s) => {
      const o = el("option", "", s.name);
      o.value = s.slug;
      form.elements.skill.append(o);
    });
  } catch { /* the list still works without the skill dropdown */ }
  FILTERS.forEach((k) => { form.elements[k].value = params.get(k) || ""; });
  load();
}

init();