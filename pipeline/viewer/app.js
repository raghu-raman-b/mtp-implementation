/* v3 course viewer: the lectures with their segments, the knowledge layer (concepts, facts, goals, the lecture graph),
 * the activities, and a question box. Served by serve.py; no build step.
 *
 * Routes   #/                          course home
 *          #/lecture/<key>[/<tab>]     a lecture (tabs: overview, concepts, map, before, activities)
 *          #/lecture/<key>/t/<sec>     ... and seek the video there
 *          #/concept/<C0042>           a concept card
 *          #/glossary  #/map  #/review
 * Every layer is optional: a lecture without knowledge/ shows its 1b segments and the 0a transcript only.
 * Developer mode (?dev=1 or the toggle) shows IDs, counts and where things came from.
 */
"use strict";

const S = { course: null, K: null, Kp: null, lec: {}, view: null, review: null, qa: [] };
const KINDS = [["introduced", "Introduced here"], ["met_again", "Met again"], ["assumed", "Assumed (not taught in the course)"],
  ["defined_later", "Explained in a later lecture"]];

// ------------------------------------------------------------------ helpers
// append / replaceChildren take nested arrays and skip null and false, as h() does
for (const m of ["append", "replaceChildren", "prepend"]) {
  const orig = Element.prototype[m];
  Element.prototype[m] = function (...kids) {
    return orig.apply(this, kids.flat(Infinity).filter((k) => k != null && k !== false));
  };
}
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
const SVG = "http://www.w3.org/2000/svg";
function s(tag, attrs, ...kids) {
  const el = document.createElementNS(SVG, tag);
  for (const [k, v] of Object.entries(attrs || {})) if (v != null) el.setAttribute(k, v);
  for (const k of kids.flat(Infinity)) if (k != null) el.append(k.nodeType ? k : document.createTextNode(String(k)));
  return el;
}
const $ = (sel, root = document) => root.querySelector(sel);
function clock(t) {
  t = Math.max(0, Math.floor(t || 0));
  const hh = Math.floor(t / 3600), m = Math.floor((t % 3600) / 60), sec = t % 60;
  return (hh ? hh + ":" + String(m).padStart(2, "0") : m) + ":" + String(sec).padStart(2, "0");
}
const cap = (x) => (!x ? x : /^[a-z][A-Z]/.test(x) ? x : x[0].toUpperCase() + x.slice(1));
const dev = (...kids) => h("span", { class: "dev" }, ...kids);
function store(key, val) {
  try {
    if (val === undefined) { const v = localStorage.getItem("v3:" + key); return v == null ? null : JSON.parse(v); }
    localStorage.setItem("v3:" + key, JSON.stringify(val));
  } catch (e) { /* private window or blocked storage: nothing is kept */ }
  return null;
}
function hashSeed(str) { let x = 2166136261; for (const c of str) x = Math.imul(x ^ c.charCodeAt(0), 16777619); return x >>> 0; }
function shuffled(arr, seed) {  // a stable shuffle (the same page shows the same order)
  let x = hashSeed(String(seed)) || 1;
  const rnd = () => ((x = Math.imul(x ^ (x >>> 15), 2246822507) ^ Math.imul(x ^ (x >>> 13), 3266489909)) >>> 0) / 4294967296;
  const a = arr.slice();
  for (let i = a.length - 1; i > 0; i--) { const j = Math.floor(rnd() * (i + 1)); [a[i], a[j]] = [a[j], a[i]]; }
  return a;
}
async function getJSON(url) {
  const r = await fetch(url);
  if (!r.ok) return null;
  return r.json();
}

// ------------------------------------------------------------------ data
async function knowledge() {  // the course-wide knowledge files, loaded once (null when the layer is absent)
  if (!S.course.layers.knowledge) return null;
  if (!S.Kp) {
    S.Kp = Promise.all(["concepts", "facts", "relations", "lecture_graph"].map((f) => getJSON(`/data/knowledge/${f}.json`)))
      .then(([concepts, facts, relations, graph]) => (S.K = { concepts: concepts || {}, facts: facts || {}, relations: relations || {}, graph: graph || {} }));
  }
  return S.Kp;
}
async function lecture(key) {
  if (!S.lec[key]) S.lec[key] = await getJSON(`/api/lecture/${encodeURIComponent(key)}`);
  return S.lec[key];
}
const lecInfo = (k) => S.course.lectures.find((l) => l.key === k) || { key: k, title: `Lecture ${k}` };
const concept = (cid) => (S.K && S.K.concepts[cid]) || null;
const cname = (cid) => cap((concept(cid) || {}).name || cid);
const fact = (fid) => (S.K && S.K.facts[fid]) || null;

// ------------------------------------------------------------------ links
function timeHref(lec, t) { return `#/lecture/${lec}/t/${Math.round((t || 0) * 10) / 10}`; }

// ---- answers: a small, safe markdown renderer (DOM nodes only, never innerHTML) ----
// paragraphs, "* "/"- " and "1. " lists, **bold**, *italic*, `code`, $math$ shown plain; "(lecture 4, 6:01)" and
// "(lecture 4, 6:01; lecture 5, 9:21)" become links that open the lecture at that time.
function mdInline(text) {
  const out = [];
  const re = /\*\*([^*]+)\*\*|\*([^*\s][^*]*)\*|`([^`]+)`|\$([^$]+)\$|lecture (\d+[a-z]?), (\d{1,2}(?::\d{2}){1,2})/g;
  let last = 0, m;
  while ((m = re.exec(text))) {
    if (m.index > last) out.push(text.slice(last, m.index));
    if (m[1] != null) out.push(h("b", {}, m[1]));
    else if (m[2] != null) out.push(h("i", {}, m[2]));
    else if (m[3] != null) out.push(h("code", {}, m[3]));
    else if (m[4] != null) out.push(m[4].replace(/\\(text|mathrm)\{([^}]*)\}/g, "$2").replace(/\\/g, ""));
    else {
      const parts = m[6].split(":").map(Number), secs = parts.reduce((a, b) => a * 60 + b, 0);
      out.push(h("a", { class: "time", href: timeHref(m[5], secs) }, `lecture ${m[5]}, ${m[6]}`));
    }
    last = re.lastIndex;
  }
  if (last < text.length) out.push(text.slice(last));
  return out;
}
function mdBlock(text) {
  const box = h("div", { class: "qa-a" });
  let list = null, para = [];
  const flush = () => { if (para.length) { box.append(h("p", {}, ...mdInline(para.join(" ")))); para = []; } };
  for (const raw of String(text || "").split("\n")) {
    const line = raw.trim();
    const bullet = line.match(/^(?:[*\-•]|\d+[.)])\s+(.*)$/);
    if (bullet) {
      flush();
      const ordered = /^\d/.test(line);
      if (!list || list.ordered !== ordered) { list = { ordered, el: h(ordered ? "ol" : "ul", {}) }; box.append(list.el); }
      list.el.append(h("li", {}, ...mdInline(bullet[1])));
    } else if (!line) { flush(); list = null; }
    else { list = null; para.push(line.replace(/^#+\s*/, "")); }
  }
  flush();
  return box;
}
function timeLink(lec, t, here) {
  const label = here === lec ? clock(t) : `Lecture ${lec} · ${clock(t)}`;
  return h("a", { class: "time", href: timeHref(lec, t), title: "Watch from here" }, "▶ " + label);
}
function conceptPill(cid, kind) {
  const c = concept(cid);
  return h("a", { class: "pill" + (kind ? " k-" + kind : ""), href: `#/concept/${cid}`, title: c && c.definition ? c.definition : null },
    cname(cid), dev(" " + cid));
}
function factLinks(fids, here) {
  const fs = (fids || []).map((f) => [f, fact(f)]).filter(([, x]) => x);
  if (!fs.length) return (fids || []).length ? h("div", { class: "fact-links" }, dev("facts: " + fids.join(", "))) : null;
  return h("div", { class: "fact-links small" }, h("span", { class: "faint" }, "Taught at:"),
    fs.map(([f, x]) => h("span", { title: x.text }, timeLink(x.lecture, x.start, here), dev(" " + f))));
}
function factList(fids, here, defining) {
  const set = new Set(defining || []);
  return h("ul", { class: "facts" }, (fids || []).map((f) => {
    const x = fact(f);
    if (!x) return h("li", {}, h("span", { class: "tx faint" }, f));
    return h("li", { class: set.has(f) ? "defining" : "" }, h("span", { class: "tx" }, x.text), dev(f), timeLink(x.lecture, x.start, here));
  }));
}

