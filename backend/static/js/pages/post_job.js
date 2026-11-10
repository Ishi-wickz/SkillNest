import { api, ensureCsrf, getMe } from "../api.js";
import { el } from "../format.js";
import { setBusy, showErrors } from "../forms.js";

const gate = document.getElementById("gate");
const box = document.getElementById("post-box");
const form = document.getElementById("job-form");

const me = await getMe();
if (!me) {
  location.replace("/login/");
} else if (me.role !== "client") {
  gate.textContent = "Only client accounts can post jobs.";
} else {
  box.hidden = false;

  // Fill the dropdown and skill checkboxes from the API
  const [cats, skills] = await Promise.all([api("/categories/"), api("/skills/")]);
  cats.forEach((c) => {
    const o = el("option", "", c.name);
    o.value = c.id;
    form.elements.category_id.append(o);
  });
  const grid = document.getElementById("skill-list");
  skills.forEach((s) => {
    const label = el("label", "skill-opt");
    const cb = document.createElement("input");
    cb.type = "checkbox";
    cb.name = "skills";   // not "skill_ids", so the error helper never treats it as a text field
    cb.value = s.id;
    label.append(cb, " " + s.name);
    grid.append(label);
  });

  form.addEventListener("submit", async (e) => {
    e.preventDefault();
    setBusy(form, true);
    const f = form.elements;
    try {
      await ensureCsrf();
      const job = await api("/jobs/", {
        method: "POST",
        body: {
          title: f.title.value.trim(),
          description: f.description.value.trim(),
          category_id: f.category_id.value || null,
          budget_type: f.budget_type.value,
          budget_amount: f.budget_amount.value,
          currency: f.currency.value,
          skill_ids: [...form.querySelectorAll('input[name="skills"]:checked')].map((c) => Number(c.value)),
        },
      });
      location.href = `/jobs/${job.id}/`;
    } catch (err) {
      showErrors(form, err);
      setBusy(form, false);
    }
  });
}