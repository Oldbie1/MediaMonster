const $ = (sel, el = document) => el.querySelector(sel);
const $$ = (sel, el = document) => [...el.querySelectorAll(sel)];

let currentProjectId = null;
let machines = [];
let editingProfile = null;

async function api(path, opts = {}) {
  const res = await fetch(path, opts);
  const text = await res.text();
  let data;
  try { data = text ? JSON.parse(text) : null; } catch { data = { detail: text }; }
  if (!res.ok) {
    const d = data && data.detail;
    throw new Error(typeof d === "string" ? d : (d && d[0] && d[0].msg) || res.statusText);
  }
  return data;
}

function badge(m) {
  return `<span class="badge ${m.status}">${m.name}: ${m.label}</span>`;
}

function cometBadge(line) {
  const cls = line.comet_followup ? "comet" : "onbekend";
  return `<span class="badge ${cls}">${line.comet_label}</span>`;
}

function showMsg(text, ok) {
  const el = $("#import-msg");
  el.hidden = false;
  el.className = "msg " + (ok ? "ok" : "err");
  el.textContent = text;
}

function switchTab(name) {
  $$(".tab").forEach((b) => b.classList.toggle("on", b.dataset.tab === name));
  $("#view-projecten").hidden = name !== "projecten";
  $("#view-catalogus").hidden = name !== "catalogus";
  if (name === "catalogus") loadCatalog();
}

$$(".tab").forEach((b) => b.addEventListener("click", () => switchTab(b.dataset.tab)));

const drop = $("#drop");
const fileInput = $("#pdf-file");
["dragenter", "dragover"].forEach((ev) => {
  drop.addEventListener(ev, (e) => { e.preventDefault(); drop.classList.add("over"); });
});
["dragleave", "drop"].forEach((ev) => {
  drop.addEventListener(ev, (e) => { e.preventDefault(); drop.classList.remove("over"); });
});
drop.addEventListener("drop", (e) => {
  const f = e.dataTransfer.files[0];
  if (f) uploadPdf(f);
});
fileInput.addEventListener("change", () => {
  if (fileInput.files[0]) uploadPdf(fileInput.files[0]);
});

async function uploadPdf(file) {
  const fd = new FormData();
  fd.append("file", file, file.name);
  try {
    const project = await api("/api/import/pdf", { method: "POST", body: fd });
    showMsg(`Project ${project.number}: ${project.lines.length} regels geïmporteerd.`, true);
    currentProjectId = project.id;
    await loadProjects();
    renderProject(project);
  } catch (err) {
    showMsg(err.message, false);
  }
}

async function loadProjects() {
  const list = await api("/api/projects");
  const ul = $("#project-list");
  if (!list.length) {
    ul.innerHTML = "<li class='empty'>Nog geen projecten</li>";
    return;
  }
  ul.innerHTML = list.map((p) => `
    <li data-id="${p.id}" class="${p.id === currentProjectId ? "active" : ""}">
      <strong>${p.number}</strong>
      <small>${p.line_count} regels · ${p.aantal_sum} staven</small>
    </li>`).join("");
  $$("#project-list li[data-id]").forEach((li) => {
    li.addEventListener("click", () => openProject(Number(li.dataset.id)));
  });
}

async function openProject(id) {
  currentProjectId = id;
  const p = await api(`/api/projects/${id}`);
  $$("#project-list li").forEach((li) => li.classList.toggle("active", Number(li.dataset.id) === id));
  renderProject(p);
}

function renderProject(p) {
  const unknown = p.unknown_count
    ? `<p class="warn">${p.unknown_count} onbekende profielen — zet ze in de catalogus.</p>`
    : "";
  const rows = p.lines.map((ln) => `
    <tr>
      <td><strong>${ln.profile_number}</strong>${ln.known ? "" : " <span class='warn'>onbekend</span>"}</td>
      <td><input class="qty" type="number" min="0" value="${ln.aantal}" data-line="${ln.id}"></td>
      <td>${ln.machines.map(badge).join(" ")}</td>
      <td>${cometBadge(ln)}</td>
      <td><button data-del="${ln.id}">Verwijder</button></td>
    </tr>`).join("");
  $("#project-detail").innerHTML = `
    <h2>Project ${p.number}</h2>
    <p class="hint">Bron: ${p.source_filename || "handmatig"}</p>
    ${unknown}
    <table>
      <thead>
        <tr><th>Profiel</th><th>Aantal</th><th>Zagen</th><th>Comet</th><th></th></tr>
      </thead>
      <tbody>${rows || "<tr><td colspan='5'>Geen regels</td></tr>"}</tbody>
    </table>
    <div class="add-row">
      <input id="add-profiel" placeholder="Profielnummer" list="cat-numbers">
      <input id="add-aantal" class="qty" type="number" min="0" value="1">
      <button class="primary" id="add-line">Regel toevoegen</button>
    </div>
    <datalist id="cat-numbers"></datalist>
  `;
  $$(".qty[data-line]").forEach((inp) => {
    inp.addEventListener("change", async () => {
      const project = await api(`/api/lines/${inp.dataset.line}`, {
        method: "PATCH",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ aantal: Number(inp.value) }),
      });
      renderProject(project);
      loadProjects();
    });
  });
  $$("button[data-del]").forEach((btn) => {
    btn.addEventListener("click", async () => {
      const project = await api(`/api/lines/${btn.dataset.del}`, { method: "DELETE" });
      renderProject(project);
      loadProjects();
    });
  });
  $("#add-line").addEventListener("click", async () => {
    const profile_number = $("#add-profiel").value;
    const aantal = Number($("#add-aantal").value);
    try {
      const project = await api(`/api/projects/${p.id}/lines`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ profile_number, aantal }),
      });
      renderProject(project);
      loadProjects();
    } catch (err) {
      showMsg(err.message, false);
    }
  });
  fillDatalist();
}

