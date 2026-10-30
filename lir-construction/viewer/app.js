/* Lecture Planner viewer: renders a whole course LIR (lir/<course>/course.json + Lxx.json).
 *
 * Routes:  #/                      course home (roadmap)
 *          #/L03/p/4               lecture L03, page 4
 *          #/L03/p/4/t/123.4       ... and seek the video to 123.4 s
 *
 * A lecture's LIR phases become pages: primer -> (watch, quiz, summary) per segment -> concept map -> questions.
 * Learner state (progress, highlights, answers, concept maps) is kept in localStorage per course.
 * Open answers and concept maps are scored by serve.py on the CPU; without it, a keyword-only scorer runs here.
 * Dev mode (toggle in the top bar) shows answers, intents, origin records and judge results.
 */
"use strict";

const S = { index: null, course: null, cid: null, lec: {}, order: [], cleanup: [] };

// append / replaceChildren accept nested arrays and skip null/false, like h() below
for (const m of ["append", "replaceChildren"]) {
  const orig = Element.prototype[m];
  Element.prototype[m] = function (...kids) {
    return orig.apply(this, kids.flat(Infinity).filter((k) => k != null && k !== false));
  };
}
const $ = (sel, root = document) => root.querySelector(sel);

// ------------------------------------------------------------------ helpers
function h(tag, attrs, ...kids) {
  const el = document.createElement(tag);
  for (const [k, v] of Object.entries(attrs || {})) {
    if (v == null || v === false) continue;
    if (k === "class") el.className = v;
    else if (k.startsWith("on")) el.addEventListener(k.slice(2), v);
    else if (k === "html") el.innerHTML = v;
    else el.setAttribute(k, v === true ? "" : v);
  }
  for (const k of kids.flat(Infinity)) if (k != null && k !== false) el.append(k.nodeType ? k : document.createTextNode(String(k)));
  return el;
}
const svgNS = "http://www.w3.org/2000/svg";
function s(tag, attrs, ...kids) {
  const el = document.createElementNS(svgNS, tag);
  for (const [k, v] of Object.entries(attrs || {})) if (v != null) el.setAttribute(k, v);
  for (const k of kids.flat(Infinity)) if (k != null) el.append(k.nodeType ? k : document.createTextNode(String(k)));
  return el;
}
function clock(t) {
  t = Math.max(0, Math.floor(t));
  const hh = Math.floor(t / 3600), m = Math.floor((t % 3600) / 60), sec = t % 60;
  return (hh ? hh + ":" + String(m).padStart(2, "0") : m) + ":" + String(sec).padStart(2, "0");
}
// Display names start with a capital letter; acronyms and words like "iPhone" are left alone.
function cap(name) {
  if (!name) return name;
  if (/^[a-z][A-Z]/.test(name)) return name;
  return name[0].toUpperCase() + name.slice(1);
}
// ------------------------------------------------------------------ math
// Generated text writes math as LaTeX between $…$. Sometimes JSON ate a backslash (the \t of \theta became a tab,
// the \f of \frac a form feed), so those are put back before KaTeX renders it. Labels inside SVG get plain text.
const CTRL = { "\t": "\\t", "\b": "\\b", "\f": "\\f", "\r": "\\r", "\n": "\\n", "\v": "\\v" };
const fixTex = (t) => t.replace(/[\t\b\f\r\n\v]/g, (c) => CTRL[c])
  .replace(/\\text\{([^}]*)\}/g, (m, x) => "\\text{" + x.replace(/(?<!\\)_/g, "\\_") + "}");  // blanks like \text{___}
const MATH_RE = /\$([^$]{1,300}?)\$/g;
const SYM = { alpha: "α", beta: "β", gamma: "γ", delta: "δ", epsilon: "ε", varepsilon: "ε", theta: "θ", lambda: "λ", mu: "μ",
  sigma: "σ", omega: "ω", pi: "π", phi: "φ", rho: "ρ", tau: "τ", eta: "η", nabla: "∇", partial: "∂", times: "×", cdot: "·",
  rightarrow: "→", to: "→", leftarrow: "←", Rightarrow: "⇒", leq: "≤", geq: "≥", neq: "≠", approx: "≈", infty: "∞",
  sum: "Σ", prod: "Π", in: "∈", Delta: "Δ", Sigma: "Σ", Omega: "Ω", Theta: "Θ", ldots: "…", cdots: "⋯" };
function plainMath(t) {
  return t.replace(MATH_RE, (m, inner) => fixTex(inner).replace(/\\(?:text|mathrm|mathbf)\{([^}]*)\}/g, "$1")
    .replace(/\\([a-zA-Z]+)/g, (x, c) => SYM[c] ?? c).replace(/[{}]/g, ""));
}
function mathFragment(t) {
  const parts = [];
  let last = 0;
  t.replace(MATH_RE, (m, inner, off) => {
    const tex = fixTex(inner);
    if (/^\s|\s$/.test(tex)) return m;  // "$5 and $10" is money, not math
    parts.push(t.slice(last, off), { tex }); last = off + m.length; return m;
  });
  if (!parts.length) {  // a short bare expression such as "n \times 1" (an answer option)
    const b = t.trim();
    if (!(b.length <= 60 && b.split(/\s+/).length <= 8 && /\\[a-zA-Z]{2,}|[\t\b\f\v][a-z]/.test(b))) return null;
    const at = t.indexOf(b);
    parts.push(t.slice(0, at), { tex: fixTex(b) }); last = at + b.length;
  }
  parts.push(t.slice(last));
  const frag = document.createDocumentFragment();
  parts.forEach((p) => {
    if (typeof p === "string") { if (p) frag.append(p); return; }
    const sp = document.createElement("span");
    try { katex.render(p.tex, sp, { throwOnError: false }); } catch { sp.textContent = p.tex; }
    frag.append(sp);
  });
  return frag;
}
// Render the math in every text node under root (new content is caught by the observer in boot).
function typeset(root) {
  if (typeof katex === "undefined" || !root) return;
  const w = document.createTreeWalker(root, NodeFilter.SHOW_TEXT, { acceptNode: (n) => {
    const p = n.parentElement;
    if (!p || p.closest(".katex, textarea, script, style, option, title")) return NodeFilter.FILTER_REJECT;
    return /\$|\\[a-zA-Z]|[\t\b\f\v]/.test(n.data) ? NodeFilter.FILTER_ACCEPT : NodeFilter.FILTER_REJECT;
  } });
  const todo = [];
  while (w.nextNode()) todo.push(w.currentNode);
  todo.forEach((n) => {
    if (n.parentElement.closest("svg")) { const t = plainMath(n.data); if (t !== n.data) n.data = t; return; }
    const f = mathFragment(n.data);
    if (f) n.replaceWith(f);
  });
}

function toast(msg) {
  document.querySelectorAll(".toast").forEach((t) => t.remove());
  const t = h("div", { class: "toast" }, msg);
  document.body.append(t);
  setTimeout(() => t.remove(), 2000);
}
const store = {
  key: (k) => `lir:${S.cid}:${k}`,
  get(k, d) { try { const v = localStorage.getItem(this.key(k)); return v == null ? d : JSON.parse(v); } catch { return d; } },
  set(k, v) { try { localStorage.setItem(this.key(k), JSON.stringify(v)); } catch { /* private mode */ } },
};
const prefs = {
  get(k, d) { try { const v = localStorage.getItem("lirpref:" + k); return v == null ? d : JSON.parse(v); } catch { return d; } },
  set(k, v) { try { localStorage.setItem("lirpref:" + k, JSON.stringify(v)); } catch { } },
};
const DEV = () => prefs.get("dev", false);
function onLeave(fn) { S.cleanup.push(fn); }
function cleanupPage() { S.cleanup.forEach((f) => { try { f(); } catch { } }); S.cleanup = []; }
function listen(target, ev, fn, opts) { target.addEventListener(ev, fn, opts); onLeave(() => target.removeEventListener(ev, fn, opts)); }

// ------------------------------------------------------------------ theme + dev toggle
// Dark (true black) is the default look; light is the learner's choice.
const theme = () => (prefs.get("theme", "dark") === "light" ? "light" : "dark");
function applyTheme() {
  if (theme() === "light") document.documentElement.setAttribute("data-theme", "light");
  else document.documentElement.removeAttribute("data-theme");
}
// Top-bar labels: the icon always shows, the word (class "long") folds away on a phone.
function themeButton() {
  const label = () => (theme() === "light" ? ["☾", h("span", { class: "long" }, " Dark")] : ["☀", h("span", { class: "long" }, " Light")]);
  const b = h("button", { class: "ghost theme-toggle", title: "Switch between dark and light", "aria-label": "Switch between dark and light" }, label());
  b.onclick = () => { prefs.set("theme", theme() === "light" ? "dark" : "light"); applyTheme(); b.replaceChildren(label()); };
  return b;
}
function devButton() {
  return h("button", { class: "toggle dev-toggle" + (DEV() ? " on" : ""), title: "Dev mode: show answers and how each item was generated",
    onclick: () => { prefs.set("dev", !DEV()); route(); } }, "Dev", h("span", { class: "long" }, DEV() ? " mode: on" : " mode"));
}

// ------------------------------------------------------------------ loading
async function getJSON(url) {
  const r = await fetch(url);
  if (!r.ok) throw new Error(`${url}: ${r.status}`);
  return r.json();
}
async function boot() {
  new MutationObserver((ms) => ms.forEach((m) => m.addedNodes.forEach((n) => typeset(n.nodeType === 1 ? n : n.parentElement))))
    .observe($("#app"), { childList: true, subtree: true });
  const q = new URLSearchParams(location.search);
  if (q.has("theme")) prefs.set("theme", q.get("theme") === "light" ? "light" : "dark");
  applyTheme();
  if (q.has("dev")) prefs.set("dev", q.get("dev") !== "0");
  try {
    S.index = await getJSON("/lir/index.json");
  } catch (e) {
    $("#app").replaceChildren(h("div", { class: "empty" }, "No LIR found. Run generate_lir.py first, then serve.py."));
    return;
  }
  if (!S.index.courses.length) return;
  const want = prefs.get("course", S.index.courses[0].course_id);
  await loadCourse((S.index.courses.find((c) => c.course_id === want) || S.index.courses[0]).course_id);
  window.addEventListener("hashchange", route);
  route();
}
async function loadCourse(cid) {
  const entry = S.index.courses.find((c) => c.course_id === cid);
  S.cid = cid; prefs.set("course", cid);
  $("#app").replaceChildren(h("div", { class: "empty" }, `Loading ${entry.title}…`));
  S.course = await getJSON(`/${entry.path}/course.json`);
  const lecs = await Promise.all(S.course.lecture_ids.map((id) => getJSON(`/${entry.path}/${id}.json`).catch(() => null)));
  S.lec = {}; S.order = [];
  lecs.filter(Boolean).forEach((l) => { S.lec[l.lecture_id] = l; S.order.push(l.lecture_id); });
  S.concepts = Object.fromEntries(S.course.concepts.map((c) => [c.id, c]));
}

// ------------------------------------------------------------------ pages of a lecture
const segOf = (L, sid) => L.segments.find((x) => x.id === sid);
function pages(L) {
  if (L._pages) return L._pages;
  const out = [];
  L.phases.forEach((ph) => {
    if (ph.type === "primer") out.push({ kind: "primer", ph });
    else if (ph.type === "segment") out.push({ kind: "watch", ph, seg: segOf(L, ph.segment_id) });
    else if (ph.type === "active") {
      const seg = segOf(L, ph.segment_id);
      if (ph.quiz && ph.quiz.items.length) out.push({ kind: "quiz", ph, seg });
      out.push({ kind: "summary", ph, seg });
    } else if (ph.type === "constructive") {
      out.push({ kind: "map", ph });
      if (ph.open_questions.length) out.push({ kind: "questions", ph });
    }
  });
  return (L._pages = out);
}
const PAGE_NAME = { primer: "Before you start", quiz: "Quiz", summary: "Summary", map: "Concept map", questions: "Questions" };
const pageName = (pg) => pg.kind === "watch" ? pg.ph.subgoal : PAGE_NAME[pg.kind];