// ------------------------------------------------------------------ concept maps (dagre layout, pan and zoom)
function textWidth(t, size = 13) { return Math.max(30, t.length * size * 0.56); }
function drawMap(nodes, edges, opts = {}) {
  const wrap = h("div", { class: "cmap-wrap" });
  if (typeof dagre === "undefined") return h("div", { class: "note" }, "The map cannot be drawn (layout library missing).");
  if (!nodes.length) return h("div", { class: "faint" }, opts.empty || "Nothing to draw.");
  const G = new dagre.graphlib.Graph({ multigraph: true });
  G.setGraph({ rankdir: opts.dir || (nodes.length > 14 ? "LR" : "TB"), nodesep: 22, ranksep: 60, edgesep: 14, marginx: 20, marginy: 20 });
  G.setDefaultEdgeLabel(() => ({}));
  for (const n of nodes) G.setNode(n.id, { width: textWidth(n.label) + 24, height: 34, n });
  edges.forEach((e, i) => {
    if (!G.hasNode(e.from) || !G.hasNode(e.to)) return;
    G.setEdge(e.from, e.to, { label: e.label, width: e.label ? textWidth(e.label, 11.5) + 10 : 1, height: e.label ? 18 : 1, labelpos: "c", e }, "e" + i);
  });
  dagre.layout(G);
  const gw = G.graph().width, gh = G.graph().height;
  const svg = s("svg", { class: "cmap", role: "img" });
  svg.append(s("defs", {}, s("marker", { id: "arr", viewBox: "0 0 10 10", refX: 9, refY: 5, markerWidth: 7, markerHeight: 7, orient: "auto-start-reverse" },
    s("path", { d: "M0,0 L10,5 L0,10 z", class: "arrowhead" }))));
  const curve = (pts) => {
    let d = `M${pts[0].x},${pts[0].y}`;
    for (let i = 1; i < pts.length - 1; i++) {
      const mx = (pts[i].x + pts[i + 1].x) / 2, my = (pts[i].y + pts[i + 1].y) / 2;
      d += ` Q${pts[i].x},${pts[i].y} ${mx},${my}`;
    }
    const l = pts[pts.length - 1];
    return d + ` L${l.x},${l.y}`;
  };
  const els = { node: {}, edge: [] };
  for (const k of G.edges()) {
    const ed = G.edge(k);
    const p = s("path", { class: "edge", d: curve(ed.points), "marker-end": "url(#arr)" });
    svg.append(p);
    els.edge.push({ a: k.v, b: k.w, el: p });
  }
  for (const k of G.edges()) {
    const ed = G.edge(k);
    if (!ed.label) continue;
    const w = textWidth(ed.label, 11.5) + 10;
    const g = s("g", { class: "elabel" + (ed.e.cls ? " " + ed.e.cls : ""), transform: `translate(${ed.x},${ed.y})` },
      s("rect", { x: -w / 2, y: -9, width: w, height: 18, rx: 4 }), s("text", { "text-anchor": "middle", y: 4 }, ed.label));
    if (ed.e.title) g.append(s("title", {}, ed.e.title));
    svg.append(g);
    els.edge.push({ a: k.v, b: k.w, el: g });
  }
  for (const id of G.nodes()) {
    const v = G.node(id), n = v.n;
    const g = s("g", { class: "node" + (n.cls ? " " + n.cls : ""), transform: `translate(${v.x},${v.y})`, tabindex: 0 },
      s("rect", { x: -v.width / 2, y: -v.height / 2, width: v.width, height: v.height, rx: 9 }),
      s("text", { "text-anchor": "middle", y: 4.5 }, n.label));
    if (n.title) g.append(s("title", {}, n.title));
    if (opts.onNode) {
      g.addEventListener("click", (ev) => { if (!wrap._dragged) opts.onNode(id, ev); });
      g.addEventListener("keydown", (ev) => { if (ev.key === "Enter") opts.onNode(id, ev); });
    }
    svg.append(g);
    els.node[id] = g;
  }
  // pan and zoom on the viewBox
  const H = opts.height || Math.min(620, Math.max(220, gh * Math.min(1, 1100 / Math.max(gw, 1)) + 20));
  let vb;
  const fit = () => {  // never enlarge a small map by more than about 1.2 (the box is about 1200 px wide)
    const w = Math.max(gw, 1000), hh = Math.max(gh, w * H / 1200);
    vb = [(gw - w) / 2, (gh - hh) / 2, w, hh]; apply();
  };
  const apply = () => svg.setAttribute("viewBox", vb.join(" "));
  svg.style.height = H + "px";
  svg.addEventListener("wheel", (ev) => {
    if (!ev.ctrlKey && !ev.metaKey && !opts.wheel) return;  // plain scrolling keeps scrolling the page
    ev.preventDefault();
    const r = svg.getBoundingClientRect(), k = ev.deltaY > 0 ? 1.15 : 1 / 1.15;
    const px = vb[0] + (ev.clientX - r.left) / r.width * vb[2], py = vb[1] + (ev.clientY - r.top) / r.height * vb[3];
    vb = [px - (px - vb[0]) * k, py - (py - vb[1]) * k, vb[2] * k, vb[3] * k]; apply();
  }, { passive: false });
  let drag = null;
  svg.addEventListener("pointerdown", (ev) => { drag = { x: ev.clientX, y: ev.clientY, vb: vb.slice() }; wrap._dragged = false; });
  window.addEventListener("pointermove", (ev) => {
    if (!drag) return;
    const r = svg.getBoundingClientRect(), sc = Math.max(vb[2] / r.width, vb[3] / r.height);
    const dx = ev.clientX - drag.x, dy = ev.clientY - drag.y;
    if (Math.abs(dx) + Math.abs(dy) > 4) wrap._dragged = true;
    vb = [drag.vb[0] - dx * sc, drag.vb[1] - dy * sc, vb[2], vb[3]]; apply();
  });
  window.addEventListener("pointerup", () => { drag = null; setTimeout(() => (wrap._dragged = false), 0); });
  const zoom = (k) => { const cx = vb[0] + vb[2] / 2, cy = vb[1] + vb[3] / 2; vb = [cx - vb[2] * k / 2, cy - vb[3] * k / 2, vb[2] * k, vb[3] * k]; apply(); };
  fit();
  wrap.append(svg, h("div", { class: "map-tools" },
    h("button", { class: "small", onclick: () => zoom(1 / 1.25), title: "Zoom in" }, "+"),
    h("button", { class: "small", onclick: () => zoom(1.25), title: "Zoom out" }, "−"),
    h("button", { class: "small", onclick: fit }, "Fit")));
  wrap.focusNode = (id) => {  // highlight a node and its neighbours, and centre on it
    const near = new Set(id ? [id] : []);
    els.edge.forEach((e) => { if (e.a === id || e.b === id) { near.add(e.a); near.add(e.b); } });
    for (const [nid, el] of Object.entries(els.node)) { el.classList.toggle("dim", !!id && !near.has(nid)); el.classList.toggle("hit", nid === id); }
    els.edge.forEach((e) => e.el.classList.toggle("dim", !!id && !(e.a === id || e.b === id)));
    if (id && G.node(id)) { const v = G.node(id); const w = Math.min(vb[2], 900), hh = w * (vb[3] / vb[2]); vb = [v.x - w / 2, v.y - hh / 2, w, hh]; apply(); }
  };
  return wrap;
}
function mapLegend() {
  return h("div", { class: "legend" },
    h("span", {}, h("i", { style: "border-color:var(--k-intro)" }), "Introduced in this lecture"),
    h("span", {}, h("i", { style: "border-color:var(--k-again)" }), "Met again"),
    h("span", {}, h("i", { style: "border-color:var(--k-assumed);border-style:dashed" }), "Assumed"),
    h("span", { class: "faint" }, "Click a concept to open its card. Drag to move; Ctrl + scroll to zoom."));
}