async function fillDatalist() {
  const profiles = await api("/api/profiles");
  const dl = $("#cat-numbers");
  if (dl) dl.innerHTML = profiles.map((p) => `<option value="${p.number}">`).join("");
}

async function loadCatalog() {
  const q = $("#cat-q").value;
  const profiles = await api("/api/profiles" + (q ? `?q=${encodeURIComponent(q)}` : ""));
  const zaag = machines.filter((m) => m.kind === "zaag");
  const head = ["Nummer", ...zaag.map((m) => m.name), "Comet", ""].map((h) => `<th>${h}</th>`).join("");
  const body = profiles.map((p) => {
    const cells = zaag.map((m) => {
      const hit = p.machines.find((x) => x.code === m.code);
      return `<td>${hit ? badge(hit) : ""}</td>`;
    }).join("");
    return `<tr>
      <td><strong>${p.number}</strong>${p.notes ? `<div class="hint">${escapeHtml(p.notes).slice(0, 80)}</div>` : ""}</td>
      ${cells}
      <td>${cometBadge(p)}</td>
      <td><button data-edit="${p.id}">Bewerken</button></td>
    </tr>`;
  }).join("");
  $("#cat-table").innerHTML = `
    <table>
      <thead><tr>${head}</tr></thead>
      <tbody>${body || "<tr><td>Geen profielen</td></tr>"}</tbody>
    </table>`;
  $$("button[data-edit]").forEach((b) => {
    b.addEventListener("click", () => {
      const p = profiles.find((x) => x.id === Number(b.dataset.edit));
      openProfileDialog(p);
    });
  });
}

function escapeHtml(s) {
  return String(s).replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
}

function openProfileDialog(profile) {
  editingProfile = profile || null;
  $("#dlg-title").textContent = profile ? `Profiel ${profile.number}` : "Nieuw profiel";
  const form = $("#profile-form");
  form.number.value = profile ? profile.number : "";
  form.notes.value = profile ? profile.notes : "";
  form.comet_followup.value = (profile && profile.comet_followup) || "";
  const zaag = machines.filter((m) => m.kind === "zaag");
  $("#dlg-flags").innerHTML = zaag.map((m) => {
    const f = (profile && profile.machine_flags && profile.machine_flags[m.code]) || {};
    return `<div class="flagbox"><strong>${m.name}</strong>
      <label><input type="checkbox" name="beperkt-${m.code}" ${f.beperkt ? "checked" : ""}> Beperkt</label>
      <label><input type="checkbox" name="niet-${m.code}" ${f.niet ? "checked" : ""}> Niet</label>
    </div>`;
  }).join("");
  $("#dlg").showModal();
}

$("#dlg-cancel").addEventListener("click", () => $("#dlg").close());
$("#profile-form").addEventListener("submit", async (e) => {
  e.preventDefault();
  const form = e.target;
  const flags = {};
  machines.filter((m) => m.kind === "zaag").forEach((m) => {
    flags[m.code] = {
      beperkt: form[`beperkt-${m.code}`].checked,
      niet: form[`niet-${m.code}`].checked,
    };
  });
  const body = {
    number: form.number.value,
    notes: form.notes.value,
    comet_followup: form.comet_followup.value || null,
    machines: flags,
  };
  try {
    await api("/api/profiles", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body),
    });
    $("#dlg").close();
    loadCatalog();
  } catch (err) {
    alert(err.message);
  }
});

$("#btn-new-profile").addEventListener("click", () => openProfileDialog(null));
let catTimer;
$("#cat-q").addEventListener("input", () => {
  clearTimeout(catTimer);
  catTimer = setTimeout(loadCatalog, 200);
});

(async function init() {
  machines = await api("/api/machines");
  await loadProjects();
})();