function route() {
  cleanupPage();
  const p = location.hash.replace(/^#\/?/, "").split("/").filter(Boolean);
  if (p[0] === "map") return renderCourseMap();
  if (!p.length || !S.lec[p[0]]) return renderHome();
  const lid = p[0];
  const idx = p[1] === "p" ? Number(p[2]) : firstOpenPage(lid);
  const t = p[3] === "t" ? Number(p[4]) : null;
  S.openRef = p[3] === "ref";
  renderLecture(lid, Math.min(Math.max(0, idx || 0), pages(S.lec[lid]).length - 1), t);
}
function go(lid, idx, t) {
  const h2 = `#/${lid}/p/${idx}` + (t != null ? `/t/${t.toFixed(1)}` : "");
  if (location.hash === h2) route(); else location.hash = h2;
}
// Jump to the watch page whose clip contains time t.
function jump(lid, t) {
  const L = S.lec[lid];
  if (!L) return toast("That lecture is not in this build");
  const pg = pages(L);
  let i = pg.findIndex((x) => x.kind === "watch" && t >= x.ph.start - 0.01 && t < x.ph.end);
  if (i < 0) i = pg.findIndex((x) => x.kind === "watch");
  go(lid, i, t);
}
const timeLink = (lid, t, text) => h("button", { class: "ghost small jump", onclick: () => jump(lid, t), title: "Watch this part again" },
  "▶ ", text || ((lid !== S.curLid ? lectureName(lid) + ", " : "") + clock(t)));

// ------------------------------------------------------------------ progress
const doneSet = (lid) => new Set(store.get(`pdone:${lid}`, []));
function markDone(lid, idx) {
  const d = doneSet(lid);
  if (d.has(idx)) return;
  d.add(idx); store.set(`pdone:${lid}`, [...d]);
  const st = document.querySelector(`.step[data-i="${idx}"]`);
  if (st) st.classList.add("done");
  const b = $("#lecbar > div"); if (b) b.style.width = lectureProgress(lid) * 100 + "%";
}
function lectureProgress(lid) { return Math.min(1, doneSet(lid).size / pages(S.lec[lid]).length); }
function firstOpenPage(lid) {
  const d = doneSet(lid);
  const i = pages(S.lec[lid]).findIndex((_, k) => !d.has(k));
  return i < 0 ? 0 : i;
}
function courseResume() {
  for (const lid of S.order) if (lectureProgress(lid) < 1) return [lid, firstOpenPage(lid)];
  return [S.order[0], 0];
}

// ------------------------------------------------------------------ home
function renderHome() {
  document.title = S.course.title;
  S.curLid = null;
  const done = S.order.reduce((a, l) => a + lectureProgress(l), 0) / S.order.length;
  const [rl, rp] = courseResume();
  const started = done > 0;
  const courseSel = S.index.courses.length > 1
    ? h("select", { class: "lec-switch", onchange: async (e) => { await loadCourse(e.target.value); location.hash = "#/"; renderHome(); } },
      S.index.courses.map((c) => h("option", { value: c.course_id, selected: c.course_id === S.cid }, c.title)))
    : null;
  const top = h("div", { class: "topbar" }, h("span", { class: "brand" }, h("span", { class: "brand-mark" }), h("span", { class: "long" }, "Lecture Planner")),
    h("span", { class: "spacer" }), courseSel, devButton(), themeButton());
  const hours = S.order.reduce((a, l) => a + S.lec[l].duration_s, 0) / 3600;
  const parts = S.order.reduce((a, l) => a + S.lec[l].segments.length, 0);
  const stat = (v, label) => h("div", { class: "stat" }, h("b", {}, v), h("span", {}, label));
  const hero = h("section", { class: "hero" },
    h("div", {},
      h("div", { class: "kicker" }, started ? "Welcome back" : "Your course"),
      h("h1", {}, S.course.title),
      // build numbers are for the developer, not the learner
      DEV() ? h("div", { class: "stats" }, stat(S.order.length, "lectures"), stat(`${Math.round(hours)} h`, "of video"),
        stat(parts, "short parts"), stat(S.course.concepts.length, "concepts")) : null,
      h("div", { class: "row cta" },
        h("button", { class: "primary big", onclick: () => go(rl, rp) }, started ? "Continue" : "Start the course", h("span", { class: "arrow" }, "→")),
        h("span", { class: "small muted" }, started ? `Up next · ${lectureName(rl)} · ${S.lec[rl].title}` : `Begins with ${S.lec[S.order[0]].title}`))),
    h("div", { class: "hero-ring" }, ring(done, "complete")));
  const goals = S.course.course_goals.length ? h("div", { class: "card goals" },
    h("h3", {}, "What you will be able to do"),
    h("ol", {}, S.course.course_goals.map((g) => h("li", {}, h("span", {}, g.text.replace(/\s*\((L\d+(, )?)+\)\.?$/, ".")))))) : null;
  // long courses default to a compact grid; the learner can switch and the choice is remembered
  const path = h("div", {});
  const viewTabs = h("div", { class: "tabs view-tabs", role: "tablist" });
  const showPath = () => {
    const view = prefs.get("homeView", S.order.length > 30 ? "grid" : "list");
    viewTabs.replaceChildren(["list", "grid"].map((v) => h("button", { class: "tab" + (view === v ? " on" : ""), role: "tab",
      "aria-selected": String(view === v), onclick: () => { prefs.set("homeView", v); showPath(); } }, v === "list" ? "List" : "Grid")));
    path.replaceChildren(view === "grid" ? lectureGrid(rl) : h("div", { class: "roadmap" }, S.order.map((lid, i) => lectureCard(lid, i))));
  };
  showPath();
  $("#app").replaceChildren(top, h("div", { class: "wrap page-in" }, hero, goals,
    h("div", { class: "section-title" }, h("h2", {}, "Your path"), h("span", { class: "spacer" }), viewTabs), path,
    h("button", { class: "finale", onclick: () => { location.hash = "#/map"; } },
      h("span", { class: "finale-mark" }, "✦"),
      h("span", {}, h("span", { class: "kicker" }, "At the end"), h("b", {}, "Course map"),
        h("span", { class: "small muted" }, "Every lecture's concept map joined into one: see how the whole course fits together.")),
      h("span", { class: "arrow" }, "→"))));
}
// Compact view: one small tile per lecture in course order; chips show which lectures serve each course goal.
function lectureGrid(nextLid) {
  const goals = S.course.course_goals || [];
  const goalOf = {};
  goals.forEach((g, k) => g.lecture_ids.forEach((l) => { goalOf[l] = k; }));
  const note = h("p", { class: "small muted goal-note" });
  const tiles = S.order.map((lid, i) => {
    const L = S.lec[lid], p = lectureProgress(lid);
    return h("button", { class: "ltile" + (p >= 1 ? " done" : p > 0 ? " started" : "") + (lid === nextLid && p < 1 ? " next" : ""),
      style: `--i:${Math.min(i, 24)};--p:${Math.round(p * 100)}%`, "data-goal": goalOf[lid] ?? "", title: cap(L.roadmap.lecture_goal),
      onclick: () => go(lid, firstOpenPage(lid)) },
      h("span", { class: "n" }, String(i + 1).padStart(2, "0")), h("span", { class: "t" }, L.title), h("span", { class: "bar" }, h("i", {})));
  });
  let pick = null;
  const chips = h("div", { class: "goal-chips" });
  const drawChips = () => {
    chips.replaceChildren(h("span", { class: "small muted" }, "Course goal"),
      [null, ...goals.map((_, k) => k)].map((k) => h("button", { class: "chip" + (pick === k ? " on" : ""), title: k == null ? "" : goals[k].text,
        onclick: () => { pick = k; drawChips(); } }, k == null ? "All" : String(k + 1))));
    tiles.forEach((t) => t.classList.toggle("dim", pick != null && t.dataset.goal !== String(pick)));
    note.textContent = pick == null ? "" : goals[pick].text.replace(/\s*\((L\d+(, )?)+\)\.?$/, ".");
  };
  drawChips();
  return h("div", {}, goals.length > 1 ? chips : null, note, h("div", { class: "lec-grid" }, tiles));
}
function lectureName(lid) { return "Lecture " + String(S.order.indexOf(lid) + 1); }
function lectureCard(lid, i) {
  const L = S.lec[lid];
  const p = lectureProgress(lid);
  const d = doneSet(lid);
  const pg = pages(L);
  const body = h("div", { class: "lec-body", hidden: true },
    L.roadmap.objectives.map((o) => h("div", { class: "obj" },
      h("div", { class: "obj-title" }, o.text),
      o.segment_ids.map((sid) => {
        const pi = pg.findIndex((x) => x.kind === "watch" && x.ph.segment_id === sid);
        return h("div", { class: "seg-line" }, h("span", { class: "check" }, d.has(pi) ? "✓" : "·"),
          h("a", { href: `#/${lid}/p/${pi}` }, segOf(L, sid).subgoal));
      }))));
  const toggle = h("button", { class: "ghost small", onclick: (e) => {
    e.stopPropagation(); body.hidden = !body.hidden; toggle.textContent = body.hidden ? "Show parts ▾" : "Hide parts ▴";
  } }, "Show parts ▾");
  return h("div", { class: "card lec" + (p >= 1 ? " done" : p > 0 ? " started" : ""), style: `--i:${i}` },
    h("div", { class: "lec-head", onclick: () => go(lid, firstOpenPage(lid)), title: "Open this lecture" },
      h("div", { class: "lec-num" }, p >= 1 ? "✓" : String(i + 1).padStart(2, "0")),
      h("div", {}, h("div", { class: "lec-title" }, L.title), h("div", { class: "lec-goal" }, cap(L.roadmap.lecture_goal)),
        h("div", { class: "lec-sub" }, DEV() ? h("span", {}, `${Math.round(L.duration_s / 60)} min · ${L.segments.length} parts`) : null, toggle)),
      h("div", { class: "lec-meta" },
        h("button", { class: p > 0 && p < 1 ? "primary" : "", onclick: (e) => { e.stopPropagation(); go(lid, firstOpenPage(lid)); } },
          p >= 1 ? "Review ▸" : p > 0 ? `Continue · ${Math.round(p * 100)}% ▸` : "Open ▸"))),
    body);
}

// ------------------------------------------------------------------ lecture shell
const WIDE = new Set(["watch", "map"]);  // pages that use the whole screen (contents list folds away)
function renderLecture(lid, idx, t) {
  const L = S.lec[lid];
  S.curLid = lid;
  const pg = pages(L);
  const page = pg[idx];
  document.title = `${lectureName(lid)} · ${L.title}`;
  const d = doneSet(lid);
  const steps = [];
  let lastObj = null;
  pg.forEach((x, i) => {
    if (x.kind === "primer") steps.push(h("div", { class: "group" }, "Start"));
    const o = x.seg ? x.seg.objective_id : null;
    if (o && o !== lastObj) {
      const obj = L.roadmap.objectives.find((y) => y.id === o);
      steps.push(h("div", { class: "group", title: obj ? obj.text : "" }, `Objective ${o.slice(1)}`));
      lastObj = o;
    }
    if (x.kind === "map") steps.push(h("div", { class: "group" }, "Wrap-up"));
    steps.push(h("div", { class: "step" + (x.kind === "quiz" || x.kind === "summary" ? " sub" : "") + (i === idx ? " current" : "") + (d.has(i) ? " done" : ""),
      "data-i": i, tabindex: 0, onclick: () => go(lid, i) },
      h("span", { class: "ic" }, d.has(i) ? "✓" : ""),
      h("span", {}, x.kind === "watch" ? h("span", { class: "faint" }, "Watch · ") : null, pageName(x))));
  });
  const li = S.order.indexOf(lid);
  const wide = WIDE.has(page.kind);
  const sideOpen = prefs.get(wide ? "side-wide" : "side", !wide);
  const top = h("div", { class: "topbar" },
    h("button", { class: "ghost", title: "Contents", onclick: () => {
      const lec = $(".lecture"); const open = lec.classList.toggle("noside") === false;
      prefs.set(wide ? "side-wide" : "side", open);
    } }, "☰"),
    h("button", { class: "ghost", "aria-label": "Roadmap", title: "Back to the course roadmap", onclick: () => { location.hash = "#/"; } }, "←", h("span", { class: "long" }, " Roadmap")),
    h("select", { class: "lec-switch", title: "Go to another lecture",
      onchange: (e) => go(e.target.value, firstOpenPage(e.target.value)) },
      S.order.map((x, k) => h("option", { value: x, selected: x === lid }, `Lecture ${k + 1} · ${S.lec[x].title}`))),
    h("span", { class: "spacer" }), devButton(), themeButton(),
    h("div", { class: "topline", id: "lecbar" }, h("div", { style: `width:${lectureProgress(lid) * 100}%` })));
  const main = h("div", { class: "main" + (wide ? " full" : "") });
  $("#app").replaceChildren(top, h("div", { class: "lecture" + (sideOpen ? "" : " noside") }, h("nav", { class: "side" }, steps), main));
  const nextLec = li < S.order.length - 1 ? S.order[li + 1] : null;
  const prev = idx > 0 ? () => go(lid, idx - 1) : li > 0 ? () => go(S.order[li - 1], pages(S.lec[S.order[li - 1]]).length - 1) : null;
  const next = idx < pg.length - 1 ? () => { markDone(lid, idx); go(lid, idx + 1); }
    : nextLec ? () => { markDone(lid, idx); go(nextLec, 0); } : () => { markDone(lid, idx); location.hash = "#/map"; };
  const nextLabel = idx < pg.length - 1 ? `Next: ${pageName(pg[idx + 1]).length > 40 ? "Watch" : pageName(pg[idx + 1])} ▸`
    : nextLec ? `Next: ${lectureName(nextLec)} ▸` : "Next: Course map ▸";
  const ctx = { L, page, idx, t, next, nextLabel };
  const content = { primer: renderPrimer, watch: renderWatch, quiz: renderQuiz, summary: renderSummary,
    map: renderMapPage, questions: renderQuestions }[page.kind](ctx);
  content.classList.add("page-in");
  main.append(content, h("div", { class: "nav" },
    h("button", { onclick: prev, disabled: !prev }, "◂ Back"),
    h("button", { class: "primary", onclick: next }, nextLabel)));
  document.querySelector(".step.current")?.scrollIntoView({ block: "nearest" });
  window.scrollTo(0, 0);
}

function head(kicker, title) {
  return h("div", { class: "phase-head" }, h("div", { style: "flex:1" }, h("div", { class: "kicker" }, kicker), h("h2", {}, title)));
}

// ------------------------------------------------------------------ dev mode panels
function quote(L, ids) {
  return (ids || []).filter((i) => L.sentences[i]).map((i) => h("div", { class: "dev-quote" },
    h("span", { class: "faint" }, `[${i}] ${clock(L.sentences[i].start)} `), L.sentences[i].text));
}
function devIntent(L, intent) {
  if (!intent) return null;
  return h("div", { class: "dev-kv" },
    kv("rule", h("code", {}, intent.rule_id)),
    kv("principle", intent.principle.join(", ")), kv("ICAP · Bloom", `${intent.icap_mode} · ${intent.bloom_level}`),
    kv("rationale", intent.rationale),
    intent.sources && intent.sources.length ? kv("sources", h("div", {}, quote(L, intent.sources.slice(0, 6)),
      intent.sources.length > 6 ? h("div", { class: "faint" }, `… ${intent.sources.length - 6} more`) : null)) : null);
}
function kv(k, v) { return h("div", { class: "kv" }, h("span", { class: "k" }, k), h("span", { class: "v" }, v)); }
function originMatches(L, keys) {
  const pre = keys.flatMap((k) => [`${L.lecture_id}.${k}.`, `${L.lecture_id}/${k}/`, `${L.lecture_id}/${k}.`, `${L.lecture_id}.${k}`]);
  return (L.origin || []).filter((o) => pre.some((p) => o.item === p.replace(/[./]$/, "") || o.item.startsWith(p)));
}
function devOrigin(L, keys) {
  const recs = originMatches(L, keys);
  const judged = ((L.quality || {}).resolved_by_code || []).filter((r) => keys.some((k) => r.item.startsWith(`${L.lecture_id}/${k}`)));
  if (!recs.length && !judged.length) return null;
  return h("div", {},
    recs.length ? h("table", { class: "dev-table" },
      h("tr", {}, ["item", "stage", "prompt", "model", "retries", "tokens in/out", "time", "checks"].map((x) => h("th", {}, x))),
      recs.map((o) => h("tr", {},
        h("td", {}, o.item), h("td", {}, o.stage), h("td", {}, `${o.prompt_id} v${o.prompt_version}`),
        h("td", { title: o.model }, (o.model || "").split(/[/:(]/)[o.engine === "openai" ? 0 : 1] || o.model),
        h("td", {}, o.retries), h("td", {}, `${o.input_tokens} / ${o.output_tokens}`), h("td", {}, `${o.latency_s}s${o.cached ? " (cache)" : ""}`),
        h("td", { class: o.validator && !o.validator.passed ? "bad" : "" },
          o.validator ? (o.validator.passed ? "pass" : "fail") + (o.validator.errors && o.validator.errors.length ? ": " + o.validator.errors.join("; ") : "") : "")))) : null,
    judged.map((r) => h("div", { class: "dev-judge" }, h("b", {}, `Judge → ${r.action}: `), r.item, " — ", r.reason)));
}
function devPanel(title, ...body) {
  if (!DEV()) return null;
  const kids = body.flat(Infinity).filter(Boolean);
  if (!kids.length) return null;
  return h("details", { class: "dev" }, h("summary", {}, "⚙ ", title), kids);
}

// ------------------------------------------------------------------ before you start
function prerequisites(L, ph) {
  if (ph.recall && ph.recall.length) return ph.recall;
  // Fallback for LIRs without recall items: earlier concepts this lecture mentions, by salience.
  const k = S.order.indexOf(L.lecture_id);
  const earlier = new Set(S.order.slice(0, k));
  return S.course.concepts
    .filter((c) => c.introduced && earlier.has(c.introduced.lecture_id) && c.mentions.some((m) => m.lecture_id === L.lecture_id) && c.definition)
    .sort((a, b) => (b.salience || 0) - (a.salience || 0)).slice(0, 4)
    .map((c) => ({ concept_id: c.id, concept: c.name, question: `What is ${cap(c.name).replace(/^(The|A|An) /, (m) => m.toLowerCase())}?`,
      recap: c.definition, jump_to: { lecture_id: c.introduced.lecture_id, t: c.introduced.t }, derived: true }));
}
function renderPrimer({ L, page, idx }) {
  const ph = page.ph;
  const out = h("div", { class: "narrow" }, head("Before you start", L.title));
  out.append(devPanel("How this page was made", devIntent(L, ph.intent), devOrigin(L, ["primer"])));
  out.append(h("div", { class: "card section" }, h("h3", {}, "Goal of this lecture"), h("p", { class: "lead" }, cap(ph.lecture_goal)),
    h("ul", { class: "objectives" }, ph.objectives.map((o) => h("li", {}, h("span", {}, o.text))))));
  const k = S.order.indexOf(L.lecture_id);
  const pre = prerequisites(L, ph);
  out.append(h("div", { class: "card section" }, h("h3", {}, "Before you continue, try to recall"),
    k === 0 ? h("p", { class: "muted", style: "margin:0" }, "This is the first lecture, so there is nothing to recall yet.")
      : !pre.length ? h("p", { class: "muted", style: "margin:0" }, "This lecture does not build on earlier lectures.")
        : [h("p", { class: "muted small", style: "margin-top:0" }, "These ideas from earlier lectures come back here. Answer each one in your head, then open it to check."),
          h("div", { class: "reveals" }, pre.map((r) => {
            const c = S.concepts[r.concept_id];
            return h("div", {}, revealCard(r.question, [h("div", {}, r.recap),
              h("div", { class: "row small", style: "margin-top:8px" },
                h("span", { class: "faint" }, `${cap(c ? c.name : r.concept)} · ${lectureName(r.jump_to.lecture_id)}`),
                timeLink(r.jump_to.lecture_id, r.jump_to.t, `Rewatch ${clock(r.jump_to.t)}`))]),
              devPanel("Recall item", r.intent ? devIntent(L, r.intent) : h("div", { class: "faint" }, "Derived in the viewer from the concept registry (no recall item in this LIR).")));
          }))]));
  if (ph.key_terms.length) {
    out.append(h("div", { class: "card section" }, h("h3", {}, "New key terms"),
      h("div", { class: "terms" }, ph.key_terms.map((t) => h("div", { class: "term" }, h("b", {}, cap(t.term)),
        h("span", { class: "small muted" }, t.definition),
        DEV() ? h("div", { class: "dev-mini" }, `${t.concept_id || ""} · sentences ${(t.sentence_ids || []).join(", ")}`) : null)))));
  }
  const timer = setTimeout(() => markDone(L.lecture_id, idx), 4000);
  onLeave(() => clearTimeout(timer));
  return out;
}

// ------------------------------------------------------------------ watch (clipped video, our controls)
function videoAvailable(url) {
  return fetch(url, { method: "HEAD" }).then((r) => r.ok).catch(() => false);
}
function renderWatch({ L, page, idx, t: seekTo, next, nextLabel }) {
  const ph = page.ph, seg = page.seg;
  const dur = ph.end - ph.start;
  const sents = L.sentences.slice(ph.sentence_range[0], ph.sentence_range[1] + 1);
  const hl = new Set(store.get(`hl:${L.lecture_id}`, []));
  const out = h("div", {}, head("Watch", ph.subgoal));
  const stage = h("div", { class: "stage" });
  const player = h("div", { class: "player" });
  const cc = h("div", { class: "cc", hidden: true, title: "Click to highlight this sentence" });
  const endCard = h("div", { class: "endcard", hidden: true },
    h("div", { class: "endcard-in" }, h("div", { class: "big-check" }, "✓"), h("div", { style: "font-weight:650;font-size:18px" }, "Part complete"),
      h("div", { class: "row", style: "justify-content:center;margin-top:14px" },
        h("button", { onclick: () => { if (video) { video.currentTime = ph.start; endCard.hidden = true; video.play(); } } }, "↺ Replay"),
        h("button", { class: "primary", onclick: next }, nextLabel))));
  const bigPlay = h("button", { class: "bigplay", title: "Play" }, "▶");
  let ccOn = prefs.get("cc-on", false), video = null;
  const playBtn = h("button", { class: "ctl", title: "Play (space)" }, "▶");
  const scrub = h("input", { type: "range", class: "scrub", min: 0, max: dur.toFixed(2), step: 0.1, value: 0, "aria-label": "Position in this part" });
  const time = h("span", { class: "time" }, `0:00 / ${clock(dur)}`);
  const ccBtn = h("button", { class: "ctl toggle" + (ccOn ? " on" : ""), title: "Captions (c). Click a caption to highlight it." }, "CC");
  const speed = h("select", { class: "ctl", title: "Speed" }, [0.75, 1, 1.25, 1.5, 1.75, 2].map((v) => h("option", { value: v, selected: v === prefs.get("speed", 1) }, v + "×")));
  const fsBtn = h("button", { class: "ctl", title: "Full screen (f)" }, "⛶");
  const ctl = h("div", { class: "vctl" }, playBtn, scrub, time, ccBtn, speed, fsBtn);
  const hlInfo = h("div", { class: "small muted hl-info" });
  const drawHlInfo = () => {
    const n = sents.filter((x) => hl.has(x.id)).length;
    hlInfo.textContent = ccOn ? `Click a caption to highlight it.${n ? ` ${n} highlighted in this part — they collect in the summary.` : ""}` : (n ? `${n} highlighted in this part.` : "");
  };
  // ambient light: a tiny copy of the current frame, blurred behind the player
  const glow = h("canvas", { class: "ambient", width: 32, height: 18, "aria-hidden": "true" });
  const gctx = glow.getContext("2d");
  stage.append(glow, player);
  // the controls float over the clip and fade away while it plays and the pointer is still
  let idleTimer = null;
  const wake = () => {
    player.classList.remove("hide-ui");
    clearTimeout(idleTimer);
    idleTimer = setTimeout(() => { if (video && !video.paused) player.classList.add("hide-ui"); }, 2400);
  };
  player.addEventListener("pointermove", wake);
  player.addEventListener("pointerleave", () => { if (video && !video.paused) player.classList.add("hide-ui"); });
  onLeave(() => { clearTimeout(idleTimer); document.body.classList.remove("playing"); });
  out.append(stage, hlInfo,
    devPanel("Segment", h("div", { class: "dev-kv" },
      kv("segment", `${seg.id} · ${seg.content_type} · objective ${seg.objective_id}`),
      kv("sentences", `${ph.sentence_range[0]}–${ph.sentence_range[1]} · ${clock(ph.start)}–${clock(ph.end)} of the lecture video`),
      kv("key points", h("div", {}, seg.key_points.map((k) => h("div", {}, h("b", {}, k.id + " "), k.text, h("span", { class: "faint" }, ` [${k.sentence_ids.join(", ")}]`))))),
      kv("concepts", (seg.concept_ids || []).map((c) => cap((S.concepts[c] || {}).name || c)).join(", "))),
      devIntent(L, ph.intent), devOrigin(L, [seg.id])));
  drawHlInfo();
  let cur = null;
  const drawCC = () => {
    cc.textContent = cur ? cur.text : "";
    cc.classList.toggle("hl", !!cur && hl.has(cur.id));
    cc.hidden = !ccOn || !cur;
  };
  cc.onclick = () => {
    if (!cur) return;
    hl.has(cur.id) ? hl.delete(cur.id) : hl.add(cur.id);
    store.set(`hl:${L.lecture_id}`, [...hl]);
    toast(hl.has(cur.id) ? "Highlighted" : "Highlight removed");
    drawCC(); drawHlInfo();
  };
  const setCC = (on) => { ccOn = on; prefs.set("cc-on", on); ccBtn.classList.toggle("on", on); drawCC(); drawHlInfo(); };
  ccBtn.onclick = () => setCC(!ccOn);
  fsBtn.onclick = () => document.fullscreenElement ? document.exitFullscreen() : stage.requestFullscreen?.();

  const src = L.video ? "/" + L.video : null;
  (src ? videoAvailable(src) : Promise.resolve(false)).then((ok) => {
    if (!ok) {
      const yt = L.youtube_id;
      ctl.hidden = true;
      player.replaceChildren(yt
        ? h("iframe", { src: `https://www.youtube-nocookie.com/embed/${yt}?start=${Math.floor(seekTo ?? ph.start)}&end=${Math.ceil(ph.end)}&rel=0`,
          allow: "autoplay; encrypted-media; fullscreen", allowfullscreen: true })
        : h("div", { class: "empty" }, "No video available for this lecture."));
      hlInfo.textContent = "The local video is not downloaded, so this part plays from YouTube (no captions or highlighting).";
      return;
    }
    video = h("video", { src: src + `#t=${ph.start.toFixed(2)},${ph.end.toFixed(2)}`, preload: "metadata", playsinline: true, disablepictureinpicture: true });
    player.replaceChildren(video, cc, bigPlay, endCard, ctl);
    video.playbackRate = Number(speed.value);
    speed.onchange = () => { video.playbackRate = Number(speed.value); prefs.set("speed", Number(speed.value)); };
    const paintGlow = () => { try { gctx.drawImage(video, 0, 0, 32, 18); } catch { /* frame not ready */ } };
    video.addEventListener("loadedmetadata", () => { video.currentTime = Math.min(Math.max(seekTo ?? ph.start, ph.start), ph.end - 0.5); tick(); });
    video.addEventListener("seeked", paintGlow);
    video.addEventListener("loadeddata", paintGlow);
    const toggle = () => {
      if (video.paused) {
        if (video.currentTime >= ph.end - 0.15) video.currentTime = ph.start;
        endCard.hidden = true; video.play();
      } else video.pause();
    };
    video.onclick = toggle; bigPlay.onclick = toggle; playBtn.onclick = toggle;
    video.addEventListener("play", () => { playBtn.textContent = "❚❚"; bigPlay.hidden = true; document.body.classList.add("playing"); wake(); });
    video.addEventListener("pause", () => {
      playBtn.textContent = "▶"; bigPlay.hidden = !endCard.hidden;
      document.body.classList.remove("playing"); player.classList.remove("hide-ui"); clearTimeout(idleTimer);
    });
    let dragging = false;
    scrub.addEventListener("input", () => { dragging = true; video.currentTime = ph.start + Number(scrub.value); time.textContent = `${clock(Number(scrub.value))} / ${clock(dur)}`; });
    scrub.addEventListener("change", () => { dragging = false; endCard.hidden = true; });
    let lastId = -2;
    function tick() {
      let t = video.currentTime;
      if (t < ph.start - 0.3) { video.currentTime = t = ph.start; }  // the clip starts here
      if (!dragging) scrub.value = Math.min(dur, Math.max(0, t - ph.start));
      scrub.style.setProperty("--p", `${Math.min(100, Math.max(0, (t - ph.start) / dur * 100))}%`);
      if (!dragging) time.textContent = `${clock(t - ph.start)} / ${clock(dur)}`;
      const c = sents.find((x) => t >= x.start && t < x.end) || null;
      const id = c ? c.id : -1;
      if (id !== lastId) { lastId = id; cur = c; drawCC(); }
      if (t >= ph.end - 0.05) {  // the clip ends here
        if (!video.paused) video.pause();
        if (endCard.hidden) { endCard.hidden = false; bigPlay.hidden = true; markDone(L.lecture_id, idx); }
      }
    }
    video.addEventListener("timeupdate", tick);
    video.addEventListener("seeking", () => { if (video.currentTime > ph.end) video.currentTime = ph.end - 0.05; });
    let frame = 0;
    const iv = setInterval(() => { if (video && !video.paused) { tick(); if (++frame % 2 === 0) paintGlow(); } }, 150);
    onLeave(() => { clearInterval(iv); video.pause(); video.removeAttribute("src"); video.load(); });
    listen(document, "keydown", (e) => {
      if (e.target.closest("input, textarea, select")) return;
      if (e.key === " " || e.key === "k") { e.preventDefault(); toggle(); }
      else if (e.key === "ArrowLeft") video.currentTime = Math.max(ph.start, video.currentTime - 5);
      else if (e.key === "ArrowRight") video.currentTime = Math.min(ph.end - 0.05, video.currentTime + 5);
      else if (e.key === "c") setCC(!ccOn);
      else if (e.key === "f") fsBtn.click();
      else return;
      wake();
    });
  });
  return out;
}

// ------------------------------------------------------------------ quiz
const TYPE_NAME = { multiple_choice: "Multiple choice", true_false: "True or false", yes_no: "Yes or no" };
function renderQuiz({ L, page, idx }) {
  const ph = page.ph, seg = page.seg;
  const key = `quiz2:${L.lecture_id}:${ph.segment_id}`;
  const st = store.get(key, { tries: {} });
  const items = ph.quiz.items;
  const maxTries = (q) => (q.options.length > 2 ? 2 : 1);
  const tries = (q) => st.tries[q.id] || [];
  const resolved = (q) => tries(q).includes(q.correct_index) || tries(q).length >= maxTries(q);
  const wrap = h("div", { class: "narrow" });
  let just = null;  // the option clicked last: only it plays the right/wrong animation
  let drawn = false;
  const draw = () => {
    if (drawn) wrap.classList.remove("page-in");  // the page rises in once, not on every answer
    drawn = true;
    const all = items.every(resolved);
    const firstRight = items.filter((q) => tries(q)[0] === q.correct_index).length;
    if (all) markDone(L.lecture_id, idx);
    wrap.replaceChildren(head("Quiz", seg.subgoal),
      devPanel("How this quiz was made", devIntent(L, ph.intent), devOrigin(L, [seg.id])),
      h("p", { class: "muted", style: "margin-top:-6px" }, items.length === 1 ? "One question on this part." : `${items.length} questions on this part. If your first answer is wrong, you get a second try.`),
      all ? h("div", { class: "card quiz-score" }, ring(firstRight / items.length),
        h("div", {}, h("b", {}, `${firstRight} of ${items.length} right on the first try`),
          h("div", { class: "small muted" }, firstRight === items.length ? "Well done." : "Read the explanations, then rewatch the part if something is unclear.")),
        h("span", { class: "spacer" }),
        h("button", { onclick: () => { st.tries = {}; store.set(key, st); draw(); } }, "Retake")) : null,
      items.map((q, qi) => {
        const tr = tries(q), done = resolved(q), gotIt = tr.includes(q.correct_index);
        const kp = seg.key_points.find((k) => k.id === q.target_key_point);
        return h("div", { class: "card qcard" },
          h("div", { class: "row" }, h("span", { class: "qnum" }, `Question ${qi + 1} · ${TYPE_NAME[q.item_type] || ""}`),
            q.interleaved_from ? h("span", { class: "tag warn" }, `Review from ${lectureName(q.interleaved_from.lecture_id)}`) : null),
          h("div", { class: "stem" }, q.stem),
          h("div", { class: "opts" }, q.options.map((o, oi) => {
            let cls = "opt";
            if (done && oi === q.correct_index) cls += " right";
            else if (tr.includes(oi)) cls += " wrong";
            else if (DEV() && oi === q.correct_index) cls += " devkey";
            if (just === `${q.id}:${oi}`) cls += " just";
            const showExpl = done && (oi === q.correct_index || tr.includes(oi) || DEV());
            return h("button", { class: cls, disabled: done || tr.includes(oi),
              onclick: () => { st.tries[q.id] = [...tr, oi]; store.set(key, st); just = `${q.id}:${oi}`; draw(); just = null; } },
              h("span", { class: "letter" }, q.options.length > 2 ? "ABCD"[oi] : o[0]),
              h("span", {}, o, showExpl ? h("span", { class: "expl" }, q.explanations[oi]) : null));
          })),
          !done && tr.length ? h("div", { class: "nudge" }, "Not quite. Think again and pick another answer.") : null,
          done ? h("div", { class: "result " + (gotIt ? "ok" : "bad") }, gotIt ? (tr.length === 1 ? "✓ Right" : "✓ Right on the second try") : "✗ Not this time. The right answer is marked in green.") : null,
          devPanel("Item", h("div", { class: "dev-kv" },
            kv("answer", `${"ABCD"[q.correct_index]} · ${q.options[q.correct_index]}`),
            kv("tests", kp ? `${kp.id}: ${kp.text}` : q.target_key_point),
            q.interleaved_from ? kv("interleaved", `${q.interleaved_from.concept} (${q.interleaved_from.lecture_id})`) : null),
            devIntent(L, q.intent), devOrigin(L, [q.id])));
      }));
  };
  draw();
  return wrap;
}
// Progress ring; the arc sweeps in from zero. An optional caption sits under the percentage.
function ring(frac, caption) {
  const r = 22, c = 2 * Math.PI * r;
  const col = caption ? "var(--accent)" : frac >= 0.75 ? "var(--ok)" : frac >= 0.5 ? "var(--accent)" : "var(--warn)";
  const arc = s("circle", { class: "arc", cx: 26, cy: 26, r, fill: "none", stroke: col, "stroke-width": caption ? 3 : 5, "stroke-linecap": frac > 0 ? "round" : "butt",
    "stroke-dasharray": `0 ${c}`, transform: "rotate(-90 26 26)", style: `filter:drop-shadow(0 0 3px ${col})` });
  requestAnimationFrame(() => requestAnimationFrame(() => arc.setAttribute("stroke-dasharray", `${Math.max(frac * c, frac > 0 ? 0.01 : 0)} ${c}`)));
  return s("svg", { class: "ring", viewBox: "0 0 52 52" },
    s("circle", { cx: 26, cy: 26, r, fill: "none", stroke: "var(--line-2)", "stroke-width": caption ? 3 : 5 }), arc,
    s("text", { x: 26, y: caption ? 27 : 30.5, "text-anchor": "middle", "font-size": caption ? 11 : 13, "font-weight": 600, fill: "var(--text)" }, Math.round(frac * 100) + "%"),
    caption ? s("text", { x: 26, y: 34, "text-anchor": "middle", "font-size": 3.6, fill: "var(--faint)", "letter-spacing": ".3" }, caption.toUpperCase()) : null);
}

// ------------------------------------------------------------------ interactive summary
function conceptTime(L, cid, seg) {
  const c = S.concepts[cid];
  const m = c && c.mentions.find((x) => x.lecture_id === L.lecture_id && x.segment_id === seg.id);
  const sid = m ? m.sentence_ids[0] : null;
  return sid != null && L.sentences[sid] ? L.sentences[sid].start : null;
}
// A question that opens to show its answer (closed until the learner has thought about it; open in dev mode).
function revealCard(question, answerKids) {
  const open = DEV();
  const ans = h("div", { class: "reveal-a" }, h("div", { class: "reveal-in" }, h("div", {}, answerKids)));
  ans.inert = !open;
  const q = h("button", { class: "reveal-q", "aria-expanded": String(open) }, h("span", {}, question), h("span", { class: "chev", "aria-hidden": "true" }, "▾"));
  const card = h("div", { class: "reveal" + (open ? " open" : "") }, q, ans);
  q.onclick = () => { const o = card.classList.toggle("open"); ans.inert = !o; q.setAttribute("aria-expanded", String(o)); };
  return card;
}
function renderSummary({ L, page, idx }) {
  const ph = page.ph, seg = page.seg, sm = ph.summary;
  const out = h("div", { class: "narrow" }, head("Summary", seg.subgoal));
  out.append(devPanel("How this summary was made", devIntent(L, ph.intent), devOrigin(L, [seg.id])));
  out.append(h("div", { class: "card section recap" }, h("p", { style: "margin:0" }, sm.recap)));
  const segTime = (ids) => { const i = (ids || []).find((x) => L.sentences[x]); return i != null ? L.sentences[i].start : null; };
  // Check-yourself cards: written review questions when the LIR has them, else one card per key concept.
  const cards = (sm.review || []).length
    ? sm.review.map((r) => ({ q: r.question, a: r.answer, t: r.t ?? segTime(r.sentence_ids) }))
    : sm.key_concepts.map((k) => ({ q: `What is ${cap(k.name)}?`, a: k.explanation, t: conceptTime(L, k.concept_id, seg) }));
  if (cards.length) {
    out.append(h("div", { class: "card section" }, h("h3", {}, "Check yourself"),
      h("p", { class: "muted small", style: "margin-top:0" }, "Answer in your head first, then click to see the answer. ▶ takes you to the moment it was explained."),
      h("div", { class: "reveals" }, cards.map((c) => revealCard(c.q, [h("div", {}, c.a),
        c.t != null ? h("div", { style: "margin-top:6px" }, timeLink(L.lecture_id, c.t, `Watch at ${clock(c.t - seg.start)}`)) : null])))));
  }
  if (sm.earlier_links.length) {
    // read each link in its edge's own direction ("src label dst")
    const fwd = (l) => l.direction ? l.direction === "from_earlier"
      : !S.course.edges.some((e) => e.src === l.to_concept_id && e.dst === l.concept_id && e.rel === l.relation);
    const other = (l) => cap((S.concepts[l.to_concept_id] || {}).name || "");
    out.append(h("div", { class: "card section" }, h("h3", {}, "Connects to what you saw earlier"),
      sm.earlier_links.map((l) => h("div", { class: "link-row" },
        h("span", {}, h("b", {}, fwd(l) ? cap(l.name) : other(l)), " ", h("span", { class: "muted" }, l.label), " ",
          h("b", {}, fwd(l) ? other(l) : cap(l.name))),
        h("span", { class: "spacer" }), timeLink(l.jump_to.lecture_id, l.jump_to.t)))));
  }
  const hl = store.get(`hl:${L.lecture_id}`, []).filter((id) => id >= seg.sentence_range[0] && id <= seg.sentence_range[1]).sort((a, b) => a - b);
  out.append(h("div", { class: "card section" }, h("h3", {}, "Your highlights"),
    hl.length ? hl.map((id) => h("div", { class: "hl-quote" }, h("span", {}, L.sentences[id].text), timeLink(L.lecture_id, L.sentences[id].start, clock(L.sentences[id].start - seg.start))))
      : h("div", { class: "small faint" }, "None yet. Turn on captions (CC) while watching and click a caption to highlight it.")));
  const timer = setTimeout(() => markDone(L.lecture_id, idx), 3000);
  onLeave(() => clearTimeout(timer));
  return out;
}

// ------------------------------------------------------------------ open questions
const TIER_ICON = { excellent: "★", good: "✓", acceptable: "◐", try_again: "↻" };
const OQ_NAME = { fill_in_steps: "Fill in the steps", compare_contrast: "Compare and contrast", self_explanation: "Explain why",
  apply_new_case: "Apply it", troubleshooting: "Troubleshoot", explain_to_someone: "Explain it to a friend" };
function hintFor(oq, missedText) {
  const kp = oq.key_points.find((k) => k.text === missedText);
  const kw = kp && kp.keywords && kp.keywords[0];
  return kw ? `Your answer does not yet say anything about “${kw}”. What role does it play here?`
    : "One of the key ideas is still missing. Reread the question and add what is left out.";
}
function keywordScore(oq, answer, cfg) {  // offline fallback: keywords only
  const stem = (w) => { for (const suf of ["ization", "isation", "ations", "ation", "ings", "ing", "ies", "ied", "ers", "er", "es", "ed", "s", "ly"]) if (w.length > suf.length + 2 && w.endsWith(suf)) return w.slice(0, -suf.length) + (suf === "ies" || suf === "ied" ? "y" : ""); return w; };
  const STOP = new Set("a an the of to in on for and or with by from is are be as at this that these those its it".split(" "));
  const words = (t) => new Set((t.toLowerCase().match(/[a-z0-9]+/g) || []).filter((w) => !STOP.has(w)).map(stem));
  const have = words(answer);
  const kps = oq.key_points.map((k) => {
    const kw = new Set(k.keywords.flatMap((x) => [...words(x)]));
    const hits = [...kw].filter((w) => have.has(w));
    return { text: k.text, covered: kw.size > 0 && hits.length >= Math.min(cfg.m, kw.size) };
  });
  const sc = kps.filter((k) => k.covered).length / Math.max(1, kps.length);
  const tier = cfg.tiers.find((t) => sc >= t.min) || cfg.tiers[cfg.tiers.length - 1];
  return { score: sc, tier, key_points: kps, missed: kps.filter((k) => !k.covered).map((k) => k.text), offline: true };
}
function renderOQ(L, oq, n) {
  const key = `oq:${L.lecture_id}:${oq.id}`;
  const st = store.get(key, { answer: "", result: null, attempts: 0 });
  const ta = h("textarea", { placeholder: "Write your answer in your own words…" });
  ta.value = st.answer;
  ta.oninput = () => { st.answer = ta.value; store.set(key, st); };
  const fb = h("div", {});
  const ref = h("div", {});
  const btn = h("button", { class: "primary" }, st.attempts ? "Revise and check again" : "Check my answer");
  const refUnlocked = () => DEV() || st.attempts >= 2 || (st.result && st.result.tier.id === "excellent");
  const refBtn = h("button", { class: "ghost" });
  let showRef = DEV();
  const drawRef = () => {
    refBtn.disabled = !refUnlocked();
    refBtn.textContent = !refUnlocked() ? (st.attempts ? "Reference answer unlocks after one more try" : "Reference answer unlocks after two tries")
      : showRef ? "Hide reference answer" : "Show reference answer";
    ref.replaceChildren(showRef && refUnlocked() ? h("div", { class: "reference" }, h("b", {}, "Reference answer"),
      h("p", { style: "margin:6px 0 0" }, oq.reference_answer),
      h("div", { style: "margin-top:10px" }, h("b", { class: "small" }, "Key points a good answer covers"),
        oq.key_points.map((k) => h("div", { class: "kp" }, h("span", { class: "mark" }, "•"), h("span", {}, k.text,
          DEV() ? h("span", { class: "faint" }, `  [${k.keywords.join(", ")}]`) : null))))) : "");
  };
  refBtn.onclick = () => { showRef = !showRef; drawRef(); };
  const drawFb = () => {
    const r = st.result;
    if (!r) return fb.replaceChildren();
    const detailed = st.attempts >= 2 || r.tier.id === "excellent";
    fb.replaceChildren(h("div", { class: "feedback" },
      h("div", { class: "row" }, h("span", { class: `tier ${r.tier.id}` }, TIER_ICON[r.tier.id] || "", " ", r.tier.label),
        r.offline ? h("span", { class: "tag warn" }, "keywords only (scoring server offline)") : null),
      !detailed && r.missed.length ? h("div", { class: "small", style: "margin-top:10px" }, h("b", {}, "Hint: "), hintFor(oq, r.missed[0]),
        h("div", { class: "faint", style: "margin-top:4px" }, "Revise your answer and check again.")) : null,
      detailed ? h("div", { style: "margin-top:10px" },
        h("div", { class: "small muted", style: "margin-bottom:4px" }, `Your answer covers ${r.key_points.filter((k) => k.covered).length} of ${r.key_points.length} key points:`),
        r.key_points.map((k) => h("div", { class: "kp " + (k.covered ? "hit" : "miss") },
          h("span", { class: "mark" }, k.covered ? "✓" : "✗"), h("span", {}, k.text)))) : null));
  };
  btn.onclick = async () => {
    if (ta.value.trim().split(/\s+/).length < 5) return toast("Write a little more first (a few sentences)");
    btn.disabled = true; btn.textContent = "Checking…";
    try {
      const r = await fetch("/api/score", { method: "POST", headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ course_id: S.cid, lecture_id: L.lecture_id, oq_id: oq.id, answer: ta.value }) });
      if (!r.ok) throw new Error();
      st.result = await r.json();
      if (st.result.error) throw new Error(st.result.error);
    } catch { st.result = keywordScore(oq, ta.value, L.scoring.open_answer); }
    st.attempts += 1; store.set(key, st);
    btn.disabled = false; btn.textContent = "Revise and check again";
    drawFb(); drawRef();
  };
  drawFb(); drawRef();
  return h("div", { class: "card oq" },
    h("div", { class: "row" }, h("span", { class: "qnum" }, `Question ${n}`), h("span", { class: "tag" }, OQ_NAME[oq.question_type] || oq.question_type)),
    h("div", { class: "prompt" }, oq.prompt), ta,
    h("div", { class: "row", style: "margin-top:10px" }, btn, refBtn),
    fb, ref,
    devPanel("How this question was made", devIntent(L, oq.intent), devOrigin(L, [oq.id])));
}
function renderQuestions({ L, page, idx }) {
  const ph = page.ph;
  const out = h("div", { class: "narrow" }, head("Wrap-up", "Questions to think about"),
    h("p", { class: "muted", style: "margin-top:-6px" }, "Answer in your own words. You get a hint after your first try; the reference answer opens after your second."));
  out.append(ph.open_questions.map((q, i) => renderOQ(L, q, i + 1)));
  const hl = store.get(`hl:${L.lecture_id}`, []).sort((a, b) => a - b);
  out.append(h("div", { class: "card section", style: "margin-top:10px" }, h("h3", {}, "Your highlights from this lecture"),
    hl.length ? hl.map((id) => h("div", { class: "hl-quote" }, h("span", {}, L.sentences[id].text), timeLink(L.lecture_id, L.sentences[id].start)))
      : h("div", { class: "small faint" }, "You did not highlight anything in this lecture.")));
  const timer = setTimeout(() => markDone(L.lecture_id, idx), 4000);
  onLeave(() => clearTimeout(timer));
  return out;
}