// ------------------------------------------------------------------ router
function route() {
  const parts = location.hash.replace(/^#\/?/, "").split("/").filter(Boolean).map(decodeURIComponent);
  return { page: parts[0] || "home", arg: parts[1], rest: parts.slice(2) };
}
async function render() {
  const r = route();
  document.querySelectorAll(".nav a").forEach((a) => a.classList.toggle("on", a.getAttribute("href") === "#/" + (r.page === "home" ? "" : r.page)));
  if (r.page === "lecture" && S.view && S.view.lecture === r.arg && document.body.contains(S.view.root)) {
    if (r.rest[0] === "t") { S.view.seek(parseFloat(r.rest[1])); return; }
    S.view.showTab(r.rest[0] || S.view.tab); return;
  }
  if (S.view && S.view.stop) S.view.stop();
  S.view = null;
  const app = $("#app");
  app.replaceChildren(h("div", { class: "empty" }, h("span", { class: "spin" }), " Loading…"));
  try {
    await knowledge();
    let el;
    if (r.page === "lecture") el = await pageLecture(r.arg, r.rest);
    else if (r.page === "concept") el = pageConcept(r.arg);
    else if (r.page === "glossary") el = pageGlossary();
    else if (r.page === "map") el = pageMap(r.arg);
    else if (r.page === "review") el = await pageReview();
    else el = pageHome();
    app.replaceChildren(el);
    if (!(r.page === "lecture" && r.rest[0] === "t")) window.scrollTo(0, 0);
  } catch (e) {
    console.error(e);
    app.replaceChildren(h("div", { class: "empty" }, "This page could not be shown.", dev(" " + e)));
  }
}

// ------------------------------------------------------------------ home
function pageHome() {
  const C = S.course, m = C.meta || {}, goals = (C.goals && C.goals.course_goals) || {};
  const weeks = {};
  for (const l of C.lectures) (weeks[l.week || ""] = weeks[l.week || ""] || []).push(l);
  const theme = (w) => ((m.syllabus || []).find((x) => String(x.week) === String(w)) || {}).theme;
  const before = h("div", {});
  const sel = h("select", { onchange: () => showBefore() }, C.lectures.map((l) => h("option", { value: l.key }, `Lecture ${l.key}: ${l.title}`)));
  const showBefore = () => before.replaceChildren(beforeLecture(sel.value, true));
  if (C.lectures.length > 1) sel.value = C.lectures[Math.min(4, C.lectures.length - 1)].key;
  showBefore();
  return h("div", {},
    h("div", { class: "hero" },
      h("h1", {}, C.title),
      h("div", { class: "sub" }, [m.platform, m.institution, m.instructor && m.instructor.name].filter(Boolean).join(" · ")),
      m.outline ? h("details", { class: "small muted", style: "margin-top:8px;max-width:900px" }, h("summary", {}, "About this course"), h("p", {}, m.outline),
        m.prerequisites ? h("p", {}, h("b", {}, "Background: "), m.prerequisites) : null) : null),
    devHome(),
    Object.keys(goals).length ? h("div", { class: "section" }, h("h2", {}, "What this course will give you"),
      h("div", { class: "goals" }, Object.entries(goals).map(([gid, g]) => h("div", { class: "card" },
        h("div", { class: "goal" }, g.goal), g.achieves ? h("div", { class: "achieves" }, g.achieves) : null,
        h("div", { class: "chips small", style: "margin-top:8px" }, (g.lectures || []).map((k) => h("a", { class: "pill", href: `#/lecture/${k}`, title: lecInfo(k).title }, `Lecture ${k}`))),
        dev(gid))))) : null,
    h("div", { class: "section row" },
      h("a", { class: "card", href: "#/glossary", style: "flex:1;min-width:220px" }, h("h3", {}, "Glossary"), h("div", { class: "muted small" }, "Every concept of the course, with its definition and where it is taught.")),
      h("a", { class: "card", href: "#/map", style: "flex:1;min-width:220px" }, h("h3", {}, "Concept map"), h("div", { class: "muted small" }, "How the concepts of the course relate, and how the lectures build on each other.")),
      C.layers.spaced_review ? h("a", { class: "card", href: "#/review", style: "flex:1;min-width:220px" }, h("h3", {}, "Review cards"), h("div", { class: "muted small" }, "Short daily reviews, scheduled for you.")) : null),
    S.K ? h("div", { class: "section card" }, h("div", { class: "row" }, h("h2", { style: "margin:0" }, "What you need before"), sel), before) : null,
    h("div", { class: "section" }, h("h2", {}, "Lectures"),
      Object.entries(weeks).map(([w, ls]) => h("div", { class: "week" },
        h("h3", {}, w ? `Week ${w}` + (theme(w) ? ` · ${theme(w)}` : "") : "Other"),
        h("div", { class: "lecs" }, ls.map((l) => h("a", { class: "card lec-card", href: `#/lecture/${l.key}` },
          h("div", { class: "n" }, `Lecture ${l.key}`), h("div", { class: "t" }, l.title),
          l.goal ? h("div", { class: "g" }, l.goal) : null,
          dev(Object.entries(l.has).filter(([, v]) => v).map(([k]) => k).join(" · ")))))))));
}
function devHome() {
  const C = S.course, idx = C.index;
  const n = (k) => C.lectures.filter((l) => l.has[k]).length;
  return h("div", { class: "dev card", style: "margin-top:12px" },
    `${C.course}: ${C.lectures.length} lectures; segments ${n("segments")}, transcript ${n("transcript")}, knowledge ${n("knowledge")}, activities ${n("activities")}, video ${n("video")}; question answering ${C.qa ? "importable" : "not available"}`,
    idx ? h("div", {}, "knowledge counts: " + Object.entries(idx.counts || {}).map(([k, v]) => `${k} ${v}`).join(", ") + ` · embedding ${(idx.embedding || {}).model}`) : h("div", {}, "no knowledge/ layer"));
}

// ------------------------------------------------------------------ before a lecture
function beforeLecture(key, withTitle) {
  const K = S.K;
  if (!K || !K.graph || !K.graph.prerequisites) return h("p", { class: "muted" }, "Not available yet for this course.");
  const pre = K.graph.prerequisites[key] || { direct: [], all: [] };
  const links = (K.graph.links || []).filter((l) => l.to === key && l.kind !== "weak");
  const weak = (K.graph.links || []).filter((l) => l.to === key && l.kind === "weak");
  const kinds = (K.graph.concept_kinds || {})[key] || {};
  const lecCard = (k) => h("a", { class: "card lec-card", href: `#/lecture/${k}` }, h("div", { class: "n" }, `Lecture ${k}`),
    h("div", { class: "t" }, lecInfo(k).title), lecInfo(k).goal ? h("div", { class: "g" }, lecInfo(k).goal) : null);
  const cBox = (cid, from, redefined) => {
    const c = concept(cid) || {}, w = (c.defined_in || []).find((d) => d.lecture === from) || (c.defined_in || [])[0];
    return h("div", { class: "cbox" }, h("div", { class: "row" }, h("a", { class: "nm", href: `#/concept/${cid}` }, cname(cid)), dev(cid), h("span", { class: "spacer" }),
      w ? timeLink(w.lecture, w.start) : null),
      c.definition ? h("div", { class: "df" }, c.definition) : null,
      redefined ? h("div", { class: "small faint" }, "Explained again in this lecture.") : null);
  };
  const others = (pre.all || []).filter((k) => !(pre.direct || []).includes(k));
  const needed = [];
  const seen = new Set();
  for (const l of links.concat(weak)) for (const c of l.concepts) if (!seen.has(c)) { seen.add(c); needed.push([c, l.from, (l.redefined || []).includes(c)]); }
  return h("div", {},
    withTitle ? h("p", { class: "muted" }, h("a", { href: `#/lecture/${key}` }, `Lecture ${key}: ${lecInfo(key).title}`)) : null,
    h("h3", {}, "Watch first"),
    (pre.direct || []).length ? h("div", { class: "lecs" }, pre.direct.map(lecCard)) : h("p", { class: "muted" }, "No earlier lecture is needed."),
    others.length ? h("p", { class: "small muted" }, "Behind those: ", others.map((k, i) => [i ? ", " : "", h("a", { href: `#/lecture/${k}`, title: lecInfo(k).title }, `Lecture ${k}`)])) : null,
    needed.length ? [h("h3", { style: "margin-top:16px" }, "Concepts this lecture builds on"),
      h("div", { class: "clist" }, needed.map(([c, from, red]) => cBox(c, from, red)))] : null,
    (kinds.assumed || []).length ? [h("h3", { style: "margin-top:16px" }, "Assumed knowledge"),
      h("p", { class: "small muted" }, "Used in this lecture but not taught in the course."),
      h("div", { class: "chips" }, kinds.assumed.map((c) => conceptPill(c, "assumed")))] : null);
}

// ------------------------------------------------------------------ lecture
async function pageLecture(key, rest) {
  const L = await lecture(key);
  if (!L) return h("div", { class: "empty" }, `There is no lecture ${key}.`);
  const KL = L.knowledge, info = lecInfo(key);
  const root = h("div", {});
  const view = { lecture: key, root, tab: rest[0] && rest[0] !== "t" ? rest[0] : "overview" };
  S.view = view;
  // player: the video file when the server has it, else the lecture on YouTube (by its youtube_id), else a note
  const video = L.video ? h("video", { controls: true, preload: "metadata", src: `/media/${key}` }) : null;
  const yt = !video && L.youtube_id ? youtubePlayer(L.youtube_id, (t) => tick(t)) : null;
  const player = h("div", { class: "player" }, video || (yt && yt.el) || h("div", { class: "novideo" }, "The video for this lecture is not available on this computer.", h("br"), "The segments and transcript still work."));
  const segEls = L.segments.map((sg, i) => h("div", { class: "seg", onclick: () => view.seek(sg.start, true) },
    h("span", { class: "num" }, i + 1),
    h("div", {}, h("div", { class: "sg" }, sg.subgoal || "(no sub-goal)"), h("div", { class: "row small" }, h("span", { class: "time" }, clock(sg.start) + " – " + clock(sg.end)), dev(sg.id)))));
  const segList = h("div", { class: "card segs" }, h("h3", { style: "padding:4px 6px" }, "In this lecture"), segEls.length ? segEls : h("p", { class: "muted" }, "No segments yet."));
  const trans = h("div", { class: "transcript" });
  const sentEls = new Map();
  let curSeg = -1, curSent = null, fakeT = 0;
  const segAt = (t) => { let k = -1; L.segments.forEach((sg, i) => { if (t >= sg.start - 0.5) k = i; }); return k; };
  const showSeg = (i) => {
    if (i === curSeg) return;
    curSeg = i;
    segEls.forEach((el, j) => el.classList.toggle("on", j === i));
    if (i >= 0) {
      const el = segEls[i], box = segList;
      if (el.offsetTop < box.scrollTop || el.offsetTop + el.offsetHeight > box.scrollTop + box.clientHeight) box.scrollTop = el.offsetTop - 40;
    }
    const sg = L.segments[i];
    sentEls.clear();
    const inSeg = sg ? L.sentences.filter((x) => x.start != null && x.start >= sg.start - 0.5 && x.start < sg.end + 0.5) : [];
    trans.replaceChildren(inSeg.length ? inSeg.map((x) => { const e = h("span", { onclick: () => view.seek(x.start, true), title: clock(x.start) }, x.text + " "); sentEls.set(x, e); return e; })
      : h("span", { class: "faint" }, L.sentences.length ? "" : "No transcript for this lecture."));
  };
  const tick = (t) => {
    showSeg(segAt(t));
    let hit = null;
    for (const [x, e] of sentEls) if (t >= x.start && t < (x.end || x.start + 5)) hit = e;
    if (hit !== curSent) {
      if (curSent) curSent.classList.remove("on");
      curSent = hit;
      if (hit) { hit.classList.add("on"); const top = hit.offsetTop - trans.offsetTop; if (top < trans.scrollTop || top > trans.scrollTop + trans.clientHeight - 30) trans.scrollTop = top - 20; }
    }
  };
  if (video) video.addEventListener("timeupdate", () => tick(video.currentTime));
  view.seek = (t, play) => {
    if (!isFinite(t)) return;
    fakeT = t;
    if (video) {
      const go = () => { try { video.currentTime = t; } catch (e) { /* not seekable yet */ } if (play) video.play().catch(() => {}); };
      if (video.readyState >= 1) go(); else video.addEventListener("loadedmetadata", go, { once: true });
    } else if (yt) yt.seek(t, play);
    tick(t);
    player.scrollIntoView({ block: "nearest", behavior: "smooth" });
  };
  view.stop = () => { if (video) video.pause(); if (yt) yt.stop(); };
  view.player = video ? "file" : yt ? "youtube" : "none";
  view.yt = yt;

  // tabs
  const hasActs = !!(L.activities && (L.activities.activities || []).length);
  const tabs = [["overview", "Overview"], KL && ["concepts", "Concepts"], KL && ["map", "Concept map"], KL && S.K && ["before", "Before this lecture"],
    hasActs && ["activities", "Activities"]].filter(Boolean);
  const tabBar = h("div", { class: "tabs" });
  const tabBody = h("div", {});
  view.showTab = (t) => {
    if (!tabs.some(([k]) => k === t)) t = "overview";
    view.tab = t;
    tabBar.replaceChildren(tabs.map(([k, label]) => h("button", { class: k === t ? "on" : "", onclick: () => { location.hash = `#/lecture/${key}/${k}`; } }, label)));
    let body;
    if (t === "overview") body = lectureOverview(L);
    else if (t === "concepts") body = lectureConcepts(L);
    else if (t === "map") body = lectureMap(L);
    else if (t === "before") body = h("div", {}, beforeLecture(key), recallFor(L));
    else body = activitiesView(L);
    tabBody.replaceChildren(body);
  };
  root.append(
    h("div", { class: "lec-head" },
      h("div", { class: "row small muted" }, h("a", { href: "#/" }, "All lectures"), "›", `Lecture ${key}` + (L.week ? ` · Week ${L.week}` : "")),
      h("h1", {}, L.title),
      KL && KL.goal ? h("div", { class: "goal" }, KL.goal.goal) : null,
      KL && KL.goal && KL.goal.achieves ? h("div", { class: "achieves" }, KL.goal.achieves) : null,
      !KL ? h("div", { class: "note", style: "margin-top:8px" }, "Goals, concepts and activities for this lecture are not ready yet. The video and its parts are below.") : null,
      dev(`segments from ${L.source}; ${L.segments.length} segments, ${L.sentences.length} sentences; activities ${L.activities ? L.activities.activities.length : "none"}`)),
    h("div", { class: "watch" }, h("div", {}, player, h("details", { class: "card", style: "margin-top:12px", open: true }, h("summary", { class: "small muted" }, "Transcript of this part"), trans)), segList),
    tabBar, tabBody);
  view.showTab(view.tab);
  showSeg(L.segments.length ? 0 : -1);
  if (rest[0] === "t") setTimeout(() => view.seek(parseFloat(rest[1])), 0);
  return root;
}

// ------------------------------------------------------------------ YouTube player (a lecture whose video file is not here)
// The embed is shown at once; the IFrame API (loaded on first use) then drives it: seek, play, pause, and the current
// time every half second for the segment and transcript highlight. Without the API (blocked, offline), a seek reloads
// the embed at that second (?start=), so segment clicks and citation links still jump.
let ytApi = null;
function loadYouTubeApi() {
  if (window.YT && window.YT.Player) return Promise.resolve(window.YT);
  if (!ytApi) {
    ytApi = new Promise((resolve, reject) => {
      const prev = window.onYouTubeIframeAPIReady;
      window.onYouTubeIframeAPIReady = () => { if (prev) prev(); resolve(window.YT); };
      const s = document.createElement("script");
      s.src = "https://www.youtube.com/iframe_api";
      s.async = true;
      s.onerror = () => reject(new Error("the YouTube player API did not load"));
      document.head.append(s);
      setTimeout(() => reject(new Error("the YouTube player API timed out")), 15000);
    }).catch((e) => { ytApi = null; throw e; });
  }
  return ytApi;
}
function youtubePlayer(id, onTime) {
  const base = `https://www.youtube.com/embed/${encodeURIComponent(id)}?enablejsapi=1&rel=0&playsinline=1&origin=${encodeURIComponent(location.origin)}`;
  const el = h("iframe", { src: base, title: "Lecture video", allow: "autoplay; encrypted-media; picture-in-picture; fullscreen", allowfullscreen: "", referrerpolicy: "strict-origin-when-cross-origin" });
  const P = { el, id, player: null, ready: false, failed: false, pending: null, timer: null };
  const apply = (t, play) => {
    const p = P.player, st = p.getPlayerState ? p.getPlayerState() : -1;
    if (!play && (st === -1 || st === 5)) p.cueVideoById({ videoId: id, startSeconds: t });   // not started: stay paused there
    else { p.seekTo(t, true); if (play) p.playVideo(); }
  };
  P.seek = (t, play) => {
    if (P.ready) return apply(t, play);
    if (P.failed) { el.src = `${base}&start=${Math.floor(t)}${play ? "&autoplay=1" : ""}`; return; }
    P.pending = { t, play };
  };
  P.time = () => (P.ready && P.player.getCurrentTime ? P.player.getCurrentTime() : null);
  P.stop = () => {
    if (P.timer) clearInterval(P.timer);
    P.timer = null;
    try { if (P.ready) P.player.pauseVideo(); } catch (e) { /* the frame is gone */ }
  };
  loadYouTubeApi().then((YT) => new Promise((resolve) => {
    P.player = new YT.Player(el, { events: { onReady: resolve } });
  })).then(() => {
    P.ready = true;
    if (P.pending) { apply(P.pending.t, P.pending.play); P.pending = null; }
    P.timer = setInterval(() => {
      if (!document.body.contains(el)) return P.stop();
      try { if (P.player.getPlayerState() === 1) onTime(P.player.getCurrentTime()); } catch (e) { /* not ready */ }
    }, 500);
  }).catch(() => {
    P.failed = true;
    if (P.pending) { P.seek(P.pending.t, P.pending.play); P.pending = null; }
  });
  return P;
}

function lectureOverview(L) {
  const KL = L.knowledge;
  if (!KL) return h("div", {}, h("h3", {}, "Parts of this lecture"), h("ol", {}, L.segments.map((sg) => h("li", {}, sg.subgoal, " ", h("a", { class: "time", href: timeHref(L.key, sg.start) }, clock(sg.start))))));
  const segIdx = Object.fromEntries(L.segments.map((sg, i) => [sg.id, i]));
  const goals = (S.course.goals && S.course.goals.course_goals) || {};
  const loose = L.segments.filter((sg) => !(KL.objectives || []).some((o) => (o.segments || []).includes(sg.id)));
  return h("div", { class: "grid2" },
    h("div", { class: "card" }, h("h3", {}, "After this lecture you can"),
      h("ul", { class: "objs" }, (KL.objectives || []).map((o) => h("li", {},
        h("div", {}, o.goal, " ", dev(o.id)), o.achieves ? h("div", { class: "achieves" }, o.achieves) : null,
        h("div", { class: "row small", style: "margin-top:4px" }, (o.segments || []).map((sid) => { const sg = L.segments[segIdx[sid]]; return sg ? h("a", { class: "time", href: timeHref(L.key, sg.start), title: sg.subgoal }, `Part ${segIdx[sid] + 1} · ${clock(sg.start)}`) : dev(sid); }))))),
      loose.length ? h("p", { class: "small muted" }, "Also in this lecture: ", loose.map((sg) => h("a", { class: "time", href: timeHref(L.key, sg.start), title: sg.subgoal, style: "margin-right:8px" }, `Part ${segIdx[sg.id] + 1}`))) : null),
    h("div", {},
      (KL.course_goals || []).length ? h("div", { class: "card" }, h("h3", {}, "This lecture serves the course goals"),
        h("ul", {}, KL.course_goals.map((g) => h("li", {}, (goals[g] || {}).goal || g, " ", dev(g))))) : null,
      h("div", { class: "card" }, h("h3", {}, "Concepts introduced here"),
        h("div", { class: "chips" }, ((KL.concepts || {}).introduced || []).map((c) => conceptPill(c, "introduced"))),
        !((KL.concepts || {}).introduced || []).length ? h("p", { class: "muted small" }, "None new: this lecture builds on concepts met before.") : null)));
}

function lectureConcepts(L) {
  const KL = L.knowledge;
  if (!KL) return h("p", { class: "muted" }, "Not ready yet for this lecture.");
  return h("div", {}, KINDS.map(([k, label]) => {
    const cs = (KL.concepts || {})[k] || [];
    if (!cs.length) return null;
    return h("div", {}, h("div", { class: "kind-head" }, h("span", { class: "dot", style: `background:var(--k-${{ introduced: "intro", met_again: "again", assumed: "assumed", defined_later: "later" }[k]})` }), h("h3", { style: "margin:0" }, label)),
      h("div", { class: "clist" }, cs.map((cid) => {
        const c = concept(cid) || {};
        const here = (c.defined_in || []).find((d) => d.lecture === L.key);
        return h("div", { class: "cbox" }, h("div", { class: "row" }, h("a", { class: "nm", href: `#/concept/${cid}` }, cname(cid)), dev(cid), h("span", { class: "spacer" }), here ? timeLink(L.key, here.start, L.key) : null),
          c.definition ? h("div", { class: "df" }, c.definition) : null);
      })));
  }));
}

function lectureMap(L) {
  const KL = L.knowledge;
  if (!KL || !S.K) return h("p", { class: "muted" }, "Not ready yet for this lecture.");
  const kindOf = {};
  for (const [k] of KINDS) for (const c of (KL.concepts || {})[k] || []) kindOf[c] = k;
  const rels = (KL.concept_map.relations || []).map((r) => [r, S.K.relations[r]]).filter(([, r]) => r);
  const linked = new Set(rels.flatMap(([, r]) => [r.subject, r.object]));
  const nodes = [...linked].map((c) => ({ id: c, label: cname(c), cls: "k-" + (kindOf[c] || "met_again"), title: (concept(c) || {}).definition }));
  const edges = rels.map(([rid, r]) => ({ from: r.subject, to: r.object, label: r.label, title: rid }));
  const alone = (KL.concept_map.concepts || []).filter((c) => !linked.has(c));
  return h("div", {}, mapLegend(),
    drawMap(nodes, edges, { onNode: (id) => (location.hash = `#/concept/${id}`), empty: "No relationships were found between this lecture's concepts." }),
    alone.length ? h("div", { style: "margin-top:12px" }, h("div", { class: "small muted" }, "Also in this lecture:"), h("div", { class: "chips", style: "margin-top:4px" }, alone.map((c) => conceptPill(c, kindOf[c])))) : null);
}

// ------------------------------------------------------------------ concept card
function pageConcept(cid) {
  const c = concept(cid);
  if (!c) return h("div", { class: "empty" }, S.K ? "There is no such concept." : "Concepts are not ready yet for this course.");
  const names = [...new Set([...(c.aliases || []), ...(c.acronyms || [])])].filter((a) => a.toLowerCase() !== c.name.toLowerCase());
  const relRow = (r, dir) => h("li", {}, dir === "out" ? [h("b", {}, cname(cid)), " ", h("span", { class: "lbl" }, r.label), " ", h("a", { href: `#/concept/${r.concept}` }, cname(r.concept))]
    : [h("a", { href: `#/concept/${r.concept}` }, cname(r.concept)), " ", h("span", { class: "lbl" }, r.label), " ", h("b", {}, cname(cid))], " ", dev(r.relation),
  relFacts(r.relation));
  const rels = [...((c.relations || {}).out || []).map((r) => relRow(r, "out")), ...((c.relations || {}).in || []).map((r) => relRow(r, "in"))];
  return h("div", {},
    h("div", { class: "row small muted" }, h("a", { href: "#/glossary" }, "Glossary"), "›", dev(cid)),
    h("h1", {}, cap(c.name)),
    names.length ? h("div", { class: "chips", style: "margin-bottom:10px" }, h("span", { class: "small muted" }, "Also called"), names.map((a) => h("span", { class: "pill" }, a))) : null,
    h("div", { class: "card" },
      c.definition ? h("div", { class: "defn" }, c.definition) : h("div", { class: "muted" }, "The course uses this concept without defining it."),
      (c.defined_in || []).length ? h("div", { class: "row small", style: "margin-top:10px" }, h("span", { class: "muted" }, "Defined in"),
        c.defined_in.map((d) => h("span", {}, h("a", { href: `#/lecture/${d.lecture}`, title: lecInfo(d.lecture).title }, `Lecture ${d.lecture}`), " ", timeLink(d.lecture, d.start, d.lecture), dev(" " + d.segment)))) : null,
      dev(`first defined ${c.first_defined || "never"}; defined ${c.defined}; definition built from ${(c.definition_facts || []).join(", ") || "none"}`)),
    h("div", { class: "grid2", style: "margin-top:14px" },
      h("div", { class: "card" }, h("h3", {}, "What the course says"), factList(c.facts, null, c.defining_facts)),
      h("div", {},
        h("div", { class: "card" }, h("h3", {}, "Related concepts"), rels.length ? h("ul", { class: "rels" }, rels) : h("p", { class: "muted small" }, "No relationships recorded.")),
        h("div", { class: "card" }, h("h3", {}, "Lectures that use it"), h("div", { class: "chips" }, (c.lectures || []).map((k) => h("a", { class: "pill", href: `#/lecture/${k}`, title: lecInfo(k).title }, `Lecture ${k}: ${lecInfo(k).title}`)))),
        (c.misplaced || []).length || (c.merged || []).length ? h("div", { class: "card dev" }, h("div", {}, "misplaced: " + (c.misplaced || []).join(", ")),
          h("div", {}, "merged: " + (c.merged || []).map((m) => `${m.segment_concept} "${m.name}" (${m.how}${m.reason ? ": " + m.reason : ""})`).join("; "))) : null)));
}
function relFacts(rid) {
  const r = S.K && S.K.relations[rid];
  if (!r || !(r.facts || []).length) return null;
  const x = fact(r.facts[0]);
  return x ? h("span", { class: "small", title: x.text }, " ", timeLink(x.lecture, x.start)) : null;
}

// ------------------------------------------------------------------ glossary and course map
function pageGlossary() {
  if (!S.K) return h("div", { class: "empty" }, "The glossary is not ready yet for this course.");
  const all = Object.entries(S.K.concepts).sort((a, b) => a[1].name.localeCompare(b[1].name, undefined, { sensitivity: "base" }));
  const list = h("div", { class: "gl" });
  const input = h("input", { type: "search", class: "gl-search", placeholder: "Search concepts, acronyms, definitions…", oninput: () => fill() });
  const fill = () => {
    const q = input.value.trim().toLowerCase();
    const hits = all.filter(([, c]) => !q || [c.name, ...(c.aliases || []), ...(c.acronyms || [])].some((n) => n.toLowerCase().includes(q)) || (c.definition || "").toLowerCase().includes(q));
    let letter = "";
    list.replaceChildren(hits.length ? hits.map(([cid, c]) => {
      const L0 = c.name[0].toUpperCase(), head = L0 !== letter && !q ? h("div", { class: "gl-letter" }, (letter = L0)) : null;
      const al = [...new Set([...(c.acronyms || []), ...(c.aliases || [])])].filter((a) => a.toLowerCase() !== c.name.toLowerCase());
      return [head, h("div", { class: "gl-item" }, h("a", { class: "nm", href: `#/concept/${cid}` }, cap(c.name)), al.length ? h("span", { class: "small muted" }, " · " + al.join(", ")) : null, dev(" " + cid),
        h("div", { class: "small muted" }, c.definition || h("i", {}, "Used in the course without a definition.")))];
    }) : h("p", { class: "muted" }, "No concept matches."));
  };
  fill();
  setTimeout(() => input.focus(), 0);
  return h("div", {}, h("h1", {}, "Glossary"), dev(`${all.length} concepts`), input, list);
}
function pageMap(which) {
  if (!S.K) return h("div", { class: "empty" }, "The concept map is not ready yet for this course.");
  const mode = which === "lectures" ? "lectures" : "concepts";
  const sw = h("div", { class: "row", style: "margin-bottom:10px" },
    h("a", { class: "pill" + (mode === "concepts" ? " k-introduced" : ""), href: "#/map" }, "Concepts"),
    h("a", { class: "pill" + (mode === "lectures" ? " k-introduced" : ""), href: "#/map/lectures" }, "How lectures build on each other"));
  if (mode === "lectures") {
    const links = (S.K.graph.links || []).filter((l) => l.kind === "direct");
    const used = new Set(links.flatMap((l) => [l.from, l.to]));
    const nodes = S.course.lectures.filter((l) => used.has(l.key)).map((l) => ({ id: l.key, label: `L${l.key}: ${l.title.length > 34 ? l.title.slice(0, 32) + "…" : l.title}`, title: l.goal || l.title }));
    const edges = links.map((l) => ({ from: l.from, to: l.to, label: l.concepts.slice(0, 2).map(cname).join(", ") + (l.concepts.length > 2 ? " …" : ""), title: l.concepts.map(cname).join(", ") }));
    return h("div", {}, h("h1", {}, "Concept map"), sw, h("p", { class: "muted small" }, "An arrow means the later lecture uses concepts the earlier one explains (labelled with them). Click a lecture to open it."),
      drawMap(nodes, edges, { dir: "LR", height: 640, wheel: true, onNode: (id) => (location.hash = `#/lecture/${id}`), empty: "No links between lectures yet." }));
  }
  const rels = Object.entries(S.K.relations);
  const ids = new Set(rels.flatMap(([, r]) => [r.subject, r.object]));
  const nodes = [...ids].map((c) => ({ id: c, label: cname(c), title: (concept(c) || {}).definition }));
  const edges = rels.map(([rid, r]) => ({ from: r.subject, to: r.object, label: r.label, title: rid }));
  const map = drawMap(nodes, edges, { height: 640, wheel: true, onNode: (id) => (location.hash = `#/concept/${id}`), empty: "No relationships yet." });
  const opts = [...ids].sort((a, b) => cname(a).localeCompare(cname(b)));
  const find = h("input", { type: "search", list: "map-names", placeholder: "Find a concept…", oninput: () => {
    const q = find.value.trim().toLowerCase();
    const hit = q && opts.find((c) => cname(c).toLowerCase() === q) || (q.length > 2 && opts.find((c) => cname(c).toLowerCase().includes(q)));
    if (map.focusNode) map.focusNode(hit || null);
  } });
  return h("div", {}, h("h1", {}, "Concept map"), sw,
    h("div", { class: "row", style: "margin-bottom:8px" }, find, h("datalist", { id: "map-names" }, opts.map((c) => h("option", { value: cname(c) }))),
      h("span", { class: "small faint" }, "Scroll to zoom, drag to move, click a concept to open it."), dev(`${nodes.length} concepts, ${edges.length} relationships`)),
    map);
}

// ------------------------------------------------------------------ activities
const KIND_LABEL = { quiz: "Quiz", recap: "Recap", recall: "Recall", open_question: "Think it through", concept_map: "Concept map",
  complete_map: "Complete the map", crossword: "Crossword", match_pairs: "Match the pairs", odd_one_out: "Odd one out", put_in_order: "Put in order" };
function activityCard(a, L) {
  const fn = RENDER[a.kind];
  let body;
  try { body = fn ? fn(a, L) : h("p", { class: "muted" }, "This kind of activity cannot be shown yet."); } catch (e) { console.error(e); body = h("p", { class: "muted" }, "This activity could not be shown.", dev(" " + e)); }
  return h("div", { class: "card act", id: "act-" + a.id },
    h("div", { class: "act-head" }, h("span", { class: "act-kind" }, KIND_LABEL[a.kind] || a.kind), a.title ? h("h3", { style: "margin:0" }, a.title) : null, h("span", { class: "spacer" }), dev(a.id)),
    body);
}
function activitiesView(L) {
  const acts = (L.activities && L.activities.activities) || [];
  if (!acts.length) return h("p", { class: "muted" }, "There are no activities for this lecture yet.");
  const segIdx = Object.fromEntries(L.segments.map((sg, i) => [sg.id, i]));
  const before = acts.filter((a) => a.kind === "recall");
  const bySeg = {};
  for (const a of acts) if (a.scope === "segment" && a.segment && a.kind !== "recall") (bySeg[a.segment] = bySeg[a.segment] || []).push(a);
  const after = acts.filter((a) => a.kind !== "recall" && !(a.scope === "segment" && a.segment));
  const segOrder = Object.keys(bySeg).sort((a, b) => (segIdx[a] ?? 999) - (segIdx[b] ?? 999));
  return h("div", {},
    before.length ? h("div", { class: "act-group" }, h("h3", {}, "Before you watch"), before.map((a) => activityCard(a, L))) : null,
    segOrder.map((sid) => {
      const i = segIdx[sid], sg = L.segments[i];
      return h("div", { class: "act-group" }, h("h3", { class: "row" }, sg ? `Part ${i + 1}: ${sg.subgoal}` : sid, sg ? h("a", { class: "time", href: timeHref(L.key, sg.start) }, "▶ " + clock(sg.start)) : null),
        bySeg[sid].map((a) => activityCard(a, L)));
    }),
    after.length ? h("div", { class: "act-group" }, h("h3", {}, "After the lecture"), after.map((a) => activityCard(a, L))) : null);
}
function recallFor(L) {
  const acts = ((L.activities && L.activities.activities) || []).filter((a) => a.kind === "recall");
  return acts.length ? h("div", { class: "section" }, h("h3", {}, "Check yourself first"), acts.map((a) => activityCard(a, L))) : null;
}
function feedback(ok, text, facts, L) {
  return h("div", { class: "feedback " + (ok == null ? "" : ok ? "ok" : "bad") }, ok == null ? null : h("b", {}, ok ? "Correct. " : "Not quite. "), text || "", factLinks(facts, L && L.key));
}
const RENDER = {
  quiz(a, L) {
    return h("div", {}, (a.data.questions || []).map((q, qi) => {
      const fb = h("div", {});
      const btns = (q.options || []).map((o, i) => h("button", { class: "opt", onclick: () => {
        btns.forEach((b, j) => { b.disabled = true; if (j === q.answer) b.classList.add("right"); else if (j === i) b.classList.add("wrong"); });
        fb.replaceChildren(feedback(i === q.answer, q.explanation, q.facts, L));
      } }, String.fromCharCode(65 + i) + ".  " + o));
      return h("div", { class: "q" }, h("div", { class: "qt" }, `${qi + 1}. ${q.question}`), h("div", { class: "opts" }, btns), fb,
        h("button", { class: "ghost small", style: "margin-top:4px", onclick: () => { btns.forEach((b) => { b.disabled = false; b.classList.remove("right", "wrong"); }); fb.replaceChildren(); } }, "Try again"));
    }));
  },
  recap(a, L) {
    return h("div", {}, a.data.text ? h("p", {}, a.data.text) : null, (a.data.points || []).length ? h("ul", {}, a.data.points.map((p) => h("li", {}, p))) : null, factLinks(a.facts, L.key));
  },
  recall(a) {
    return h("div", { class: "flips" }, (a.data.items || []).map((it) => {
      const c = concept(it.concept), w = c && (c.defined_in || [])[0];
      const card = h("div", { class: "flip", tabindex: 0, onclick: () => card.classList.toggle("on"), onkeydown: (e) => { if (e.key === "Enter" || e.key === " ") { e.preventDefault(); card.classList.toggle("on"); } } },
        h("div", { class: "in" },
          h("div", { class: "face" }, h("div", {}, it.prompt || cname(it.concept)), h("div", { class: "hint" }, "Recall it, then click to check")),
          h("div", { class: "face back" }, h("div", {}, it.answer), h("div", { class: "hint" },
            it.from_lecture ? h("a", { href: w && w.lecture === it.from_lecture ? timeHref(w.lecture, w.start) : `#/lecture/${it.from_lecture}`, onclick: (e) => e.stopPropagation() }, `From lecture ${it.from_lecture}`) : null,
            it.concept ? [" · ", h("a", { href: `#/concept/${it.concept}`, onclick: (e) => e.stopPropagation() }, cname(it.concept))] : null))));
      return card;
    }));
  },
  open_question(a, L) {
    return h("div", {}, (a.data.questions || []).map((q, qi) => {
      const key = `oq:${S.course.course}:${a.id}:${qi}`;
      const ta = h("textarea", { placeholder: "Write your answer here (it stays in this browser)…", oninput: () => store(key, ta.value) });
      ta.value = store(key) || "";
      const ref = h("div", { hidden: true, class: "feedback" }, h("b", {}, "A good answer: "), q.reference_answer,
        (q.key_facts || []).length && S.K ? h("div", { style: "margin-top:8px" }, h("div", { class: "small muted" }, "Key points from the lectures:"), factList(q.key_facts, L.key)) : factLinks(q.key_facts, L.key),
        (q.concepts || []).length ? h("div", { class: "chips", style: "margin-top:6px" }, q.concepts.map((c) => conceptPill(c))) : null);
      return h("div", { class: "q" }, h("div", { class: "qt" }, `${qi + 1}. ${q.question}`), ta,
        h("button", { class: "small", style: "margin-top:6px", onclick: (e) => { ref.hidden = !ref.hidden; e.target.textContent = ref.hidden ? "Show a good answer" : "Hide the answer"; } }, "Show a good answer"), ref);
    }));
  },
  concept_map(a) {
    const d = a.data;
    return drawMap((d.nodes || []).map((n) => ({ id: n.id, label: cap(n.label), title: (concept(n.id) || {}).definition })),
      (d.edges || []).map((e) => ({ from: e.from, to: e.to, label: e.label })), { onNode: (id) => concept(id) && (location.hash = `#/concept/${id}`) });
  },
  complete_map(a) {
    const d = a.data, edges = (d.edges || []).map((e) => ({ ...e })), nodes = (d.nodes || []).map((n) => ({ id: n.id, label: cap(n.label) }));
    const hidden = new Set();
    (d.blanks || []).forEach((b, i) => {
      const e = edges[b.edge];
      if (!e) return;
      const tag = `(${i + 1})`;
      if (b.hide === "label") { e.label = tag; e.cls = "blank"; }
      else { const end = b.hide === "from" ? "from" : "to"; hidden.add(e[end]); const nid = `__blank${i}`; nodes.push({ id: nid, label: `${tag} ?`, cls: "blank" }); e[end] = nid; }
    });
    const stillUsed = new Set(edges.flatMap((e) => [e.from, e.to]));
    const shown = nodes.filter((n) => !hidden.has(n.id) || stillUsed.has(n.id));
    const sels = (d.blanks || []).map((b, i) => {
      const sel = h("select", {}, h("option", { value: "" }, "Choose…"), (b.options || []).map((o) => h("option", { value: o }, o)));
      const mark = h("span", {});
      return { b, sel, mark, row: h("div", { class: "row" }, h("b", {}, `(${i + 1})`), h("span", { class: "small muted" }, b.hide === "label" ? "the link" : "the concept"), sel, mark) };
    });
    return h("div", {}, drawMap(shown, edges, {}),
      h("div", { class: "blanks" }, sels.map((x) => x.row)),
      h("div", { class: "row", style: "margin-top:10px" },
        h("button", { class: "primary small", onclick: () => sels.forEach((x) => { const ok = x.sel.value === x.b.answer; x.mark.replaceChildren(h("span", { style: `color:var(--${ok ? "ok" : "bad"})` }, ok ? "✓ right" : x.sel.value ? "✗ not this one" : "")); }) }, "Check"),
        h("button", { class: "ghost small", onclick: () => sels.forEach((x) => { x.sel.value = x.b.answer; x.mark.replaceChildren(h("span", { class: "muted" }, "answer shown")); }) }, "Show answers")),
      factLinks(a.facts));
  },
  crossword(a) {
    const d = a.data, W = d.width, Hh = d.height;
    const cells = {};
    for (const e of d.entries || []) {
      const ans = (e.answer || "").replace(/[^A-Z]/gi, "").toUpperCase();
      for (let i = 0; i < ans.length; i++) {
        const r = e.row + (e.direction === "down" ? i : 0), c = e.col + (e.direction === "across" ? i : 0);
        const k = r + "," + c;
        cells[k] = cells[k] || { ch: ans[i], entries: [] };
        cells[k].entries.push(e);
        if (i === 0) cells[k].no = e.number;
      }
    }
    let dir = "across";
    const inputs = {};
    const grid = h("div", { class: "xw-grid", style: `grid-template-columns:repeat(${W}, 32px)` });
    const move = (r, c, step) => {
      const dr = dir === "down" ? step : 0, dc = dir === "across" ? step : 0;
      const nk = (r + dr) + "," + (c + dc);
      if (inputs[nk]) inputs[nk].focus();
    };
    for (let r = 0; r < Hh; r++) for (let c = 0; c < W; c++) {
      const k = r + "," + c, cell = cells[k];
      if (!cell) { grid.append(h("div", { class: "xw-cell blk" })); continue; }
      const inp = h("input", { maxlength: 1, "aria-label": `row ${r + 1} column ${c + 1}` });
      inp.addEventListener("focus", () => { if (!cell.entries.some((e) => e.direction === dir)) dir = cell.entries[0].direction; inp.select(); });
      inp.addEventListener("input", () => { inp.value = inp.value.replace(/[^a-z]/gi, "").toUpperCase(); box.classList.remove("right", "wrong"); if (inp.value) move(r, c, 1); });
      inp.addEventListener("keydown", (ev) => {
        if (ev.key === "Backspace" && !inp.value) { move(r, c, -1); }
        else if (ev.key === "ArrowRight") { dir = "across"; move(r, c, 1); } else if (ev.key === "ArrowLeft") { dir = "across"; move(r, c, -1); }
        else if (ev.key === "ArrowDown") { dir = "down"; move(r, c, 1); } else if (ev.key === "ArrowUp") { dir = "down"; move(r, c, -1); }
      });
      inputs[k] = inp;
      const box = h("div", { class: "xw-cell" }, cell.no ? h("span", { class: "no" }, cell.no) : null, inp);
      cell.box = box;
      grid.append(box);
    }
    const clue = (e) => h("li", { onclick: () => { dir = e.direction; const k = e.row + "," + e.col; if (inputs[k]) inputs[k].focus(); }, style: "cursor:pointer" },
      h("b", {}, e.number), e.clue, " ", h("span", { class: "faint small" }, `(${(e.answer || "").replace(/[^A-Z]/gi, "").length})`));
    const ents = d.entries || [];
    const across = ents.filter((e) => e.direction === "across").sort((x, y) => x.number - y.number);
    const down = ents.filter((e) => e.direction === "down").sort((x, y) => x.number - y.number);
    const status = h("span", { class: "small muted" });
    return h("div", {}, h("div", { class: "xw" }, grid,
      h("div", { class: "xw-clues" }, h("h4", {}, "Across"), h("ol", {}, across.map(clue)), h("h4", {}, "Down"), h("ol", {}, down.map(clue)))),
      h("div", { class: "row", style: "margin-top:10px" },
        h("button", { class: "primary small", onclick: () => {
          let right = 0, total = 0;
          for (const [k, cell] of Object.entries(cells)) { total++; const v = inputs[k].value; cell.box.classList.toggle("right", v === cell.ch); cell.box.classList.toggle("wrong", !!v && v !== cell.ch); if (v === cell.ch) right++; }
          status.textContent = right === total ? "Solved!" : `${right} of ${total} letters right.`;
        } }, "Check"),
        h("button", { class: "ghost small", onclick: () => { for (const [k, cell] of Object.entries(cells)) { inputs[k].value = cell.ch; cell.box.classList.remove("wrong"); } status.textContent = "Answers shown."; } }, "Reveal"),
        h("button", { class: "ghost small", onclick: () => { for (const [k, cell] of Object.entries(cells)) { inputs[k].value = ""; cell.box.classList.remove("right", "wrong"); } status.textContent = ""; } }, "Clear"),
        status));
  },
  match_pairs(a) {
    const pairs = a.data.pairs || [];
    const rights = shuffled(pairs.map((p, i) => i), a.id);
    let sel = null, done = 0;
    const status = h("span", { class: "small muted" }, `0 of ${pairs.length} matched`);
    const leftBtns = pairs.map((p, i) => h("button", { onclick: () => { if (leftBtns[i].classList.contains("done")) return; leftBtns.forEach((b) => b.classList.remove("sel")); sel = i; leftBtns[i].classList.add("sel"); } }, cap(p.left)));
    const rightBtns = rights.map((i) => h("button", { onclick: (ev) => {
      const b = ev.currentTarget;
      if (sel == null || b.classList.contains("done")) return;
      if (sel === i) {
        b.classList.add("done"); leftBtns[sel].classList.remove("sel"); leftBtns[sel].classList.add("done"); sel = null; done++;
        status.textContent = done === pairs.length ? "All matched. Well done!" : `${done} of ${pairs.length} matched`;
      } else { b.classList.add("miss"); setTimeout(() => b.classList.remove("miss"), 600); }
    } }, pairs[i].right));
    return h("div", {}, h("p", { class: "small muted" }, "Pick a term, then its description."),
      h("div", { class: "pairs" }, h("div", { class: "col" }, leftBtns), h("div", { class: "col" }, rightBtns)),
      h("div", { class: "row", style: "margin-top:8px" }, status));
  },
  odd_one_out(a, L) {
    return h("div", {}, (a.data.items || []).map((it, qi) => {
      const fb = h("div", {});
      const btns = (it.options || []).map((o, i) => h("button", { class: "opt", onclick: () => {
        btns.forEach((b, j) => { b.disabled = true; if (j === it.odd) b.classList.add("right"); else if (j === i) b.classList.add("wrong"); });
        fb.replaceChildren(feedback(i === it.odd, it.reason, it.facts, L));
      } }, o));
      return h("div", { class: "q" }, h("div", { class: "qt" }, `${qi + 1}. Which one does not belong?`), h("div", { class: "opts", style: "grid-template-columns:1fr 1fr" }, btns), fb);
    }));
  },
  put_in_order(a, L) {
    return h("div", {}, (a.data.items || []).map((it, qi) => {
      const steps = it.steps || [];
      let order = shuffled(steps.map((_, i) => i), a.id + qi);
      if (steps.length > 1 && order.every((v, i) => v === i)) order = order.slice().reverse();
      const list = h("ol", { class: "order" });
      const fb = h("div", {});
      let dragFrom = null;
      const draw = (marks) => list.replaceChildren(order.map((si, pos) => {
        const li = h("li", { draggable: "true", class: marks ? (si === pos ? "right" : "wrong") : "" },
          h("span", { class: "n" }, pos + 1), h("span", { class: "tx" }, steps[si]),
          h("button", { class: "ghost small", title: "Move up", disabled: pos === 0, onclick: () => { swap(pos, pos - 1); } }, "↑"),
          h("button", { class: "ghost small", title: "Move down", disabled: pos === order.length - 1, onclick: () => { swap(pos, pos + 1); } }, "↓"));
        li.addEventListener("dragstart", (e) => { dragFrom = pos; li.classList.add("dragging"); e.dataTransfer.effectAllowed = "move"; try { e.dataTransfer.setData("text/plain", String(pos)); } catch (x) { /* old browsers */ } });
        li.addEventListener("dragend", () => li.classList.remove("dragging"));
        li.addEventListener("dragover", (e) => e.preventDefault());
        li.addEventListener("drop", (e) => { e.preventDefault(); if (dragFrom == null || dragFrom === pos) return; const [m] = order.splice(dragFrom, 1); order.splice(pos, 0, m); dragFrom = null; fb.replaceChildren(); draw(); });
        return li;
      }));
      const swap = (i, j) => { [order[i], order[j]] = [order[j], order[i]]; fb.replaceChildren(); draw(); };
      draw();
      return h("div", { class: "q" }, h("div", { class: "qt" }, it.title || "Put these steps in order"), h("p", { class: "small muted" }, "Drag the steps, or use the arrows."), list,
        h("div", { class: "row", style: "margin-top:8px" },
          h("button", { class: "primary small", onclick: () => { const ok = order.every((v, i) => v === i); draw(true); fb.replaceChildren(feedback(ok, ok ? "That is the order the lecture gives." : "The steps in red are not in place yet.", ok ? it.facts : null, L)); } }, "Check"),
          h("button", { class: "ghost small", onclick: () => { order = steps.map((_, i) => i); draw(true); fb.replaceChildren(feedback(null, "The order the lecture gives.", it.facts, L)); } }, "Show the order")),
        fb);
    }));
  },
};

// ------------------------------------------------------------------ spaced review (cards scheduled in this browser)
const BOX_DAYS = [0, 1, 2, 4, 8, 16, 32, 64];
async function pageReview() {
  if (!S.review) S.review = (S.course.layers.activities && (await getJSON("/data/activities/course.json"))) || {};
  const cards = ((S.review.spaced_review || {}).cards || []).filter((c) => c.concept);
  if (!cards.length) return h("div", { class: "empty" }, "Review cards are not ready yet for this course.");
  const key = `review:${S.course.course}`;
  const st = store(key) || {};
  const save = () => store(key, st);
  const upto = h("select", { onchange: () => { store(key + ":upto", upto.value); next(); } }, h("option", { value: "" }, "all lectures"),
    S.course.lectures.map((l) => h("option", { value: l.key }, `lectures up to ${l.key}`)));
  upto.value = store(key + ":upto") || "";
  const idx = (k) => S.course.lectures.findIndex((l) => l.key === k);
  const stage = h("div", {});
  const counts = h("div", { class: "small muted" });
  const next = () => {
    const now = Date.now(), lim = upto.value ? idx(upto.value) : Infinity;
    const pool = cards.filter((c) => (c.lectures || []).some((k) => idx(k) <= lim) || !(c.lectures || []).length);
    const due = pool.filter((c) => st[c.concept] && st[c.concept].due <= now).sort((a, b) => st[a.concept].due - st[b.concept].due);
    const fresh = pool.filter((c) => !st[c.concept]);
    counts.textContent = `${due.length} due · ${fresh.length} new · ${pool.length - due.length - fresh.length} scheduled later`;
    const card = due[0] || fresh[0];
    if (!card) {
      const soon = pool.map((c) => st[c.concept] && st[c.concept].due).filter(Boolean).sort((a, b) => a - b)[0];
      stage.replaceChildren(h("div", { class: "card review-card" }, h("div", { class: "front" }, "All done for now."),
        soon ? h("div", { class: "back" }, "Next card due " + new Date(soon).toLocaleString()) : null));
      return;
    }
    const back = h("div", { class: "back", hidden: true }, card.back,
      h("div", { class: "chips", style: "justify-content:center;margin-top:12px" }, (card.lectures || []).map((k) => h("a", { class: "pill", href: `#/lecture/${k}` }, `Lecture ${k}`)), concept(card.concept) ? h("a", { class: "pill", href: `#/concept/${card.concept}` }, "Concept card") : null));
    const rate = (q) => {
      const cur = st[card.concept] || { box: 0 };
      const box = q === "again" ? 0 : q === "hard" ? Math.max(1, cur.box) : Math.min(BOX_DAYS.length - 1, cur.box + (q === "easy" ? 2 : 1));
      st[card.concept] = { box, due: Date.now() + (box === 0 ? 60 * 1000 : BOX_DAYS[box] * 86400 * 1000), seen: (cur.seen || 0) + 1 };
      save(); next();
    };
    const grades = h("div", { class: "row", hidden: true, style: "justify-content:center;margin-top:18px" },
      h("button", { onclick: () => rate("again") }, "Again"), h("button", { onclick: () => rate("hard") }, "Hard"),
      h("button", { class: "primary", onclick: () => rate("good") }, "Good"), h("button", { onclick: () => rate("easy") }, "Easy"));
    const show = h("button", { class: "primary", style: "margin-top:18px", onclick: () => { back.hidden = false; grades.hidden = false; show.hidden = true; } }, "Show the answer");
    stage.replaceChildren(h("div", { class: "card review-card" }, h("div", { class: "small faint" }, st[card.concept] ? "Review" : "New card"),
      h("div", { class: "front" }, cap(card.front)), back, show, grades, dev(card.concept + (st[card.concept] ? ` box ${st[card.concept].box}` : ""))));
  };
  next();
  return h("div", {}, h("h1", {}, "Review"), h("div", { class: "row" }, h("span", { class: "muted" }, "Cards from"), upto, h("span", { class: "spacer" }), counts,
    h("button", { class: "ghost small", onclick: () => { if (confirm("Forget your review progress in this browser?")) { for (const k of Object.keys(st)) delete st[k]; save(); next(); } } }, "Reset")), stage);
}

// ------------------------------------------------------------------ questions
async function ask(q) {
  const lec = S.view && S.view.lecture || null;
  const drawer = $("#drawer"), body = $("#drawer-body");
  drawer.hidden = false;
  const ans = h("div", {}, h("span", { class: "spin" }), h("span", { class: "muted" }, " Looking through the course…"));
  const item = h("div", { class: "qa-item" }, h("div", { class: "qa-q" }, q), lec ? h("div", { class: "small faint" }, `Asked from lecture ${lec}`) : null, ans);
  body.prepend(item);
  try {
    const r = await fetch("/api/ask", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ question: q, lecture: lec }) });
    const res = await r.json();
    if (res.available === false) { ans.replaceChildren(h("p", { class: "muted" }, res.answer || "Question answering is not available."), dev(res.error || "")); return; }
    const cites = res.citations || [];
    ans.replaceChildren(mdBlock(res.answer || "(no answer)"),
      cites.length ? h("ul", { class: "cites" }, cites.map((c) => h("li", {},
        c.lecture != null ? h("a", { class: "time", href: timeHref(c.lecture, c.start) }, `▶ Lecture ${c.lecture} · ${clock(c.start)}`) : null, " ", c.text || "", dev(" " + (c.fact || ""))))) : null,
      res.covered === false ? h("div", { class: "small muted", style: "margin-top:6px" }, "The course may not cover this.") : null,
      res.error ? dev(res.error) : null,
      res.steps ? h("details", { class: "dev" }, h("summary", {}, "steps"), h("pre", { style: "white-space:pre-wrap" }, JSON.stringify(res.steps, null, 1))) : null);
  } catch (e) {
    ans.replaceChildren(h("p", { class: "muted" }, "The question could not be sent. Is the server running?"));
  }
}

