"use strict";
// JobOps SPA — renders artifacts, drives the CLI via the backend. No external calls.

const SCREENS = [
  ["new", "1 · New"], ["match", "2 · Match"], ["resume", "3 · Resume"],
  ["approve", "4 · Approve & Export"], ["prep", "5 · Prep"], ["tracker", "6 · Tracker"],
];
const state = { slug: null, screen: "new", summary: null, apps: [] };
const $ = (id) => document.getElementById(id);
const el = (h) => { const t = document.createElement("template"); t.innerHTML = h.trim(); return t.content.firstChild; };
const esc = (s) => (s == null ? "" : String(s).replace(/[&<>]/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;" }[c])));

async function api(method, path, body) {
  const opt = { method, headers: { "Content-Type": "application/json" } };
  if (body) opt.body = JSON.stringify(body);
  const r = await fetch(path, opt);
  const j = await r.json().catch(() => ({}));
  if (!r.ok) {                                          // normalize every error envelope into {ok:false,error}
    j.ok = false;                                       // FastAPI raises {"detail": ...} with no `ok` field,
    const d = j.detail;                                 // so without this report() saw no failure and
    j.error = j.error ||                                // swallowed 400/404s as silent "success" toasts.
      (typeof d === "string" ? d
        : Array.isArray(d) ? d.map((e) => e.msg || JSON.stringify(e)).join("; ")
        : `HTTP ${r.status}`);
  }
  return j;
}
async function text(path) { const r = await fetch(path); return r.ok ? r.text() : ""; }

function toast(msg, kind) {
  const t = el(`<div class="toast ${kind || ""}">${esc(msg)}</div>`);
  document.body.appendChild(t);
  setTimeout(() => t.remove(), 4200);
}
function report(res, okMsg) {
  if (res.ok === false) { toast(res.error || "failed", "err"); return false; }
  if (res.exit_code && res.exit_code !== 0) {
    toast((res.messages && res.messages.slice(-1)[0]) || `exit ${res.exit_code}`, "warn"); return true;
  }
  if (okMsg) toast(okMsg, "ok");
  return true;
}

async function refreshApps() {
  const r = await api("GET", "/api/track");
  state.apps = r.rows || [];
  const pick = $("appPicker");
  pick.innerHTML = `<option value="">— select application —</option>` +
    state.apps.map((a) => `<option value="${esc(a.id)}"${a.id === state.slug ? " selected" : ""}>${esc(a.id)} (${esc(a.status)})</option>`).join("");
}
async function loadApp(slug) {
  state.slug = slug || null;
  state.summary = slug ? (await api("GET", `/api/app/${slug}`)).summary : null;
}

// --------------------------------------------------------------------------- screens
const screens = {};

screens.new = () => {
  const box = el(`<div>
    <div class="panel"><h2>New application</h2>
      <div class="row">
        <div><label>Slug (private, kebab-case)</label><input type="text" id="f-slug" placeholder="tesla-adas-validation-2026-07"></div>
        <div><label>Company</label><input type="text" id="f-company" placeholder="Tesla"></div>
        <div><label>Positioning track</label><input type="text" id="f-pos" placeholder="adas-av-validation"></div>
      </div>
      <label>Paste the job description</label><textarea id="f-jd" placeholder="Paste the full JD here…"></textarea>
      <div style="margin-top:12px"><button class="act" id="f-create">Create + parse JD</button></div>
    </div>
    <div id="g1"></div>
  </div>`);
  box.querySelector("#f-create").onclick = async () => {
    const slug = $("f-slug").value.trim();
    if (!/^[a-z0-9][a-z0-9._-]{0,80}$/.test(slug)) {     // mirror server SLUG_RE — guide instead of a silent 400
      toast("Slug must be kebab-case: lowercase letters, digits and - . _ (e.g. tesla-adas-validation-2026-07)", "err");
      return;
    }
    const res = await api("POST", "/api/new", {
      slug, company: $("f-company").value.trim(), positioning: $("f-pos").value.trim(), jd_text: $("f-jd").value,
    });
    if (!report(res, null)) return;                      // `new` itself failed
    const jp = res.jd_parse;                             // the parse sub-step may have failed independently
    if (jp && (jp.ok === false || (jp.exit_code && jp.exit_code !== 0))) {
      toast((jp.messages && jp.messages.slice(-1)[0]) || jp.error || "created, but JD parse failed", "warn");
    } else {
      toast(jp ? "Application created + JD parsed" : "Application created", "ok");
    }
    await refreshApps(); await loadApp(slug); renderG1(box.querySelector("#g1"));
  };
  if (state.slug) renderG1(box.querySelector("#g1"));
  return box;
};

async function renderG1(mount) {
  if (!state.slug) return;
  const parsed = await text(`/api/artifact/${state.slug}/jd.parsed.yaml`);
  if (!parsed) {
    mount.innerHTML = "";
    mount.appendChild(el(`<div class="panel"><h2>Gate G1 · parse the JD</h2>
      <p class="muted">No <code class="cmd">jd.parsed.yaml</code> yet. Run the LLM parse to produce it, then confirm the keyword/quote pairs.</p>
      <div style="margin-top:10px"><button class="act" id="g1-parse">Run parse with Claude</button>
        <span class="muted" style="margin-left:10px">headless on → runs here; headless off → shows the <code class="cmd">/jd-parse ${esc(state.slug)}</code> command to run in Claude Code</span></div></div>`));
    const pb = mount.querySelector("#g1-parse");
    pb.onclick = async () => {
      const label = pb.textContent; pb.disabled = true; pb.textContent = "Running parse…";
      const r = await api("POST", "/api/llm/jd-parse", { slug: state.slug });
      llmToast(r);
      pb.disabled = false; pb.textContent = label;
      await loadApp(state.slug); renderG1(mount);      // if the parse produced jd.parsed.yaml, flip to the confirm panel
    };
    return;
  }
  const confirmed = state.summary?.jd?.confirmed;
  mount.innerHTML = "";
  mount.appendChild(el(`<div class="panel"><h2>Gate G1 · confirm the parse ${confirmed ? '<span class="pill ok">confirmed</span>' : ""}</h2>
    <p class="muted">Each keyword shows its verbatim JD quote. Review, then confirm.</p>
    <pre class="art">${esc(parsed)}</pre>
    <div style="margin-top:10px"><button class="act" id="g1-confirm"${confirmed ? " disabled" : ""}>Confirm parse (G1)</button></div></div>`));
  const b = mount.querySelector("#g1-confirm");
  if (b) b.onclick = async () => { const r = await api("POST", "/api/jd/confirm", { slug: state.slug }); if (report(r, "Parse confirmed → status parsed")) { await refreshApps(); await loadApp(state.slug); render(); } };
}

screens.match = () => {
  const box = el(`<div>
    <div class="panel"><h2>Match — classify JD keywords vs the registry</h2>
      <div class="row"><button class="act" id="m-run">Run match</button>
        <button class="act sec" id="m-llm">Classify with Claude (/jd-match)</button></div>
    </div><div id="m-body"></div></div>`);
  box.querySelector("#m-run").onclick = async () => { const r = await api("POST", "/api/match", { slug: state.slug }); if (report(r, "Matched")) { await loadApp(state.slug); fill(); } };
  box.querySelector("#m-llm").onclick = async () => { const r = await api("POST", "/api/llm/jd-match", { slug: state.slug }); llmToast(r); };
  const fill = async () => {
    const m = box.querySelector("#m-body");
    if (!state.slug) { m.innerHTML = `<p class="muted">Select an application.</p>`; return; }
    const match = await text(`/api/artifact/${state.slug}/match.yaml`);
    const gap = await text(`/api/artifact/${state.slug}/gap_report.md`);
    const plan = await text(`/api/artifact/${state.slug}/portfolio_plan.md`);
    const sup = state.summary?.match?.support || {};
    const conf = state.summary?.match?.confirmed;
    m.innerHTML = "";
    if (match) m.appendChild(el(`<div class="panel"><h2>Gate G2 · confirm classifications ${conf ? '<span class="pill ok">confirmed</span>' : ""}</h2>
      <p class="muted">support: ${Object.entries(sup).map(([k, v]) => `${esc(k)}:${v}`).join("  ")}</p>
      <pre class="art">${esc(match)}</pre>
      <div style="margin-top:10px"><button class="act" id="m-confirm"${conf ? " disabled" : ""}>Confirm match (G2)</button></div></div>`));
    if (gap) m.appendChild(el(`<div class="panel"><h2>Gap report + pre-resume verdict</h2><pre class="art">${esc(gap)}</pre></div>`));
    if (plan) m.appendChild(el(`<div class="panel"><h2>Portfolio emphasis plan</h2><pre class="art">${esc(plan)}</pre></div>`));
    const cb = m.querySelector("#m-confirm");
    if (cb) cb.onclick = async () => { const r = await api("POST", "/api/match/confirm", { slug: state.slug }); if (report(r, "Match confirmed → status matched")) { await refreshApps(); await loadApp(state.slug); fill(); } };
  };
  fill();
  return box;
};

screens.resume = () => {
  const box = el(`<div>
    <div class="panel"><h2>Resume draft</h2>
      <div class="row"><button class="act sec" id="r-llm">Draft with Claude (/resume-plan)</button>
        <button class="act sec" id="r-save">Save &amp; validate resume.yaml</button>
        <button class="act" id="r-render">Render + gate</button></div>
      <label>resume.yaml</label><textarea id="r-yaml" style="min-height:280px"></textarea>
    </div>
    <div id="r-gate"></div>
    <div class="panel"><h2>Live preview — resume_ats.html</h2><iframe class="preview" id="r-prev"></iframe></div>
  </div>`);
  const load = async () => {
    box.querySelector("#r-yaml").value = state.slug ? await text(`/api/artifact/${state.slug}/resume.yaml`) : "";
    box.querySelector("#r-prev").src = state.slug ? `/api/artifact/${state.slug}/out/resume_ats.html` : "about:blank";
    renderGate(box.querySelector("#r-gate"));
  };
  box.querySelector("#r-llm").onclick = async () => { llmToast(await api("POST", "/api/llm/resume-plan", { slug: state.slug })); };
  box.querySelector("#r-save").onclick = async () => { const r = await api("POST", "/api/resume", { slug: state.slug, yaml_text: box.querySelector("#r-yaml").value }); report(r, "Saved + validated"); await loadApp(state.slug); };
  box.querySelector("#r-render").onclick = async () => { const r = await api("POST", "/api/render", { slug: state.slug }); report(r, "Rendered + gated"); await loadApp(state.slug); await refreshApps(); load(); };
  load();
  return box;
};

function renderGate(mount) {
  const g = state.summary?.gate_report;
  if (!g) { mount.innerHTML = `<div class="panel muted">No gate report yet — render the resume.</div>`; return; }
  const list = (arr) => (arr && arr.length ? arr.map((x) => `<span class="pill">${esc(x)}</span>`).join(" ") : '<span class="muted">none</span>');
  mount.innerHTML = "";
  mount.appendChild(el(`<div class="panel"><h2>ATS gate</h2>
    <div class="gate-grid">
      <div class="stat"><div class="n v-${esc(g.verdict)}">${esc(g.verdict || "—")}</div><div class="l">verdict</div></div>
      <div class="stat"><div class="n">${esc(g.must_have_coverage || "—")}</div><div class="l">must-have coverage</div></div>
      <div class="stat"><div class="n">${esc(g.confidence || "—")}</div><div class="l">confidence tier</div></div>
    </div>
    <p class="muted" style="margin-top:8px">recommendation: <b>${esc(g.recommendation || "—")}</b> · errors: ${g.error_count ?? 0}
      <span title="No probability is shown until a calibration module is trained on recorded outcomes.">· (no probability — by design)</span></p>
    <label>missing terms</label><div>${list(g.missing_terms)}</div>
    <label>risky for review</label><div>${list(g.risky_for_review)}</div></div>`));
}

screens.approve = () => {
  const box = el(`<div>
    <div id="a-checklist"></div>
    <div class="panel"><h2>Approve &amp; export</h2>
      <div class="row">
        <button class="act" id="a-approve">Approve gated package (G3)</button>
        <button class="act sec" id="a-pdf">Run pdfcheck</button>
      </div>
      <p class="steps" style="margin-top:10px">Export the resume to <code class="cmd">out/resume_final.pdf</code> with the browser's <b>Save as PDF</b> (never “Print to PDF”), then pdfcheck.</p>
      <div class="check"><input type="checkbox" id="a-ack"><label for="a-ack" style="margin:0">acknowledge HIGH_RISK (only if the gate is HIGH_RISK)</label></div>
      <div style="margin-top:8px"><button class="act" id="a-submit">Submit (G4 hard gate)</button></div>
    </div></div>`);
  (async () => {
    const cl = await text(`/api/artifact/${state.slug}/checklist.md`);
    box.querySelector("#a-checklist").innerHTML = cl
      ? `<div class="panel"><h2>Checklist</h2><pre class="art">${esc(cl)}</pre></div>` : "";
  })();
  box.querySelector("#a-approve").onclick = async () => { const r = await api("POST", "/api/status", { slug: state.slug, status: "approved" }); if (report(r, "Approved (G3)")) { await refreshApps(); await loadApp(state.slug); } };
  box.querySelector("#a-pdf").onclick = async () => { const r = await api("POST", "/api/pdfcheck", { slug: state.slug }); report(r, "pdfcheck passed"); };
  box.querySelector("#a-submit").onclick = async () => {
    const r = await api("POST", "/api/status", { slug: state.slug, status: "submitted", acknowledge_risk: box.querySelector("#a-ack").checked });
    if (r.ok === false) { toast(r.error, "err"); } else { report(r, "Submitted (G4)"); await refreshApps(); await loadApp(state.slug); }
  };
  return box;
};

screens.prep = () => {
  const box = el(`<div>
    <div class="panel"><h2>Interview pack</h2>
      <div class="row"><button class="act sec" id="p-illm">Write with Claude (/interview-pack)</button>
        <button class="act" id="p-ival">Validate + render</button></div>
      <div id="p-int"></div></div>
    <div class="panel"><h2>Coding pack</h2>
      <div class="row"><button class="act sec" id="p-cllm">Write with Claude (/coding-pack)</button>
        <button class="act" id="p-cval">Validate + render</button></div>
      <div id="p-cod"></div></div></div>`);
  const show = async (rel, mount) => { const t = await text(`/api/artifact/${state.slug}/${rel}`); box.querySelector(mount).innerHTML = t ? `<pre class="art">${esc(t)}</pre>` : `<p class="muted">not built yet</p>`; };
  box.querySelector("#p-illm").onclick = async () => llmToast(await api("POST", "/api/llm/interview-pack", { slug: state.slug }));
  box.querySelector("#p-cllm").onclick = async () => llmToast(await api("POST", "/api/llm/coding-pack", { slug: state.slug }));
  box.querySelector("#p-ival").onclick = async () => { report(await api("POST", "/api/pack/interview", { slug: state.slug }), "Interview pack valid"); show("prep/interview_pack.md", "#p-int"); };
  box.querySelector("#p-cval").onclick = async () => { report(await api("POST", "/api/pack/coding", { slug: state.slug }), "Coding pack valid"); show("prep/coding_pack.md", "#p-cod"); };
  show("prep/interview_pack.md", "#p-int"); show("prep/coding_pack.md", "#p-cod");
  return box;
};

screens.tracker = () => {
  const box = el(`<div>
    <div class="panel"><h2>Applications</h2><table><thead><tr><th>id</th><th>company</th><th>status</th><th>gate</th><th>outcome</th></tr></thead><tbody id="t-rows"></tbody></table></div>
    <div id="t-detail"></div>
    <div class="panel"><h2>Learning</h2><button class="act sec" id="t-lessons">lessons compile</button> <span class="muted">→ anonymized ledger draft from closed apps</span></div>
  </div>`);
  const tb = box.querySelector("#t-rows");
  tb.innerHTML = state.apps.map((a) => `<tr class="clickable" data-s="${esc(a.id)}"><td>${esc(a.id)}</td><td>${esc(a.company)}</td><td>${esc(a.status)}</td><td class="v-${esc(a.verdict)}">${esc(a.verdict || "")}</td><td>${esc(a.outcome || "")}</td></tr>`).join("");
  tb.querySelectorAll("tr").forEach((tr) => tr.onclick = async () => { await loadApp(tr.dataset.s); await refreshApps(); renderDetail(box.querySelector("#t-detail")); $("appPicker").value = tr.dataset.s; });
  box.querySelector("#t-lessons").onclick = async () => { const r = await api("POST", "/api/lessons/compile", {}); report(r, "Ledger draft written"); };
  if (state.slug) renderDetail(box.querySelector("#t-detail"));
  return box;
};

function renderDetail(mount) {
  const s = state.summary || {};
  mount.innerHTML = "";
  const statuses = ["screen", "interview", "offer", "hired", "rejected", "ghosted", "withdrawn"];
  const d = el(`<div class="panel"><h2>${esc(state.slug)} <span class="pill">${esc(s.status || "?")}</span></h2>
    <div class="row">
      <div><label>advance status</label><select id="d-status">${statuses.map((x) => `<option>${x}</option>`).join("")}</select></div>
      <div><label>&nbsp;</label><button class="act sec" id="d-setstatus">set status</button></div>
    </div>
    <label>log an event</label><div class="row"><input type="text" id="d-note" placeholder="recruiter call…"><button class="act sec" id="d-log">log</button></div>
    <div style="margin-top:10px"><button class="act sec" id="d-rej">Diagnose outcome (/rejection)</button></div></div>`);
  d.querySelector("#d-setstatus").onclick = async () => { const r = await api("POST", "/api/status", { slug: state.slug, status: d.querySelector("#d-status").value }); if (r.ok === false) toast(r.error, "err"); else { report(r, "status set"); await refreshApps(); await loadApp(state.slug); renderDetail(mount); } };
  d.querySelector("#d-log").onclick = async () => { report(await api("POST", "/api/log", { slug: state.slug, note: d.querySelector("#d-note").value }), "event logged"); };
  d.querySelector("#d-rej").onclick = async () => llmToast(await api("POST", "/api/llm/rejection", { slug: state.slug }));
  mount.appendChild(d);
}

function llmToast(r) {
  if (r.ok === false) return toast(r.error, "err");
  if (r.mode === "manual") toast(`Run ${r.command} in Claude Code (headless off), then refresh.`, "");
  else toast(`Claude Code ran ${r.command} (exit ${r.exit_code}).`, r.exit_code ? "warn" : "ok");
}

// --------------------------------------------------------------------------- shell
function renderNav() {
  const nav = $("nav");
  nav.innerHTML = "";
  SCREENS.forEach(([id, label]) => {
    const b = el(`<button class="${id === state.screen ? "active" : ""}"${!state.slug && id !== "new" && id !== "tracker" ? " disabled" : ""}>${esc(label)}</button>`);
    b.onclick = () => { state.screen = id; render(); };
    nav.appendChild(b);
  });
}
function render() {
  renderNav();
  const v = $("view");
  v.innerHTML = "";
  v.appendChild((screens[state.screen] || screens.new)());
}

$("appPicker").onchange = async (e) => {
  await loadApp(e.target.value);
  // clearing the selection must not leave a gated screen's actions live with a null slug
  if (!state.slug && state.screen !== "new" && state.screen !== "tracker") state.screen = "new";
  render();
};

(async function init() {
  await refreshApps();
  render();
})();