// ------------------------------------------------------------------ concept map
function wrapName(name, max = 22) {
  const words = cap(name).split(/\s+/), lines = [];
  let cur = "";
  for (const w of words) {
    if (cur && (cur + " " + w).length > max) { lines.push(cur); cur = w; } else cur = cur ? cur + " " + w : w;
  }
  if (cur) lines.push(cur);
  if (lines.length > 3) { lines.length = 3; lines[2] = lines[2].slice(0, max - 1) + "…"; }
  return lines;
}
const CH = 7.3;  // approx. character width at 13px
function nodeBox(name) {
  const lines = wrapName(name);
  return { lines, w: Math.max(...lines.map((l) => l.length)) * CH + 28, h: lines.length * 16 + 18 };
}
function nodeEl(name, cls, x, y) {
  const b = nodeBox(name);
  return s("g", { class: "node " + (cls || ""), transform: `translate(${x},${y})` },
    s("rect", { x: -b.w / 2, y: -b.h / 2, width: b.w, height: b.h, rx: Math.min(b.h / 2, 17) }),
    s("text", { "text-anchor": "middle", y: -((b.lines.length - 1) * 16) / 2 + 4.5 },
      b.lines.map((l, i) => s("tspan", { x: 0, dy: i ? 16 : 0 }, l))));
}
function labelPill(text, x, y, cls) {
  if (!text) return null;
  const w = text.length * 6.1 + 12;
  return s("g", { class: "lbl " + (cls || ""), transform: `translate(${x},${y})` },
    s("rect", { x: -w / 2, y: -9, width: w, height: 18, rx: 9 }), s("text", { "text-anchor": "middle", y: 4 }, text));
}
// Pan and zoom an svg by rewriting its viewBox: wheel, drag, two-finger pinch, and animated moves (to).
// onView(view) runs after every change; moved() tells a click from the end of a drag.
function panZoom(svg, vb, onView) {
  let [x, y, w, hh] = vb, raf = 0, movedPx = 0;
  const set = () => { svg.setAttribute("viewBox", `${x} ${y} ${w} ${hh}`); if (onView) onView([x, y, w, hh]); };
  set();
  const at = (cx, cy) => { const r = svg.getBoundingClientRect(); return [x + (cx - r.left) / r.width * w, y + (cy - r.top) / r.height * hh]; };
  const zoomAt = (px, py, k) => { w *= k; hh *= k; x = px - (px - x) * k; y = py - (py - y) * k; set(); };
  svg.addEventListener("wheel", (e) => {
    e.preventDefault(); cancelAnimationFrame(raf);
    const [px, py] = at(e.clientX, e.clientY); zoomAt(px, py, e.deltaY > 0 ? 1.12 : 1 / 1.12);
  }, { passive: false });
  const ptrs = new Map();
  let drag = null, pinch = null;
  const isBg = (t) => t === svg || t.classList.contains("bg") || t.classList.contains("pan");
  svg.addEventListener("pointerdown", (e) => {
    if (!isBg(e.target) && !ptrs.size) return;
    cancelAnimationFrame(raf);
    ptrs.set(e.pointerId, [e.clientX, e.clientY]); svg.setPointerCapture(e.pointerId); movedPx = 0;
    if (ptrs.size === 1) drag = { cx: e.clientX, cy: e.clientY, x, y };
    if (ptrs.size === 2) {
      const [a, b] = [...ptrs.values()];
      pinch = { d: Math.hypot(a[0] - b[0], a[1] - b[1]), mid: at((a[0] + b[0]) / 2, (a[1] + b[1]) / 2), w, hh, x, y };
      drag = null;
    }
  });
  svg.addEventListener("pointermove", (e) => {
    if (!ptrs.has(e.pointerId)) return;
    ptrs.set(e.pointerId, [e.clientX, e.clientY]);
    const r = svg.getBoundingClientRect();
    if (pinch && ptrs.size === 2) {
      const [a, b] = [...ptrs.values()], k = pinch.d / Math.max(10, Math.hypot(a[0] - b[0], a[1] - b[1]));
      w = pinch.w * k; hh = pinch.hh * k; x = pinch.mid[0] - (pinch.mid[0] - pinch.x) * k; y = pinch.mid[1] - (pinch.mid[1] - pinch.y) * k;
      movedPx = 99; set();
    } else if (drag) {
      movedPx = Math.max(movedPx, Math.hypot(e.clientX - drag.cx, e.clientY - drag.cy));
      x = drag.x - (e.clientX - drag.cx) / r.width * w; y = drag.y - (e.clientY - drag.cy) / r.height * hh; set();
    }
  });
  const up = (e) => { ptrs.delete(e.pointerId); if (ptrs.size < 2) pinch = null; if (!ptrs.size) drag = null; };
  svg.addEventListener("pointerup", up); svg.addEventListener("pointercancel", up);
  const to = (t, D = 520) => {
    cancelAnimationFrame(raf);
    if (matchMedia("(prefers-reduced-motion: reduce)").matches) { [x, y, w, hh] = t; return set(); }
    const f = [x, y, w, hh], t0 = performance.now();
    const step = (now) => {
      const u = Math.min(1, (now - t0) / D), e = 1 - Math.pow(1 - u, 3);
      [x, y, w, hh] = f.map((v, k) => v + (t[k] - v) * e); set();
      if (u < 1) raf = requestAnimationFrame(step);
    };
    raf = requestAnimationFrame(step);
  };
  return { reset: () => to(vb), to, view: () => [x, y, w, hh], moved: () => movedPx > 5,
    zoom: (k) => to([x + w * (1 - k) / 2, y + hh * (1 - k) / 2, w * k, hh * k], 260) };
}
// Pick a readable reference map: connected concepts only, at most `cap` nodes, seeds and this lecture's concepts first.
function referenceSubgraph(cm, L, capN = 14, maxEarlier = 4) {
  const byId = Object.fromEntries(cm.reference_nodes.map((n) => [n.concept_id, n]));
  const own = (id) => byId[id].lecture_id === L.lecture_id;
  // only links that involve this lecture's own concepts
  const edges = cm.reference_edges.filter((e) => byId[e.src] && byId[e.dst] && e.src !== e.dst && (own(e.src) || own(e.dst)));
  const deg = {};
  edges.forEach((e) => { deg[e.src] = (deg[e.src] || 0) + 1; deg[e.dst] = (deg[e.dst] || 0) + 1; });
  const score = (n) => (n.is_seed ? 3 : 0) + Math.min(deg[n.concept_id] || 0, 5) + ((S.concepts[n.concept_id] || {}).salience || 0);
  const ranked = cm.reference_nodes.filter((n) => deg[n.concept_id]).sort((a, b) => score(b) - score(a));
  const ownIds = ranked.filter((n) => own(n.concept_id)).slice(0, capN - Math.min(maxEarlier, 2));
  const earlierIds = ranked.filter((n) => !own(n.concept_id)).slice(0, Math.min(maxEarlier, capN - ownIds.length));
  let keep = new Set([...ownIds, ...earlierIds].map((n) => n.concept_id));
  const es = edges.filter((e) => keep.has(e.src) && keep.has(e.dst));
  const linked = new Set(es.flatMap((e) => [e.src, e.dst]));
  keep = new Set([...keep].filter((c) => linked.has(c)));
  const others = cm.reference_nodes.filter((n) => !keep.has(n.concept_id) && own(n.concept_id)).map((n) => n.name);
  return { nodes: [...keep].map((c) => byId[c]), edges: es, others };
}
function referenceMap(cm, L) {
  const g = referenceSubgraph(cm, L);
  const box = h("div", { class: "refmap" });
  if (!g.nodes.length || typeof dagre === "undefined") return h("div", { class: "faint" }, "No reference links for this lecture.");
  // Lay out top-down and left-right, keep the one whose shape best fits the canvas (about 2.3 : 1).
  const layout = (dir) => {
    const G = new dagre.graphlib.Graph({ multigraph: true });
    G.setGraph({ rankdir: dir, nodesep: dir === "TB" ? 18 : 22, ranksep: dir === "TB" ? 34 : 56, edgesep: 12, marginx: 16, marginy: 16 });
    G.setDefaultEdgeLabel(() => ({}));
    g.nodes.forEach((n) => { const b = nodeBox(n.name); G.setNode(n.concept_id, { width: b.w, height: b.h, n }); });
    g.edges.forEach((e, i) => G.setEdge(e.src, e.dst, { label: e.label, width: (e.label || "").length * 6.4 + 14, height: 20, labelpos: "c", e }, "e" + i));
    dagre.layout(G);
    const r = G.graph().width / G.graph().height;
    return { G, fit: Math.abs(Math.log(r / 2.3)) };
  };
  const G = [layout("TB"), layout("LR")].sort((a, b) => a.fit - b.fit)[0].G;
  const gw = G.graph().width, gh = G.graph().height;
  const svg = s("svg", { class: "cmap ref", preserveAspectRatio: "xMidYMid meet" });
  svg.append(s("defs", {}, s("marker", { id: "arr", viewBox: "0 0 10 10", refX: 9, refY: 5, markerWidth: 6, markerHeight: 6, orient: "auto-start-reverse" },
    s("path", { d: "M0,0 L10,5 L0,10 z", class: "arrowhead" }))));
  svg.append(s("rect", { class: "bg", x: -5000, y: -5000, width: 10000, height: 10000, fill: "transparent" }));
  const curve = (pts) => {  // smooth path through dagre's points
    let d = `M${pts[0].x},${pts[0].y}`;
    for (let i = 1; i < pts.length - 1; i++) {
      const mx = (pts[i].x + pts[i + 1].x) / 2, my = (pts[i].y + pts[i + 1].y) / 2;
      d += ` Q${pts[i].x},${pts[i].y} ${mx},${my}`;
    }
    const last = pts[pts.length - 1];
    return d + ` L${last.x},${last.y}`;
  };
  // draw order follows the layout (top-left first), so the map builds itself outward
  const order = G.nodes().slice().sort((a, b) => (G.node(a).y - G.node(b).y) || (G.node(a).x - G.node(b).x));
  const rank = Object.fromEntries(order.map((id, i) => [id, i]));
  const tag = (el, a, b, d) => { el.dataset.a = a; el.dataset.b = b; el.style.setProperty("--d", d); return el; };
  G.edges().forEach((k) => svg.append(tag(s("path", { class: "edge-path", d: curve(G.edge(k).points), "marker-end": "url(#arr)", pathLength: 1 }),
    k.v, k.w, Math.max(rank[k.v], rank[k.w]))));
  G.edges().forEach((k) => { const e = G.edge(k), pill = labelPill(e.label, e.x, e.y); if (pill) svg.append(tag(pill, k.v, k.w, Math.max(rank[k.v], rank[k.w]) + 3)); });
  G.nodes().forEach((id) => {
    const v = G.node(id), n = v.n;
    const el = nodeEl(n.name, (n.is_seed ? "seed" : "") + (n.lecture_id !== L.lecture_id ? " earlier" : ""), v.x, v.y);
    el.dataset.id = id; el.style.setProperty("--d", rank[id]);
    const c = S.concepts[id];
    if (c && c.definition) el.append(s("title", {}, `${cap(c.name)}: ${c.definition}`));
    // hover: keep this concept, its links and its neighbours lit; fade the rest
    el.addEventListener("pointerenter", () => {
      const near = new Set([id]);
      svg.querySelectorAll(".edge-path, .lbl").forEach((x) => {
        const hot = x.dataset.a === id || x.dataset.b === id;
        x.classList.toggle("hot", hot);
        if (hot) { near.add(x.dataset.a); near.add(x.dataset.b); }
      });
      svg.querySelectorAll(".node").forEach((x) => x.classList.toggle("hot", near.has(x.dataset.id)));
      svg.classList.add("focusing");
    });
    el.addEventListener("pointerleave", () => svg.classList.remove("focusing"));
    svg.append(el);
  });
  box.append(svg);
  // never scale text up by more than ~1.3x on small graphs
  const vw = Math.max(gw, 900), vh = Math.max(gh, 900 / 2.3);
  const pz = panZoom(svg, [(gw - vw) / 2, (gh - vh) / 2, vw, vh]);
  return h("div", {},
    h("div", { class: "row small muted", style: "margin:4px 0 8px" },
      h("span", { class: "legend seed" }, "Seed concept"), h("span", { class: "legend earlier" }, "From an earlier lecture"),
      h("span", {}, "Arrows read as “concept → link → concept”. Hover a concept to see its links; scroll to zoom, drag to pan."), h("span", { class: "spacer" }),
      h("button", { class: "ghost small", onclick: () => pz.reset() }, "Fit")),
    box,
    g.others.length ? h("div", { class: "small muted", style: "margin-top:8px" }, "Also in this lecture: ", g.others.map(cap).join(" · ")) : null);
}
const MW = 1200, MH = 620, GRID = 24;
const snap = (v) => Math.round(v / GRID) * GRID;
// A gently curved link from a to b that starts and ends at the edge of each concept's pill.
function linkPath(a, b) {
  const dx = b.x - a.x, dy = b.y - a.y, len = Math.hypot(dx, dy) || 1;
  const bend = Math.min(40, len * 0.12);
  const cx = (a.x + b.x) / 2 - dy / len * bend, cy = (a.y + b.y) / 2 + dx / len * bend;
  const edge = (n, tx, ty, pad) => {  // where the line from n's centre towards (tx, ty) leaves its box
    const bx = nodeBox(n.name), vx = tx - n.x, vy = ty - n.y;
    const k = Math.min(Math.abs(vx) > 0.01 ? (bx.w / 2 + pad) / Math.abs(vx) : Infinity, Math.abs(vy) > 0.01 ? (bx.h / 2 + pad) / Math.abs(vy) : Infinity, 1);
    return [n.x + vx * k, n.y + vy * k];
  };
  const [x1, y1] = edge(a, cx, cy, 2), [x2, y2] = edge(b, cx, cy, 5);
  return { d: `M${x1},${y1} Q${cx},${cy} ${x2},${y2}`, mx: 0.25 * x1 + 0.5 * cx + 0.25 * x2, my: 0.25 * y1 + 0.5 * cy + 0.25 * y2 };
}
function renderMapPage({ L, page, idx }) {
  const cm = page.ph.concept_map;
  const key = `cmap:${L.lecture_id}`;
  let st = store.get(key, null);
  if (!st) {
    st = { nodes: cm.seeds.map((n, i) => {
      const a = (i / cm.seeds.length) * 2 * Math.PI - Math.PI / 2;
      return { name: cap(n.name), x: snap(MW / 2 + 380 * Math.cos(a)), y: snap(MH / 2 + 210 * Math.sin(a)), seed: true };
    }), links: [], result: null, checked: false };
  }
  const save = () => store.set(key, st);
  let sel = null, drag = null, tab = "mine";
  const svg = s("svg", { class: "cmap learn", viewBox: `0 0 ${MW} ${MH}` });
  const defs = s("defs", {},
    s("marker", { id: "arr-l", viewBox: "0 0 10 10", refX: 9, refY: 5, markerWidth: 6, markerHeight: 6, orient: "auto-start-reverse" },
      s("path", { d: "M0,0 L10,5 L0,10 z", class: "arrowhead" })),
    s("pattern", { id: "dots-l", width: GRID, height: GRID, patternUnits: "userSpaceOnUse", x: -GRID / 2, y: -GRID / 2 },
      s("circle", { cx: GRID / 2, cy: GRID / 2, r: 1.2, class: "dot" })));
  const ghost = s("path", { class: "ghost-link", d: "" });
  const wrap = h("div", { class: "cmap-wrap" });
  const status = h("div", { class: "small muted", style: "margin-top:6px" });
  const res = h("div", {});
  const input = h("input", { type: "text", placeholder: "Add a concept…" });
  const addNode = () => {
    const name = input.value.trim();
    if (!name) return;
    if (st.nodes.some((n) => n.name.toLowerCase() === name.toLowerCase())) return toast("Already on the map");
    st.nodes.push({ name: cap(name), x: snap(120 + Math.random() * (MW - 240)), y: snap(80 + Math.random() * (MH - 160)) });
    input.value = ""; save(); draw();
  };
  input.onkeydown = (e) => { if (e.key === "Enter") addNode(); };
  const pt = (e) => { const p = svg.createSVGPoint(); p.x = e.clientX; p.y = e.clientY; return p.matrixTransform(svg.getScreenCTM().inverse()); };
  function draw() {
    const bg = s("rect", { class: "bg", x: 0, y: 0, width: MW, height: MH, fill: "url(#dots-l)" });
    bg.addEventListener("pointerdown", () => { if (sel) { sel = null; draw(); } });
    svg.replaceChildren(defs, bg);
    st.links.forEach((l, i) => {
      const a = st.nodes.find((n) => n.name === l.a), b = st.nodes.find((n) => n.name === l.b);
      if (!a || !b) return;
      const ls = st.result && st.result.links.find((x) => x.a === l.a && x.b === l.b);
      const cls = ls ? (ls.in_reference ? " ok" : " extra") : "";
      const k = linkPath(a, b);
      const g = s("g", { class: "edge" + cls, style: "cursor:pointer" },
        s("path", { class: "hit", d: k.d }), s("path", { class: "edge-path", d: k.d, "marker-end": "url(#arr-l)" }),
        labelPill(l.label, k.mx, k.my, cls));
      g.append(s("title", {}, `${l.a} → ${l.label || "…"} → ${l.b} (click to remove)`));
      g.addEventListener("click", () => { st.links.splice(i, 1); st.result = null; save(); draw(); toast("Link removed"); });
      svg.append(g);
    });
    svg.append(ghost);
    st.nodes.forEach((n) => {
      const ok = st.result && st.result.nodes[n.name] && st.result.nodes[n.name].concept_id;
      const g = nodeEl(n.name, (n.seed ? "seed" : "") + (sel === n ? " sel" : "") + (ok ? " ok" : ""), n.x, n.y);
      g.addEventListener("pointerdown", (e) => {
        e.preventDefault();
        const p = pt(e); drag = { n, dx: n.x - p.x, dy: n.y - p.y, moved: false };
        svg.setPointerCapture(e.pointerId);
      });
      g.addEventListener("dblclick", () => {
        if (n.seed) return toast("Seed concepts stay on the map");
        st.nodes = st.nodes.filter((x) => x !== n); st.links = st.links.filter((l) => l.a !== n.name && l.b !== n.name); st.result = null; save(); draw();
      });
      svg.append(g);
    });
    if (!sel) ghost.setAttribute("d", "");
    status.textContent = sel ? `Selected “${sel.name}”: click another concept to link them (Esc to cancel).`
      : `${st.nodes.length} concepts, ${st.links.length} links. Click one concept, then another, to link them. Drag to move. Click a link to remove it; double-click a concept you added to remove it.`;
    check.disabled = st.links.length < 2;
    check.title = st.links.length < 2 ? "Draw at least two links first" : "";
  }
  svg.addEventListener("pointermove", (e) => {
    const p = pt(e);
    if (!drag) {  // while a concept is selected, a dashed line follows the pointer
      if (sel) ghost.setAttribute("d", `M${sel.x},${sel.y} L${p.x},${p.y}`);
      return;
    }
    const x = snap(Math.max(70, Math.min(MW - 70, p.x + drag.dx))), y = snap(Math.max(24, Math.min(MH - 24, p.y + drag.dy)));
    if (x === drag.n.x && y === drag.n.y) return;
    drag.n.x = x; drag.n.y = y; drag.moved = true; draw();
  });
  svg.addEventListener("pointerup", () => {
    if (!drag) return;
    const n = drag.n, moved = drag.moved; drag = null;
    if (moved) return save();
    if (!sel) { sel = n; return draw(); }
    if (sel === n) { sel = null; return draw(); }
    const a = sel; sel = null; draw();
    if (st.links.some((l) => (l.a === a.name && l.b === n.name) || (l.a === n.name && l.b === a.name))) return toast("Already linked");
    askLabel(a, n);
  });
  listen(document, "keydown", (e) => { if (e.key === "Escape" && sel) { sel = null; draw(); } });
  function askLabel(a, b) {
    const box = h("div", { class: "card label-box" });
    const li = h("input", { type: "text", placeholder: `${a.name} … ${b.name}` });
    const done = (keep) => {
      if (keep) { st.links.push({ a: a.name, b: b.name, label: li.value.trim() }); st.result = null; save(); draw(); }
      box.remove();
    };
    li.onkeydown = (e) => { if (e.key === "Enter") done(true); if (e.key === "Escape") done(false); };
    box.append(h("div", { class: "small", style: "margin-bottom:6px" }, h("b", {}, `${a.name} → ${b.name}`), h("div", { class: "muted" }, "Label the link, e.g. “is part of”")), li,
      h("div", { class: "row", style: "margin-top:8px" }, h("button", { class: "primary", onclick: () => done(true) }, "Add link"),
        h("button", { class: "ghost", onclick: () => done(false) }, "Cancel")));
    wrap.append(box); li.focus();
  }
  const check = h("button", { class: "primary" }, "Check my map");
  check.onclick = async () => {
    check.disabled = true;
    try {
      const resp = await fetch("/api/cmap", { method: "POST", headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ course_id: S.cid, lecture_id: L.lecture_id, nodes: st.nodes.map((n) => n.name), links: st.links }) });
      st.result = await resp.json();
      if (st.result.error) throw new Error(st.result.error);
      st.checked = true; save(); draw(); drawResult(); drawTabs(); markDone(L.lecture_id, idx);
    } catch (e) { toast("The scoring server is not running (python3 serve.py)"); }
    check.disabled = false;
  };
  function drawResult() {
    const r = st.result;
    if (!r) return res.replaceChildren();
    res.replaceChildren(h("div", { class: "feedback" },
      h("div", { class: "row" }, h("span", { class: `tier ${r.tier.id}` }, TIER_ICON[r.tier.id] || "", " ", r.tier.label),
        h("span", { class: "small muted" }, `You found ${r.found} of the ${r.reference_edges_reachable} reference links between the concepts on your map. Green links match the reference.`)),
      r.missing.length ? h("div", { class: "small", style: "margin-top:10px" }, h("b", {}, "Links you could add: "),
        r.missing.slice(0, 6).map((m) => `${cap(m.src)} — ${m.label} — ${cap(m.dst)}`).join(" · ")) : null,
      r.links.some((l) => !l.in_reference) ? h("div", { class: "small faint", style: "margin-top:6px" },
        "Dashed links are not in the reference map. That does not make them wrong.") : null));
  }
  const refUnlocked = () => st.checked || DEV();
  const tabs = h("div", { class: "tabs" });
  // Tidy up: lay the learner's map out like the reference map (dagre), unlinked concepts in a row below, then glide there.
  function tidy() {
    if (typeof dagre === "undefined") return;
    const names = new Set(st.nodes.map((n) => n.name));
    const links = st.links.filter((l) => names.has(l.a) && names.has(l.b) && l.a !== l.b);
    const linked = new Set(links.flatMap((l) => [l.a, l.b]));
    const loose = st.nodes.filter((n) => !linked.has(n.name));
    const target = new Map();
    if (linked.size) {
      const lay = (dir) => {
        const G = new dagre.graphlib.Graph({ multigraph: true });
        G.setGraph({ rankdir: dir, nodesep: 30, ranksep: dir === "TB" ? 60 : 90, edgesep: 14 });
        G.setDefaultEdgeLabel(() => ({}));
        st.nodes.filter((n) => linked.has(n.name)).forEach((n) => { const b = nodeBox(n.name); G.setNode(n.name, { width: b.w, height: b.h }); });
        links.forEach((l, i) => G.setEdge(l.a, l.b, { label: l.label, width: (l.label || "").length * 6.4 + 14, height: 20, labelpos: "c" }, "e" + i));
        dagre.layout(G);
        return { G, fit: Math.abs(Math.log(G.graph().width / G.graph().height / (MW / (MH - (loose.length ? 90 : 0))))) };
      };
      const G = [lay("TB"), lay("LR")].sort((a, b) => a.fit - b.fit)[0].G;
      const gw = G.graph().width, gh = G.graph().height, room = MH - (loose.length ? 110 : 40);
      const k = Math.min(1.9, (MW - 160) / gw, room / gh);  // spread a small map out, shrink a big one
      G.nodes().forEach((id) => { const v = G.node(id); target.set(id, [MW / 2 + (v.x - gw / 2) * k, 20 + room / 2 + (v.y - gh / 2) * k]); });
    }
    const rowY = linked.size ? MH - 50 : MH / 2;
    const widths = loose.map((n) => nodeBox(n.name).w + 24), total = widths.reduce((a, b) => a + b, 0);
    let x = MW / 2 - Math.min(total, MW - 80) / 2;
    loose.forEach((n, i) => { target.set(n.name, [Math.min(MW - 70, x + widths[i] / 2), rowY]); x += widths[i]; });
    const from = new Map(st.nodes.map((n) => [n.name, [n.x, n.y]]));
    const end = () => { st.nodes.forEach((n) => { const t = target.get(n.name); if (t) { n.x = snap(t[0]); n.y = snap(t[1]); } }); save(); draw(); };
    if (matchMedia("(prefers-reduced-motion: reduce)").matches) return end();
    const t0 = performance.now(), D = 420;
    const step = (now) => {
      const u = Math.min(1, (now - t0) / D), e = 1 - Math.pow(1 - u, 3);
      st.nodes.forEach((n) => { const a = from.get(n.name), t = target.get(n.name); if (t) { n.x = a[0] + (snap(t[0]) - a[0]) * e; n.y = a[1] + (snap(t[1]) - a[1]) * e; } });
      draw();
      if (u < 1) requestAnimationFrame(step); else end();
    };
    requestAnimationFrame(step);
  }
  const mine = h("div", {}, h("div", { class: "cmap-tools" }, input, h("button", { onclick: addNode }, "Add"),
    h("button", { class: "ghost", title: "Arrange the concepts neatly", onclick: tidy }, "Tidy up"), h("span", { class: "spacer" }),
    h("button", { class: "ghost", onclick: () => { if (confirm("Start the map over?")) { store.set(key, null); route(); } } }, "Reset"), check),
    wrap, status, res);
  const refPane = h("div", { hidden: true });
  function drawTabs() {
    const t = (id, label, locked) => h("button", { class: "tab" + (tab === id ? " on" : ""), disabled: locked,
      title: locked ? "Check your map first to compare it with the reference" : "",
      onclick: () => { tab = id; mine.hidden = id !== "mine"; refPane.hidden = id !== "ref"; if (id === "ref" && !refPane.firstChild) refPane.append(referenceMap(cm, L)); drawTabs(); } },
      label, locked ? " 🔒" : "");
    tabs.replaceChildren(t("mine", "Your map", false), t("ref", "Reference map", !refUnlocked()));
  }
  wrap.append(svg);
  draw(); drawResult(); drawTabs();
  if (S.openRef && refUnlocked()) setTimeout(() => tabs.lastChild.click(), 0);
  return h("div", {}, head("Wrap-up", "Connect the ideas"),
    h("p", { class: "muted", style: "margin-top:-6px" }, cm.instructions),
    devPanel("How this map was made", devIntent(L, cm.intent || page.ph.intent),
      h("div", { class: "dev-kv" }, kv("reference", `${cm.reference_nodes.length} nodes, ${cm.reference_edges.length} edges in the LIR; the viewer draws the ${14}-node core`))),
    tabs, mine, refPane);
}