// ------------------------------------------------------------------ start
function setDev(on) { document.body.classList.toggle("devmode", on); $("#dev-box").checked = on; store("dev", on); }
async function main() {
  const params = new URLSearchParams(location.search);
  setDev(params.has("dev") ? params.get("dev") !== "0" : !!store("dev"));
  $("#dev-box").addEventListener("change", (e) => setDev(e.target.checked));
  $("#theme-btn").addEventListener("click", () => {
    const dark = getComputedStyle(document.documentElement).colorScheme.includes("dark");
    document.documentElement.setAttribute("data-theme", dark ? "light" : "dark");
    try { localStorage.setItem("v3:theme", dark ? "light" : "dark"); } catch (e) { /* not kept */ }
  });
  $("#ask-form").addEventListener("submit", (e) => { e.preventDefault(); const q = $("#ask-input").value.trim(); if (q) { ask(q); $("#ask-input").value = ""; } });
  $("#drawer-close").addEventListener("click", () => ($("#drawer").hidden = true));
  S.course = await getJSON("/api/course");
  if (!S.course) { $("#app").replaceChildren(h("div", { class: "empty" }, "The course could not be loaded.")); return; }
  document.title = S.course.title;
  $("#brand").textContent = S.course.title;
  if (!S.course.layers.spaced_review) $("#nav-review").hidden = true;
  if (!S.course.layers.knowledge) document.querySelectorAll('.nav a[href="#/glossary"], .nav a[href="#/map"]').forEach((a) => (a.hidden = true));
  window.addEventListener("hashchange", render);
  render();
}
main();
