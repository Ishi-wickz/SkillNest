// Small DOM helper: element with class and text (text is never parsed as HTML)
export function el(tag, className, text) {
  const node = document.createElement(tag);
  if (className) node.className = className;
  if (text !== undefined) node.textContent = text;
  return node;
}

export function money(amount, currency) {
  try {
    return new Intl.NumberFormat("en-US", { style: "currency", currency, maximumFractionDigits: 0 })
      .format(Number(amount));
  } catch {
    return `${amount} ${currency}`;
  }
}

export function budgetLabel(job) {
  const price = money(job.budget_amount, job.currency);
  return job.budget_type === "hourly" ? { price: price + "/hr", kind: "Hourly" }
                                      : { price, kind: "Fixed price" };
}

export function timeAgo(iso) {
  const s = Math.max(0, (Date.now() - new Date(iso).getTime()) / 1000);
  for (const [name, secs] of [["day", 86400], ["hour", 3600], ["minute", 60]]) {
    const n = Math.floor(s / secs);
    if (n >= 1) return `${n} ${name}${n > 1 ? "s" : ""} ago`;
  }
  return "just now";
}

export function skillChips(skills) {
  const wrap = el("div", "chips");
  skills.forEach((s) => wrap.append(el("span", "chip-skill", s.name)));
  return wrap;
}