// ------------------------------------------------------------------ course map (end of the course)
// All the lectures' reference concept maps joined into one. No new content: nodes and links come from the LIR.
function courseGraph() {
  if (S.cgraph && S.cgraph.cid === S.cid) return S.cgraph;
  const goals = S.course.course_goals || [];
  const goalOf = {};
  goals.forEach((g, k) => g.lecture_ids.forEach((l) => { goalOf[l] = k; }));
  const nodes = new Map(), edges = new Map();
  S.order.forEach((lid) => {
    const cm = (S.lec[lid].phases[S.lec[lid].phases.length - 1] || {}).concept_map;
    if (!cm) return;
    cm.reference_nodes.forEach((n) => { if (!nodes.has(n.concept_id)) nodes.set(n.concept_id, { id: n.concept_id, name: cap(n.name), lid: n.lecture_id }); });
    cm.reference_edges.forEach((e) => { if (e.src !== e.dst) edges.set(e.src + ">" + e.dst, e); });
  });
  const E = [...edges.values()].filter((e) => nodes.has(e.src) && nodes.has(e.dst));
  E.forEach((e) => { for (const id of [e.src, e.dst]) { const n = nodes.get(id); n.deg = (n.deg || 0) + 1; } });
  const N = [...nodes.values()].filter((n) => n.deg);
  N.forEach((n) => {
    const c = S.concepts[n.id], intro = (c && c.introduced) || {};
    n.lid = intro.lecture_id || n.lid; n.t = intro.t; n.li = Math.max(0, S.order.indexOf(n.lid));
    n.goal = goalOf[n.lid] ?? -1; n.r = 4 + Math.sqrt(n.deg) * 2.2;
  });
  // force layout, done once per course: links pull, concepts push apart, each goal pulls its concepts into a region
  let seed = 7; const rnd = () => (seed = (seed * 16807) % 2147483647) / 2147483647;
  const G = Math.max(1, goals.length), R = 64 * Math.sqrt(N.length);
  const anchor = (k) => k < 0 ? [0, 0] : [R * Math.cos(-Math.PI / 2 + 2 * Math.PI * k / G), R * Math.sin(-Math.PI / 2 + 2 * Math.PI * k / G)];
  N.forEach((n) => { const [ax, ay] = anchor(n.goal), a = rnd() * 2 * Math.PI, d = rnd() * R * 0.45; n.x = ax + d * Math.cos(a); n.y = ay + d * Math.sin(a); n.vx = 0; n.vy = 0; });
  const byId = new Map(N.map((n) => [n.id, n]));
  const L = E.map((e) => [byId.get(e.src), byId.get(e.dst)]);
  for (let it = 0, IT = 300; it < IT; it++) {
    const alpha = 1 - it / IT;
    for (let i = 0; i < N.length; i++) {
      const a = N[i];
      for (let j = i + 1; j < N.length; j++) {
        const b = N[j]; let dx = b.x - a.x, dy = b.y - a.y, d2 = dx * dx + dy * dy;
        if (d2 > 160000) continue;
        if (d2 < 0.01) { dx = rnd() - 0.5; dy = rnd() - 0.5; d2 = 0.5; }
        const d = Math.sqrt(d2), min = a.r + b.r + 16;
        let f = 2600 * (0.35 + 0.65 * alpha) / d2;
        if (d < min) f += (min - d) * 0.5 / d;
        a.vx -= dx * f / d; a.vy -= dy * f / d; b.vx += dx * f / d; b.vy += dy * f / d;
      }
    }
    L.forEach(([a, b]) => {
      const dx = b.x - a.x, dy = b.y - a.y, d = Math.hypot(dx, dy) || 1, f = (d - 70) * 0.05;
      a.vx += dx / d * f; a.vy += dy / d * f; b.vx -= dx / d * f; b.vy -= dy / d * f;
    });
    N.forEach((n) => {
      const [ax, ay] = anchor(n.goal);
      n.vx += (ax - n.x) * 0.007; n.vy += (ay - n.y) * 0.007;
      n.vx *= 0.55; n.vy *= 0.55;
      const sp = Math.hypot(n.vx, n.vy), cap_ = 30 * alpha + 2;
      if (sp > cap_) { n.vx *= cap_ / sp; n.vy *= cap_ / sp; }
      n.x += n.vx; n.y += n.vy;
    });
  }
  const degs = N.map((n) => n.deg).sort((a, b) => b - a);
  const major = degs[Math.min(degs.length - 1, Math.max(8, Math.round(N.length * 0.07)))] || 1;
  N.forEach((n) => { n.tier = n.deg > major ? 0 : n.deg >= 2 ? 1 : 2; });
  const adj = new Map(N.map((n) => [n.id, []]));
  E.forEach((e) => { adj.get(e.src).push(e); adj.get(e.dst).push(e); });
  const regions = goals.map((g, k) => {
    const ns = N.filter((n) => n.goal === k);
    if (!ns.length) return null;
    const cx = ns.reduce((s_, n) => s_ + n.x, 0) / ns.length, cy = ns.reduce((s_, n) => s_ + n.y, 0) / ns.length;
    const ds = ns.map((n) => Math.hypot(n.x - cx, n.y - cy)).sort((a, b) => a - b);
    const rr = (ds[Math.floor(ds.length * 0.8)] || 40) + 34;
    const inside = ns.filter((n) => Math.hypot(n.x - cx, n.y - cy) <= rr);  // the goal's name sits above its highest concept inside the circle
    return { top: Math.min(cy - rr, ...inside.map((n) => n.y - n.r)) - 16, k, text: g.text.replace(/\s*\((L\d+(, )?)+\)\.?$/, "."), cx, cy, r: rr, ns };
  }).filter(Boolean);
  return (S.cgraph = { cid: S.cid, N, E, byId, adj, regions, goals });
}
// the smallest view box with the svg's own shape that holds the given points
function boxFor(pts, svg, pad = 60, minW = 260, coverFrac = 0) {
  const xs = pts.map((p) => p[0]), ys = pts.map((p) => p[1]);
  let x0 = Math.min(...xs) - pad, x1 = Math.max(...xs) + pad, y0 = Math.min(...ys) - pad, y1 = Math.max(...ys) + pad;
  const asp = (svg.clientWidth || 1200) * (1 - coverFrac) / (svg.clientHeight || 640);
  let w = Math.max(x1 - x0, minW), hh = Math.max(y1 - y0, minW / asp);
  if (w / hh > asp) hh = w / asp; else w = hh * asp;
  const cx = (x0 + x1) / 2, cy = (y0 + y1) / 2;
  return [cx - w / 2, cy - hh / 2, w / (1 - coverFrac), hh];  // the panel covers the right-hand part
}
function renderCourseMap() {
  cleanupPage();
  S.curLid = null;
  document.title = `Course map · ${S.course.title}`;
  const g = courseGraph();
  const top = h("div", { class: "topbar" },
    h("button", { class: "ghost", "aria-label": "Roadmap", title: "Back to the course roadmap", onclick: () => { location.hash = "#/"; } }, "←", h("span", { class: "long" }, " Roadmap")),
    h("span", { class: "title" }, "Course map"), h("span", { class: "spacer" }), devButton(), themeButton());
  const svg = s("svg", { class: "cmap course", role: "img", "aria-label": "Map of every concept in the course and how they link" });
  const wrap = h("div", { class: "cmap-wrap course-wrap" }, svg);
  const panel = h("aside", { class: "card cpanel", hidden: true });
  wrap.append(panel);
  const bg = s("rect", { class: "bg", x: -1e5, y: -1e5, width: 2e5, height: 2e5, fill: "transparent" });
  const layerR = s("g", {}), layerE = s("g", {}), layerN = s("g", {}), layerL = s("g", {}), layerT = s("g", {});
  svg.append(bg, layerR, layerE, layerN, layerL, layerT);  // labels sit above every dot
  const col = (k) => k < 0 ? "var(--muted)" : `var(--g${(k % 5) + 1})`;
  // regions: one soft disc per course goal; click to zoom into it
  const regionEls = g.regions.map((r) => {
    const el = s("g", { class: "region", style: `--c:${col(r.k)}` }, s("circle", { cx: r.cx, cy: r.cy, r: r.r }));
    // the goal's name goes in the top layer so dots never cover it
    layerT.append(s("text", { class: "rlabel", style: `--c:${col(r.k)}`, x: r.cx, y: Math.min(r.cy - r.r - 8, r.top), "text-anchor": "middle" }, `Goal ${r.k + 1}`));
    el.append(s("title", {}, `Goal ${r.k + 1}: ${r.text} (click to zoom in)`));
    el.addEventListener("click", () => { if (!pz.moved()) showGoal(r.k); });
    layerR.append(el);
    return el;
  });
  const edgeEls = g.E.map((e) => {
    const a = g.byId.get(e.src), b = g.byId.get(e.dst);
    const ln = s("line", { class: "cl", x1: a.x, y1: a.y, x2: b.x, y2: b.y });
    ln.dataset.a = e.src; ln.dataset.b = e.dst;
    const lb = s("text", { class: "elabel", x: (a.x + b.x) / 2, y: (a.y + b.y) / 2, "text-anchor": "middle" }, e.label || "");
    lb.dataset.a = e.src; lb.dataset.b = e.dst;
    layerE.append(ln); layerT.append(lb);
    return { e, ln, lb };
  });
  const nodeEls = new Map(), labelEls = new Map();
  g.N.forEach((n) => {
    const el = s("g", { class: `cn t${n.tier}`, transform: `translate(${n.x},${n.y})`, style: `--c:${col(n.goal)};--r:${n.r}` },
      s("circle", { r: n.r }));
    const lb = s("g", { class: `cn-l t${n.tier}`, transform: `translate(${n.x},${n.y})`, style: `--r:${n.r}` },
      s("text", { class: "nlabel", y: 0, "text-anchor": "middle" }, n.name));
    layerL.append(lb); labelEls.set(n.id, lb);
    el.dataset.id = n.id;
    el.addEventListener("pointerenter", () => { if (!sel) focus(n.id); });
    el.addEventListener("pointerleave", () => { if (!sel) unfocus(); });
    el.addEventListener("click", () => { if (!pz.moved()) select(n.id, true); });
    layerN.append(el); nodeEls.set(n.id, el);
  });
  let sel = null, upTo = S.order.length - 1, goalPick = null, focusSet = null, focusId = null;
  function focus(id) {
    const near = new Set([id]);
    const me = g.byId.get(id);
    edgeEls.forEach(({ e, ln, lb }) => {
      const hot = e.src === id || e.dst === id;
      ln.classList.toggle("hot", hot); lb.classList.toggle("hot", hot);
      if (hot) {
        near.add(e.src); near.add(e.dst);
      }
    });
    nodeEls.forEach((el, k) => { el.classList.toggle("hot", near.has(k)); el.classList.toggle("me", k === id); });
    labelEls.forEach((el, k) => el.classList.toggle("hot", near.has(k)));
    focusSet = near; focusId = id;
    placeLabels(pz.view());
    svg.classList.add("focusing");
    return near;
  }
  function unfocus() { svg.classList.remove("focusing"); focusSet = null; focusId = null; placeLabels(pz.view()); }
  const fullBox = () => boxFor([...g.N.map((n) => [n.x, n.y]), ...g.regions.flatMap((r) => [[r.cx - r.r, Math.min(r.cy - r.r, r.top) - 30], [r.cx + r.r, r.cy + r.r]])], svg, 30);
  const cover = () => (innerWidth > 760 ? Math.min(0.45, 384 / (svg.clientWidth || 1200)) : 0);
  function select(id, zoom) {
    sel = id;
    const near = focus(id), n = g.byId.get(id);
    if (zoom) pz.to(boxFor([...near].map((k) => [g.byId.get(k).x, g.byId.get(k).y]), svg, 90, 420, cover()));
    const c = S.concepts[id] || {}, L = S.lec[n.lid];
    const rel = g.adj.get(id).map((e) => {
      const out = e.src === id, other = g.byId.get(out ? e.dst : e.src);
      const name = h("button", { class: "linklike", onclick: () => select(other.id, true) }, other.name);
      return h("li", {}, out ? [h("span", { class: "muted" }, "→ " + (e.label || "links to") + " → "), name]
        : [name, h("span", { class: "muted" }, " → " + (e.label || "links to") + " → this")]);
    });
    panel.replaceChildren(
      h("button", { class: "ghost small close", "aria-label": "Close", onclick: clearSel }, "✕"),
      h("div", { class: "kicker", style: `color:${col(n.goal)}` }, n.goal >= 0 ? `Goal ${n.goal + 1}` : "Concept"),
      h("h3", {}, n.name),
      c.definition ? h("p", {}, c.definition) : null,
      L ? h("div", { class: "taught" }, h("span", { class: "small muted" }, "Taught in "),
        n.t != null ? timeLink(n.lid, n.t, `${lectureName(n.lid)} · ${L.title}, ${clock(n.t)}`) : h("b", {}, `${lectureName(n.lid)} · ${L.title}`)) : null,
      rel.length ? h("div", {}, h("div", { class: "small muted", style: "margin:12px 0 4px" }, "Linked to"), h("ul", { class: "rels" }, rel)) : null);
    panel.hidden = false;
  }
  function clearSel() { sel = null; unfocus(); panel.hidden = true; }
  function showGoal(k) {
    goalPick = k; drawChips(); clearSel();
    const r = g.regions.find((x) => x.k === k);
    if (r) {
      pz.to(boxFor(r.ns.map((n) => [n.x, n.y]), svg, 70, 420, cover()));
      panel.replaceChildren(h("button", { class: "ghost small close", "aria-label": "Close", onclick: () => { panel.hidden = true; } }, "✕"),
        h("div", { class: "kicker", style: `color:${col(k)}` }, `Goal ${k + 1}`), h("p", {}, r.text),
        h("p", { class: "small muted" }, "Click a concept to see what it means and where it was taught."));
      panel.hidden = false;
    }
    applyFilters();
  }
  function applyFilters() {
    nodeEls.forEach((el, k) => {
      const n = g.byId.get(k);
      el.classList.toggle("later", n.li > upTo);
      el.classList.toggle("dim", goalPick != null && n.goal !== goalPick);
      labelEls.get(k).classList.toggle("later", n.li > upTo);
    });
    edgeEls.forEach(({ e, ln, lb }) => {
      const later = g.byId.get(e.src).li > upTo || g.byId.get(e.dst).li > upTo;
      ln.classList.toggle("later", later); lb.classList.toggle("later", later);
    });
    regionEls.forEach((el, i) => el.classList.toggle("dim", goalPick != null && g.regions[i].k !== goalPick));
    placeLabels(pz.view());
  }
  // labels keep one size on screen; more of them appear as you zoom in
  let full = null, lraf = 0;
  const byDeg = g.N.slice().sort((a, b) => b.deg - a.deg);
  // Labels: most-linked first, never on top of each other, each tries below / above / right / left of its dot.
  // More fit as you zoom in. While a concept is in focus, only it, its neighbours and their link labels are placed.
  const placeLabels = (v) => {
    if (!v) return;
    const W = svg.clientWidth || 1200, H = svg.clientHeight || 640, u = v[2] / W, z = full ? full[2] / v[2] : 1;
    const maxTier = z < 1.6 ? 0 : z < 3 ? 1 : 2, boxes = [];
    const free = (b) => b[2] > 0 && b[0] < W && b[3] > 0 && b[1] < H && !boxes.some((o) => b[0] < o[2] && b[2] > o[0] && b[1] < o[3] && b[3] > o[1]);
    if (!focusSet) g.regions.forEach((r) => {  // goal names are fixed; concept labels keep clear of them
      const sx = (r.cx - v[0]) / u, sy = (Math.min(r.cy - r.r - 8, r.top) - v[1]) / u;
      boxes.push([sx - 44, sy - 13, sx + 44, sy + 4]);
    });
    const order = focusSet ? [g.byId.get(focusId), ...byDeg.filter((n) => focusSet.has(n.id) && n.id !== focusId)] : byDeg;
    const shown = new Set();
    order.forEach((n) => {
      if (!focusSet && !(n.tier <= maxTier && n.li <= upTo && !(goalPick != null && n.goal !== goalPick))) return;
      const sx = (n.x - v[0]) / u, sy = (n.y - v[1]) / u, rr = n.r * 0.9 + 4, w = n.name.length * 6.7 + 8;
      for (const [dx, dy, anc] of [[0, rr + 12, "middle"], [0, -rr - 4, "middle"], [rr + 2, 4, "start"], [-rr - 2, 4, "end"]]) {
        const x0 = anc === "middle" ? sx + dx - w / 2 : anc === "start" ? sx + dx : sx + dx - w;
        const b = [x0, sy + dy - 12, x0 + w, sy + dy + 4];
        if (free(b)) {
          boxes.push(b); shown.add(n.id);
          const t = labelEls.get(n.id).firstChild;
          t.setAttribute("x", dx * u); t.setAttribute("y", dy * u); t.setAttribute("text-anchor", anc);
          break;
        }
      }
    });
    labelEls.forEach((el, k) => el.firstChild.classList.toggle("show", shown.has(k)));
    if (!focusSet) return;
    const me = g.byId.get(focusId);
    edgeEls.forEach(({ lb }) => {
      if (!lb.classList.contains("hot")) return;
      const o = g.byId.get(lb.dataset.a === focusId ? lb.dataset.b : lb.dataset.a), w = lb.textContent.length * 6.2 + 8;
      let ok = false;
      for (const t of [0.55, 0.4, 0.7, 0.3, 0.8, 0.48, 0.62]) {
        const x = me.x + (o.x - me.x) * t, y = me.y + (o.y - me.y) * t, sx = (x - v[0]) / u, sy = (y - v[1]) / u;
        const b = [sx - w / 2, sy - 12, sx + w / 2, sy + 4];
        if (free(b)) { lb.setAttribute("x", x); lb.setAttribute("y", y); boxes.push(b); ok = true; break; }
      }
      lb.classList.toggle("show", ok);  // no room: the side panel still lists the link
    });
  };
  const onView = (v) => {
    svg.style.setProperty("--u", (v[2] / (svg.clientWidth || 1200)).toFixed(4));
    cancelAnimationFrame(lraf); lraf = requestAnimationFrame(() => placeLabels(v));
  };
  const pz = panZoom(svg, [-600, -400, 1200, 800], onView);
  bg.addEventListener("click", () => { if (!pz.moved() && sel) clearSel(); });
  listen(document, "keydown", (e) => { if (e.key === "Escape") { clearSel(); goalPick = null; drawChips(); applyFilters(); pz.to(full); } });
  // controls
  const names = h("datalist", { id: "cm-names" }, g.N.slice().sort((a, b) => a.name.localeCompare(b.name)).map((n) => h("option", { value: n.name })));
  const find = h("input", { type: "text", class: "cm-find", placeholder: "Find a concept…", list: "cm-names", "aria-label": "Find a concept" });
  const doFind = () => {
    const q = find.value.trim().toLowerCase();
    if (!q) return;
    const n = g.N.find((x) => x.name.toLowerCase() === q) || g.N.find((x) => x.name.toLowerCase().startsWith(q)) || g.N.find((x) => x.name.toLowerCase().includes(q));
    if (!n) return toast("Not on the map");
    if (n.li > upTo) { upTo = S.order.length - 1; slider.value = upTo; sliderLabel(); applyFilters(); }
    select(n.id, true);
  };
  find.addEventListener("change", doFind);
  find.addEventListener("keydown", (e) => { if (e.key === "Enter") doFind(); });
  const chips = h("div", { class: "goal-chips" });
  function drawChips() {
    chips.replaceChildren(h("span", { class: "small muted" }, "Course goal"),
      [null, ...g.goals.map((_, k) => k)].map((k) => h("button", { class: "chip" + (goalPick === k ? " on" : ""), title: k == null ? "Whole course" : g.goals[k].text,
        style: k == null ? "" : `--c:${col(k)}`, onclick: () => {
          if (k == null) { goalPick = null; drawChips(); applyFilters(); clearSel(); pz.to(full); } else showGoal(k);
        } }, k == null ? "All" : h("span", {}, h("i", { class: "sw" }), String(k + 1)))));
  }
  const slider = h("input", { type: "range", min: 0, max: S.order.length - 1, value: upTo, "aria-label": "Show concepts taught up to this lecture" });
  const sLabel = h("span", { class: "small mono" });
  const sliderLabel = () => { sLabel.textContent = Number(slider.value) === S.order.length - 1 ? "All lectures" : `Up to ${lectureName(S.order[slider.value])}`; };
  slider.addEventListener("input", () => { upTo = Number(slider.value); sliderLabel(); applyFilters(); });
  let playing = 0;
  const play = h("button", { class: "ghost small", title: "Watch the map grow, lecture by lecture" }, "▶ Grow");
  play.onclick = () => {
    if (playing) { clearInterval(playing); playing = 0; play.textContent = "▶ Grow"; return; }
    if (matchMedia("(prefers-reduced-motion: reduce)").matches) { upTo = S.order.length - 1; slider.value = upTo; sliderLabel(); return applyFilters(); }
    upTo = 0; play.textContent = "❚❚ Pause";
    const tick = () => {
      slider.value = upTo; sliderLabel(); applyFilters();
      if (upTo >= S.order.length - 1) { clearInterval(playing); playing = 0; play.textContent = "▶ Grow"; } else upTo++;
    };
    tick(); playing = setInterval(tick, Math.max(90, 6000 / S.order.length));
  };
  onLeave(() => clearInterval(playing));
  sliderLabel(); drawChips();
  const zoomBtns = h("div", { class: "zoom-btns" },
    h("button", { class: "ghost small", "aria-label": "Zoom in", onclick: () => pz.zoom(0.7) }, "+"),
    h("button", { class: "ghost small", "aria-label": "Zoom out", onclick: () => pz.zoom(1 / 0.7) }, "−"),
    h("button", { class: "ghost small", onclick: () => { clearSel(); pz.to(full); } }, "Fit"));
  wrap.append(zoomBtns);
  const legend = h("div", { class: "row small muted cm-legend" },
    h("span", {}, "Each dot is a concept; bigger dots have more links. Colour shows the course goal it serves."),
    h("span", {}, "Click a goal or a concept to zoom in; Esc or Fit to see the whole course."));
  const lastLid = S.order[S.order.length - 1];
  const content = h("div", { class: "course-map page-in" },
    head("The whole course", "Everything you learned, connected"),
    h("p", { class: "muted", style: "margin-top:-6px;max-width:80ch" },
      "The concept maps of every lecture, joined into one. Concepts from different lectures meet where the course linked them."),
    devPanel("How this map was made", h("div", { class: "dev-kv" },
      kv("source", "union of every lecture's reference concept map (no generation)"),
      kv("size", `${g.N.length} linked concepts, ${g.E.length} links, ${g.regions.length} goal regions`),
      kv("layout", "force layout in the browser, each goal pulls its concepts into a region"))),
    h("div", { class: "cmap-tools course-tools" }, find, chips, h("span", { class: "spacer" }), h("div", { class: "grow" }, play, slider, sLabel)),
    wrap, legend, names,
    h("div", { class: "nav" },
      h("button", { onclick: () => go(lastLid, pages(S.lec[lastLid]).length - 1) }, "◂ Back"),
      h("button", { class: "primary", onclick: () => { prefs.set("courseMapSeen:" + S.cid, true); location.hash = "#/"; } }, "Finish course ✓")));
  $("#app").replaceChildren(top, h("div", { class: "wrap wide" }, content));
  // fit once the svg has its size
  requestAnimationFrame(() => { full = fullBox(); pz.to(full, 0); onView(full); });
  window.scrollTo(0, 0);
}

boot();
