import { api, ensureCsrf, getMe } from "../api.js";
import { el } from "../format.js";
import { setBusy, showErrors } from "../forms.js";

const gate = document.getElementById("gate");
const box = document.getElementById("profile-box");
const form = document.getElementById("profile-form");
const saved = document.getElementById("saved");

const me = await getMe();
if (!me) {
  location.replace("/login/");
} else if (me.role !== "client" && me.role !== "freelancer") {
  gate.textContent = "Administrators don't have a public profile.";
} else {
  const isFree = me.role === "freelancer";
  document.querySelectorAll(".freelancer-only").forEach((n) => (n.hidden = !isFree));

  try {
    const [profile, skills] = await Promise.all([api("/profile/"), isFree ? api("/skills/") : []]);
    form.elements.full_name.value = profile.full_name;
    form.elements.bio.value = profile.bio;
    if (isFree) {
      form.elements.hourly_rate.value = profile.hourly_rate ?? "";
      const mine = new Set(profile.skills.map((s) => s.id));
      const grid = document.getElementById("skill-list");
      skills.forEach((s) => {
        const label = el("label", "skill-opt");
        const cb = document.createElement("input");
        cb.type = "checkbox";
        cb.name = "skills";
        cb.value = s.id;
        cb.checked = mine.has(s.id);
        label.append(cb, " " + s.name);
        grid.append(label);
      });
    }
    gate.remove();
    box.hidden = false;
  } catch {
    gate.textContent = "Could not load your profile. Please try again.";
  }

  form.addEventListener("submit", async (e) => {
    e.preventDefault();
    saved.textContent = "";
    setBusy(form, true);
    const f = form.elements;
    try {
      await ensureCsrf();
      const body = { full_name: f.full_name.value.trim(), bio: f.bio.value.trim() };
      if (isFree) {
        body.hourly_rate = f.hourly_rate.value || null;
        body.skill_ids = [...form.querySelectorAll('input[name="skills"]:checked')].map((c) => Number(c.value));
      }
      await api("/profile/", { method: "PATCH", body });
            form.querySelectorAll(".field-error").forEach((n) => n.remove());
            document.getElementById("form-error").textContent = "";
      saved.textContent = "Profile saved.";
    } catch (err) {
      showErrors(form, err);
    }
    setBusy(form, false);
  });
}