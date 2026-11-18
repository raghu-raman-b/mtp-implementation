/* v3 course viewer, design C "Signal".
 * Served by serve.py; no build step, one file. Its sections: helpers, data, progress and notes, the markdown renderer;
 * the concept maps; the activities; the player and the lecture page; the router, pages, Ask, search and start-up.
 *
 * Routes   #/                              the roadmap (home): continue card and the weeks of the course
 *          #/lecture/<key>[/watch|activities[/A12]|recap]   a lecture; #/lecture/<key>/t/<sec> plays it from there
 *          #/map[/<key>]                   lecture map: how the lectures build on each other
 *          #/concepts[/<key>]              concept map of a lecture; #/concepts/explore[/<C0042>] one concept's links
 *          #/ask                           the Ask chat
 *          #/concept/<C0042>  #/glossary  #/review
 * Every layer is optional: a lecture without knowledge/ shows its 1b segments and the 0a transcript only.
 * Developer mode (?dev=1 or the menu) shows IDs, judge marks, where things came from and the answer timing; the
 * learner never sees counts of pipeline internals. */
"use strict";

/* ------------------------------------------------------------------ helpers, the data caches, the learner's progress and notes (this browser), the safe
 * markdown renderer for answers.
 *
 * Data: only the server's lean routes (/api/home at start; /api/view/<key> when a lecture is opened; /api/glossary,
 * /api/coursemap, /api/concept/<id>, /api/review, /api/qa_status when their page is opened). Each answer is fetched
 * once and kept in the page; the concepts and facts they carry go into one cache (S.cc, S.fc).
 * Display rules are applied by the server: a connecting concept ("connecting": true) has no card and no definition;
 * the page draws it muted and never links it. */

const S = { course: null, goals: {}, cc: {}, fc: {}, lec: {}, req: new Map(), view: null, asks: [], from: null };

// ------------------------------------------------------------------ DOM helpers
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
    else if (k === "style" && typeof v === "object") Object.assign(el.style, v);
    else if (k.startsWith("on") && typeof v === "function") el.addEventListener(k.slice(2), v);
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
// icons (our own constant paths; stroke icons follow the text colour)
const ICONS = {
  play: [["path", { d: "M7 4l13 8-13 8z", fill: "currentColor", stroke: "none" }]],
  pause: [["rect", { x: 6, y: 4.5, width: 4, height: 15, rx: 1, fill: "currentColor", stroke: "none" }], ["rect", { x: 14, y: 4.5, width: 4, height: 15, rx: 1, fill: "currentColor", stroke: "none" }]],
  back10: [["path", { d: "M4 12a8 8 0 1 0 2.4-5.7" }], ["path", { d: "M4 4v4h4" }], ["text", { x: 12, y: 15.5, "font-size": 7, "text-anchor": "middle", fill: "currentColor", stroke: "none", "font-family": "Geist, sans-serif" }, "10"]],
  fwd10: [["path", { d: "M20 12a8 8 0 1 1-2.4-5.7" }], ["path", { d: "M20 4v4h-4" }], ["text", { x: 12, y: 15.5, "font-size": 7, "text-anchor": "middle", fill: "currentColor", stroke: "none", "font-family": "Geist, sans-serif" }, "10"]],
  cc: [["rect", { x: 3, y: 5, width: 18, height: 14, rx: 3 }], ["path", { d: "M10 10.5a2 2 0 1 0 0 3M17 10.5a2 2 0 1 0 0 3" }]],
  notes: [["path", { d: "M6 3h9l4 4v14H6z" }], ["path", { d: "M9 11h7M9 15h7" }]],
  full: [["path", { d: "M4 9V4h5M20 9V4h-5M4 15v5h5M20 15v5h-5" }]],
  unfull: [["path", { d: "M9 4v5H4M15 4v5h5M9 20v-5H4M15 20v-5h5" }]],
  left: [["path", { d: "M15 5l-7 7 7 7" }]],
  chev: [["path", { d: "M6 9l6 6 6-6" }]],
  check: [["path", { d: "M5 12l5 5 9-10" }]],
  close: [["path", { d: "M6 6l12 12M18 6L6 18" }]],
  arrow: [["path", { d: "M5 12h14M13 6l6 6-6 6" }]],
  cards: [["rect", { x: 4, y: 6, width: 13, height: 14, rx: 2 }], ["path", { d: "M8 3h11a2 2 0 0 1 2 2v12" }]],
};
function icon(name, size = 18, sw = 1.8) {
  return s("svg", { width: size, height: size, viewBox: "0 0 24 24", fill: "none", stroke: "currentColor", "stroke-width": sw, "stroke-linecap": "round", "stroke-linejoin": "round", "aria-hidden": "true", focusable: "false" },
    (ICONS[name] || []).map(([t, a, txt]) => s(t, a, txt)));
}
function clock(t) {
  t = Math.max(0, Math.floor(t || 0));
  const hh = Math.floor(t / 3600), m = Math.floor((t % 3600) / 60), sec = t % 60;
  return (hh ? hh + ":" + String(m).padStart(2, "0") : m) + ":" + String(sec).padStart(2, "0");
}
const cap = (x) => (!x ? x : /^[a-z][A-Z]/.test(x) ? x : x[0].toUpperCase() + x.slice(1));
const dev = (...kids) => h("span", { class: "dev" }, ...kids);
const isDev = () => document.body.classList.contains("devmode");
const plural = (n, one, many) => `${n} ${n === 1 ? one : many || one + "s"}`;
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
// vendored libraries the first screen does not need, loaded once when a page needs them (window.LAZY, index.html)
const lazyScripts = {};
function need(name) {
  if (!lazyScripts[name]) {
    lazyScripts[name] = new Promise((resolve, reject) => {
      const sc = document.createElement("script");
      sc.src = (window.LAZY || {})[name];
      sc.onload = resolve;
      sc.onerror = () => { delete lazyScripts[name]; reject(new Error(`${name} did not load`)); };
      document.head.append(sc);
    });
  }
  return lazyScripts[name];
}
const needDagre = () => (typeof dagre !== "undefined" ? Promise.resolve() : need("dagre"));
const needMath = () => (window.katex && window.renderMath ? Promise.resolve() : need("katex").then(() => Promise.all([need("autorender"), need("math")])));
const idle = (fn, ms = 300) => setTimeout(() => (window.requestIdleCallback ? requestIdleCallback(fn, { timeout: 2000 }) : fn()), ms);
let toastTimer = null;
function toast(...kids) {
  const t = $("#toast");
  t.replaceChildren(icon("check", 14, 2.6), ...kids);
  t.classList.add("on");
  clearTimeout(toastTimer);
  toastTimer = setTimeout(() => t.classList.remove("on"), 2200);
}

// ------------------------------------------------------------------ data
function cget(url) {  // a GET kept in the page (as its promise, so two callers share one request); a miss is not kept
  let p = S.req.get(url);
  if (!p) {
    p = getJSON(url).then((x) => { if (x == null) S.req.delete(url); return x; }, (e) => { S.req.delete(url); throw e; });
    S.req.set(url, p);
  }
  return p;
}
function addConcepts(map, fillOnly) {  // fillOnly: a partial record (a name, a shortened definition) never overwrites
  for (const [cid, c] of Object.entries(map || {})) {
    const old = S.cc[cid];
    if (!old) S.cc[cid] = { ...c };
    else if (fillOnly) { for (const [k, v] of Object.entries(c)) if (old[k] == null || old[k] === "") old[k] = v; }
    else Object.assign(old, c);
  }
}
function addFacts(map) { Object.assign(S.fc, map || {}); }
function adaptView(V) {  // /api/view/<key> in the shape the lecture page reads
  addConcepts(V.concepts);
  addFacts(V.facts);
  for (const n of (V.map && V.map.nodes) || []) addConcepts({ [n.id]: { name: n.name, connecting: !!n.connecting } }, true);
  const KL = V.source === "knowledge" ? { goal: V.goal, objectives: V.objectives || [], course_goals: V.course_goals || [], concepts: V.kinds || {},
    map: V.map, prerequisites: V.prerequisites || { direct: [], all: [] }, before: V.before || [] } : null;
  return { ...V, knowledge: KL, activities: V.activities ? { activities: V.activities } : null };
}
function lecture(key) {  // fetched when the lecture is first opened (or prefetched), then kept
  if (!S.lec[key]) {
    S.lec[key] = getJSON(`/api/view/${encodeURIComponent(key)}`).then((V) => { if (!V) { delete S.lec[key]; return null; } return adaptView(V); },
      (e) => { delete S.lec[key]; throw e; });
  }
  return S.lec[key];
}
function prefetch(key) { if (key && !S.lec[key] && S.course.lectures.some((l) => l.key === key)) lecture(key).catch(() => {}); }
const lecInfo = (k) => S.course.lectures.find((l) => l.key === k) || { key: k, title: `Lecture ${k}` };
const concept = (cid) => S.cc[cid] || null;
const cname = (cid) => cap((concept(cid) || {}).name || cid);
const isConn = (cid) => !!(concept(cid) || {}).connecting;   // a connecting concept: no card, no definition, muted
const fact = (fid) => S.fc[fid] || null;
const hasKnowledge = () => !!(S.course && S.course.layers.knowledge);
const preferYouTube = () => { const v = store("yt"); return v == null ? !!(S.course && S.course.prefer_youtube) : !!v; };
const partTitle = (sg, i) => (sg && sg.title) || `Part ${i + 1}`;

// ------------------------------------------------------------------ the learner's progress and notes (this browser)
// progress:<course> = {last: {lecture, t, at}, lec: {<key>: {t, max, end, done}}}
function progress() { return store(`progress:${S.course.course}`) || { last: null, lec: {} }; }
function saveProgress(key, t, end, done) {
  const P = progress();
  const p = P.lec[key] || { t: 0, max: 0 };
  p.t = t; p.max = Math.max(p.max || 0, t); if (end) p.end = end; if (done) p.done = true;
  P.lec[key] = p;
  P.last = { lecture: key, t, at: Date.now() };
  store(`progress:${S.course.course}`, P);
}
function notesAll() { return store(`notes:${S.course.course}`) || []; }
function notesOf(key) { return notesAll().filter((n) => n.lecture === key).sort((a, b) => a.start - b.start); }
function noteHas(id) { return notesAll().some((n) => n.id === id); }
function noteToggle(sent, key) {  // a caption sentence saved to (or removed from) the notes, with its ID and time
  const all = notesAll(), i = all.findIndex((n) => n.id === sent.id);
  if (i >= 0) all.splice(i, 1);
  else all.push({ id: sent.id, lecture: key, start: sent.start, text: sent.text, at: Date.now() });
  store(`notes:${S.course.course}`, all);
  notesChanged();
  return i < 0;
}
function noteRemove(id) { store(`notes:${S.course.course}`, notesAll().filter((n) => n.id !== id)); notesChanged(); }
const noteListeners = new Set();
function onNotes(el, fn) {  // fn runs when the notes change while el is in the page; dropped once el has left it
  const w = () => { if (el.isConnected) { w.seen = true; fn(); } else if (w.seen) noteListeners.delete(w); };
  noteListeners.add(w);
}
function notesChanged() { for (const fn of noteListeners) { try { fn(); } catch (e) { console.error(e); } } }
function noteRow(n, opts = {}) {
  return h("a", { class: "note-row", href: timeHref(n.lecture, n.start), onclick: opts.onopen || null },
    h("span", { class: "nm" }, h("span", { class: "idchip" }, n.id), h("span", { class: "tm" }, "▶ " + (opts.withLecture ? `Lecture ${n.lecture} · ` : "") + clock(n.start))),
    h("span", { class: "tx" }, n.text),
    h("button", { class: "del", "aria-label": `Remove note ${n.id}`, title: "Remove", onclick: (ev) => { ev.preventDefault(); ev.stopPropagation(); noteRemove(n.id); } }, icon("close", 14, 2)));
}

// ------------------------------------------------------------------ links
function timeHref(lec, t) { return `#/lecture/${lec}/t/${Math.round((t || 0) * 10) / 10}`; }
function timeLink(lec, t, here) {
  const label = here === lec ? clock(t) : `Lecture ${lec} · ${clock(t)}`;
  return h("a", { class: "tlink", href: timeHref(lec, t), title: "Watch from here" }, "▶ " + label);
}
function conceptPill(cid, kind) {  // a connecting concept is plain text (no card to open)
  if (isConn(cid)) return h("span", { class: "pill conn", title: "Explained through its links in the lectures" }, cname(cid), dev(" " + cid));
  return h("a", { class: "pill" + (kind ? " k-" + kind : ""), href: `#/concept/${cid}` }, cname(cid), dev(" " + cid));
}
function factLinks(fids, here) {
  const fs = (fids || []).map((f) => [f, fact(f)]).filter(([, x]) => x);
  if (!fs.length) return (fids || []).length ? h("div", { class: "fact-links" }, dev("facts: " + fids.join(", "))) : null;
  const seen = new Set();
  return h("div", { class: "fact-links" }, h("span", {}, "Taught at"),
    fs.filter(([, x]) => { const k = x.lecture + "@" + Math.round(x.start); if (seen.has(k)) return false; seen.add(k); return true; })
      .map(([f, x]) => h("span", { title: x.text }, timeLink(x.lecture, x.start, here), dev(" " + f))));
}
function factList(fids, here, defining) {
  const set = new Set(defining || []);
  return h("ul", { class: "facts" }, (fids || []).map((f) => {
    const x = fact(f);
    if (!x) return h("li", {}, h("span", { class: "tx muted" }, f));
    return h("li", { class: set.has(f) ? "defining" : "" }, h("span", { class: "tx" }, x.text, dev(f)), timeLink(x.lecture, x.start, here));
  }));
}

// ------------------------------------------------------------------ answers: a small, safe markdown renderer
// DOM nodes only, never innerHTML. Paragraphs, "* "/"- " and "1. " lists, **bold**, *italic*, `code`. Formulas are kept
// out of the markdown pass ($$...$$, \[...\], \(...\), $...$ with math.js's guard), so "$x_*y*$" stays as written for
// renderMath (math.js) to typeset once the answer is complete. Citations "(lecture 4, 6:01)" and "(lecture 4, 6:01;
// lecture 5, 9:21)" become chips that open the lecture at that time.
const TIME_RE = "\\d{1,2}(?::\\d{2}){1,2}";
const CITE_GROUP = new RegExp(`\\(\\s*((?:lecture\\s+\\d+[a-z]?,\\s*)?${TIME_RE}(?:\\s*[;,]\\s*(?:lecture\\s+\\d+[a-z]?,\\s*)?${TIME_RE})*)\\s*\\)`, "g");
const INLINE_MATH = /\u0000(\d+)\u0000|\\\([\s\S]+?\\\)|(^|[^\\$])(\$(?![\s\d$])(?:[^$\\\n]|\\.)+?(?<![\s\\])\$(?!\d))/g;
const secsOf = (txt) => txt.split(":").map(Number).reduce((a, b) => a * 60 + b, 0);
function citeChip(lec, time) {
  return h("a", { class: "cite", href: timeHref(lec, secsOf(time)), title: `Watch lecture ${lec} at ${time}` }, icon("play", 8), `Lecture ${lec}, ${time}`);
}
function citeGroup(inner) {  // "lecture 4, 6:01; lecture 5, 9:21" (a time without its lecture belongs to the one before)
  const out = [];
  let lec = null;
  for (const part of inner.split(/\s*;\s*|\s*,\s*(?=lecture\b)|(?<=\d:\d\d)\s*,\s*/)) {
    const m = part.match(new RegExp(`^(?:lecture\\s+(\\d+[a-z]?),\\s*)?(${TIME_RE})$`));
    if (!m) return null;
    lec = m[1] || lec;
    if (!lec) return null;
    out.push(citeChip(lec, m[2]));
  }
  return out;
}
function mdText(text) {  // markdown inline on text that holds no formula
  const out = [];
  const re = new RegExp(`\\*\\*([^*]+)\\*\\*|\\*([^*\\s][^*]*)\\*|\`([^\`]+)\`|${CITE_GROUP.source}|lecture (\\d+[a-z]?), (${TIME_RE})`, "g");
  let last = 0, m;
  while ((m = re.exec(text))) {
    let node = null;
    if (m[1] != null) node = h("b", {}, m[1]);
    else if (m[2] != null) node = h("i", {}, m[2]);
    else if (m[3] != null) node = h("code", {}, m[3]);
    else if (m[4] != null) node = citeGroup(m[4]);
    else node = citeChip(m[5], m[6]);
    if (!node) continue;  // a bracket that only looked like a citation stays text
    if (m.index > last) out.push(text.slice(last, m.index));
    out.push(node);
    last = re.lastIndex;
  }
  if (last < text.length) out.push(text.slice(last));
  return out;
}
function mdInline(text, maths = []) {  // formulas stay raw text nodes; the rest goes through mdText
  const out = [];
  let last = 0, m;
  INLINE_MATH.lastIndex = 0;
  while ((m = INLINE_MATH.exec(text))) {
    let start = m.index, raw;
    if (m[1] != null) raw = maths[+m[1]] || "";
    else if (m[3] != null) { start += m[2].length; raw = m[3]; }
    else raw = m[0];
    if (start > last) out.push(...mdText(text.slice(last, start)));
    out.push(document.createTextNode(raw));
    last = INLINE_MATH.lastIndex;
  }
  if (last < text.length) out.push(...mdText(text.slice(last)));
  return out;
}
function mdBlock(text, caret) {
  const maths = [];
  const src = String(text || "").replace(/\$\$[\s\S]+?\$\$|\\\[[\s\S]+?\\\]/g, (x) => { maths.push(x); return `\u0000${maths.length - 1}\u0000`; });
  const box = h("div", { class: "md" });
  let list = null, para = [], lastEl = null;
  const flush = () => { if (para.length) { lastEl = h("p", {}, ...mdInline(para.join(" "), maths)); box.append(lastEl); para = []; } };
  for (const raw of src.split("\n")) {
    const line = raw.trim();
    const bullet = line.match(/^(?:[*\-•]|\d+[.)])\s+(.*)$/);
    if (bullet) {
      flush();
      const ordered = /^\d/.test(line);
      if (!list || list.ordered !== ordered) { list = { ordered, el: h(ordered ? "ol" : "ul", {}) }; box.append(list.el); }
      lastEl = h("li", {}, ...mdInline(bullet[1], maths));
      list.el.append(lastEl);
    } else if (!line) { flush(); list = null; }
    else { list = null; para.push(line.replace(/^#+\s*/, "")); }
  }
  flush();
  if (caret) (lastEl || box).append(h("span", { class: "caret", "aria-hidden": "true" }));
  return box;
}

/* ------------------------------------------------------------------ concept maps (one renderer for every map), the lecture map (course overview), the
 * concept explorer and the lecture concept maps. Connecting concepts are drawn muted and are never clickable. */

// ------------------------------------------------------------------ concept maps
// One renderer for every map (lecture maps, the two map activities, the course maps). Labels are measured and
// wrapped; three layouts:
//   graph   dagre, every link labelled (the key-concepts view, small maps, a concept's neighbourhood);
//           dense: true lays it out without label space and shows a link's label on hover or selection
//   parts   the concepts grouped by the lecture part that teaches them, the parts in lecture order like lines of
//           text; links inside a part drawn faint, links between parts drawn only for the hovered or selected concept
//   custom  opts.place(nodes, edges) gives the positions (the course's lecture overview)
// Click a node: its neighbourhood stays lit, the rest fades, its card opens (opts.card). Double-click: zoom to it
// (or opts.onDouble). Drag pans; Ctrl/⌘ + scroll, a pinch or the buttons zoom; Esc or a click on the background
// clears the selection.
const KINDS = [["introduced", "Introduced here"], ["met_again", "Met again"], ["assumed", "Assumed (not taught in the course)"],
  ["defined_later", "Explained in a later lecture"]];
const MAPF = { node: 13, edge: 11, nodeW: 150, edgeW: 124, lineN: 16, lineE: 13 };
const CORE_MAX = 20;          // a lecture map opens on at most this many concepts ...
const CORE_FROM = 27;         // ... when it has at least this many
let mapSeq = 0, measureCtx = null, mapFont = null;
function tw(text, size, weight) {
  if (!measureCtx) { measureCtx = document.createElement("canvas").getContext("2d"); mapFont = getComputedStyle(document.body).fontFamily || "sans-serif"; }
  measureCtx.font = `${weight || 400} ${size}px ${mapFont}`;
  return measureCtx.measureText(text).width;
}
function wrapText(text, maxW, size, weight, maxLines = 3) {
  const lines = [];
  let cur = "";
  for (const w of String(text || "").split(/\s+/).filter(Boolean)) {
    const t = cur ? cur + " " + w : w;
    if (!cur || tw(t, size, weight) <= maxW) cur = t;
    else { lines.push(cur); cur = w; }
  }
  if (cur) lines.push(cur);
  if (lines.length <= maxLines) return lines;
  const kept = lines.slice(0, maxLines);
  let last = kept[maxLines - 1] + "…";
  while (tw(last, size, weight) > maxW && last.length > 2) last = last.slice(0, -2).trimEnd() + "…";
  kept[maxLines - 1] = last;
  return kept;
}
function textBlock(lines, size, weight, maxW, maxLines) {
  const ls = Array.isArray(lines) ? lines : wrapText(lines, maxW, size, weight, maxLines);
  return { lines: ls, w: Math.max(0, ...ls.map((l) => tw(l, size, weight))) };
}
function svgLines(lines, lineH, attrs = {}, x = 0) {  // a <text> of centred tspans around y = 0 (or from attrs.y0)
  const y0 = attrs.y0 != null ? attrs.y0 : -((lines.length - 1) * lineH) / 2;
  const a = { ...attrs }; delete a.y0;
  return s("text", { "dominant-baseline": "central", ...a }, lines.map((l, i) => s("tspan", { x, y: y0 + i * lineH }, l)));
}
function sizeNode(n) {
  if (n.circle) { n.lines = [n.label]; n.w = n.h = 2 * n.circle; return; }
  const weight = n.kind === "introduced" || n.cls === "centre" ? 650 : 550;
  const tb = textBlock(n.label, MAPF.node, weight, n.maxW || MAPF.nodeW, 3);
  const pad = n.badge ? n.badge.r * 2 + 18 : 0;
  n.lines = tb.lines;
  n.w = Math.ceil(n.fixedW || tb.w + 22 + pad);
  n.h = Math.ceil(Math.max(n.badge ? n.badge.r * 2 + 12 : 0, tb.lines.length * MAPF.lineN + 14));
}
function dagreLayout(nodes, edges, dir, labels) {
  const G = new dagre.graphlib.Graph({ multigraph: true });
  G.setGraph({ rankdir: dir, nodesep: labels ? 16 : 14, ranksep: labels ? 30 : 38, edgesep: 8, marginx: 14, marginy: 14 });
  G.setDefaultEdgeLabel(() => ({}));
  for (const n of nodes) G.setNode(n.id, { width: n.w, height: n.h });
  edges.forEach((e) => {
    if (e.from === e.to || !G.hasNode(e.from) || !G.hasNode(e.to)) return;
    G.setEdge(e.from, e.to, labels && e.lab ? { width: e.lab.w + 10, height: e.lab.lines.length * MAPF.lineE + 6, labelpos: "c" } : { width: 0, height: 0 }, e.key);
  });
  dagre.layout(G);
  const pos = {}, route = {};
  for (const id of G.nodes()) { const v = G.node(id); pos[id] = { x: v.x, y: v.y }; }
  for (const k of G.edges()) { const ed = G.edge(k); route[k.name] = { points: ed.points, lx: ed.x, ly: ed.y }; }
  return { pos, route, width: G.graph().width, height: G.graph().height };
}
function bestGraph(nodes, edges, labels, boxW, boxH) {  // LR or TB, whichever shows the map larger in the box
  let best = null;
  for (const dir of ["LR", "TB"]) {
    const L = dagreLayout(nodes, edges, dir, labels);
    L.scale = Math.min(boxW / L.width, boxH / L.height);
    if (!best || L.scale > best.scale * 1.02) best = L;
  }
  return best;
}
function partsLayout(nodes, edges, groups, maxW) {
  const byId = Object.fromEntries(nodes.map((n) => [n.id, n]));
  const GAP = 16, PAD = 14;
  const panels = [];
  for (const g of groups) {
    const ns = g.ids.map((id) => byId[id]).filter(Boolean);
    if (!ns.length) continue;
    const ids = new Set(ns.map((n) => n.id));
    const inner = edges.filter((e) => ids.has(e.from) && ids.has(e.to) && e.from !== e.to);
    const linked = new Set(inner.flatMap((e) => [e.from, e.to]));
    const conn = ns.filter((n) => linked.has(n.id)), iso = ns.filter((n) => !linked.has(n.id));
    let L = { pos: {}, route: {}, width: 0, height: 0 };
    if (conn.length) {  // the more compact of LR and TB that fits the width
      const cands = ["LR", "TB"].map((d) => dagreLayout(conn, inner, d, false));
      const fit = cands.filter((c) => c.width <= maxW - 2 * PAD);
      const pool = fit.length ? fit : cands;
      L = pool.reduce((a, b) => (Math.abs(Math.log(a.width / a.height / 0.9)) <= Math.abs(Math.log(b.width / b.height / 0.9)) ? a : b));
    }
    // the concepts with no link inside the part flow in rows under it
    const flowW = Math.max(L.width - 28, Math.min(maxW - 2 * PAD, 360));
    let x = 0, y = 0, rowH = 0, isoW = 0;
    const isoPos = {};
    for (const n of iso) {
      if (x && x + n.w > flowW) { x = 0; y += rowH + 10; rowH = 0; }
      isoPos[n.id] = { x: x + n.w / 2, y: y + n.h / 2 };
      x += n.w + 10; rowH = Math.max(rowH, n.h); isoW = Math.max(isoW, x - 10);
    }
    const isoH = iso.length ? y + rowH : 0;
    const innerW = Math.max(L.width ? L.width - 28 : 0, isoW, 200);
    const title = textBlock(g.title, 12, 700, innerW, 1), sub = textBlock(g.sub || "", 12.5, 400, innerW, 3);
    const headH = 14 + 18 + sub.lines.length * 16 + 6;
    panels.push({ g, L, isoPos, title, sub, headH, isoH, w: innerW + 2 * PAD, h: headH + (L.height ? L.height - 28 : 0) + (L.height && iso.length ? 12 : 0) + isoH + PAD + 4 });
  }
  // shelf packing in lecture order: left to right, then the next row
  const pos = {}, route = {};
  let x = 0, y = 0, rowH = 0, width = 0;
  const rows = [[]];
  for (const p of panels) {
    if (x && x + p.w > maxW) { x = 0; y += rowH + GAP; rowH = 0; rows.push([]); }
    p.x = x; p.y = y; x += p.w + GAP; rowH = Math.max(rowH, p.h); width = Math.max(width, x - GAP);
    rows[rows.length - 1].push(p);
  }
  for (const row of rows) {  // stretch the panels of a row to the row's height and the row to the full width
    const rh = Math.max(...row.map((p) => p.h)), used = row.reduce((a, p) => a + p.w, 0) + GAP * (row.length - 1);
    const extra = row.length > 1 || used > width * 0.6 ? (width - used) / row.length : 0;
    let cx = 0;
    for (const p of row) { p.x = cx; p.w += extra; p.h = rh; cx += p.w + GAP; }
  }
  for (const p of panels) {
    const ox = p.x + (p.w - (p.L.width ? p.L.width - 28 : 0)) / 2 - 14, oy = p.y + p.headH - 14;
    for (const [id, v] of Object.entries(p.L.pos)) pos[id] = { x: v.x + ox, y: v.y + oy };
    for (const [k, r] of Object.entries(p.L.route)) route[k] = { points: r.points.map((q) => ({ x: q.x + ox, y: q.y + oy })), lx: r.lx + ox, ly: r.ly + oy };
    const iy = p.y + p.headH + (p.L.height ? p.L.height - 28 + 12 : 0), ix = p.x + 14;
    for (const [id, v] of Object.entries(p.isoPos)) pos[id] = { x: v.x + ix, y: v.y + iy };
  }
  return { pos, route, panels, width, height: y + rowH };
}
function curveThrough(pts) {
  let d = `M${pts[0].x},${pts[0].y}`;
  for (let i = 1; i < pts.length - 1; i++) {
    const mx = (pts[i].x + pts[i + 1].x) / 2, my = (pts[i].y + pts[i + 1].y) / 2;
    d += ` Q${pts[i].x},${pts[i].y} ${mx},${my}`;
  }
  const l = pts[pts.length - 1];
  return d + ` L${l.x},${l.y}`;
}
function boxEdge(c, w, h, tx, ty) {  // where the line from the centre c towards (tx, ty) leaves a w x h box
  const dx = tx - c.x, dy = ty - c.y;
  if (!dx && !dy) return { x: c.x, y: c.y };
  const k = Math.min(Math.abs((w / 2 + 2) / (dx || 1e-9)), Math.abs((h / 2 + 2) / (dy || 1e-9)));
  return { x: c.x + dx * k, y: c.y + dy * k };
}
function straightRoute(a, b, A, B, bend = 0.12) {  // a gentle curve between two boxes, the label at its middle
  const out = (n, c, t) => {
    if (!n.circle) return boxEdge(c, n.w, n.h, t.x, t.y);
    const dx = t.x - c.x, dy = t.y - c.y, l = Math.hypot(dx, dy) || 1;
    return { x: c.x + dx / l * (n.circle + 2), y: c.y + dy / l * (n.circle + 2) };
  };
  const p0 = out(a, A, B), p1 = out(b, B, A);
  const mx = (p0.x + p1.x) / 2, my = (p0.y + p1.y) / 2, dx = p1.x - p0.x, dy = p1.y - p0.y;
  const cx = mx - dy * bend, cy = my + dx * bend;
  return { d: `M${p0.x},${p0.y} Q${cx},${cy} ${p1.x},${p1.y}`, lx: (p0.x + 2 * cx + p1.x) / 4, ly: (p0.y + 2 * cy + p1.y) / 4 };
}
function mapBoxWidth() { const a = $("#app"); return Math.max(320, Math.min(1240, (a && a.clientWidth ? a.clientWidth - 40 : 1200))); }

function drawMap(nodes, edges, opts = {}) {
  if (typeof dagre === "undefined" && opts.mode !== "custom") return h("div", { class: "note" }, "The map cannot be drawn (layout library missing).");
  if (!nodes.length) return h("div", { class: "faint" }, opts.empty || "Nothing to draw.");
  const uid = "m" + (++mapSeq);
  nodes = nodes.map((n) => ({ ...n }));
  nodes.forEach(sizeNode);
  const byId = Object.fromEntries(nodes.map((n) => [n.id, n]));
  edges = edges.filter((e) => byId[e.from] && byId[e.to] && e.from !== e.to).map((e, i) => ({ ...e, key: "e" + i }));
  const dense = !!opts.dense || opts.mode === "parts" || opts.mode === "custom";
  for (const e of edges) if (e.label) e.lab = textBlock(e.label, MAPF.edge, e.cls === "blank" ? 700 : 400, MAPF.edgeW, 3);
  const boxW = opts.boxW || mapBoxWidth(), maxH = opts.height || 600;
  let L;
  if (opts.mode === "custom") L = opts.place(nodes, edges, boxW);
  else if (opts.mode === "parts") L = partsLayout(nodes, edges, opts.groups, Math.max(boxW, 600));
  else L = bestGraph(nodes, edges.filter((e) => !e.extra), !dense, boxW, maxH);  // extra links: drawn on selection only
  const tall = opts.mode === "parts" || opts.mode === "custom";
  const cw = Math.max(L.width, 1), ch = Math.max(L.height, 1);
  const fitScale = Math.min(boxW / cw, tall ? 1 : maxH / ch, opts.maxScale || 1.15);
  const H = Math.round(tall ? Math.max(200, ch * Math.min(1, boxW / cw) + 4) : Math.max(220, Math.min(maxH, ch * fitScale + 30)));

  const wrap = h("div", { class: "cmap-wrap" + (tall ? " tall" : "") });
  const svg = s("svg", { class: "cmap", role: "group", "aria-label": opts.aria || "Concept map" });
  svg.style.height = H + "px";
  svg.append(s("defs", {},
    s("marker", { id: uid + "a", viewBox: "0 0 10 10", refX: 9, refY: 5, markerWidth: 6.5, markerHeight: 6.5, orient: "auto-start-reverse", class: "arrowhead" }, s("path", { d: "M0,1 L10,5 L0,9 z" })),
    s("marker", { id: uid + "h", viewBox: "0 0 10 10", refX: 9, refY: 5, markerWidth: 6.5, markerHeight: 6.5, orient: "auto-start-reverse", class: "arrowhead hi" }, s("path", { d: "M0,1 L10,5 L0,9 z" }))));
  const scene = s("g", {});
  svg.append(scene);
  const gPanels = s("g", {}), gEdges = s("g", {}), gLabels = s("g", {}), gNodes = s("g", {});
  scene.append(gPanels, gEdges, gNodes, gLabels);

  // panels (lecture parts, or the week bands of the course overview)
  for (const p of L.panels || []) {
    const g = s("g", { class: "panel" + (p.band ? " band" : "") + (p.cls ? " " + p.cls : "") });
    g.append(s("rect", { x: p.x, y: p.y, width: p.w, height: p.h, rx: p.band ? 10 : 12 }));
    const tx = p.x + 14, tl = p.title.lines.length ? p.title.lines : [""];
    const title = s("text", { class: "ptitle" }, tl.map((l, i) => s("tspan", { x: tx, y: p.y + 22 + i * 17 }, l)));
    if (p.g.time != null) title.append(s("tspan", { class: "ptime", dx: 8 }, clock(p.g.time)));
    g.append(title, svgLines(p.sub.lines, 16, { class: "psub", y0: p.y + 22 + (tl.length - 1) * 17 + 20 }, tx));
    if (p.g.href) {
      g.classList.add("link");
      g.addEventListener("click", (ev) => { if (!dragged) { ev.stopPropagation(); location.hash = p.g.href; } });
      g.append(s("title", {}, p.g.hrefTitle || "Watch this part"));
    }
    gPanels.append(g);
  }

  // edges: a visible path, a wide invisible one for the pointer, and the label
  const adj = {}, pairN = {};
  const E = edges.map((e) => {
    const A = L.pos[e.from], B = L.pos[e.to], a = byId[e.from], b = byId[e.to];
    let d, lx, ly, cross = false;
    const r = L.route && L.route[e.key];
    if (opts.route) ({ d, lx, ly } = opts.route(e, a, b, A, B));
    else if (r) { d = curveThrough(r.points); lx = r.lx; ly = r.ly; if (dense || lx == null) { const m = r.points[Math.floor(r.points.length / 2)]; lx = m.x; ly = m.y; } }
    else {  // parallel links between one pair fan out
      const pk = [e.from, e.to].sort().join("|"), k = (pairN[pk] = (pairN[pk] || 0) + 1) - 1;
      const bend = [0.12, -0.12, 0.26, -0.26, 0.4, -0.4][k % 6] * (e.from < e.to ? 1 : -1);
      ({ d, lx, ly } = straightRoute(a, b, A, B, bend));
      cross = opts.mode === "parts" || !!e.extra;
    }
    const path = s("path", { class: "edge" + (cross ? " cross" : "") + (e.cls ? " " + e.cls : ""), d, "marker-end": `url(#${uid}a)` });
    const hit = s("path", { class: "ehit", d });
    gEdges.append(path, hit);
    let lab = null;
    if (e.lab) {
      const lw = e.lab.w + 10, lh = e.lab.lines.length * MAPF.lineE + 5;
      lab = s("g", { class: "elabel" + (e.cls ? " " + e.cls : "") + ((dense || e.extra) && !e.always ? " lazy" : ""), transform: `translate(${lx},${ly})` },
        s("rect", { x: -lw / 2, y: -lh / 2, width: lw, height: lh, rx: 4 }), svgLines(e.lab.lines, MAPF.lineE, { "text-anchor": "middle" }));
      lab._w = lw; lab._h = lh; lab._x = lx; lab._y = ly;
      gLabels.append(lab);
    }
    const rec = { e, path, hit, lab, cross: cross || !!e.cross };
    if (rec.cross) path.classList.add("cross");
    if (e.always) path.classList.add("always");
    (adj[e.from] = adj[e.from] || []).push(rec);
    (adj[e.to] = adj[e.to] || []).push(rec);
    hit.addEventListener("pointerenter", () => hoverEdges([rec], true));
    hit.addEventListener("pointerleave", () => hoverEdges([rec], false));
    return rec;
  });

  // nodes
  const N = {};
  for (const n of nodes) {
    const P = L.pos[n.id];
    if (!P) continue;
    // a connecting concept (no definition of its own in the course): muted, not focusable, no card, no selection
    const g = s("g", n.conn ? { class: "node conn", transform: `translate(${P.x},${P.y})`, "aria-label": n.label + " (explained through its links)" }
      : { class: "node" + (n.kind ? " k-" + n.kind : "") + (n.cls ? " " + n.cls : ""), transform: `translate(${P.x},${P.y})`, tabindex: 0, role: "button", "aria-label": n.label });
    if (n.conn) g.append(s("title", {}, `${n.label}: explained through its links in the lectures`));
    if (n.circle) {
      g.classList.add("circ");
      g.append(s("circle", { r: n.circle }), s("text", { "text-anchor": "middle", "dominant-baseline": "central" }, n.label));
      if (n.title) g.append(s("title", {}, n.title));
    } else g.append(s("rect", { x: -n.w / 2, y: -n.h / 2, width: n.w, height: n.h, rx: n.badge ? 10 : 8 }));
    if (n.circle) { /* drawn */ } else if (n.badge) {
      const bx = -n.w / 2 + 8 + n.badge.r;
      g.append(s("circle", { class: "badge", cx: bx, cy: 0, r: n.badge.r }), s("text", { class: "badge-t", x: bx, y: 0, "text-anchor": "middle", "dominant-baseline": "central" }, n.badge.text));
      g.append(svgLines(n.lines, MAPF.lineN, { "text-anchor": "start" }, bx + n.badge.r + 9));
    } else g.append(svgLines(n.lines, MAPF.lineN, { "text-anchor": "middle" }));
    if (!n.conn) {
      g.addEventListener("click", (ev) => { ev.stopPropagation(); if (!dragged) select(n.id === sel ? null : n.id); });
      g.addEventListener("dblclick", (ev) => { ev.stopPropagation(); if (opts.onDouble) opts.onDouble(n.id); else { select(n.id); zoomTo(n.id); } });
      g.addEventListener("keydown", (ev) => { if (ev.key === "Enter" || ev.key === " ") { ev.preventDefault(); select(n.id); zoomTo(n.id, true); } });
    } else g.addEventListener("click", (ev) => ev.stopPropagation());
    g.addEventListener("pointerenter", () => hoverEdges(adj[n.id] || [], true));
    g.addEventListener("pointerleave", () => hoverEdges(adj[n.id] || [], false));
    gNodes.append(g);
    N[n.id] = g;
  }

  // labels shown on demand must not sit on each other: nudge them apart, in order of height
  const placeLabels = (recs) => {  // the concepts at the ends of these links are obstacles too
    const placed = [];
    for (const id of new Set(recs.flatMap((r) => [r.e.from, r.e.to]))) { const P = L.pos[id], n = byId[id]; if (P) placed.push({ x: P.x, y: P.y, w: n.w, h: n.h }); }
    for (const r of recs.filter((x) => x.lab).sort((p, q) => p.lab._y - q.lab._y)) {
      let y = r.lab._y;
      const x = r.lab._x, w = r.lab._w, hh = r.lab._h;
      for (let guard = 0; guard < 40; guard++) {
        const o = placed.find((p) => Math.abs(p.x - x) < (p.w + w) / 2 + 2 && Math.abs(p.y - y) < (p.h + hh) / 2 + 1);
        if (!o) break;
        y = o.y + (o.h + hh) / 2 + 2;
      }
      placed.push({ x, y, w, h: hh });
      r.lab.setAttribute("transform", `translate(${x},${y})`);
    }
  };
  const resetLabels = (recs) => recs.forEach((r) => r.lab && r.lab.setAttribute("transform", `translate(${r.lab._x},${r.lab._y})`));
  let hovered = null;
  const hoverEdges = (recs, on) => {
    if (sel) return;   // a selection already shows its links
    for (const r of recs) {
      r.path.classList.toggle("hov", on);
      r.path.setAttribute("marker-end", `url(#${uid}${on ? "h" : "a"})`);
      if (r.lab) r.lab.classList.toggle("hov", on);
    }
    if (on) placeLabels(recs.filter((r) => r.lab && r.lab.classList.contains("lazy"))); else resetLabels(recs);
    hovered = on ? recs : null;
  };

  // selection
  let sel = null, setIds = null;
  const card = h("div", { class: "map-card", hidden: true });
  const select = (id, keepCard) => {
    if (hovered) { const hv = hovered; hovered = null; hv.forEach((r) => { r.path.classList.remove("hov"); r.path.setAttribute("marker-end", `url(#${uid}a)`); if (r.lab) r.lab.classList.remove("hov"); }); resetLabels(hv); }
    sel = id && N[id] && !(byId[id] && byId[id].conn) ? id : null;
    setIds = null;
    const near = new Set(sel ? [sel] : []);
    const lit = sel ? adj[sel] || [] : [];
    for (const r of lit) { near.add(r.e.from); near.add(r.e.to); }
    wrap.classList.toggle("focusing", !!sel);
    for (const [nid, g] of Object.entries(N)) { g.classList.toggle("near", near.has(nid)); g.classList.toggle("hit", nid === sel); }
    const litSet = new Set(lit);
    for (const r of E) {
      const on = litSet.has(r);
      r.path.classList.toggle("near", on); r.path.setAttribute("marker-end", `url(#${uid}${on ? "h" : "a"})`);
      if (r.lab) r.lab.classList.toggle("near", on);
    }
    resetLabels(E);
    placeLabels(lit.filter((r) => r.lab && r.lab.classList.contains("lazy")));
    if (sel) gNodes.append(N[sel]);  // on top
    const body = sel && opts.card ? opts.card(sel) : null;
    if (body && !tall && L.pos[sel]) card.classList.toggle("left", (L.pos[sel].x - vb[0]) / vb[2] > 0.55);  // keep clear of it
    if (body && !keepCard) { card.replaceChildren(h("button", { class: "close", "aria-label": "Close the card", onclick: () => select(null) }, icon("close", 14, 2)), body); card.hidden = false; }
    else if (!body) card.hidden = true;
    if (opts.onSelect) opts.onSelect(sel);
  };
  const highlightSet = (ids) => {  // light a set of nodes (and the links among them), fade the rest
    select(null);
    if (!ids || !ids.length) return;
    setIds = new Set(ids);
    wrap.classList.add("focusing");
    for (const [nid, g] of Object.entries(N)) g.classList.toggle("near", setIds.has(nid));
    for (const r of E) { const on = setIds.has(r.e.from) && setIds.has(r.e.to); r.path.classList.toggle("near", on); r.path.setAttribute("marker-end", `url(#${uid}${on ? "h" : "a"})`); }
  };

  // pan and zoom on the viewBox (smoothly animated for the buttons, fit and zoom-to)
  let vb = null, anim = null, userMoved = false;
  const box = () => { const r = svg.getBoundingClientRect(); return { w: r.width || boxW, h: r.height || H }; };
  const apply = () => svg.setAttribute("viewBox", vb.map((v) => Math.round(v * 10) / 10).join(" "));
  const animateTo = (t, ms = 280) => {
    cancelAnimationFrame(anim);
    if (!vb || ms === 0) { vb = t; apply(); return; }
    const from = vb.slice(), t0 = performance.now();
    const step = (now) => {
      const k = Math.min(1, (now - t0) / ms), q = 1 - Math.pow(1 - k, 3);
      vb = from.map((v, i) => v + (t[i] - v) * q); apply();
      if (k < 1) anim = requestAnimationFrame(step);
    };
    anim = requestAnimationFrame(step);
  };
  const fitBox = () => {
    const b = box(), sc = Math.min(b.w / cw, b.h / ch, opts.maxScale || 1.15);
    const w = b.w / sc, hh = b.h / sc;
    return [(cw - w) / 2, (ch - hh) / 2, w, hh];
  };
  const fit = (ms) => { userMoved = false; animateTo(fitBox(), ms); };
  const zoom = (k, cx, cy) => {
    const t = vb.slice();
    cx = cx == null ? t[0] + t[2] / 2 : cx; cy = cy == null ? t[1] + t[3] / 2 : cy;
    userMoved = true;
    return [cx - (cx - t[0]) * k, cy - (cy - t[1]) * k, t[2] * k, t[3] * k];
  };
  const zoomTo = (id, gentle) => {
    const P = L.pos[id], n = byId[id];
    if (!P) return;
    const b = box(), cur = b.w / vb[2], want = Math.max(cur, gentle ? cur : Math.min(1.5, cur * 1.6));
    const inView = P.x > vb[0] + 40 && P.x < vb[0] + vb[2] - 40 && P.y > vb[1] + 30 && P.y < vb[1] + vb[3] - 30;
    if (gentle && inView) return;
    const w = b.w / want, hh = b.h / want;
    userMoved = true;
    animateTo([P.x - w / 2, P.y - hh / 2 + (n ? 0 : 0), w, hh]);
  };
  svg.addEventListener("wheel", (ev) => {
    if (!ev.ctrlKey && !ev.metaKey && !opts.wheel) return;  // plain scrolling keeps scrolling the page
    ev.preventDefault();
    cancelAnimationFrame(anim);
    const r = svg.getBoundingClientRect(), k = Math.exp(Math.max(-0.5, Math.min(0.5, ev.deltaY * 0.0022)));
    vb = zoom(k, vb[0] + (ev.clientX - r.left) / r.width * vb[2], vb[1] + (ev.clientY - r.top) / r.height * vb[3]); apply();
  }, { passive: false });
  let drag = null, dragged = false;
  svg.addEventListener("pointerdown", (ev) => {
    if (ev.button !== 0) return;
    drag = { x: ev.clientX, y: ev.clientY, vb: vb.slice(), id: ev.pointerId };
    dragged = false;
  });
  svg.addEventListener("pointermove", (ev) => {
    if (!drag) return;
    const r = svg.getBoundingClientRect(), sc = vb[2] / r.width;
    const dx = ev.clientX - drag.x, dy = ev.clientY - drag.y;
    if (!dragged && Math.abs(dx) + Math.abs(dy) > 4) { dragged = true; try { svg.setPointerCapture(drag.id); } catch (e) { /* gone */ } svg.classList.add("dragging"); }
    if (!dragged) return;
    cancelAnimationFrame(anim);
    userMoved = true;
    vb = [drag.vb[0] - dx * sc, drag.vb[1] - dy * sc, vb[2], vb[3]]; apply();
  });
  const endDrag = () => { drag = null; svg.classList.remove("dragging"); setTimeout(() => (dragged = false), 0); };
  svg.addEventListener("pointerup", endDrag);
  svg.addEventListener("pointercancel", endDrag);
  svg.addEventListener("click", () => { if (!dragged && (sel || setIds)) { select(null); if (opts.onClear) opts.onClear(); } });
  wrap.addEventListener("keydown", (ev) => { if (ev.key === "Escape" && (sel || setIds)) { select(null); if (opts.onClear) opts.onClear(); } });

  vb = fitBox();
  apply();
  if (typeof ResizeObserver !== "undefined") {  // fit again once the map has its real size, and when the page resizes
    let last = 0;
    new ResizeObserver(() => { const w = box().w; if (w && Math.abs(w - last) > 1) { last = w; if (!userMoved) { vb = fitBox(); apply(); } } }).observe(svg);
  }
  wrap.append(svg, card, h("div", { class: "map-tools" },
    h("button", { class: "small", onclick: () => animateTo(zoom(1 / 1.3)), title: "Zoom in", "aria-label": "Zoom in" }, "+"),
    h("button", { class: "small", onclick: () => animateTo(zoom(1.3)), title: "Zoom out", "aria-label": "Zoom out" }, "−"),
    h("button", { class: "small", onclick: () => fit(), title: "Show the whole map", "aria-label": "Fit the map" }, "Fit"),
    h("button", { class: "small", onclick: () => { select(null); if (opts.onClear) opts.onClear(); fit(); }, title: "Clear the selection and show the whole map", "aria-label": "Reset the map" }, "Reset")));
  wrap.focusNode = (id) => { select(id || null); if (id) zoomTo(id, true); };
  wrap.highlightSet = highlightSet;
  wrap.nodes = N;
  wrap.select = select;
  if (opts.focus && N[opts.focus]) setTimeout(() => select(opts.focus), 0);
  return wrap;
}

// the legend of the node styles a map uses
const MAP_KIND_LABEL = { introduced: "New in this lecture", met_again: "Met in an earlier lecture", defined_later: "Explained in a later lecture", assumed: "Not taught in this course" };
function mapLegend(kinds, hint, conn) {
  const present = Object.keys(MAP_KIND_LABEL).filter((k) => !kinds || kinds.has(k));
  return h("div", { class: "legend" },
    present.map((k) => h("span", {}, h("i", { class: "sw k-" + k }), MAP_KIND_LABEL[k])),
    conn ? h("span", {}, h("i", { class: "sw conn" }), "Explained through its links") : null,
    hint ? h("span", { class: "faint hint" }, hint) : null);
}

// the key concepts of a large map: the seeds (what the lecture introduces, or a complete-map's blanks) best connected,
// then the concepts most linked to those already chosen; always a connected-looking map of at most max concepts
function coreOf(nodes, edges, seeds, must, max = CORE_MAX) {
  const deg = {}, nb = {};
  for (const e of edges) {
    if (e.from === e.to) continue;
    deg[e.from] = (deg[e.from] || 0) + 1; deg[e.to] = (deg[e.to] || 0) + 1;
    (nb[e.from] = nb[e.from] || new Set()).add(e.to); (nb[e.to] = nb[e.to] || new Set()).add(e.from);
  }
  const seedSet = new Set(seeds);
  const chosen = new Set((must || []).filter((id) => deg[id]));
  for (const id of seeds.filter((x) => deg[x] && !chosen.has(x)).sort((a, b) => deg[b] - deg[a]).slice(0, Math.max(0, Math.round(max * 0.6) - chosen.size))) chosen.add(id);
  if (!chosen.size) { const top = nodes.map((n) => n.id).filter((id) => deg[id]).sort((a, b) => deg[b] - deg[a])[0]; if (top) chosen.add(top); }
  while (chosen.size < max) {
    let best = null, bs = -1;
    for (const n of nodes) {
      if (chosen.has(n.id) || !deg[n.id]) continue;
      let links = 0;
      for (const m of nb[n.id]) if (chosen.has(m)) links++;
      const sc = links * 100 + Math.min(deg[n.id], 40) + (seedSet.has(n.id) ? 60 : 0);
      if (sc > bs) { bs = sc; best = n.id; }
    }
    if (!best) break;
    chosen.add(best);
  }
  return chosen;
}

// A lecture's map (its own tab, the concept_map activity and the complete_map activity share it): the key concepts
// first when the map is large, the whole map grouped by lecture part one click away.
function lectureKinds(L) {
  const kindOf = {};
  const KL = L && L.knowledge;
  if (KL) for (const [k] of KINDS) for (const c of (KL.concepts || {})[k] || []) kindOf[c] = k;
  return kindOf;
}
function partGroups(L, ids, homeOf) {  // each concept in the part that teaches it (defined there, else first met)
  const segs = (L && L.segments) || [];
  const KL = L && L.knowledge;
  if (segs.length < 2 || !KL) return null;
  const home = {};
  for (const id of ids) {
    const c = concept(homeOf ? homeOf(id) : id);
    const d = c && (c.defined_in || []).find((x) => x.lecture === L.key);
    if (d && segs.some((sg) => sg.id === d.segment)) { home[id] = d.segment; continue; }
    const cid = homeOf ? homeOf(id) : id;
    const sg = segs.find((x) => (x.concepts || ((KL.segments || {})[x.id] || {}).concepts || []).includes(cid));
    home[id] = sg ? sg.id : "__other";
  }
  const groups = segs.map((sg, i) => ({ key: sg.id, title: `Part ${i + 1}` + (sg.title ? ` · ${sg.title}` : ""), time: sg.start, sub: sg.subgoal || "", href: timeHref(L.key, sg.start), ids: ids.filter((id) => home[id] === sg.id) }));
  const other = ids.filter((id) => home[id] === "__other");
  if (other.length) groups.push({ key: "__other", title: "Also in this lecture", sub: "", ids: other });
  return groups;
}
function conceptCard(cid, here) {  // the card a map opens for a concept (never for a connecting one)
  const c = concept(cid);
  if (!c || c.connecting) return null;
  const d = (c.defined_in || []).find((x) => x.lecture === here) || (c.defined_in || [])[0];
  const def = c.definition || "";
  const acr = (c.acronyms || []).find((a) => a.length <= 8);
  let partNo = null;
  if (d && here && d.lecture === here) { const L = S.lecSync && S.lecSync[here]; if (L) { const i = L.segments.findIndex((sg) => sg.id === d.segment); if (i >= 0) partNo = i + 1; } }
  return h("div", {},
    h("div", { class: "mc-kicker" }, acr ? h("span", { class: "idchip" }, acr) : null, d ? `explained in lecture ${d.lecture}` : "used in the course", dev(cid)),
    h("div", { class: "mc-name" }, cap(c.name)),
    def ? h("div", { class: "mc-def" }, def.length > 360 ? def.slice(0, 340).replace(/\s+\S*$/, "") + " …" : def) : null,
    h("div", { class: "mc-acts" },
      d ? h("a", { class: "mc-go", href: timeHref(d.lecture, d.start) }, icon("play", 13),
        h("span", {}, "Where it is explained", h("small", {}, `Lecture ${d.lecture} · ${clock(d.start)}` + (partNo ? ` · Part ${partNo}` : "")))) : null,
      h("a", { class: "mc-sec", href: `#/concept/${cid}` }, "Open the concept card"),
      h("a", { class: "mc-sec", href: "#/ask", onclick: () => { S.askDraft = `What is ${c.name}?`; } }, `Ask about ${acr || c.name}`)));
}
function keyEdges(edges, nodes) {
  // the links the key view draws and labels: first those that join the concepts into one map (blanks, then links of
  // new concepts, then the most specific), then more up to about one per concept; the rest appear on selection
  const kind = Object.fromEntries(nodes.map((n) => [n.id, n.kind]));
  const deg = {};
  for (const e of edges) { deg[e.from] = (deg[e.from] || 0) + 1; deg[e.to] = (deg[e.to] || 0) + 1; }
  const prio = (e) => (e.always ? 100 : 0) + (kind[e.from] === "introduced") * 3 + (kind[e.to] === "introduced") * 3 - (deg[e.from] + deg[e.to]) / 50;
  const order = edges.map((e, i) => [e, prio(e), i]).sort((a, b) => b[1] - a[1] || a[2] - b[2]).map((x) => x[0]);
  const parent = {};
  const find = (x) => (parent[x] == null || parent[x] === x ? x : (parent[x] = find(parent[x])));
  const keep = new Set(), pairs = new Set();
  const pair = (e) => [e.from, e.to].sort().join("|");
  for (const e of order) {
    const a = find(e.from), b = find(e.to);
    if (e.always || a !== b) { keep.add(e); pairs.add(pair(e)); if (a !== b) parent[a] = b; }
  }
  const cap = nodes.length + 6;
  for (const e of order) if (keep.size < cap && !keep.has(e) && !pairs.has(pair(e))) { keep.add(e); pairs.add(pair(e)); }
  return edges.map((e) => (keep.has(e) ? e : { ...e, extra: true }));
}
function lectureMapView(L, nodes, edges, o = {}) {
  // nodes [{id, label}], edges [{from, to, label, cls?, always?}]; o.seeds: the concepts the key view starts from;
  // o.must: concepts the key view always keeps; o.card(id); o.homeOf(id): the concept a node stands for (blanks)
  const kindOf = lectureKinds(L);
  const linked = new Set(edges.flatMap((e) => [e.from, e.to]));
  nodes = nodes.filter((n) => linked.has(n.id)).map((n) => ({ ...n, conn: n.conn != null ? n.conn : isConn(o.homeOf ? o.homeOf(n.id) : n.id) }))
    .map((n) => ({ ...n, kind: n.conn ? null : n.kind || kindOf[n.id] }));
  const kinds = new Set(nodes.map((n) => n.kind).filter(Boolean));
  const anyConn = nodes.some((n) => n.conn);
  const big = nodes.length >= CORE_FROM;
  const seeds = o.seeds || nodes.filter((n) => n.kind === "introduced").map((n) => n.id);
  const core = big ? coreOf(nodes, edges, seeds, o.must) : null;
  const groups = big ? partGroups(L, nodes.map((n) => n.id), o.homeOf) : null;
  const key = `mapview:${o.store || "lecture"}`;
  let mode = big ? (store(key) === "all" && !o.keyFirst ? "all" : "key") : "all";
  const holder = h("div", {});
  const hint = h("span", { class: "faint hint" });
  // each view is laid out once and kept: switching back and forth only swaps them (zoom and selection stay)
  const built = {};
  const build = (m) => {
    let el, text;
    const card = o.card === null ? null : o.card || ((id) => conceptCard(id, L.key));
    if (m === "key") {
      const ns = nodes.filter((n) => core.has(n.id)), es = keyEdges(edges.filter((e) => core.has(e.from) && core.has(e.to)), ns);
      el = drawMap(ns, es, { card, height: 620, aria: "Key concepts of the lecture" });
      text = "The key concepts and how they connect. Click a concept for its links and its card; double-click to zoom in.";
      if (es.some((e) => e.extra)) text += " Some links are shown only when you select a concept.";
    } else if (big && groups) {
      el = drawMap(nodes, edges, { mode: "parts", groups, card, aria: "All the concepts of the lecture, by part" });
      text = "Grouped by the part of the lecture that explains them (click a part's title to watch it). Point at or click a concept to see its links.";
    } else {
      const es = edges.length > nodes.length * 1.6 ? keyEdges(edges, nodes) : edges;
      el = drawMap(nodes, es, { card, height: 620, dense: big && edges.length > 60 });
      text = "Click a concept to see all its links and its card; double-click to zoom in. Drag to move; Ctrl + scroll to zoom." + (es.some((e) => e.extra) ? " Some links are shown only when you select a concept." : "");
    }
    return (built[m] = { el, text });
  };
  const put = (m) => { holder.replaceChildren(built[m].el); hint.textContent = built[m].text; holder.style.minHeight = ""; };
  const btn = (m, label) => h("button", { role: "tab", onclick: () => show(m) }, label);
  const btns = big ? { key: btn("key", "Key"), all: btn("all", `All ${nodes.length}` + (groups ? ", by part" : "")) } : null;
  const seg = big ? h("div", { class: "seg-ctl", role: "tablist" }, btns.key, btns.all) : null;
  const show = (m) => {
    mode = m;
    if (big) store(key, mode);
    if (btns) for (const [k, b] of Object.entries(btns)) { b.classList.toggle("on", k === m); b.setAttribute("aria-selected", String(k === m)); }
    if (built[m] || !holder.firstChild) { if (!built[m]) build(m); put(m); return; }
    // not laid out yet: answer the click at once, lay out after the next paint, keep the height (no jump)
    holder.style.minHeight = holder.offsetHeight + "px";
    holder.replaceChildren(h("div", { class: "empty" }, h("span", { class: "spin" }), " Arranging the concepts…"));
    requestAnimationFrame(() => setTimeout(() => { if (mode === m) { if (!built[m]) build(m); put(m); } }, 0));
  };
  show(mode);
  // the other view of a large map is laid out in idle time, so the switch is instant
  if (big) idle(() => { const other = mode === "key" ? "all" : "key"; if (!built[other] && document.body.contains(holder)) build(other); }, 1500);
  return h("div", { class: "lecmap" },
    h("div", { class: "map-head" }, seg, o.legend === false ? null : mapLegend(kinds, null, anyConn)),
    holder, h("div", { class: "small map-hint" }, hint));
}

function lectureMap(L) {
  const KL = L.knowledge;
  if (!KL || !KL.map) return h("p", { class: "muted" }, "Not ready yet for this lecture.");
  const kindOf = lectureKinds(L);
  const rels = (KL.map.relations || []).filter((r) => r.from && r.to);
  const linked = new Set(rels.flatMap((r) => [r.from, r.to]));
  const nodes = [...linked].map((c) => ({ id: c, label: cname(c) }));
  const edges = rels.map((r) => ({ from: r.from, to: r.to, label: r.label, rid: r.id }));
  const alone = (KL.map.concepts || []).filter((c) => !linked.has(c));
  if (!nodes.length) return h("p", { class: "muted" }, "No relationships were found between this lecture's concepts.");
  return h("div", {}, lectureMapView(L, nodes, edges),
    alone.length ? h("div", { style: "margin-top:14px" }, h("div", { class: "small muted" }, "Also in this lecture:"), h("div", { class: "chips", style: "margin-top:4px" }, alone.map((c) => conceptPill(c, kindOf[c])))) : null);
}

// ------------------------------------------------------------------ glossary and course map
function glossaryData() {  // /api/glossary, with what the search needs (lower-cased once)
  if (!S.gloss) {
    S.gloss = cget("/api/glossary").then((G) => {
      if (!G) { S.gloss = null; return null; }
      for (const c of G.concepts) { c.hay = [c.name, ...(c.also || [])].join("\n").toLowerCase(); c.defl = (c.definition || "").toLowerCase(); }
      return G;
    });
  }
  return S.gloss;
}

// The course map opens on the lectures (rows of weeks; each lecture's circle grows with the concepts it introduces;
// an arrow means a later lecture builds on concepts an earlier one explains) and opens into the concepts: a concept
// and its nearest neighbours, any concept found by name, one click to walk on to the next.
function coursemapData() {
  return cget("/api/coursemap").then((M) => {
    if (M) addConcepts(Object.fromEntries(Object.entries(M.names || {}).map(([c, n]) => [c, { name: n }])), true);
    if (M) addConcepts(Object.fromEntries(Object.entries(M.nodes || {}).map(([c, n]) => [c, { name: n.name, connecting: !!n.connecting }])), true);
    return M;
  });
}
// Lecture map (#/map[/<lecture>]): how the lectures build on each other, the lecture the learner is at selected.
async function pageLectureMap(rest) {
  if (!hasKnowledge()) return h("div", { class: "empty" }, "The lecture map is not ready yet for this course.");
  const M = await coursemapData();
  if (!M) return h("div", { class: "empty" }, "The lecture map is not ready yet for this course.");
  const P = progress();
  const pick = rest && rest[0] && S.course.lectures.some((l) => l.key === rest[0]) ? rest[0] : null;
  const here = P.last && P.last.lecture;
  const DEF = "How the lectures build on each other";
  const DEF_SUB = "The course in its chapters, week by week. Each circle is a lecture, grouped by topic; the larger the circle, the more new ideas it introduces. An arrow means a later lecture builds on what an earlier one explains. Select a lecture to see what it needs and where it leads; double-click to open it.";
  const title = h("h1", {}, DEF);
  const sub = h("p", { class: "map-sub" }, DEF_SUB);
  const pre = M.prerequisites || {};
  const onPick = (k) => {
    if (!k) { title.textContent = DEF; sub.textContent = DEF_SUB; return; }
    const d = (pre[k] || {}).direct || [], all = ((pre[k] || {}).all || []).filter((x) => !d.includes(x));
    title.textContent = d.length ? `Lecture ${k} builds on ${d.join(", ")}` : `Lecture ${k} needs no earlier lecture`;
    const rest = all.slice(-5).reverse();
    sub.textContent = (d.length && rest.length ? `And, through ${d.length > 1 ? "them" : "it"}, on ${rest.join(", ")}${all.length > 5 ? " and earlier lectures" : ""}. ` : "") + lecInfo(k).title + ".";
  };
  return h("div", { class: "page tight" },
    h("section", { class: "card map-sec" },
      h("div", { class: "row", style: "justify-content:space-between;align-items:flex-end" },
        h("div", { style: "display:flex;flex-direction:column;gap:4px;min-width:0;flex:1 1 520px" }, h("span", { class: "kicker" }, "LECTURE MAP"), title, sub),
        h("div", { class: "legend-dots" }, h("span", {}, h("i", { class: "dot-done" }), "Watched"), h("span", {}, h("i", { class: "dot-here" }), "You are here"), h("span", {}, h("i", { class: "dot-ahead" }), "Ahead"))),
      courseOverview(M, { here, focus: pick || here, onPick })));
}
// Concept map (#/concepts[/<lecture>], #/concepts/explore[/<concept>]): a lecture's concept map, or one concept and its
// neighbours. Connecting concepts are drawn muted and never open a card.
async function pageConceptMap(arg, rest) {
  if (!hasKnowledge()) return h("div", { class: "empty" }, "The concept map is not ready yet for this course.");
  const explore = arg === "explore";
  const P = progress();
  const withK = S.course.lectures.filter((l) => l.has.knowledge);
  const key = !explore && arg && withK.some((l) => l.key === arg) ? arg
    : (P.last && withK.some((l) => l.key === P.last.lecture) ? P.last.lecture : (withK[0] || S.course.lectures[0] || {}).key);
  const sw = h("div", { class: "seg-ctl", role: "tablist", "aria-label": "Concept map view" },
    h("a", { class: explore ? "" : "on", href: `#/concepts/${key}`, role: "tab", "aria-selected": String(!explore) }, "A lecture's concepts"),
    h("a", { class: explore ? "on" : "", href: "#/concepts/explore", role: "tab", "aria-selected": String(explore) }, "Explore a concept"));
  const allLink = h("a", { class: "btn ghost sm", href: "#/glossary" }, "All concepts, A to Z");
  if (explore) {
    const cid = rest && /^C\d+$/.test(rest[0] || "") ? rest[0] : null;
    if (cid) conceptData(cid).catch(() => {});  // both requests at once (no waterfall through a slow link)
    const M = await coursemapData();
    if (!M) return h("div", { class: "empty" }, "The concept map is not ready yet for this course.");
    return h("div", { class: "page tight" }, h("section", { class: "card map-sec" },
      h("div", { class: "row", style: "justify-content:space-between;align-items:flex-end" },
        h("div", { style: "display:flex;flex-direction:column;gap:2px" }, h("span", { class: "kicker" }, "CONCEPT MAP · EXPLORE"), h("h1", {}, "One concept and its links")),
        h("div", { class: "row" }, sw, allLink)),
      await conceptExplorer(M, cid)));
  }
  if (!key) return h("div", { class: "empty" }, "The concept map is not ready yet for this course.");
  const L = await lecture(key);
  if (!L) return h("div", { class: "empty" }, `There is no lecture ${key}.`);
  const pick = h("select", { "aria-label": "Choose a lecture", onchange: () => { location.hash = `#/concepts/${pick.value}`; } },
    withK.map((l) => h("option", { value: l.key }, `Lecture ${l.key}: ${l.title}`)));
  pick.value = key;
  return h("div", { class: "page tight" }, h("section", { class: "card map-sec" },
    h("div", { class: "row", style: "justify-content:space-between;align-items:flex-end" },
      h("div", { style: "display:flex;flex-direction:column;gap:2px;min-width:0" }, h("span", { class: "kicker" }, `CONCEPT MAP · LECTURE ${key}`), h("h1", {}, L.title)),
      h("div", { class: "row" }, sw, pick)),
    lectureMap(L),
    h("div", { class: "row", style: "justify-content:space-between" }, h("a", { class: "btn sm", href: `#/lecture/${key}` }, icon("play", 12), `Watch lecture ${key}`), allLink)));
}
function courseTopics(lectures) {  // consecutive lectures of one topic ("VR Hardware", "VR Hardware II") together
  const norm = (t) => {
    let x = String(t || "").toLowerCase().replace(/[‐-―:()-]/g, " ").replace(/\s+/g, " ").trim();
    for (let i = 0; i < 2; i++) x = x.replace(/\s+(i{1,3}|iv|vi{0,3}|ix|x|\d+|part \w+)$/, "").trim();
    return x;
  };
  const lev = (a, b) => {
    const d = Array.from({ length: b.length + 1 }, (_, j) => j);
    for (let i = 1; i <= a.length; i++) {
      let prev = d[0]; d[0] = i;
      for (let j = 1; j <= b.length; j++) { const t = d[j]; d[j] = Math.min(d[j] + 1, d[j - 1] + 1, prev + (a[i - 1] === b[j - 1] ? 0 : 1)); prev = t; }
    }
    return d[b.length];
  };
  const same = (a, b) => a === b || lev(a, b) <= Math.max(1, Math.floor(Math.min(a.length, b.length) * 0.12));
  const topics = [];
  for (const l of lectures) {
    const n = norm(l.title), t = topics[topics.length - 1];
    if (t && same(t.norm, n)) t.keys.push(l.key);
    else topics.push({ norm: n, title: String(l.title).replace(/[\s\-–]+(I{1,3}|IV|VI{0,3}|\d+)$/, "").trim(), keys: [l.key] });
  }
  return topics;
}
function courseOverview(M, o = {}) {
  // chapters (runs of lectures that serve one course goal) as bands; in each, its topics as cards; in each topic its
  // lectures as circles that grow with the concepts they introduce; arrows: a later lecture builds on an earlier one
  const C = S.course, pre = M.prerequisites || {};
  const nIntro = (k) => (M.introduced[k] || {}).n || 0;
  const maxI = Math.max(1, ...C.lectures.map((l) => nIntro(l.key)));
  const links = M.links || [];
  const goals = S.goals;
  const syl = C.syllabus || [];
  const theme = (w) => (syl.find((x) => String(x.week) === String(w)) || {}).theme || "";
  const chapters = [];  // runs of weeks with one syllabus theme
  for (const l of C.lectures) {
    const th = theme(l.week) || (l.week ? `Week ${l.week}` : "");
    let ch = chapters[chapters.length - 1];
    if (!ch || ch.theme !== th) chapters.push((ch = { theme: th, weeks: [], lectures: [] }));
    ch.lectures.push(l);
    if (l.week && !ch.weeks.includes(l.week)) ch.weeks.push(l.week);
  }
  chapters.forEach((ch) => (ch.topics = courseTopics(ch.lectures)));
  const R = 19;
  const prog = progress().lec || {};
  const nodes = C.lectures.map((l) => ({ id: l.key, label: l.key, circle: Math.round(9 + (R - 9) * Math.sqrt(nIntro(l.key) / maxI)),
    cls: "lec" + (l.key === o.here ? " here" : (prog[l.key] || {}).done ? " watched" : ""), title: `Lecture ${l.key}: ${l.title}` }));
  const edges = links.map((l) => ({ from: l.from, to: l.to, label: l.concepts.slice(0, 3).map(cname).join(", ") + (l.more || l.concepts.length > 3 ? ", …" : "") }));
  const STEP = 2 * R + 12, GAP = 14, PADX = 16;
  const place = (ns, es, W) => {
    const pos = {}, panels = [];
    let y = 0;
    for (const ch of chapters) {
      const wk = ch.weeks.length > 1 ? `Weeks ${ch.weeks[0]}–${ch.weeks[ch.weeks.length - 1]}` : ch.weeks.length ? `Week ${ch.weeks[0]}` : "";
      const head = { band: true, x: 0, y, w: W, h: 0, g: {}, title: textBlock(wk || ch.theme || "Lectures", 12, 700, W - 40, 1), sub: textBlock(wk ? ch.theme : "", 13.5, 600, W - 40, 2) };
      panels.push(head);
      let x = PADX, rowY = y + 38 + head.sub.lines.length * 16 + 4, rowH = 0;
      for (const t of ch.topics) {
        const tb = textBlock(t.title, 13, 650, 190, 2);
        const w = Math.max(tb.w + 28, t.keys.length * STEP + 18, 120), hh = 14 + tb.lines.length * 17 + 6 + 2 * R + 14;
        if (x > PADX && x + w > W - PADX) { x = PADX; rowY += rowH + GAP; rowH = 0; }
        panels.push({ x, y: rowY, w, h: hh, cls: "topic", g: {}, title: tb, sub: textBlock("", 12, 400, w, 1) });
        const cy = rowY + 14 + tb.lines.length * 17 + 6 + R, x0 = x + (w - t.keys.length * STEP) / 2 + STEP / 2;
        t.keys.forEach((k, i) => (pos[k] = { x: x0 + i * STEP, y: cy }));
        x += w + GAP; rowH = Math.max(rowH, hh);
      }
      head.h = rowY + rowH + 14 - y;
      y += head.h + 10;
    }
    return { pos, panels, width: W, height: y - 10 };
  };
  let map = null;
  const lecCard = (k) => {
    const l = lecInfo(k), before = (pre[k] || {}).direct || [], after = links.filter((x) => x.from === k).map((x) => x.to);
    const jump = (p) => h("a", { href: `#/map/${p}`, title: lecInfo(p).title, onclick: (ev) => { ev.preventDefault(); map.focusNode(p); } }, `Lecture ${p}`);
    const list = (ks) => ks.map((p, i) => [i ? ", " : "", jump(p)]);
    const news = (M.introduced[k] || {}).top || [];  // the most used first
    return h("div", {},
      h("div", { class: "mc-kicker" }, `Lecture ${k}` + (l.week ? ` · Week ${l.week}` : "")),
      h("div", { class: "mc-name" }, l.title),
      l.goal ? h("div", { class: "mc-def" }, l.goal) : null,
      h("div", { class: "small", style: "margin-top:10px" }, before.length ? [h("span", { class: "muted" }, "Builds on "), list(before)] : h("span", { class: "muted" }, "Needs no earlier lecture.")),
      after.length ? h("div", { class: "small" }, h("span", { class: "muted" }, "Leads to "), list(after)) : null,
      news.length ? [h("div", { class: "small muted", style: "margin-top:10px" }, "New here"), h("div", { class: "chips", style: "margin-top:6px" }, news.slice(0, 8).map((c) => isConn(c) ? conceptPill(c) : h("a", { class: "pill", href: `#/concepts/explore/${c}`, title: "Explore its links" }, cname(c))))] : null,
      h("div", { class: "mc-acts" }, h("a", { class: "mc-go", href: `#/lecture/${k}` }, icon("play", 13), h("span", {}, "Open the lecture", h("small", {}, `Lecture ${k}` + (l.week ? ` · Week ${l.week}` : "")))),
        h("a", { class: "mc-sec", href: `#/concepts/${k}` }, "Its concept map")));
  };
  const info = h("div", { class: "small muted goal-line" });
  let goalOn = null;
  const chips = Object.entries(goals).map(([gid, g], i) => {
    const b = h("button", { class: "chip-btn", title: g.goal, onclick: () => {
      goalOn = goalOn === gid ? null : gid;
      map.highlightSet(goalOn ? g.lectures || [] : null);
      chips.forEach((x) => x.classList.toggle("on", x === b && !!goalOn));
      info.textContent = goalOn ? g.goal : "";
    } }, `Goal ${i + 1}`);
    return b;
  });
  const route = (e, a, b, A, B) => {  // along a row: straight to the next lecture, an arc over the ones between
    if (Math.abs(A.y - B.y) > 1 || Math.abs(B.x - A.x) < STEP + 1) return straightRoute(a, b, A, B, Math.abs(A.y - B.y) > 1 ? 0.12 : 0);
    const dir = Math.sign(B.x - A.x), lift = Math.min(34, 12 + Math.abs(B.x - A.x) * 0.06);
    const x0 = A.x + dir * a.circle * 0.5, x1 = B.x - dir * b.circle * 0.5, y0 = A.y - a.circle * 0.87, y1 = B.y - b.circle * 0.87;
    return { d: `M${x0},${y0} C${x0},${y0 - lift} ${x1},${y1 - lift} ${x1},${y1}`, lx: (x0 + x1) / 2, ly: Math.min(y0, y1) - lift * 0.75 };
  };
  map = drawMap(nodes, edges, { mode: "custom", place, route, card: lecCard, onDouble: (k) => (location.hash = `#/lecture/${k}`),
    aria: "The lectures of the course and how they build on each other",
    onSelect: (k) => {  // the whole chain of earlier lectures stays half lit
      if (k) prefetch(k);
      const all = new Set(k ? (pre[k] || {}).all || [] : []);
      for (const [id, g] of Object.entries(map.nodes)) g.classList.toggle("chain", all.has(id));
      if (k && goalOn) { goalOn = null; chips.forEach((x) => x.classList.remove("on")); info.textContent = ""; }
      if (o.onPick) o.onPick(k);
    }, focus: o.here });
  map.classList.add("overview");
  return h("div", { class: "map-sec" },
    chips.length ? h("div", { class: "goal-row" }, h("span", { class: "small muted" }, "Show the lectures of a course goal:"), chips, info) : null,
    map);
}

async function conceptExplorer(M, cid) {
  // the centre's card (/api/concept/<id>) carries its neighbours; the server picks the start (the best connected
  // concept the first lecture defines)
  let c = /^C\d+$/.test(cid || "") ? await conceptData(cid) : null;
  if (!c && M.start_concept) { cid = M.start_concept; c = await conceptData(cid); }
  if (!c) return h("p", { class: "muted" }, "No relationships yet.");
  S.trail = (S.trail || []).filter((x) => x !== cid).concat([cid]).slice(-6);
  const rels = [...(c.relations.out || []).map((r) => ({ ...r, dir: "out" })), ...(c.relations.in || []).map((r) => ({ ...r, dir: "in" }))]
    .filter((r) => r.concept && r.concept !== cid);
  const side = {};
  for (const r of rels) side[r.concept] = side[r.concept] || r;
  const score = (n) => (side[n].definition ? 3 : 0) + Math.log(1 + (side[n].lectures || 0));
  const nbs = Object.keys(side).sort((a, b) => score(b) - score(a));
  const shown = new Set(nbs.slice(0, 12));
  const per = {};
  const edges = [];
  for (const r of rels) {
    if (!shown.has(r.concept) || (per[r.concept] = (per[r.concept] || 0) + 1) > 1) continue;
    edges.push(r.dir === "out" ? { from: cid, to: r.concept, label: r.label } : { from: r.concept, to: cid, label: r.label });
  }
  const nodes = [{ id: cid, label: cname(cid), cls: "centre" }, ...[...shown].map((n) => ({ id: n, label: cname(n), conn: !!side[n].connecting || isConn(n) }))];
  const card = (id) => {
    const body = conceptCard(id);
    if (body && id !== cid) body.querySelector(".mc-acts").append(h("a", { class: "mc-sec", href: `#/concepts/explore/${id}` }, "Centre the map here"));
    return body;
  };
  const map = drawMap(nodes, edges, { height: 580, card, onDouble: (id) => (location.hash = `#/concepts/explore/${id}`), aria: `${cname(cid)} and the concepts it links to` });
  // the search box: the names of every concept with links (the glossary's list, fetched after the map is shown)
  const datalist = h("datalist", { id: "map-names" });
  let names = null;
  const loadNames = () => glossaryData().then((G) => {
    if (names) return names;
    names = ((G && G.concepts) || []).filter((x) => x.linked).map((x) => [x.id, cap(x.name)]);
    datalist.replaceChildren(names.map(([, n]) => h("option", { value: n })));
    return names;
  });
  const find = h("input", { type: "search", class: "map-find", list: "map-names", placeholder: "Find a concept…", "aria-label": "Find a concept", onfocus: () => loadNames() });
  const go = async () => {
    const q = find.value.trim().toLowerCase();
    if (!q) return;
    const ns = await loadNames();
    const hit = ns.find(([, n]) => n.toLowerCase() === q) || ns.find(([, n]) => n.toLowerCase().startsWith(q)) || ns.find(([, n]) => n.toLowerCase().includes(q));
    if (hit) location.hash = `#/concepts/explore/${hit[0]}`;
  };
  find.addEventListener("change", go);
  find.addEventListener("keydown", (ev) => { if (ev.key === "Enter") { ev.preventDefault(); go(); } });
  idle(() => loadNames().catch(() => {}), 1500);
  const more = rels.filter((r) => !shown.has(r.concept));
  const sentence = (r) => h("li", {}, r.dir === "out" ? [h("b", {}, cname(cid)), " ", h("span", { class: "lbl" }, r.label), " ", h("a", { href: `#/concepts/explore/${r.concept}` }, cname(r.concept))]
    : [h("a", { href: `#/concepts/explore/${r.concept}` }, cname(r.concept)), " ", h("span", { class: "lbl" }, r.label), " ", h("b", {}, cname(cid))]);
  return h("div", {},
    h("div", { class: "row", style: "margin-bottom:10px" }, find, datalist,
      S.trail.length > 1 ? h("div", { class: "trail small" }, S.trail.map((t, i) => [i ? h("span", { class: "faint" }, " › ") : null, t === cid ? h("b", {}, cname(t)) : h("a", { href: `#/concepts/explore/${t}` }, cname(t))])) : null,
      dev(`${cid}: ${rels.length} relationships, ${nbs.length} neighbours`)),
    h("div", { class: "explore-head" }, h("h2", { style: "margin:0" }, cap(c.name)), c.definition ? h("div", { class: "muted" }, c.definition) : null),
    map,
    h("div", { class: "small map-hint faint" }, "Click a concept for its card; double-click to centre the map on it."),
    more.length ? h("details", { class: "card", style: "margin-top:14px" }, h("summary", {}, "More links of ", h("b", {}, cname(cid))), h("ul", { class: "rels", style: "margin-top:8px" }, more.slice(0, 200).map(sentence))) : null);
}

/* ------------------------------------------------------------------ the activities. One renderer per kind, used both in the player's glass panel (.dark) and in
 * the light Activities tab; the breaks of a lecture (start, after each part, end); the Activities and Recap tabs.
 * The server already applied the display rules: a recap carries only passing points (its text may be absent; a recap
 * with none is gone), a crossword entry with "prefilled": true has no clue (its letters are shown filled in), a
 * connecting concept has no card. Items the judge failed are marked in developer mode; those in a.judge_hide and
 * activities marked "unresolved" are shown only there. */

const KIND_LABEL = { quiz: "Quick quiz", recap: "Recap", recall: "Recall", open_question: "Think it through", concept_map: "Concept map",
  complete_map: "Complete the map", crossword: "Crossword", match_pairs: "Match the terms", odd_one_out: "Odd one out", put_in_order: "Put in order",
  goal: "Goal", notes: "Your notes" };
const ITEMS = { quiz: "questions", recap: "points", open_question: "questions", odd_one_out: "items", put_in_order: "items", crossword: "entries" };
const jfail = (a, n) => !!(a.judge_failed && a.judge_failed[n]);
const jhide = (a, n) => !!(a.judge_hide && a.judge_hide.includes(n));
function jf(a, n) { return jhide(a, n) ? " jf dev-only" : jfail(a, n) ? " jf" : ""; }
const jfMark = (a, n) => (jfail(a, n) ? dev(`judge failed (${a.judge_failed[n].join(", ") || "?"})${jhide(a, n) ? ", hidden" : ""} `) : null);
function actHidden(a) {  // the whole activity is hidden from learners
  if (a.unresolved) return true;
  const list = ITEMS[a.kind], n = list ? ((a.data || {})[list] || []).length : 0;
  return !!(a.judge_hide || []).length && n > 0 && Array.from({ length: n }, (_, i) => i + 1).every((i) => jhide(a, i))
    && !(a.kind === "recap" && a.data.text);
}
const shown = (a) => !actHidden(a) || isDev();
function actMeta(a) {  // what the learner meets, in plain words
  const d = a.data || {};
  const vis = (list) => (list || []).filter((_, i) => !jhide(a, i + 1) || isDev()).length;
  switch (a.kind) {
    case "quiz": return plural(vis(d.questions), "question");
    case "recap": return (d.points || []).length ? plural(d.points.length, "point") : "summary";
    case "recall": return plural((d.items || []).length, "card");
    case "open_question": return plural(vis(d.questions), "question");
    case "concept_map": return plural((d.nodes || []).length, "concept");
    case "complete_map": return plural((d.blanks || []).length, "blank");
    case "crossword": return plural((d.entries || []).filter((e) => !e.prefilled).length, "word");
    case "match_pairs": return plural((d.pairs || []).length, "pair");
    case "odd_one_out": return plural(vis(d.items), "set");
    case "put_in_order": return plural(vis(d.items), "list");
    default: return "";
  }
}
function seenAll() { return store(`seen:${S.course.course}`) || {}; }
function markSeen(id) { const x = seenAll(); if (!x[id]) { x[id] = Date.now(); store(`seen:${S.course.course}`, x); } }

// a link to a moment: inside the lecture being watched it seeks (ctx.jump), elsewhere it opens the lecture there
function jumpLink(fids, L, ctx, label) {
  const x = (fids || []).map(fact).find(Boolean);
  if (!x) return null;
  const text = (label || "Jump to") + " " + clock(x.start) + (L && x.lecture !== L.key ? ` in lecture ${x.lecture}` : "") + " ↗";
  if (ctx && ctx.jump && L && x.lecture === L.key) return h("button", { class: "btn ghost sm jump", onclick: () => ctx.jump(x.start) }, text);
  return h("a", { class: "jump", href: timeHref(x.lecture, x.start) }, text);
}

const RENDER = {
  // one question at a time; options settle with a small spring; the verdict explains and links to the moment
  quiz(a, L, ctx) {
    const qs = (a.data.questions || []).map((q, i) => ({ q, n: i + 1 })).filter((x) => !jhide(a, x.n) || isDev());
    if (!qs.length) return h("p", { class: "muted" }, "No questions here.");
    let i = 0;
    const box = h("div", { class: "act-body", style: "display:flex;flex-direction:column;gap:12px" });
    const draw = () => {
      const { q, n } = qs[i];
      const verdict = h("div", {});
      const nav = h("div", { class: "act-nav" });
      const btns = (q.options || []).map((o, k) => h("button", { class: "opt", onclick: () => pick(k) },
        h("span", { class: "k" }, "ABCDEFGH"[k]), h("span", { class: "x" }, o), h("span", { class: "tag" })));
      const pick = (k) => {
        btns.forEach((b, j) => {
          b.disabled = true;
          if (j === q.answer) { b.classList.add("right"); b.querySelector(".tag").textContent = "Correct"; }
          else if (j === k) { b.classList.add("wrong"); b.querySelector(".tag").textContent = "Your pick"; }
          else b.classList.add("rest");
        });
        const ok = k === q.answer;
        verdict.replaceChildren(h("div", { class: "verdict" + (ok ? "" : " bad") },
          h("b", {}, ok ? "Correct." : `Not this one. It is ${String(q.options[q.answer]).replace(/[.]$/, "")}.`),
          q.explanation ? h("span", { class: "ex" }, q.explanation) : null, jumpLink(q.facts, L, ctx)));
        nav.replaceChildren(
          h("button", { class: "btn ghost sm", onclick: () => draw() }, "Try again"),
          i < qs.length - 1 ? h("button", { class: "btn sm " + (ctx && ctx.dark ? "light" : "ink"), onclick: () => { i++; draw(); } }, "Next question") : null);
        if (ctx && ctx.answered) ctx.answered(i === qs.length - 1);
      };
      box.replaceChildren(
        h("div", { class: "quiz-q" + jf(a, n) }, h("p", {}, jfMark(a, n), q.question), h("span", { class: "mono" }, `${i + 1} / ${qs.length}`)),
        h("div", { class: "opts" }, btns), verdict, nav);
    };
    draw();
    return box;
  },
  // the passing points reveal one by one
  recap(a, L) {
    const pts = a.data.points || [];
    return h("div", { style: "display:flex;flex-direction:column;gap:10px" },
      a.judge_dropped ? dev(`judge dropped: ${a.judge_dropped.text ? "text, " : ""}points ${(a.judge_dropped.points || []).join(", ") || "none"}`) : null,
      a.data.text ? h("p", { class: "rv-text" + jf(a, 0) }, jfMark(a, 0), a.data.text) : null,
      pts.length ? h("div", { class: "rv-pts" }, pts.map((p, k) => h("div", { class: "rv-pt" + jf(a, k + 1), style: { animationDelay: `${k * 80}ms` } },
        h("span", { class: "mono" }, String(k + 1).padStart(2, "0")), h("span", {}, jfMark(a, k + 1), p)))) : null,
      factLinks(a.facts, L && L.key));
  },
  recall(a) {
    return h("div", { style: "display:flex;flex-direction:column;gap:10px" }, h("p", { class: "act-intro" }, "Recall each idea from earlier lectures, then turn the card to check."),
      h("div", { class: "flips" }, (a.data.items || []).map((it, k) => {
        const c = concept(it.concept), w = c && (c.defined_in || [])[0];
        const card = h("div", { class: "flip", tabindex: 0, role: "button", "aria-pressed": "false", style: { animation: `rise .3s ${k * 40}ms var(--spring-soft) both` },
          onclick: () => { card.classList.toggle("on"); card.setAttribute("aria-pressed", String(card.classList.contains("on"))); },
          onkeydown: (e) => { if (e.key === "Enter" || e.key === " ") { e.preventDefault(); card.click(); } } },
          h("div", { class: "in" },
            h("div", { class: "face" }, h("div", {}, it.prompt || cname(it.concept)), h("div", { class: "hint" }, "Recall it, then turn the card")),
            h("div", { class: "face back" }, h("div", {}, it.answer), h("div", { class: "hint" },
              it.from_lecture ? h("a", { href: w && w.lecture === it.from_lecture ? timeHref(w.lecture, w.start) : `#/lecture/${it.from_lecture}`, onclick: (e) => e.stopPropagation() }, `From lecture ${it.from_lecture}`) : null))));
        return card;
      })));
  },
  open_question(a, L) {
    return h("div", {}, (a.data.questions || []).map((q, qi) => {
      const key = `oq:${S.course.course}:${a.id}:${qi}`;
      const ta = h("textarea", { placeholder: "Write your answer here (it stays in this browser)…", "aria-label": "Your answer", oninput: () => store(key, ta.value) });
      ta.value = store(key) || "";
      const ref = h("div", { hidden: true, class: "ref" }, h("span", { class: "lbl" }, "A GOOD ANSWER"), h("span", {}, q.reference_answer),
        (q.key_facts || []).filter(fact).length ? [h("span", { class: "lbl" }, "FROM THE LECTURES"), factList(q.key_facts, L && L.key)] : factLinks(q.key_facts, L && L.key),
        (q.concepts || []).length ? h("div", { class: "chips" }, q.concepts.map((c) => conceptPill(c))) : null);
      const btn = h("button", { class: "btn sm soft", onclick: () => { ref.hidden = !ref.hidden; btn.textContent = ref.hidden ? "Show a good answer" : "Hide the answer"; } }, "Show a good answer");
      return h("div", { class: "qblock" + jf(a, qi + 1) }, h("div", { class: "qt" }, jfMark(a, qi + 1), q.question), ta, h("div", {}, btn), ref);
    }));
  },
  concept_map(a, L) {
    const d = a.data;
    return lectureMapView(L, (d.nodes || []).map((n) => ({ id: n.id, label: cap(n.label), conn: !!n.connecting })),
      (d.edges || []).map((e) => ({ from: e.from, to: e.to, label: e.label })), { store: "activity" });
  },
  complete_map(a, L) {
    // the blanks stay in the key view (with the links around them); a hidden concept becomes a "(n) ?" node
    const d = a.data, edges = (d.edges || []).map((e) => ({ ...e })), nodes = (d.nodes || []).map((n) => ({ id: n.id, label: cap(n.label), conn: !!n.connecting }));
    const hidden = new Set(), stands = {}, must = [];
    (d.blanks || []).forEach((b, i) => {
      const e = edges[b.edge];
      if (!e) return;
      const tag = `(${i + 1})`;
      if (b.hide === "label") { e.label = tag; e.cls = "blank"; e.always = true; must.push(e.from, e.to); }
      else {
        const end = b.hide === "from" ? "from" : "to";
        hidden.add(e[end]);
        const nid = `__blank${i}`;
        stands[nid] = e[end];
        nodes.push({ id: nid, label: `${tag} ?`, cls: "blank", conn: false });
        e[end] = nid; e.always = true;
        must.push(e.from, e.to);
      }
    });
    const stillUsed = new Set(edges.flatMap((e) => [e.from, e.to]));
    const keep = nodes.filter((n) => !hidden.has(n.id) || stillUsed.has(n.id));
    const sels = (d.blanks || []).map((b, i) => {
      const sel = h("select", { "aria-label": `Blank ${i + 1}` }, h("option", { value: "" }, "Choose…"), (b.options || []).map((o) => h("option", { value: o }, o)));
      const mark = h("span", {});
      return { b, sel, mark, row: h("div", { class: "row" }, h("b", {}, `(${i + 1})`), h("span", { class: "small muted" }, b.hide === "label" ? "the link" : "the concept"), sel, mark) };
    });
    return h("div", { style: "display:flex;flex-direction:column;gap:12px" },
      lectureMapView(L, keep, edges, { seeds: must, must, card: null, store: "complete", keyFirst: true, homeOf: (id) => stands[id] || id }),
      h("div", { class: "blanks" }, sels.map((x) => x.row)),
      h("div", { class: "row" },
        h("button", { class: "btn sm primary", onclick: () => sels.forEach((x) => { const ok = x.sel.value === x.b.answer; x.mark.replaceChildren(h("span", { class: ok ? "ok-t" : "bad-t" }, ok ? "✓ right" : x.sel.value ? "✗ not this one" : "")); }) }, "Check"),
        h("button", { class: "btn sm ghost", onclick: () => sels.forEach((x) => { x.sel.value = x.b.answer; x.mark.replaceChildren(h("span", { class: "muted small" }, "answer shown")); }) }, "Show answers")),
      factLinks(a.facts, L && L.key));
  },
  crossword(a) { return crossword(a); },
  match_pairs(a) {
    const pairs = a.data.pairs || [];
    const rights = shuffled(pairs.map((p, i) => i), a.id);
    let sel = null, done = 0;
    const bar = h("i", {});
    const status = h("span", {}, `0 of ${pairs.length} matched`);
    const leftBtns = pairs.map((p, i) => h("button", { onclick: () => { if (leftBtns[i].classList.contains("done")) return; leftBtns.forEach((b) => b.classList.remove("sel")); sel = i; leftBtns[i].classList.add("sel"); } }, cap(p.left)));
    const rightBtns = rights.map((i) => h("button", { onclick: (ev) => {
      const b = ev.currentTarget;
      if (sel == null || b.classList.contains("done")) return;
      if (sel === i) {
        b.classList.add("done"); leftBtns[sel].classList.remove("sel"); leftBtns[sel].classList.add("done"); sel = null; done++;
        bar.style.width = `${(100 * done) / pairs.length}%`;
        status.textContent = done === pairs.length ? "All matched. Well done!" : `${done} of ${pairs.length} matched`;
      } else { b.classList.remove("miss"); void b.offsetWidth; b.classList.add("miss"); setTimeout(() => b.classList.remove("miss"), 500); }
    } }, pairs[i].right));
    return h("div", { style: "display:flex;flex-direction:column;gap:12px" },
      h("div", { class: "row", style: "justify-content:space-between" }, h("span", { class: "act-intro" }, "Pick a term, then its description."), h("span", { class: "prog" }, h("span", { class: "pb" }, bar), status)),
      h("div", { class: "pairs" }, h("div", { class: "col" }, leftBtns), h("div", { class: "col" }, rightBtns)));
  },
  odd_one_out(a, L, ctx) {
    return h("div", {}, (a.data.items || []).map((it, qi) => {
      const fb = h("div", {});
      const btns = (it.options || []).map((o, i) => h("button", { class: "opt", onclick: () => {
        btns.forEach((b, j) => { b.disabled = true; if (j === it.odd) b.classList.add("right"); else if (j === i) b.classList.add("wrong"); else b.classList.add("rest"); });
        fb.replaceChildren(h("div", { class: "verdict" + (i === it.odd ? "" : " bad") }, h("b", {}, i === it.odd ? "Correct." : `Not this one. It is ${it.options[it.odd]}.`),
          it.reason ? h("span", { class: "ex" }, it.reason) : null, jumpLink(it.facts, L, ctx)));
      } }, h("span", { class: "x" }, o)));
      return h("div", { class: "qblock" + jf(a, qi + 1) }, h("div", { class: "qt" }, jfMark(a, qi + 1), "Which one does not belong?"), h("div", { class: "opts two" }, btns), fb);
    }));
  },
  put_in_order(a, L, ctx) {
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
          h("button", { "aria-label": "Move up", title: "Move up", disabled: pos === 0, onclick: () => swap(pos, pos - 1) }, "↑"),
          h("button", { "aria-label": "Move down", title: "Move down", disabled: pos === order.length - 1, onclick: () => swap(pos, pos + 1) }, "↓"));
        li.addEventListener("dragstart", (e) => { dragFrom = pos; li.classList.add("dragging"); e.dataTransfer.effectAllowed = "move"; try { e.dataTransfer.setData("text/plain", String(pos)); } catch (x) { /* old browsers */ } });
        li.addEventListener("dragend", () => li.classList.remove("dragging"));
        li.addEventListener("dragover", (e) => e.preventDefault());
        li.addEventListener("drop", (e) => { e.preventDefault(); if (dragFrom == null || dragFrom === pos) return; const [m] = order.splice(dragFrom, 1); order.splice(pos, 0, m); dragFrom = null; fb.replaceChildren(); draw(); });
        return li;
      }));
      const swap = (i, j) => { [order[i], order[j]] = [order[j], order[i]]; fb.replaceChildren(); draw(); };
      draw();
      return h("div", { class: "qblock" + jf(a, qi + 1) }, h("div", { class: "qt" }, jfMark(a, qi + 1), it.title || "Put these steps in order"),
        h("span", { class: "act-intro" }, "Drag the steps, or use the arrows."), list,
        h("div", { class: "row" },
          h("button", { class: "btn sm primary", onclick: () => { const ok = order.every((v, i) => v === i); draw(true); fb.replaceChildren(h("div", { class: "feedback " + (ok ? "ok" : "bad") }, h("b", {}, ok ? "Right. " : "Not yet. "), ok ? "That is the order the lecture gives." : "The steps marked in red are not in place yet.", ok ? jumpLink(it.facts, L, ctx, " Watch it at") : null)); } }, "Check"),
          h("button", { class: "btn sm ghost", onclick: () => { order = steps.map((_, i) => i); draw(true); fb.replaceChildren(h("div", { class: "feedback" }, "The order the lecture gives.", jumpLink(it.facts, L, ctx, " Watch it at"))); } }, "Show the order")),
        fb);
    }));
  },
};

// ------------------------------------------------------------------ crossword
// The active word gets a cobalt band; each correct word fills lime from left to right in 180 ms and its clue is
// ticked and moved down; completing the grid ripples once across all words. A prefilled entry (its clue failed the
// judge) has its letters filled in, is never asked and never shows a clue.
function crossword(a) {
  const d = a.data, W = d.width, Hh = d.height;
  const cells = {};
  const ents = (d.entries || []).map((e, i) => {
    const ans = (e.answer || "").replace(/[^A-Z]/gi, "").toUpperCase();
    const keys = [];
    for (let k = 0; k < ans.length; k++) {
      const r = e.row + (e.direction === "down" ? k : 0), c = e.col + (e.direction === "across" ? k : 0), key = r + "," + c;
      cells[key] = cells[key] || { r, c, ch: ans[k], ents: [] };
      cells[key].ents.push(i);
      keys.push(key);
    }
    return { ...e, i, ans, keys, given: !!e.prefilled, solved: !!e.prefilled };
  });
  const asked = ents.filter((e) => !e.given);
  for (const cell of Object.values(cells)) cell.given = cell.ents.every((i) => ents[i].given) || cell.ents.some((i) => ents[i].given);
  // a cell's number shows only when an asked entry starts there
  for (const e of asked) cells[e.keys[0]].no = e.number;
  const root = h("div", { class: "xw" });
  const grid = h("div", { class: "xw-grid", style: { gridTemplateColumns: `repeat(${W}, var(--xw, 32px))` }, role: "grid", "aria-label": `Crossword, ${W} by ${Hh}` });
  const inputs = {}, boxes = {};
  let act = asked[0] || null, cur = act ? act.keys[0] : null;
  const bar = h("i", {}), status = h("span", {});
  const activeCard = h("div", { class: "xw-active", "aria-live": "polite" });
  const clueList = h("div", { style: "display:flex;flex-direction:column;gap:2px" });
  const setProg = () => {
    const n = asked.filter((e) => e.solved).length;
    bar.style.width = asked.length ? `${(100 * n) / asked.length}%` : "0";
    status.textContent = `${n} of ${asked.length} words`;
  };
  const paint = () => {
    for (const [k, b] of Object.entries(boxes)) {
      b.classList.toggle("band", !!act && act.keys.includes(k));
      b.classList.toggle("cursor", k === cur);
    }
    if (act) {
      activeCard.replaceChildren(h("span", { class: "mono" }, `${act.number} ${act.direction.toUpperCase()} · ${act.ans.length} LETTERS`), h("span", {}, act.clue || ""));
      activeCard.hidden = false;
    } else activeCard.hidden = true;
    drawClues();
  };
  const drawClues = () => {
    const order = asked.slice().sort((x, y) => (x.solved - y.solved) || (x.direction === y.direction ? x.number - y.number : x.direction === "across" ? -1 : 1));
    clueList.replaceChildren(order.map((e) => h("button", { class: "xw-clue" + (e.solved ? " done" : "") + (e === act ? " on" : ""), onclick: () => select(e, true) },
      h("span", { class: "mono" }, `${e.number}${e.direction === "across" ? "A" : "D"}`),
      h("span", { style: "flex:1" }, e.clue || "", /\(\d+(?:[,-]\d+)*\)\s*$/.test(e.clue || "") ? null : h("span", { class: "muted" }, ` (${e.ans.length})`)))));
  };
  const select = (e, focus) => {
    act = e;
    cur = e.keys.find((k) => !inputs[k].value && !cells[k].given) || e.keys.find((k) => !cells[k].given) || e.keys[0];
    paint();
    if (focus && inputs[cur]) inputs[cur].focus({ preventScroll: true });
  };
  const checkSolved = () => {
    for (const e of asked) {
      const was = e.solved;
      e.solved = e.keys.every((k) => inputs[k].value === cells[k].ch);
      if (e.solved && !was) e.keys.forEach((k, idx) => { const b = boxes[k]; b.style.setProperty("--k", idx); b.classList.remove("solved"); void b.offsetWidth; b.classList.add("solved"); });
    }
    for (const [k, b] of Object.entries(boxes)) if (!cells[k].given && !cells[k].ents.some((i) => ents[i].solved && !ents[i].given)) b.classList.remove("solved");
    setProg();
    const all = asked.length && asked.every((e) => e.solved);
    if (all && !root.classList.contains("done")) { root.classList.add("done"); status.textContent = "Solved!"; }
    else if (!all) root.classList.remove("done");
  };
  const step = (k, dir) => {  // the next free cell of the active word
    if (!act) return null;
    let i = act.keys.indexOf(k);
    for (;;) { i += dir; if (i < 0 || i >= act.keys.length) return null; if (!cells[act.keys[i]].given) return act.keys[i]; }
  };
  for (let r = 0; r < Hh; r++) for (let c = 0; c < W; c++) {
    const k = r + "," + c, cell = cells[k];
    if (!cell) { grid.append(h("div", { class: "xw-cell blk", "aria-hidden": "true" })); continue; }
    const inp = h("input", { maxlength: 1, "aria-label": `Row ${r + 1}, column ${c + 1}`, autocomplete: "off", autocapitalize: "characters", spellcheck: "false", inputmode: "text" });
    const box = h("div", { class: "xw-cell" + (cell.given ? " given" : ""), style: { "--d": r + c } }, cell.no ? h("span", { class: "no" }, cell.no) : null, inp);
    if (cell.given) { inp.value = cell.ch; inp.readOnly = true; inp.tabIndex = -1; }
    inp.addEventListener("focus", () => {
      if (cell.given) return;
      if (!act || !act.keys.includes(k)) { const e = cell.ents.map((i) => ents[i]).find((x) => !x.given); if (e) act = e; }
      cur = k; paint();
    });
    inp.addEventListener("click", () => {  // a second click on a crossing switches the direction
      if (cell.given) return;
      const others = cell.ents.map((i) => ents[i]).filter((x) => !x.given && x !== act);
      if (cur === k && others.length && document.activeElement === inp && inp._clicked) { act = others[0]; paint(); }
      inp._clicked = true;
    });
    inp.addEventListener("blur", () => { inp._clicked = false; });
    inp.addEventListener("input", () => {
      inp.value = inp.value.replace(/[^a-z]/gi, "").slice(-1).toUpperCase();
      box.classList.remove("wrong");
      checkSolved();
      if (inp.value) { const nk = step(k, 1); if (nk) inputs[nk].focus(); }
    });
    inp.addEventListener("keydown", (ev) => {
      const mv = (dr, dc, dir) => {
        let rr = r + dr, cc = c + dc;
        while (cells[rr + "," + cc] && cells[rr + "," + cc].given) { rr += dr; cc += dc; }
        const nk = rr + "," + cc;
        if (cells[nk]) { const e = cells[nk].ents.map((i) => ents[i]).find((x) => !x.given && x.direction === dir); if (e) act = e; inputs[nk].focus(); }
        ev.preventDefault();
      };
      if (ev.key === "Backspace" && !inp.value) { const pk = step(k, -1); if (pk) { inputs[pk].value = ""; inputs[pk].focus(); checkSolved(); } ev.preventDefault(); }
      else if (ev.key === "ArrowRight") mv(0, 1, "across"); else if (ev.key === "ArrowLeft") mv(0, -1, "across");
      else if (ev.key === "ArrowDown") mv(1, 0, "down"); else if (ev.key === "ArrowUp") mv(-1, 0, "down");
    });
    inputs[k] = inp; boxes[k] = box;
    grid.append(box);
  }
  const anyGiven = ents.some((e) => e.given);
  root.append(h("div", { class: "xw-scroll" }, grid),
    h("div", { class: "xw-side" }, activeCard, clueList, anyGiven ? h("div", { class: "xw-given" }, "Words shown in grey are filled in for you.") : null));
  const tools = h("div", { class: "row" },
    h("span", { class: "prog" }, h("span", { class: "pb" }, bar), status),
    h("span", { class: "spacer" }),
    h("button", { class: "btn sm ink", onclick: () => { for (const [k, cell] of Object.entries(cells)) { if (cell.given) continue; const v = inputs[k].value; boxes[k].classList.toggle("wrong", !!v && v !== cell.ch); } } }, "Check"),
    h("button", { class: "btn sm ghost", onclick: () => { for (const [k, cell] of Object.entries(cells)) { inputs[k].value = cell.ch; boxes[k].classList.remove("wrong"); } checkSolved(); } }, "Reveal"),
    h("button", { class: "btn sm ghost", onclick: () => { for (const [k, cell] of Object.entries(cells)) { if (cell.given) continue; inputs[k].value = ""; boxes[k].classList.remove("wrong"); } checkSolved(); } }, "Clear"));
  setProg();
  paint();
  return h("div", { style: "display:flex;flex-direction:column;gap:16px" }, tools, root, a.judge_failed ? dev(`judge failed: entries ${Object.keys(a.judge_failed).join(", ")}`) : null);
}

// ------------------------------------------------------------------ an activity, ready to show
function renderAct(a, L, ctx = {}) {
  if (a.kind === "goal") return goalStep(L, ctx);
  if ((a.kind === "concept_map" || a.kind === "complete_map") && typeof dagre === "undefined") {  // the layout library first
    const box = h("div", { class: "empty", style: { padding: "40px 0" } }, h("span", { class: "spin" }), " Drawing the map…");
    needDagre().then(() => { if (box.isConnected) box.replaceWith(renderAct(a, L, ctx)); }, () => box.replaceChildren("The map cannot be drawn right now."));
    return box;
  }
  if (a.kind === "notes") return notesStep(L, ctx);
  const fn = RENDER[a.kind];
  try {
    return h("div", { class: "act-wrap" + (actHidden(a) ? " dev-only" : "") },
      a.unresolved ? dev("unresolved by the checks: " + ((a.check && a.check.problems) || []).map((p) => (typeof p === "string" ? p : JSON.stringify(p))).join("; ")) : null,
      a.judge_failed && a.kind !== "crossword" ? dev(`judge failed: items ${Object.keys(a.judge_failed).join(", ")}${(a.judge_hide || []).length ? `; hidden from learners: ${a.judge_hide.join(", ")}` : ""}`) : null,
      dev(a.id), fn ? fn(a, L, ctx) : h("p", { class: "muted" }, "This kind of activity cannot be shown yet."));
  } catch (e) { console.error(e); return h("p", { class: "muted" }, "This activity could not be shown.", dev(" " + e)); }
}
// the start of a lecture: its goal and what it builds on
function goalStep(L) {
  const KL = L.knowledge;
  const pre = (KL && KL.prerequisites) || { direct: [] };
  const needed = [], seen = new Set();
  for (const l of (KL && KL.before) || []) if (l.kind !== "weak") for (const c of l.concepts) if (!seen.has(c)) { seen.add(c); needed.push(c); }
  return h("div", { style: "display:flex;flex-direction:column;gap:14px" },
    KL && KL.goal ? h("div", { class: "goal-box" }, h("span", { class: "lbl" }, "BY THE END OF THIS LECTURE"), h("span", { class: "g" }, KL.goal.goal),
      KL.goal.achieves ? h("span", { class: "a" }, KL.goal.achieves) : null) : null,
    (pre.direct || []).length ? h("div", { class: "pre-list" }, h("span", { class: "pre-h" }, "IT BUILDS ON"),
      h("div", { class: "chips" }, pre.direct.map((k) => h("a", { class: "pill", href: `#/lecture/${k}` }, h("span", { class: "mono" }, `L${k}`), lecInfo(k).title)))) : null,
    needed.length ? h("div", { class: "pre-list" }, h("span", { class: "pre-h" }, "IDEAS FROM EARLIER LECTURES"), h("div", { class: "chips" }, needed.slice(0, 12).map((c) => conceptPill(c)))) : null,
    !KL ? h("p", { class: "muted" }, "The goals for this lecture are not ready yet.") : null);
}
function notesStep(L) {
  const list = h("div", {});
  const draw = () => {
    const ns = notesOf(L.key);
    list.replaceChildren(ns.length ? ns.map((n) => noteRow(n)) : h("p", { class: "notes-empty" }, "Click a caption sentence while you watch to save it here, with its time."));
  };
  draw();
  onNotes(list, draw);
  return list;
}

// ------------------------------------------------------------------ the breaks of a lecture
// start: goal (+ prerequisites) and recall; after each part: recap, quiz, put in order; end: complete the map, match
// the terms, crossword, odd one out, (put in order), think it through, and the notes. A break with nothing to show is left out.
const END_ORDER = ["concept_map", "complete_map", "match_pairs", "crossword", "odd_one_out", "put_in_order", "open_question"];
const SEG_ORDER = ["recap", "quiz", "put_in_order"];
function lectureBreaks(L, forPlayer) {
  const acts = ((L.activities && L.activities.activities) || []).filter(shown);
  const segIdx = Object.fromEntries(L.segments.map((sg, i) => [sg.id, i]));
  const rank = (order, k) => { const i = order.indexOf(k); return i < 0 ? 99 : i; };
  const start = [L.knowledge ? { kind: "goal", id: "goal" } : null, ...acts.filter((a) => a.kind === "recall")].filter(Boolean);
  const seg = {};
  for (const a of acts) if (a.kind !== "recall" && a.scope === "segment" && a.segment in segIdx) (seg[a.segment] = seg[a.segment] || []).push(a);
  for (const k of Object.keys(seg)) seg[k].sort((x, y) => rank(SEG_ORDER, x.kind) - rank(SEG_ORDER, y.kind));
  const end = acts.filter((a) => a.kind !== "recall" && !(a.scope === "segment" && a.segment in segIdx) && !(forPlayer && a.kind === "concept_map"))
    .sort((x, y) => rank(END_ORDER, x.kind) - rank(END_ORDER, y.kind));
  if (forPlayer) end.push({ kind: "notes", id: "notes" });
  return { start, seg, end };
}

// ------------------------------------------------------------------ Activities tab (C-Activities)
function activitiesTab(L, view, wantId) {
  const B = lectureBreaks(L, false);
  const P = progress().lec[L.key] || {};
  const curSeg = L.segments.findIndex((sg) => (P.t || 0) >= sg.start - 0.5 && (P.t || 0) < sg.end + 0.5);
  const groups = [];
  if (B.start.length) groups.push({ key: "B", mark: "B", title: "Before you watch", at: "", items: B.start, state: P.max > (L.segments[0] || {}).start + 5 ? "done" : "todo" });
  L.segments.forEach((sg, i) => {
    const items = B.seg[sg.id] || [];
    if (!items.length) return;
    const state = P.done || (P.max || 0) >= sg.end - 1 ? "done" : i === curSeg ? "now" : "todo";
    groups.push({ key: sg.id, mark: String(i + 1), title: sg.title ? `Part ${i + 1} · ${sg.title}` : `Part ${i + 1}`, at: sg.start, items, state });
  });
  if (B.end.length) groups.push({ key: "A", mark: "A", title: "After the lecture", at: "", items: B.end, state: P.done ? "done" : "todo" });
  const all = groups.flatMap((g) => g.items.map((a) => ({ a, g })));
  if (!all.length) return h("p", { class: "muted" }, "There are no activities for this lecture yet.");
  const seen = seenAll();
  let open = all.find((x) => wantId && x.a.id === `${L.key}/${wantId}`) || all.find((x) => x.g.state === "now" && !seen[x.a.id]) || all.find((x) => !seen[x.a.id] && x.a.kind !== "goal") || all[0];
  const itemBtns = new Map();
  const card = h("article", { class: "card lift act-card", "aria-live": "polite" });
  const show = (x, focus) => {
    open = x;
    markSeen(x.a.id);
    for (const [y, b] of itemBtns) { b.classList.toggle("open", y === x); b.classList.toggle("seen", y !== x && !!seenAll()[y.a.id]); b.setAttribute("aria-current", y === x ? "true" : "false"); }
    const gi = x.g.items.indexOf(x.a);
    card.replaceChildren(
      h("div", { class: "act-card-h" },
        h("div", { style: "display:flex;flex-direction:column;gap:2px" },
          h("span", { class: "kicker cobalt" }, `${x.g.title.toUpperCase()} · ${gi + 1} OF ${x.g.items.length}`),
          h("h2", {}, x.a.kind === "goal" ? "Goal of the lecture" : (KIND_LABEL[x.a.kind] || x.a.kind))),
        x.g.at !== "" ? h("a", { class: "btn sm", href: timeHref(L.key, x.g.at) }, icon("play", 12), `Watch part ${x.g.mark}`) : null),
      h("div", { class: "act-card-b" }, renderAct(x.a, L, {})));
    if (focus && matchMedia("(max-width: 860px)").matches) card.scrollIntoView({ behavior: "smooth", block: "start" });
    history.replaceState(null, "", `#/lecture/${L.key}/activities` + (x.a.id.includes("/") ? "/" + x.a.id.split("/").pop() : ""));
  };
  const tl = h("ol", { class: "tl", "aria-label": "Activities of the lecture" }, h("span", { class: "rail", "aria-hidden": "true" }),
    groups.map((g, gi) => h("li", { style: { "--i": gi } },
      h("span", { class: "node " + g.state, "aria-hidden": "true" }, g.state === "done" ? "✓" : g.mark),
      h("div", { class: "grp" },
        h("div", { class: "gh" }, h("b", {}, g.title), g.at !== "" ? h("a", { class: "mono", href: timeHref(L.key, g.at), title: "Watch this part" }, clock(g.at)) : null),
        g.items.map((a) => {
          const x = all.find((y) => y.a === a);
          const b = h("button", { class: "it", onclick: () => show(x, true) }, h("span", {}, a.kind === "goal" ? "Goal and what it builds on" : KIND_LABEL[a.kind] || a.kind), h("span", { class: "mono" }, actMeta(a)));
          itemBtns.set(x, b);
          return b;
        })))));
  show(open);
  return h("div", { class: "acts" }, tl, card);
}

// ------------------------------------------------------------------ Recap tab (C-Recap): cards expand, points reveal one by one
function recapTab(L) {
  const recs = ((L.activities && L.activities.activities) || []).filter((a) => a.kind === "recap" && shown(a) && a.segment);
  const segIdx = Object.fromEntries(L.segments.map((sg, i) => [sg.id, i]));
  const rows = recs.map((a) => ({ a, i: segIdx[a.segment] })).filter((x) => x.i != null).sort((x, y) => x.i - y.i);
  const P = progress().lec[L.key] || {};
  const cur = L.segments.findIndex((sg) => (P.t || 0) >= sg.start - 0.5 && (P.t || 0) < sg.end + 0.5);
  let openI = rows.findIndex((r) => r.i === cur);
  if (openI < 0) openI = 0;
  const list = h("section", { class: "rc-list", "aria-label": "Recap of each part" });
  const cards = rows.map((r, k) => {
    const sg = L.segments[r.i], pts = r.a.data.points || [];
    const body = h("div", { class: "rc-b", id: `rc-${k}` });
    const btn = h("button", { class: "rc-h", "aria-expanded": "false", "aria-controls": `rc-${k}`, onclick: () => toggle(k) },
      h("span", { class: "rc-n" }, String(r.i + 1)),
      h("span", { class: "rc-t" }, h("b", {}, partTitle(sg, r.i)), h("span", { class: "mono" }, `${clock(sg.start)} – ${clock(sg.end)} · ${pts.length ? plural(pts.length, "point") : "summary"}`)),
      h("span", { class: "rc-chev" }, icon("chev", 16, 2)));
    const el = h("div", { class: "rc", style: { "--i": k } }, btn, body);
    return { el, btn, body, r, sg, pts };
  });
  const toggle = (k) => {
    cards.forEach((c, j) => {
      const on = j === k && !c.el.classList.contains("open");
      c.el.classList.toggle("open", on);
      c.btn.setAttribute("aria-expanded", String(on));
      c.body.replaceChildren(on ? [
        dev(c.r.a.id + (c.r.a.judge_dropped ? ` · judge dropped: ${c.r.a.judge_dropped.text ? "text, " : ""}points ${(c.r.a.judge_dropped.points || []).join(", ") || "none"}` : "")),
        c.r.a.data.text ? h("p", { class: "rc-text" }, c.r.a.data.text) : null,
        c.pts.length ? h("div", { class: "rc-pts" }, c.pts.map((p, n) => h("div", { class: "rc-pt", style: { animationDelay: `${n * 60}ms` } }, h("span", { class: "mono" }, String(n + 1).padStart(2, "0")), h("span", {}, p)))) : null,
        h("a", { class: "watch", href: timeHref(L.key, c.sg.start) }, `▶ Watch part ${c.r.i + 1} from ${clock(c.sg.start)}`)] : []);
      c.body.hidden = !on;
    });
  };
  list.append(cards.length ? cards.map((c) => c.el) : h("p", { class: "muted" }, "There is no recap for this lecture yet."));
  if (cards.length) toggle(openI);
  const notesList = h("div", {});
  const count = h("span", { class: "mono", style: "font-size:11px;color:var(--muted)" });
  const drawNotes = () => {
    const ns = notesOf(L.key);
    count.textContent = ns.length ? plural(ns.length, "sentence") : "";
    notesList.replaceChildren(ns.length ? ns.map((n) => noteRow(n)) : h("p", { class: "notes-empty" }, "Nothing saved yet. While you watch, click a caption sentence to keep it here."));
  };
  drawNotes();
  onNotes(notesList, drawNotes);
  return h("div", { class: "recaps" }, list,
    h("aside", { class: "card notes-aside", "aria-label": "Your notes from this lecture" },
      h("div", { class: "sec-head" }, h("h2", {}, "Your notes"), count),
      h("span", { class: "small muted" }, "Saved from the captions. Click one to watch that moment."), notesList));
}

/* ------------------------------------------------------------------ the lecture page. Watch: the video full-window with our own controls only, cut by segment
 * (play ranges, no file cutting); it pauses at each part's end and the activities appear in a glass panel (subtitles
 * go away, the video is blurred and dimmed, the controls are hidden; the panel takes their place). Subtitles are
 * centred; a click on a sentence saves it to the notes with its sentence ID and time. Activities and Recap tabs.
 * The video: the file when the server has it, else the lecture on YouTube (its youtube_id; ?yt=1 or the menu prefers
 * YouTube), else a clock, so the parts, captions and activities still work without a video. */

const RATES = [1, 1.25, 1.5, 1.75, 2, 0.75];

// ------------------------------------------------------------------ media: one small interface over the three players
function fileMedia(L, onState, onFail) {
  const v = h("video", { preload: "metadata", playsinline: true, "webkit-playsinline": true, src: `/media/${encodeURIComponent(L.key)}`, "aria-label": `Video of lecture ${L.key}` });
  let pending = null;
  const M = {
    node: v, kind: "file",
    play() { const p = v.play(); return p && p.catch ? p.catch(() => { onState("blocked"); }) : null; },
    pause() { v.pause(); },
    time() { return pending != null ? pending : v.currentTime; },  // a seek not applied yet wins (metadata may still be loading)
    seek(t) { pending = t; if (v.readyState >= 1) { try { v.currentTime = t; } catch (e) { /* not seekable yet */ } pending = null; } },
    paused() { return v.paused; },
    rate(r) { v.playbackRate = r; },
    destroy() { v.pause(); v.removeAttribute("src"); try { v.load(); } catch (e) { /* gone */ } },
  };
  v.addEventListener("loadedmetadata", () => { if (pending != null) { try { v.currentTime = pending; } catch (e) { /* later */ } pending = null; } onState("meta"); });
  for (const e of ["play", "pause", "ended", "seeked", "waiting", "playing"]) v.addEventListener(e, () => onState(e));
  v.addEventListener("timeupdate", () => onState("time"));
  v.addEventListener("error", () => onFail && onFail());
  return M;
}
let ytApi = null;
function loadYouTubeApi() {
  if (window.YT && window.YT.Player) return Promise.resolve(window.YT);
  if (!ytApi) {
    ytApi = new Promise((resolve, reject) => {
      const prev = window.onYouTubeIframeAPIReady;
      window.onYouTubeIframeAPIReady = () => { if (prev) prev(); resolve(window.YT); };
      const sc = document.createElement("script");
      sc.src = "https://www.youtube.com/iframe_api";
      sc.async = true;
      sc.onerror = () => reject(new Error("the YouTube player API did not load"));
      document.head.append(sc);
      setTimeout(() => reject(new Error("the YouTube player API timed out")), 15000);
    }).catch((e) => { ytApi = null; throw e; });
  }
  return ytApi;
}
function ytMedia(L, onState, onNative) {
  const id = L.youtube_id;
  const base = `https://www.youtube.com/embed/${encodeURIComponent(id)}?enablejsapi=1&controls=0&disablekb=1&rel=0&playsinline=1&modestbranding=1&iv_load_policy=3&origin=${encodeURIComponent(location.origin)}`;
  const el = h("iframe", { src: base, title: `Video of lecture ${L.key}`, allow: "autoplay; encrypted-media; picture-in-picture; fullscreen", referrerpolicy: "strict-origin-when-cross-origin" });
  let P = null, ready = false, failed = false, pend = null, playing = false, rate = 1;
  const M = {
    node: el, kind: "youtube",
    play() { if (ready) P.playVideo(); else pend = { ...(pend || {}), play: true }; },
    pause() { if (ready) P.pauseVideo(); else if (pend) pend.play = false; },
    time() { try { return ready ? P.getCurrentTime() : (pend && pend.t) || 0; } catch (e) { return 0; } },
    seek(t) {
      if (ready) { const st = P.getPlayerState(); if (st === -1 || st === 5) P.cueVideoById({ videoId: id, startSeconds: t }); else P.seekTo(t, true); }
      else if (failed) el.src = base.replace("controls=0", "controls=1") + `&start=${Math.floor(t)}`;
      else pend = { ...(pend || {}), t };
    },
    paused() { return !playing; },
    rate(r) { rate = r; if (ready) try { P.setPlaybackRate(r); } catch (e) { /* unsupported rate */ } },
    destroy() { try { if (ready) P.pauseVideo(); } catch (e) { /* the frame is gone */ } },
  };
  loadYouTubeApi().then((YT) => new Promise((resolve) => {
    P = new YT.Player(el, { events: { onReady: resolve, onStateChange: (e) => { playing = e.data === 1 || e.data === 3; onState(e.data === 1 ? "playing" : e.data === 2 ? "pause" : e.data === 0 ? "ended" : "state"); } } });
  })).then(() => {
    ready = true;
    if (rate !== 1) M.rate(rate);
    if (pend) { if (pend.t != null) P.seekTo(pend.t, true); if (pend.play) P.playVideo(); pend = null; }
    onState("meta");
  }).catch(() => {  // no API (blocked, offline): YouTube's own controls in the frame, our controls step back
    failed = true;
    el.src = base.replace("controls=0", "controls=1") + (pend && pend.t ? `&start=${Math.floor(pend.t)}` : "");
    onNative();
  });
  return M;
}
function clockMedia(L, onState) {  // no video on this computer: a clock drives the parts, captions and activities
  let t = 0, playing = false, last = 0, rate = 1;
  const node = h("div", { class: "novideo" }, h("div", {}, h("b", {}, L.title), h("span", {}, "The video of this lecture is not on this computer. The parts, captions and activities still play along.")));
  return {
    node, kind: "none",
    play() { playing = true; last = performance.now(); onState("playing"); },
    pause() { if (playing) { t = this.time(); playing = false; onState("pause"); } },
    time() { if (playing) { const now = performance.now(); t += ((now - last) / 1000) * rate; last = now; } return t; },
    seek(x) { t = x; last = performance.now(); onState("seeked"); },
    paused() { return !playing; },
    rate(r) { this.time(); rate = r; },
    destroy() { playing = false; },
  };
}

// ------------------------------------------------------------------ the player
function buildPlayer(L, view) {
  const key = L.key, segs = L.segments || [];
  const first = segs.length ? segs[0].start : 0;
  const last = segs.length ? segs[segs.length - 1].end : null;
  const sents = (L.sentences || []).filter((x) => x.start != null).sort((a, b) => a.start - b.start);
  const nextL = L.next ? lecInfo(L.next) : null;
  const root = h("div", { class: "player dark", role: "region", "aria-label": `Lecture ${key} player` });
  const mediaBox = h("div", { class: "media" });
  const st = { open: null, done: new Set(), later: null, lastT: null, raf: 0, idleT: 0, saveAt: 0, ended: false, started: false };
  let M = null;
  const onState = (e) => {
    if (e === "blocked") { showBig("paused"); return; }
    if (e === "playing" || e === "play") { st.started = true; hideBig(); loop(); wake(); }
    if (e === "pause") { if (!st.open && !st.ended) showBig("paused"); save(); wake(); }
    if (e === "ended") { atEnd(); }
    if (e === "time" || e === "seeked" || e === "meta") tick();
    syncPlay();
  };
  const useYouTube = () => { if (M) M.destroy(); M = ytMedia(L, onState, () => root.classList.add("yt-native")); mediaBox.replaceChildren(M.node); M.seek(first); };
  if (L.video && !(preferYouTube() && L.youtube_id)) {
    M = fileMedia(L, onState, () => { if (L.youtube_id && M.kind === "file") useYouTube(); });
    mediaBox.append(M.node);
  } else if (L.youtube_id) { M = ytMedia(L, onState, () => root.classList.add("yt-native")); mediaBox.append(M.node); }
  else { M = clockMedia(L, onState); mediaBox.append(M.node); }
  const rate0 = Number(store("rate")) || 1;
  M.rate(rate0);

  // header: back, where we are, the lecture tabs
  const where = h("span", { class: "mono" });
  const head = h("header", { class: "p-head" },
    h("a", { class: "p-back glass", href: "#/", "aria-label": "Back to the roadmap" }, icon("left", 16, 2), h("span", {}, "Roadmap")),
    h("div", { class: "p-title" }, where, h("b", {}, L.title)),
    lectureTabs(key, "watch", true));

  // captions: centred block, centred text, near the bottom above the controls
  const caps = h("div", { class: "caps", "aria-live": "off" });
  let capOn = store("caps") !== false, capIdx = -2;
  const capBtn = (x, prev) => {
    const saved = noteHas(x.id);
    const b = h("button", { class: "cap" + (prev ? " prev" : "") + (saved ? " saved" : ""), title: saved ? "Saved to your notes (click to remove)" : "Save this sentence to your notes",
      onclick: (ev) => {
        ev.stopPropagation();
        const on = noteToggle(x, key);
        if (on) toast("Saved · ", h("span", { class: "mono" }, `${x.id} · ${clock(x.start)}`)); else toast("Removed from your notes");
        capIdx = -2; tick();
      } },
      h("span", { class: "cm" }, `${x.id} · ${clock(x.start)}`, h("span", { class: "mk" }, saved ? "Saved" : "Save to notes")),
      h("span", { class: "tx" }, x.text));
    return b;
  };
  const sentAt = (t) => {  // the last sentence that started, if it is still being said (or just ended)
    let lo = 0, hi = sents.length - 1, k = -1;
    while (lo <= hi) { const mid = (lo + hi) >> 1; if (sents[mid].start <= t + 0.05) { k = mid; lo = mid + 1; } else hi = mid - 1; }
    if (k < 0) return -1;
    const end = sents[k].end != null ? sents[k].end : sents[k].start + 6;
    return t <= end + 1.5 ? k : -1;
  };
  const drawCaps = (t) => {
    const k = sentAt(t);
    if (k === capIdx) return;
    capIdx = k;
    caps.replaceChildren(k < 0 ? [] : [k > 0 && sents[k - 1].end != null && t - sents[k - 1].end < 6 ? capBtn(sents[k - 1], true) : null, capBtn(sents[k], false)]);
  };

  // chapter bar: the parts with their titles; a lime mark where activities wait
  const chapters = segs.map((sg, i) => {
    const fill = h("i", {});
    const hasBreak = () => { const B = lectureBreaks(L, true); return (B.seg[sg.id] || []).length > 0 || (i === segs.length - 1 && B.end.length > 0); };
    const mark = hasBreak() ? h("span", { class: "end", title: "Activities here" }) : null;
    const tip = h("span", { class: "hover-t", hidden: true });
    const b = h("button", { class: "ch", style: { flex: `${Math.max(1, sg.end - sg.start)} 1 0` }, "aria-label": `Part ${i + 1}: ${partTitle(sg, i)}, from ${clock(sg.start)}`,
      onclick: (ev) => { const r = b.getBoundingClientRect(); const f = ev.detail ? Math.min(1, Math.max(0, (ev.clientX - r.left) / r.width)) : 0; jumpTo(sg.start + f * (sg.end - sg.start)); },
      onpointermove: (ev) => { const r = b.getBoundingClientRect(); const f = Math.min(1, Math.max(0, (ev.clientX - r.left) / r.width)); tip.hidden = false; tip.style.left = `${f * 100}%`; tip.textContent = clock(sg.start + f * (sg.end - sg.start)); },
      onpointerleave: () => { tip.hidden = true; } },
      h("span", { class: "bar" }, fill), h("span", { class: "lab" }, sg.title ? `${i + 1} · ${sg.title}` : `Part ${i + 1}`), mark, tip);
    if (mark) mark.addEventListener("click", (ev) => { ev.stopPropagation(); openSeg(i); });
    return { b, fill, mark };
  });
  const bar = h("div", { class: "p-bar" }, chapters.map((c) => c.b));

  // controls
  const playBtn = h("button", { class: "play", "aria-label": "Play", onclick: () => toggle() }, icon("play", 18));
  const timeEl = h("span", { class: "time", "aria-live": "off" }, "0:00");
  let rate = rate0;
  const rateBtn = h("button", { class: "rate", "aria-label": `Playback speed ${rate}×`, title: "Playback speed", onclick: () => { rate = RATES[(RATES.indexOf(rate) + 1) % RATES.length]; M.rate(rate); store("rate", rate); rateBtn.textContent = `${rate}×`; rateBtn.setAttribute("aria-label", `Playback speed ${rate}×`); } }, `${rate}×`);
  const capsBtn = h("button", { class: capOn ? "on" : "", "aria-label": "Captions", "aria-pressed": String(capOn), title: "Captions (c)", onclick: () => setCaps(!capOn) }, icon("cc", 19, 1.7));
  const nBadge = h("span", { class: "badge", hidden: true });
  const notesBtn = h("button", { class: "nb", "aria-label": "Your notes", title: "Your notes", onclick: () => openNotes(key) }, icon("notes", 19, 1.7), nBadge);
  const fsBtn = h("button", { "aria-label": "Full screen", title: "Full screen (f)", onclick: () => fullscreen() }, icon("full", 19, 1.7));
  const ctl = h("div", { class: "p-ctl glass" },
    h("button", { "aria-label": "Back 10 seconds", title: "Back 10 seconds (j)", onclick: () => jumpTo(Math.max(first, M.time() - 10)) }, icon("back10", 21, 1.7)),
    playBtn,
    h("button", { "aria-label": "Forward 10 seconds", title: "Forward 10 seconds (l)", onclick: () => jumpTo(Math.min(last != null ? last - 0.2 : 1e9, M.time() + 10)) }, icon("fwd10", 21, 1.7)),
    timeEl, h("span", { class: "sep", "aria-hidden": "true" }), rateBtn, capsBtn, notesBtn, fsBtn);
  const dock = h("div", { class: "p-dock" }, caps, bar, h("div", { class: "p-ctl-wrap" }, ctl));
  const big = h("button", { class: "bigplay glass", hidden: true });
  const reopen = h("button", { class: "reopen glass", hidden: true });
  root.append(mediaBox, h("div", { class: "dim", "aria-hidden": "true" }), h("div", { class: "shade-top", "aria-hidden": "true" }), h("div", { class: "shade", "aria-hidden": "true" }), head, big, reopen, dock);
  mediaBox.addEventListener("click", () => { if (root.classList.contains("idle") && matchMedia("(pointer: coarse)").matches) { wake(); return; } toggle(); });

  const setCaps = (on) => { capOn = on; store("caps", on); caps.hidden = !on; capsBtn.classList.toggle("on", on); capsBtn.setAttribute("aria-pressed", String(on)); };
  setCaps(capOn);
  const drawBadge = () => { const n = notesOf(key).length; nBadge.hidden = !n; nBadge.textContent = n; notesBtn.setAttribute("aria-label", n ? `Your notes, ${n} saved` : "Your notes"); };
  drawBadge();
  onNotes(root, () => { drawBadge(); capIdx = -2; tick(); });
  const syncPlay = () => {
    const p = M.paused();
    playBtn.replaceChildren(icon(p ? "play" : "pause", 18));
    playBtn.setAttribute("aria-label", p ? "Play" : "Pause");
  };
  const segAt = (t) => { let k = -1; segs.forEach((sg, i) => { if (t >= sg.start - 0.3) k = i; }); return k; };
  const tick = () => {
    const t = M.time();
    const i = Math.max(0, segAt(t));
    if (!M.paused() && st.lastT != null && t >= st.lastT - 0.05 && t - st.lastT < 2.5 && !st.open) {
      const j = segs.findIndex((sg) => st.lastT < sg.end - 0.15 && t >= sg.end - 0.15);
      if (j >= 0) { st.lastT = t; segEnd(j); return; }
    }
    if (!M.paused() && segs.length && t < first - 0.4) M.seek(first);
    st.lastT = t;
    if (capOn) drawCaps(t);
    chapters.forEach((c, k) => {
      const sg = segs[k];
      c.fill.style.width = t >= sg.end ? "100%" : t <= sg.start ? "0" : `${(100 * (t - sg.start)) / (sg.end - sg.start)}%`;
      c.b.classList.toggle("cur", k === i);
    });
    where.textContent = (L.week ? `W${L.week} · ` : "") + `L${key}` + (segs.length ? ` · Part ${i + 1} of ${segs.length}` : "");
    timeEl.textContent = `${clock(t)} / ${clock(last != null ? last : t)}`;
    if (st.later != null && i > st.later + 1) { st.later = null; reopen.hidden = true; }
    const now = Date.now();
    if (now - st.saveAt > 4000 && st.started) { st.saveAt = now; save(); }
  };
  const loop = () => { cancelAnimationFrame(st.raf); const f = () => { tick(); if (!M.paused()) st.raf = requestAnimationFrame(f); }; st.raf = requestAnimationFrame(f); };
  const save = () => { if (!st.started) return; const t = M.time(); saveProgress(key, t, last, st.ended || (last != null && t >= last - 1)); };
  const toggle = () => { if (st.open) return; if (M.paused()) { if (st.ended) { st.ended = false; jumpTo(first); } M.play(); } else M.pause(); };
  const jumpTo = (t) => { st.lastT = null; st.ended = false; M.seek(t); setTimeout(tick, 30); };

  // a part's end: pause, the activities appear (each break once per visit); no activities: skip the gap to the next part
  const breakItems = (j) => {
    const B = lectureBreaks(L, true), sid = segs[j].id;
    return j === segs.length - 1 ? [...(B.seg[sid] || []), ...B.end] : B.seg[sid] || [];
  };
  const segEnd = (j) => {
    const isLast = j === segs.length - 1;
    const items = breakItems(j).filter((a) => a.kind !== "notes" || notesOf(key).length || breakItems(j).length > 1);
    if (items.length && !st.done.has(j)) { M.pause(); openBreak({ kind: isLast ? "end" : "seg", j, items }); return; }
    if (!isLast) { const nx = segs[j + 1]; if (nx.start - segs[j].end > 0.6) M.seek(nx.start); }
    else atEnd();
  };
  const atEnd = () => { M.pause(); st.ended = true; saveProgress(key, last != null ? last : M.time(), last, true); showBig("ended"); };
  const openSeg = (j) => { const items = breakItems(j); if (items.length) { M.pause(); openBreak({ kind: j === segs.length - 1 ? "end" : "seg", j, items }); } };
  const resumeAfter = (br) => {
    if (br.kind === "seg") { const nx = segs[br.j + 1]; if (nx && nx.start - segs[br.j].end > 0.6) M.seek(nx.start); }
    if (br.kind === "start") M.seek(Math.max(first, M.time()));
    if (br.kind === "end") { atEnd(); return; }
    st.lastT = null;
    M.play();
  };

  // the glass panel: one step at a time (recap, quiz, ...), Later / Continue
  const openBreak = (br) => {
    closePanel();
    st.open = br;
    root.classList.add("act-open");
    hideBig(); reopen.hidden = true;
    let k = 0;
    const sg = segs[br.j];
    const kicker = br.kind === "start" ? `Lecture ${key} · Before you watch` : br.kind === "end" ? `End of the lecture · ${clock(last)}` : `End of Part ${br.j + 1} · ${clock(sg.end)}`;
    const title = br.kind === "start" ? L.title : br.kind === "end" ? "Bring it together" : partTitle(sg, br.j);
    const stepsEl = h("span", { class: "ap-steps", role: "tablist", "aria-label": "Steps" });
    const body = h("div", { class: "ap-body" });
    const foot = h("div", { class: "ap-foot" });
    const scroll = h("div", { class: "ap-scroll" }, h("div", { class: "ap-head" }, h("span", { class: "mono" }, kicker), stepsEl), h("h2", { tabindex: -1 }, title), body);
    const panel = h("section", { class: "ap", role: "dialog", "aria-label": `Activities: ${title}` }, h("span", { class: "ap-grip", "aria-hidden": "true" }), scroll, foot);
    const ctx = { dark: true, jump: (t) => { closePanel(); st.done.add(br.j); jumpTo(t); M.play(); } };
    const label = (a) => (a.kind === "goal" ? "Goal" : a.kind === "quiz" ? "Quiz" : a.kind === "open_question" ? "Think" : a.kind === "complete_map" ? "Map" : a.kind === "match_pairs" ? "Match" : KIND_LABEL[a.kind] || a.kind);
    const show = (n) => {
      k = n;
      const a = br.items[k];
      if (a.id && a.kind !== "goal" && a.kind !== "notes") markSeen(a.id);
      panel.classList.toggle("wide", ["crossword", "complete_map", "concept_map", "match_pairs"].includes(a.kind));
      stepsEl.replaceChildren(br.items.length > 1 ? br.items.map((x, i) => h("button", { class: i === k ? "on" : "", role: "tab", "aria-selected": String(i === k), onclick: () => show(i) }, `${i + 1} · ${label(x)}`)) : []);
      body.replaceChildren(renderAct(a, L, ctx));
      scroll.scrollTop = 0;
      const lastStep = k === br.items.length - 1;
      const nextBtn = br.kind === "start"
        ? h("button", { class: "btn light", onclick: () => (lastStep ? finish() : show(k + 1)) }, lastStep ? [icon("play", 13), "Start the lecture"] : `Next · ${label(br.items[k + 1])}`)
        : lastStep ? h("button", { class: "btn light", onclick: () => finish() }, br.kind === "end" ? (nextL ? `Finish` : "Finish") : "Continue lecture")
          : h("button", { class: "btn light", onclick: () => show(k + 1) }, a.kind === "recap" && br.items[k + 1].kind === "quiz" ? "Got it, quiz me" : `Next · ${label(br.items[k + 1])}`);
      foot.replaceChildren(
        br.kind === "start" ? h("button", { class: "btn soft", onclick: () => { closePanel(); st.done.add(-1); M.seek(first); M.play(); } }, "Skip") : h("button", { class: "btn soft", onclick: () => later() }, "Later"),
        br.kind !== "start" && !lastStep ? h("button", { class: "btn soft", onclick: () => finish() }, br.kind === "end" ? "Finish" : "Continue lecture") : null,
        nextBtn);
    };
    const finish = () => { st.done.add(br.kind === "start" ? -1 : br.j); closePanel(); resumeAfter(br); };
    const later = () => {
      st.done.add(br.j);
      closePanel();
      if (br.kind === "seg" || br.kind === "end") { st.later = br.j; reopen.hidden = false; reopen.replaceChildren(br.kind === "end" ? "Reopen the end-of-lecture activities" : `Reopen the Part ${br.j + 1} activity`); reopen.onclick = () => openSeg(br.j); }
      resumeAfter(br);
    };
    panel.addEventListener("keydown", (ev) => { if (ev.key === "Escape") { ev.stopPropagation(); later(); } });
    root.append(panel);
    st.panel = panel;
    show(0);
    setTimeout(() => { const h2 = panel.querySelector("h2"); if (h2) h2.focus({ preventScroll: true }); }, 60);
  };
  const closePanel = () => { if (st.panel) st.panel.remove(); st.panel = null; st.open = null; root.classList.remove("act-open"); capIdx = -2; };

  // the big glass button: resume, play after a pause, or the end of the lecture
  const showBig = (mode, t) => {
    if (st.open) return;
    big.hidden = false;
    if (mode === "resume") { big.replaceChildren(icon("play", 22), h("span", {}, `Resume at ${clock(t)}`, h("small", {}, "or press space"))); big.onclick = () => { jumpTo(t); M.play(); }; }
    else if (mode === "ended") {
      big.replaceChildren(icon("check", 22, 2.4), h("span", {}, "Lecture complete", h("small", {}, nextL ? `Up next: Lecture ${nextL.key} · ${nextL.title}` : "This is the last lecture")));
      big.onclick = () => { if (nextL) location.hash = `#/lecture/${nextL.key}`; else { st.ended = false; jumpTo(first); M.play(); } };
    } else { big.replaceChildren(icon("play", 22), h("span", {}, "Play", h("small", {}, clock(M.time())))); big.onclick = () => toggle(); }
  };
  const hideBig = () => { big.hidden = true; };

  // idle: the head, chapter bar and controls fade while the video plays and the pointer rests
  const wake = () => {
    root.classList.remove("idle");
    clearTimeout(st.idleT);
    if (!M.paused() && !st.open) st.idleT = setTimeout(() => { if (!M.paused() && !st.open && !root.contains(document.activeElement && document.activeElement.closest(".p-ctl, .p-bar"))) root.classList.add("idle"); }, 3200);
  };
  root.addEventListener("pointermove", wake);
  root.addEventListener("pointerdown", wake);
  root.addEventListener("focusin", wake);
  const fullscreen = () => {
    if (document.fullscreenElement) document.exitFullscreen().catch(() => {});
    else if (root.requestFullscreen) root.requestFullscreen().catch(() => {});
    else if (M.node.webkitEnterFullscreen) M.node.webkitEnterFullscreen();
  };
  const onFs = () => { const on = !!document.fullscreenElement; fsBtn.replaceChildren(icon(on ? "unfull" : "full", 19, 1.7)); fsBtn.setAttribute("aria-label", on ? "Exit full screen" : "Full screen"); };
  document.addEventListener("fullscreenchange", onFs);
  const onKey = (ev) => {
    if (view.tab !== "watch" || ev.ctrlKey || ev.metaKey || ev.altKey) return;
    const tg = ev.target;
    if (tg && (tg.closest("input, textarea, select, [contenteditable]") || (st.open && tg.closest(".ap")))) return;
    if ($("#search") && !$("#search").hidden) return;
    const k = ev.key.toLowerCase();
    if (k === " " || k === "k") { if (tg && tg.tagName === "BUTTON" && k === " ") return; ev.preventDefault(); if (!big.hidden && big.onclick) big.onclick(); else toggle(); }
    else if (k === "j" || k === "arrowleft") { ev.preventDefault(); jumpTo(Math.max(first, M.time() - (k === "j" ? 10 : 5))); }
    else if (k === "l" || k === "arrowright") { ev.preventDefault(); jumpTo(Math.min(last != null ? last - 0.2 : 1e9, M.time() + (k === "l" ? 10 : 5))); }
    else if (k === "c") setCaps(!capOn);
    else if (k === "f") fullscreen();
    else if (k === "n") openNotes(key);
    wake();
  };
  document.addEventListener("keydown", onKey);

  return {
    el: root,
    start(t, play) {  // open the lecture: at a time (a citation), at the learner's place, or at the start with its goal
      const P = progress().lec[key] || {};
      if (t != null && isFinite(t)) { closePanel(); st.done.add(-1); jumpTo(t); if (play) M.play(); return; }
      if (P.t && P.t > first + 5 && !P.done && (last == null || P.t < last - 5)) { M.seek(P.t); showBig("resume", P.t); tick(); return; }
      M.seek(first);
      const B = lectureBreaks(L, true);
      if (B.start.length && !st.done.has(-1)) openBreak({ kind: "start", j: 0, items: B.start });
      else showBig("paused");
      tick();
    },
    seek(t, play) { closePanel(); hideBig(); st.done.add(-1); jumpTo(t); if (play) M.play(); },
    pause() { if (M && !M.paused()) M.pause(); },
    stop() {
      save();
      cancelAnimationFrame(st.raf); clearTimeout(st.idleT);
      document.removeEventListener("keydown", onKey);
      document.removeEventListener("fullscreenchange", onFs);
      if (document.fullscreenElement === root) document.exitFullscreen().catch(() => {});
      if (M) M.destroy();
    },
    kind: () => M.kind,
    openBreakAt: (j) => openSeg(j),
    state: st,
  };
}

// ------------------------------------------------------------------ the lecture page
function lectureTabs(key, on, dark) {
  const tab = (k, label) => h("a", { class: k === on ? "on" : "", href: `#/lecture/${key}/${k}`, "aria-current": k === on ? "page" : null }, label);
  return h("nav", { class: dark ? "p-tabs glass" : "seg-ctl", "aria-label": "Lecture" }, tab("watch", "Watch"), tab("activities", "Activities"), tab("recap", "Recap"));
}
async function pageLecture(key, rest) {
  const L = await lecture(key);
  if (!L) return h("div", { class: "empty" }, `There is no lecture ${key}.`);
  S.lecSync = S.lecSync || {};
  S.lecSync[key] = L;
  const root = h("div", { class: "lecture" });
  const view = { lecture: key, root, tab: null };
  root.view = view;
  const player = buildPlayer(L, view);
  const lightBody = h("div", {});
  const tabsHolder = h("div", {});
  const light = h("div", { class: "page tight", hidden: true },
    h("div", { class: "lec-top" },
      h("div", { style: "display:flex;flex-direction:column;gap:6px;min-width:0" },
        h("span", { class: "kicker" }, (L.week ? `Week ${L.week} · ` : "") + `Lecture ${key}`),
        h("h1", {}, L.title),
        L.knowledge && L.knowledge.goal ? h("p", { class: "lec-goal" }, L.knowledge.goal.goal) : null),
      tabsHolder),
    dev(`segments from ${L.source}; ${L.segments.length} segments, ${L.sentences.length} sentences; activities ${L.activities ? L.activities.activities.length : "none"}; ${Object.keys(L.concepts || {}).length} concepts and ${Object.keys(L.facts || {}).length} facts sent; player ${player.kind()}`),
    lightBody);
  root.append(player.el, light);
  let started = false;
  view.showTab = (t, arg) => {
    if (!["watch", "activities", "recap"].includes(t)) t = "watch";
    view.tab = t;
    const watch = t === "watch";
    document.body.classList.toggle("immersive", watch);
    player.el.hidden = !watch;
    light.hidden = watch;
    if (watch) { if (!started) { started = true; player.start(view.pendingT, true); view.pendingT = null; } return; }
    player.pause();
    tabsHolder.replaceChildren(lectureTabs(key, t, false));
    let body;
    try { body = t === "activities" ? activitiesTab(L, view, arg) : recapTab(L); } catch (e) { console.error(e); body = h("p", { class: "muted" }, "This part could not be shown.", dev(" " + e)); }
    lightBody.replaceChildren(body);
    window.scrollTo(0, 0);
  };
  view.seek = (t, play) => {
    if (!isFinite(t)) return;
    if (view.tab !== "watch") { view.pendingT = started ? null : t; history.replaceState(null, "", timeHref(key, t)); view.showTab("watch"); }
    if (started) player.seek(t, play);
  };
  view.stop = () => { player.stop(); document.body.classList.remove("immersive"); };
  if (rest[0] === "t") view.pendingT = parseFloat(rest[1]);
  root.afterShow = () => {
    view.showTab(rest[0] === "t" ? "watch" : rest[0] || "watch", rest[1]);
    idle(() => { prefetch(L.next); prefetch(L.prev); needDagre().catch(() => {}); }, 1500);  // the neighbours open at once
  };
  return root;
}

/* ------------------------------------------------------------------ the router, the pages, Ask, search, start-up */

// ------------------------------------------------------------------ router
function route() {
  const parts = location.hash.replace(/^#\/?/, "").split("/").filter(Boolean).map(decodeURIComponent);
  return { page: parts[0] || "home", arg: parts[1], rest: parts.slice(2) };
}
const NAV_OF = { home: "home", lecture: "home", review: "home", map: "map", concepts: "concepts", concept: "concepts", glossary: "concepts", ask: "ask" };
let renderSeq = 0;
async function render() {
  let r = route();
  // older links keep working
  if (r.page === "lecture" && ["map"].includes(r.rest[0])) { location.replace(`#/concepts/${r.arg}`); return; }
  if (r.page === "lecture" && ["overview", "concepts", "before"].includes(r.rest[0])) { location.replace(`#/lecture/${r.arg}`); return; }
  if (r.page === "map" && r.arg === "concepts") { location.replace(`#/concepts/explore${r.rest[0] ? "/" + r.rest[0] : ""}`); return; }
  document.querySelectorAll(".nav a").forEach((a) => { const on = a.dataset.page === NAV_OF[r.page]; a.classList.toggle("on", on); if (on) a.setAttribute("aria-current", "page"); else a.removeAttribute("aria-current"); });
  closeMenu();
  if (r.page === "lecture" && S.view && S.view.lecture === r.arg && document.body.contains(S.view.root)) {
    if (r.rest[0] === "t") { S.view.seek(parseFloat(r.rest[1]), true); return; }
    S.view.showTab(r.rest[0] || "watch", r.rest[1]); return;
  }
  if (S.view && S.view.stop) { S.from = S.view.lecture; S.view.stop(); }
  S.view = null;
  document.body.classList.remove("immersive", "full");
  const app = $("#app"), seq = ++renderSeq;
  // the page stays as it is while the next one loads (most are ready at once); a spinner only after a short wait
  const slow = setTimeout(() => { if (seq === renderSeq) app.replaceChildren(h("div", { class: "empty" }, h("span", { class: "spin" }), " Loading…")); }, 140);
  try {
    let el;
    if (r.page === "lecture") el = await pageLecture(r.arg, r.rest);
    else if (r.page === "concept") el = await pageConcept(r.arg);
    else if (r.page === "glossary") el = await pageGlossary();
    else if (r.page === "map") el = await pageLectureMap(r.arg ? [r.arg] : []);
    else if (r.page === "concepts") { await needDagre().catch(() => {}); el = await pageConceptMap(r.arg, r.rest); }
    else if (r.page === "review") el = await pageReview();
    else if (r.page === "ask") el = pageAsk();
    else el = pageHome();
    if (seq !== renderSeq) return;  // another page was asked for meanwhile
    clearTimeout(slow);
    app.replaceChildren(el, r.page === "ask" || r.page === "lecture" ? null : siteFoot());
    if (el.view) S.view = el.view;
    window.scrollTo(0, 0);
    if (el.afterShow) el.afterShow();
  } catch (e) {
    console.error(e);
    clearTimeout(slow);
    if (seq === renderSeq) app.replaceChildren(h("div", { class: "empty" }, "This page could not be shown.", dev(" " + e)));
  }
}
function siteFoot() {
  const m = S.course.meta || {};
  return h("footer", { class: "site-foot" }, h("span", {}, [m.platform, m.institution].filter(Boolean).join(" · ")), h("span", {}, "Every answer and activity comes from the lectures, with the moment it is said."));
}

// ------------------------------------------------------------------ home: the roadmap
function pageHome() {
  const C = S.course, m = C.meta || {};
  const P = progress();
  const here = P.last && P.last.lecture;
  const weeks = [];
  for (const l of C.lectures) { let w = weeks[weeks.length - 1]; if (!w || w.week !== (l.week || "")) weeks.push((w = { week: l.week || "", ls: [] })); w.ls.push(l); }
  const theme = (w) => ((C.syllabus || []).find((x) => String(x.week) === String(w)) || {}).theme || "";
  const stop = (l) => {
    const p = P.lec[l.key] || {}, state = l.key === here ? "here" : p.done ? "done" : "";
    const meta = state === "here" ? `L${l.key} · ${p.done ? "watched" : "resume at " + clock(p.t)}` : state === "done" ? `L${l.key} · watched` : `L${l.key}`;
    return h("a", { class: "stop " + state, href: `#/lecture/${l.key}`, onpointerenter: () => prefetch(l.key), onfocus: () => prefetch(l.key), "aria-current": state === "here" ? "step" : null },
      h("span", { class: "d", "aria-hidden": "true" }), h("span", { class: "t" }, h("b", {}, l.title), h("span", { class: "mono" }, meta)));
  };
  const route = h("section", { class: "sec", style: "display:flex;flex-direction:column;gap:16px", "aria-labelledby": "route-h" },
    h("div", { class: "sec-head" }, h("h2", { id: "route-h" }, "The route"),
      h("span", { class: "legend-dots" }, h("span", {}, h("i", { class: "dot-done" }), "Watched"), h("span", {}, h("i", { class: "dot-here" }), "You are here"), h("span", {}, h("i", { class: "dot-ahead" }), "Ahead"))),
    h("div", { class: "route" }, weeks.map((w, wi) => {
      const n = w.ls.length, done = w.ls.filter((l) => (P.lec[l.key] || {}).done).length, pct = Math.round((100 * done) / n);
      return h("div", { class: "week", style: { "--i": wi } },
        h("div", { class: "week-h" }, h("span", {}, h("b", {}, w.week ? `Week ${w.week}` : "More"), h("span", { class: "mono" }, n > 1 ? `L${w.ls[0].key}–${w.ls[n - 1].key}` : `L${w.ls[0].key}`)),
          theme(w.week) ? h("span", { class: "theme" }, theme(w.week)) : null),
        h("div", { class: "stops" }, h("span", { class: "rail", "aria-hidden": "true", style: { background: `linear-gradient(#0E1116 0 ${pct}%, #D5D9E0 ${pct}% 100%)` } }), w.ls.map(stop)));
    })));
  const page = h("div", { class: "page" },
    h("section", { class: "hero" },
      h("div", { class: "hero-l" },
        h("span", { class: "kicker" }, [m.platform, m.institution, m.instructor && m.instructor.name].filter(Boolean).join(" · ")),
        h("h1", {}, C.title)),
      continueCard(P)),
    devHome(),
    route);
  return page;
}
function continueCard(P) {
  const C = S.course;
  let key = P.last && P.last.lecture, mode = "resume";
  if (!key || !C.lectures.some((l) => l.key === key)) { key = (C.lectures[0] || {}).key; mode = "first"; }
  const lp = P.lec[key] || {};
  if (mode === "resume" && lp.done) { const i = C.lectures.findIndex((l) => l.key === key); if (C.lectures[i + 1]) { key = C.lectures[i + 1].key; mode = "next"; } }
  const l = lecInfo(key), p = P.lec[key] || {};
  const meta = h("span", { class: "cont-meta" }, (l.week ? `Week ${l.week} · ` : "") + `Lecture ${key}`);
  const barEl = h("div", { class: "cont-bar", "aria-hidden": "true" });
  const foot = h("span", { class: "cont-foot" });
  const t = mode === "resume" ? p.t || 0 : 0;
  const cta = h("a", { class: "btn primary", href: mode === "resume" && t > 5 ? timeHref(key, t) : `#/lecture/${key}` }, icon("play", 13),
    mode === "resume" && t > 5 ? `Resume at ${clock(t)}` : mode === "first" ? `Start with lecture ${key}` : `Start lecture ${key}`);
  const review = h("a", { class: "chip-dark", href: "#/review", hidden: true }, icon("cards", 13, 2), "Review ", h("b", {}, ""));
  const card = h("article", { class: "cont", "aria-label": "Continue" },
    h("div", { class: "cont-top" }, h("span", { class: "cont-tag" }, mode === "resume" ? "Continue" : mode === "next" ? "Up next" : "Start here"), review),
    h("div", { style: "display:flex;flex-direction:column;gap:6px" }, meta, h("h2", {}, l.title), l.goal ? h("p", {}, l.goal) : null),
    h("div", { style: "display:flex;flex-direction:column;gap:8px" }, barEl, foot),
    cta);
  lecture(key).then((L) => {  // the parts of that lecture: watched ones in lime
    if (!L || !L.segments.length) return;
    const segs = L.segments, i = Math.max(0, segs.findIndex((sg) => t >= sg.start - 0.5 && t < sg.end + 0.5));
    barEl.replaceChildren(segs.map((sg, k) => h("span", { class: k < i || (mode === "resume" && p.done) ? "on" : "", style: { flex: `${Math.max(1, sg.end - sg.start)}` } })));
    if (mode === "resume" && t > 5) meta.textContent = (l.week ? `Week ${l.week} · ` : "") + `Lecture ${key} · Part ${i + 1} of ${segs.length}`;
    const nx = mode === "resume" && t > 5 ? segs[i + 1] : segs[0];
    const ni = mode === "resume" && t > 5 ? i + 1 : 0;
    foot.replaceChildren(h("span", {}, nx ? (ni === 0 ? "First: " : "Next: ") + partTitle(nx, ni) : "Last part"), h("span", {}, mode === "resume" && t > 5 ? `${clock(t)} / ${clock(segs[segs.length - 1].end)}` : clock(segs[segs.length - 1].end - segs[0].start)));
  }).catch(() => {});
  // the review cards (a large route) are fetched for the count only once the learner has used the review; before
  // that the chip shows without a count as soon as a lecture has been started
  if (C.layers.spaced_review && Object.keys(store(`review:${C.course}`) || {}).length) idle(() => reviewDue().then((n) => { if (n > 0) { review.hidden = false; review.querySelector("b").textContent = n; review.setAttribute("aria-label", `Review, ${n} cards due`); } }).catch(() => {}), 200);
  else if (C.layers.spaced_review && Object.keys(P.lec || {}).length) { review.hidden = false; review.querySelector("b").remove(); review.setAttribute("aria-label", "Review cards"); }
  return card;
}
async function reviewDue() {  // review cards due now or new, from the lectures the learner has started
  const R = await cget("/api/review");
  const cards = ((R && R.cards) || []).filter((c) => c.concept);
  const started = new Set(Object.keys(progress().lec || {}));
  const st = store(`review:${S.course.course}`) || {}, now = Date.now();
  const due = cards.filter((c) => st[c.concept] && st[c.concept].due <= now).length;
  const fresh = cards.filter((c) => !st[c.concept] && (c.lectures || []).some((k) => started.has(k))).length;
  return due + Math.min(20, fresh);  // a day's batch: what is due, and up to 20 new cards
}
function devHome() {
  const C = S.course;
  const n = (k) => C.lectures.filter((l) => l.has[k]).length;
  return h("div", { class: "dev card" },
    `${C.course}: ${C.lectures.length} lectures; knowledge ${n("knowledge")}, activities ${n("activities")}, video ${n("video")}, youtube ${n("youtube")}; question answering ${C.qa ? "importable" : "not available"}`,
    C.counts ? h("div", {}, "knowledge counts: " + Object.entries(C.counts).map(([k, v]) => `${k} ${v}`).join(", ")) : h("div", {}, "no knowledge/ layer"));
}

// ------------------------------------------------------------------ concept card (defined concepts only; a connecting concept has none)
function conceptData(cid) {  // /api/concept/<id>, its facts and its neighbours added to the caches
  return cget(`/api/concept/${encodeURIComponent(cid)}`).then((c) => {
    if (!c) return null;
    addConcepts({ [cid]: { name: c.name, definition: c.definition, defined_in: c.defined_in, first_defined: c.first_defined, acronyms: c.acronyms, connecting: false } });
    for (const r of [...(c.relations.out || []), ...(c.relations.in || [])]) {
      if (r.concept) addConcepts({ [r.concept]: { name: r.name, definition: r.connecting ? undefined : r.definition, defined_in: r.defined_in, connecting: !!r.connecting } }, true);
      if (r.fact) addFacts({ [r.fact.id]: r.fact });
    }
    addFacts(Object.fromEntries((c.facts || []).map((f) => [f.id, f])));
    return c;
  });
}
async function pageConcept(cid) {
  if (!hasKnowledge()) return h("div", { class: "empty" }, "Concepts are not ready yet for this course.");
  const c = /^C\d+$/.test(cid || "") ? await conceptData(cid) : null;
  if (!c) return h("div", { class: "empty" }, "There is no card for this concept.", h("br"), h("a", { href: "#/glossary" }, "See all concepts"));
  const names = [...new Set([...(c.aliases || []), ...(c.acronyms || [])])].filter((a) => a.toLowerCase() !== c.name.toLowerCase());
  const other = (r) => (r.connecting || isConn(r.concept) ? h("span", { class: "muted" }, cname(r.concept)) : h("a", { href: `#/concept/${r.concept}` }, cname(r.concept)));
  const relRow = (r, dir) => h("li", {}, dir === "out" ? [h("b", {}, cap(c.name)), " ", h("span", { class: "lbl" }, r.label), " ", other(r)]
    : [other(r), " ", h("span", { class: "lbl" }, r.label), " ", h("b", {}, cap(c.name))], " ", dev(r.relation),
  r.fact ? h("span", { title: r.fact.text }, " ", timeLink(r.fact.lecture, r.fact.start)) : null);
  const rels = [...(c.relations.out || []).map((r) => relRow(r, "out")), ...(c.relations.in || []).map((r) => relRow(r, "in"))];
  const d = c.dev || {};
  return h("div", { class: "page tight" },
    h("div", { class: "cc-head" },
      h("span", { class: "kicker" }, h("a", { href: "#/glossary" }, "All concepts"), "  ·  ", h("a", { href: `#/concepts/explore/${cid}` }, "Explore its links"), dev(" " + cid)),
      h("h1", {}, cap(c.name)),
      names.length ? h("div", { class: "chips" }, h("span", { class: "small muted" }, "Also called"), names.map((a) => h("span", { class: "pill" }, a))) : null),
    h("div", { class: "card lift", style: "display:flex;flex-direction:column;gap:12px" },
      c.definition ? h("div", { class: "defn" }, c.definition) : h("div", { class: "muted" }, "The course uses this concept without defining it."),
      (c.defined_in || []).length ? h("div", { class: "row small" }, h("span", { class: "muted" }, "Explained in"),
        c.defined_in.map((x) => h("span", {}, timeLink(x.lecture, x.start), dev(" " + x.segment)))) : null,
      dev(`first defined ${c.first_defined || "never"}; defined ${d.defined}; definition built from ${(d.definition_facts || []).join(", ") || "none"}`)),
    h("div", { class: "grid2" },
      h("div", { class: "card" }, h("h3", {}, "What the course says"), factList((c.facts || []).map((f) => f.id), null, c.defining_facts)),
      h("div", { style: "display:flex;flex-direction:column;gap:16px" },
        h("div", { class: "card" }, h("h3", {}, "Related concepts"), rels.length ? h("ul", { class: "rels" }, rels) : h("p", { class: "muted small" }, "No relationships recorded.")),
        h("div", { class: "card" }, h("h3", {}, "Lectures that use it"), h("div", { class: "chips" }, (c.lectures || []).map((l) => h("a", { class: "pill", href: `#/lecture/${l.key}`, onpointerenter: () => prefetch(l.key) }, h("span", { class: "mono" }, `L${l.key}`), l.title)))),
        (d.misplaced || []).length || (d.merged || []).length ? h("div", { class: "card dev" }, h("div", {}, "misplaced: " + (d.misplaced || []).join(", ")),
          h("div", {}, "merged: " + (d.merged || []).map((x) => `${x.segment_concept} "${x.name}" (${x.how}${x.reason ? ": " + x.reason : ""})`).join("; "))) : null)));
}

// ------------------------------------------------------------------ glossary (defined concepts only)
async function pageGlossary() {
  if (!hasKnowledge()) return h("div", { class: "empty" }, "The glossary is not ready yet for this course.");
  const G = await glossaryData();
  if (!G) return h("div", { class: "empty" }, "The glossary is not ready yet for this course.");
  const all = G.concepts.filter((c) => c.listed !== false && !c.connecting);
  const list = h("div", { class: "gl" });
  const input = h("input", { type: "search", class: "gl-search", placeholder: "Search concepts, acronyms, definitions…", "aria-label": "Search the concepts" });
  let job = 0, timer = null;
  const item = (c) => h("div", { class: "gl-item" }, h("div", {}, h("a", { class: "nm", href: `#/concept/${c.id}` }, cap(c.name)), c.also.length ? h("span", { class: "small muted" }, " · " + c.also.join(", ")) : null, dev(" " + c.id)),
    h("div", { class: "small muted" }, c.definition || h("i", {}, "Used in the course without a definition.")));
  const fill = () => {  // the first screenful at once, the rest in small slices between frames (the page never freezes)
    const my = ++job, q = input.value.trim().toLowerCase();
    const hits = q ? all.filter((c) => c.hay.includes(q) || c.defl.includes(q)) : all;
    list.replaceChildren();
    if (!hits.length) { list.append(h("p", { class: "muted", style: "padding:16px 0" }, "No concept matches.")); return; }
    let i = 0, letter = "";
    const slice = (n) => {
      const frag = document.createDocumentFragment();
      for (const end = Math.min(hits.length, i + n); i < end; i++) {
        const c = hits[i], L0 = (c.name[0] || "").toUpperCase();
        if (!q && L0 !== letter) frag.append(h("div", { class: "gl-letter" }, (letter = L0)));
        frag.append(item(c));
      }
      list.append(frag);
    };
    slice(60);
    const more = () => { if (my !== job || !list.isConnected) return; slice(200); if (i < hits.length) requestAnimationFrame(() => setTimeout(more, 0)); };
    if (i < hits.length) requestAnimationFrame(() => setTimeout(more, 0));
  };
  input.addEventListener("input", () => { clearTimeout(timer); timer = setTimeout(fill, 90); });
  fill();
  const page = h("div", { class: "page tight" },
    h("div", { class: "cc-head" }, h("span", { class: "kicker" }, h("a", { href: "#/concepts" }, "Concept map"), " · A to Z"), h("h1", {}, "All concepts")),
    h("div", { class: "dev" }, `${all.length} concepts listed; ${G.connecting || 0} connecting concepts not listed`),
    input, list);
  page.afterShow = () => input.focus({ preventScroll: true });
  return page;
}

// ------------------------------------------------------------------ spaced review (cards scheduled in this browser)
const BOX_DAYS = [0, 1, 2, 4, 8, 16, 32, 64];
async function pageReview() {
  const R = S.course.layers.spaced_review ? await cget("/api/review") : null;
  const cards = ((R && R.cards) || []).filter((c) => c.concept);
  if (!cards.length) return h("div", { class: "empty" }, "Review cards are not ready yet for this course.");
  const key = `review:${S.course.course}`;
  const st = store(key) || {};
  const save = () => store(key, st);
  const upto = h("select", { "aria-label": "Cards from", onchange: () => { store(key + ":upto", upto.value); next(); } }, h("option", { value: "" }, "all lectures"),
    S.course.lectures.map((l) => h("option", { value: l.key }, `lectures up to ${l.key}`)));
  const furthest = Object.keys(progress().lec || {}).sort((a, b) => S.course.lectures.findIndex((l) => l.key === b) - S.course.lectures.findIndex((l) => l.key === a))[0];
  upto.value = store(key + ":upto") || furthest || "";
  const idx = (k) => S.course.lectures.findIndex((l) => l.key === k);
  const stage = h("div", {});
  const counts = h("span", { class: "small muted" });
  const next = () => {
    const now = Date.now(), lim = upto.value ? idx(upto.value) : Infinity;
    const pool = cards.filter((c) => (c.lectures || []).some((k) => idx(k) <= lim) || !(c.lectures || []).length);
    const due = pool.filter((c) => st[c.concept] && st[c.concept].due <= now).sort((a, b) => st[a.concept].due - st[b.concept].due);
    const fresh = pool.filter((c) => !st[c.concept]);
    counts.textContent = `${due.length} due · ${fresh.length} new`;
    const card = due[0] || fresh[0];
    if (!card) {
      const soon = pool.map((c) => st[c.concept] && st[c.concept].due).filter(Boolean).sort((a, b) => a - b)[0];
      stage.replaceChildren(h("div", { class: "card review-card" }, h("div", { class: "front" }, "All done for now."), soon ? h("div", { class: "back" }, "Next card due " + new Date(soon).toLocaleString()) : null));
      return;
    }
    const back = h("div", { class: "back", hidden: true }, card.back,
      h("div", { class: "chips", style: "justify-content:center;margin-top:12px" }, (card.lectures || []).map((k) => h("a", { class: "pill", href: `#/lecture/${k}` }, `Lecture ${k}`)), hasKnowledge() && !isConn(card.concept) ? h("a", { class: "pill", href: `#/concept/${card.concept}` }, "Concept card") : null));
    const rate = (q) => {
      const cur = st[card.concept] || { box: 0 };
      const box = q === "again" ? 0 : q === "hard" ? Math.max(1, cur.box) : Math.min(BOX_DAYS.length - 1, cur.box + (q === "easy" ? 2 : 1));
      st[card.concept] = { box, due: Date.now() + (box === 0 ? 60 * 1000 : BOX_DAYS[box] * 86400 * 1000), seen: (cur.seen || 0) + 1 };
      save(); next();
    };
    const grades = h("div", { class: "row", hidden: true, style: "justify-content:center" },
      h("button", { class: "btn", onclick: () => rate("again") }, "Again"), h("button", { class: "btn", onclick: () => rate("hard") }, "Hard"),
      h("button", { class: "btn primary", onclick: () => rate("good") }, "Good"), h("button", { class: "btn", onclick: () => rate("easy") }, "Easy"));
    const show = h("button", { class: "btn ink", onclick: () => { back.hidden = false; grades.hidden = false; show.hidden = true; } }, "Show the answer");
    stage.replaceChildren(h("div", { class: "card lift review-card" }, h("span", { class: "kicker" }, st[card.concept] ? "REVIEW" : "NEW CARD"),
      h("div", { class: "front" }, cap(card.front)), back, show, grades, dev(card.concept + (st[card.concept] ? ` box ${st[card.concept].box}` : ""))));
  };
  next();
  return h("div", { class: "page tight" },
    h("div", { class: "cc-head" }, h("span", { class: "kicker" }, "SPACED REVIEW"), h("h1", {}, "Review")),
    h("div", { class: "row" }, h("span", { class: "muted" }, "Cards from"), upto, h("span", { class: "spacer" }), counts,
      h("button", { class: "btn ghost sm", onclick: () => { if (confirm("Forget your review progress in this browser?")) { for (const k of Object.keys(st)) delete st[k]; save(); next(); } } }, "Reset")),
    stage);
}

// ------------------------------------------------------------------ Ask: a full-window chat with "what the model is doing"
// The steps are the stream's own events (schemas/qa_stream.md): a step per tool call with its display line, each one
// opening onto its raw call and result summary; then the answer as it is written; KaTeX once it is complete.
const SAMPLE_FALLBACK = [
  { q: "What is the difference between immersion and presence?", category: "comparison" },
  { q: "What is HRTF?", category: "definition" },
  { q: "What do I need to know before lecture 9?", category: "prerequisite" },
  { q: "Who won the 2022 FIFA World Cup?", category: "not_covered" },
];
const CATEGORY = { definition: "A DEFINITION", explanation: "AN EXPLANATION", comparison: "TWO CONCEPTS", list: "A LIST", formula: "A FORMULA",
  where: "WHERE IT IS SAID", prerequisite: "PREREQUISITES", structure: "THE COURSE", not_covered: "OUTSIDE THE COURSE" };
const TOOL_TITLE = {  // [while it runs, when it is done, when it found nothing close]
  check_concept: ["Loading the concept card", "Concept loaded", "Concept not in the course"],
  fact_lookup: ["Checking the lectures' facts", "Facts checked", "No close facts found"],
  lecture_dependencies: ["Checking what the lecture builds on", "Prerequisites checked", "Prerequisites checked"],
  lecture_overview: ["Reading the lecture's overview", "Lecture overview read", "Lecture overview read"],
  course_goals: ["Reading the course goals", "Course goals read", "Course goals read"],
};
function samplesData() {
  if (!S.samples) S.samples = getJSON("/api/samples").then((x) => ((x && x.questions) || []).filter((q) => q && q.q).length ? x.questions.filter((q) => q && q.q) : SAMPLE_FALLBACK, () => SAMPLE_FALLBACK);
  return S.samples;
}
function argText(args) {
  if (args == null) return "";
  if (typeof args !== "object") return String(args);
  return Object.entries(args).map(([k, v]) => `${k}: ${JSON.stringify(v)}`).join(", ");
}
function pageAsk() {
  document.body.classList.add("full");
  const col = h("div", { class: "ask-col" });
  const main = h("div", { class: "ask-main" }, col);
  const banner = h("div", {});
  const hello = h("div", { class: "ask-hello" },
    h("span", { class: "kicker" }, "ASK THE COURSE"),
    h("h1", {}, `Ask anything in the ${S.course.lectures.length} lectures`),
    h("p", {}, "Answers come only from the course, and every claim opens the video where it is said. Watch how the answer is put together: the concepts it loads, the facts it checks, then the answer as it is written."));
  const helloSamples = h("div", { class: "samples" });
  const footSamples = h("div", { class: "samples compact", "aria-label": "Sample questions" });
  const input = h("input", { type: "text", placeholder: `Ask anything in the ${S.course.lectures.length} lectures`, "aria-label": "Ask a question about the course", autocomplete: "off", enterkeyhint: "send" });
  let ctxLec = S.from && S.course.lectures.some((l) => l.key === S.from) ? S.from : null;
  const ctxChip = h("span", { class: "ctx-chip", hidden: !ctxLec, title: "The question is asked from this lecture" }, ctxLec ? `From lecture ${ctxLec}` : "",
    h("button", { "aria-label": "Ask without the lecture", onclick: () => { ctxLec = null; ctxChip.hidden = true; } }, icon("close", 12, 2)));
  const form = h("form", { class: "composer", onsubmit: (e) => { e.preventDefault(); send(input.value); } }, ctxChip, input,
    h("button", { class: "send", type: "submit", "aria-label": "Ask" }, icon("arrow", 18, 2.2)));
  const sq = (x, i) => h("button", { class: "sq", style: { "--i": i }, onclick: () => send(x.q, x.lecture) }, h("span", { class: "mono" }, CATEGORY[x.category] || "A QUESTION"), h("span", {}, x.q));
  samplesData().then((qs) => { helloSamples.replaceChildren(qs.map(sq)); footSamples.replaceChildren(qs.map(sq)); });
  const layout = () => { const any = S.asks.length > 0; hello.hidden = any; footSamples.hidden = !any; };
  const send = (q, lec) => {
    q = String(q || "").trim();
    if (!q) return;
    input.value = "";
    const turn = askTurn(q, lec !== undefined && lec !== null ? String(lec) : ctxLec);
    S.asks.push(turn);
    col.append(turn.el);
    layout();
    requestAnimationFrame(() => turn.el.scrollIntoView({ behavior: "smooth", block: "start" }));
  };
  col.append(banner, hello, h("div", { style: "display:contents" }), ...S.asks.map((t) => t.el));
  hello.append(helloSamples);
  layout();
  const page = h("div", { class: "ask" }, main, h("footer", { class: "ask-foot" }, h("div", { class: "ask-foot-in" }, footSamples, form)));
  // is the assistant there? (qa off on this computer, still starting, or failed to start)
  let poll = null;
  const status = () => getJSON("/api/qa_status").then((x) => {
    if (!page.isConnected && poll) return;
    if (!x) { banner.replaceChildren(); return; }
    if (!x.importable) banner.replaceChildren(h("div", { class: "ask-banner" }, h("span", { class: "dotw" }), h("span", {}, h("b", {}, "The assistant is not available on this computer. "), "You can still watch the lectures, do the activities and explore the maps.")));
    else if (x.state === "warming") { banner.replaceChildren(h("div", { class: "ask-banner warm" }, h("span", { class: "dotw" }), h("span", {}, h("b", {}, "The assistant is starting. "), "The first answer may take a minute."), dev(x.seconds != null ? ` ${Math.round(x.seconds)} s` : ""))); clearTimeout(poll); poll = setTimeout(status, 3000); }
    else if (x.state === "failed") banner.replaceChildren(h("div", { class: "ask-banner" }, h("span", { class: "dotw" }), h("span", {}, h("b", {}, "The assistant could not start. "), "Questions may not be answered right now."), dev(" " + (x.error || ""))));
    else banner.replaceChildren();
  }).catch(() => {});
  page.afterShow = () => {
    status();
    idle(() => needMath().catch(() => {}), 800);  // KaTeX ready before the first answer completes
    if (S.askDraft) { input.value = S.askDraft; S.askDraft = null; }
    if (S.askNow) { const q = S.askNow; S.askNow = null; send(q); }
    input.focus({ preventScroll: true });
    if (S.asks.length) main.scrollTop = main.scrollHeight;
  };
  return page;
}
function stepItem(o) {  // one row of the progress rail; with a trace it opens onto the raw call
  const icn = h("span", { class: "ic", "aria-hidden": "true" });
  const title = h("b", {}), sub = h("span", {});
  const chev = h("span", { class: "chev", "aria-hidden": "true" }, icon("chev", 14, 2));
  let row = h("div", { class: "step-row" }, icn, h("span", { class: "lb" }, title, sub));
  const el = h("li", { class: "step" }, row);
  let traceEl = null;
  const set = (x) => {
    if (x.state) { el.className = "step " + x.state; icn.replaceChildren(x.state === "done" ? icon("check", 12, 3) : x.state === "miss" ? icon("close", 11, 2.6) : ""); }
    if (x.title != null) title.textContent = x.title;
    if (x.sub != null) { sub.textContent = x.sub; sub.hidden = !x.sub; }
    if (x.trace && !traceEl) {
      traceEl = x.trace; traceEl.hidden = true; traceEl.id = "tr" + Math.random().toString(36).slice(2, 9);
      const btn = h("button", { class: "step-row", type: "button", "aria-expanded": "false", "aria-controls": traceEl.id, title: "Show the call and its result",
        onclick: () => { const open = btn.getAttribute("aria-expanded") !== "true"; btn.setAttribute("aria-expanded", String(open)); traceEl.hidden = !open; } },
      icn, h("span", { class: "lb" }, title, sub), chev);
      row.replaceWith(btn); row = btn;
      el.append(traceEl);
    }
  };
  set(o);
  return { el, set };
}
function traceOf(ev) {  // design B's monospace trace: the call, its result summary, its time
  return h("div", { class: "trace" },
    h("div", {}, h("span", { class: "fn" }, ev.tool || "tool"), h("span", { class: "ar" }, `(${argText(ev.args)})`)),
    ev.result_summary ? h("div", { class: "res" }, "→ " + ev.result_summary) : null,
    h("div", { class: "meta" }, [ev.seconds != null ? `${Number(ev.seconds).toFixed(3)} s` : null, ev.round != null ? `round ${ev.round}` : null, ev.t != null ? `at ${Number(ev.t).toFixed(2)} s` : null].filter(Boolean).join(" · ")),
    ev.detail ? h("pre", { class: "dev" }, JSON.stringify(ev.detail, null, 1)) : null);
}
function askTurn(q, lec) {
  const t0 = performance.now();
  const badge = h("span", { class: "st-badge" }, "Working");
  const barI = h("i", {}), barEl = h("div", { class: "doing-bar", "aria-hidden": "true" }, barI);
  const stepsEl = h("ol", { class: "steps" });
  const doing = h("section", { class: "doing", "aria-label": "What the model is doing" }, h("div", { class: "doing-h" }, h("span", { class: "mono" }, "WHAT THE MODEL IS DOING"), badge), barEl, stepsEl);
  const ans = h("article", { class: "answer", "aria-live": "polite", "aria-busy": "true" }, h("span", { class: "ph" }, "The answer appears here as it is written."));
  const el = h("div", { class: "turn" }, h("div", { class: "qb" }, q), lec ? h("span", { class: "qb-ctx" }, `asked from lecture ${lec}`) : null, doing, ans);
  const reading = stepItem({ title: "Reading the question", sub: "Deciding what to look up", state: "active" });
  const writing = stepItem({ title: "Writing the answer", sub: "Waits for the lookups", state: "pending" });
  stepsEl.append(reading.el, writing.el);
  const calls = new Map();
  let wState = "pending", draftText = "", drawn = null, finished = false, readDone = false;
  const progressBar = () => {
    const n = calls.size + 2;
    let done = (readDone ? 1 : 0) + [...calls.values()].filter((c) => c.done).length;
    if (wState === "active") done += Math.min(0.9, draftText.length / 700);
    barI.style.width = `${Math.max(4, Math.round((100 * done) / n))}%`;
  };
  const doneReading = (sub) => { if (!readDone) { readDone = true; reading.set({ state: "done", title: "Read the question", sub: sub || "" }); } };
  const timer = setInterval(() => { if (!finished) badge.textContent = `Working · ${Math.round((performance.now() - t0) / 1000)} s`; }, 1000);
  const follow = () => { const m = el.closest(".ask-main"); if (m && m.scrollHeight - m.scrollTop - m.clientHeight < 160) m.scrollTop = m.scrollHeight; };
  const drawDraft = () => requestAnimationFrame(() => {
    if (finished || drawn === draftText) return;
    drawn = draftText;
    ans.replaceChildren(draftText ? mdBlock(draftText, true) : h("span", { class: "ph" }, "The answer appears here as it is written."));
    progressBar(); follow();
  });
  const stepFor = (ev) => {
    let c = calls.get(ev.index);
    if (!c) {
      const T = TOOL_TITLE[ev.tool] || ["Looking through the course", "Looked through the course", "Nothing close found"];
      c = { T, item: stepItem({ title: T[0], sub: argText(ev.args).replace(/^\w+: /, ""), state: "active" }), done: false };
      calls.set(ev.index, c);
      stepsEl.insertBefore(c.item.el, writing.el);
    }
    return c;
  };
  const onEvent = (ev) => {
    switch (ev.event) {
      case "round": if (ev.final && wState === "pending") writing.set({ sub: "Next: the answer" }); break;
      case "thinking": if (!readDone) reading.set({ sub: "Thinking about what to look up" }); break;
      case "call": doneReading(); stepFor(ev); break;
      case "step": {
        doneReading();
        const c = stepFor(ev);
        c.done = true;
        c.item.set({ state: ev.found === false ? "miss" : "done", title: ev.found === false ? c.T[2] : c.T[1], sub: ev.label || ev.result_summary || "", trace: traceOf(ev) });
        break;
      }
      case "answer_start": doneReading(calls.size ? "" : "Answered from what it already knows of the course"); wState = "active"; writing.set({ state: "active", sub: "Streaming" }); break;
      case "draft": if (wState !== "active") { doneReading(); wState = "active"; writing.set({ state: "active", sub: "Streaming" }); } draftText = ev.text || ""; drawDraft(); break;
      case "reset": draftText = ""; wState = "pending"; writing.set({ state: "pending", sub: "Looking up more first" }); drawDraft(); break;
      case "done": finish(ev.result || {}, ev.timing); return true;
      default: break;
    }
    progressBar();
    return false;
  };
  const finish = (res, timing) => {
    if (finished) return;
    finished = true;
    clearInterval(timer);
    ans.setAttribute("aria-busy", "false");
    if (res.available === false) {
      badge.textContent = "Unavailable"; badge.className = "st-badge off";
      reading.set({ state: "miss", title: "The assistant is not running", sub: "Questions cannot be answered on this computer right now" });
      writing.el.remove();
      barEl.hidden = true;
      ans.replaceChildren(h("div", { class: "md" }, h("p", {}, h("b", {}, "The assistant is not available right now.")),
        h("p", { class: "muted" }, "You can still watch the lectures, do the activities and explore the lecture and concept maps. Ask again once the assistant has started.")), res.error ? dev(res.error) : null);
      return;
    }
    doneReading();
    const cites = res.citations || [];
    writing.set({ state: res.answer ? "done" : "miss", title: res.answer ? "Answer written" : "No answer", sub: cites.length ? `With ${plural(new Set(cites.map((c) => c.lecture + "@" + Math.round(c.start))).size, "moment")} from the lectures` : res.covered === false ? "The course does not cover this" : "" });
    badge.textContent = "Answered"; badge.className = "st-badge done";
    barEl.classList.add("done"); barI.style.width = "100%";
    const byLec = new Map();
    for (const c of cites) if (c.lecture != null && !byLec.has(String(c.lecture))) byLec.set(String(c.lecture), c);
    ans.replaceChildren(mdBlock(res.answer || "(no answer)"),
      res.covered === false ? h("p", { class: "uncovered" }, "The course does not seem to cover this.") : null,
      byLec.size ? h("div", { class: "sources" }, h("span", {}, "Sources"), [...byLec.values()].map((c) => h("a", { href: timeHref(c.lecture, c.start), title: `Watch lecture ${c.lecture} at ${clock(c.start)}` }, `Lecture ${c.lecture} · ${lecInfo(String(c.lecture)).title}`))) : null,
      res.error ? dev(res.error) : null,
      timing ? h("details", { class: "dev" }, h("summary", {}, `timing: total ${timing.total} s, first step ${timing.first_step} s, first draft ${timing.first_draft} s`), h("pre", { style: "white-space:pre-wrap" }, JSON.stringify(timing, null, 1))) : null);
    needMath().then(() => window.renderMath(ans), () => {});  // formulas typeset once the answer is complete
    follow();
  };
  const body = JSON.stringify({ question: q, lecture: lec || null });
  (async () => {
    try {
      // streamed: the steps, then the answer as it is written; a server without the stream route gets /api/ask
      const r = await fetch("/api/ask_stream", { method: "POST", headers: { "Content-Type": "application/json" }, body });
      if (!r.ok || !r.body || !r.body.getReader) throw new Error("no stream");
      const reader = r.body.getReader(), dec = new TextDecoder();
      let buf = "", done = false;
      while (!done) {
        const { value, done: end } = await reader.read();
        if (end) break;
        buf += dec.decode(value, { stream: true });
        let nl;
        while ((nl = buf.indexOf("\n")) >= 0) {
          const line = buf.slice(0, nl).trim();
          buf = buf.slice(nl + 1);
          if (!line) continue;
          try { if (onEvent(JSON.parse(line))) { done = true; break; } } catch (e) { console.error(e); }
        }
      }
      if (!done) throw new Error("the stream ended early");
    } catch (e) {
      if (draftText) { finish({ answer: draftText + "\n\n(The answer was cut off. Please ask again.)", citations: [], error: String(e) }); return; }
      try {
        const r = await fetch("/api/ask", { method: "POST", headers: { "Content-Type": "application/json" }, body });
        finish(await r.json());
      } catch (e2) {
        finished = true; clearInterval(timer);
        badge.textContent = "Not sent"; badge.className = "st-badge off";
        ans.replaceChildren(h("p", { class: "muted" }, "The question could not be sent. Is the server running?"));
      }
    }
  })();
  return { el, q };
}

// ------------------------------------------------------------------ notes drawer, search, menu
let lastFocus = null;
function openNotes(focusKey) {
  lastFocus = document.activeElement;
  const body = $("#notes-body");
  const draw = () => {
    const all = notesAll();
    $("#notes-count").hidden = !all.length; $("#notes-count").textContent = all.length;
    if (!all.length) { body.replaceChildren(h("p", { class: "notes-empty", style: "padding-top:14px" }, "Nothing saved yet. While a lecture plays, click a caption sentence to keep it here with its time.")); return; }
    const keys = [...new Set(all.map((n) => n.lecture))].sort((a, b) => (a === focusKey ? -1 : b === focusKey ? 1 : S.course.lectures.findIndex((l) => l.key === a) - S.course.lectures.findIndex((l) => l.key === b)));
    body.replaceChildren(keys.map((k) => [h("h3", {}, h("a", { href: `#/lecture/${k}`, onclick: closeNotes }, lecInfo(k).title), h("span", { class: "mono" }, `L${k}`)),
      notesOf(k).map((n) => noteRow(n, { onopen: closeNotes }))]));
  };
  draw();
  onNotes(body, draw);
  $("#notes").hidden = false; $("#scrim").hidden = false;
  $("#notes-close").focus();
}
function closeNotes() { $("#notes").hidden = true; $("#scrim").hidden = true; if (lastFocus && lastFocus.focus) lastFocus.focus({ preventScroll: true }); }
function openSearch() {
  const box = $("#search"), input = $("#search-input");
  box.hidden = false;
  input.value = "";
  input.focus();
  searchFill("");
  if (hasKnowledge()) glossaryData().then((G) => { searchFill.G = G; if (!box.hidden) searchFill(input.value); }).catch(() => {});
}
function closeSearch() { $("#search").hidden = true; }
function searchFill(raw) {
  const out = $("#search-results"), q = raw.trim().toLowerCase();
  const items = [];
  const num = q.match(/^(?:l|lecture\s*)?(\d+[a-z]?)$/);
  const lecs = S.course.lectures.filter((l) => (num && l.key === num[1]) || (q && l.title.toLowerCase().includes(q))).slice(0, 6);
  const groups = [];
  if (!q) groups.push(["JUMP TO", [
    ["Roadmap", "#/", ""], ["Lecture map", "#/map", ""], ["Concept map", "#/concepts", ""], ["Ask the course", "#/ask", ""], ["All concepts, A to Z", "#/glossary", ""]].map(([t, href]) => ({ t, href, m: "→" }))]);
  if (lecs.length) groups.push(["LECTURES", lecs.map((l) => ({ t: l.title, sub: l.goal || "", href: `#/lecture/${l.key}`, m: `L${l.key}` }))]);
  const gl = searchFill.G;
  if (q && gl) {
    const pool = gl.concepts.filter((c) => !c.connecting && c.listed !== false);
    const hits = [...pool.filter((c) => c.name.toLowerCase().startsWith(q)), ...pool.filter((c) => !c.name.toLowerCase().startsWith(q) && c.hay.includes(q))].slice(0, 8);
    if (hits.length) groups.push(["CONCEPTS", hits.map((c) => ({ t: cap(c.name), sub: c.definition || "", href: `#/concept/${c.id}`, m: "" }))]);
  }
  if (q) groups.push(["ASK", [{ t: `Ask the course: “${raw.trim()}”`, href: "#/ask", m: "?", ask: raw.trim() }]]);
  out.replaceChildren(groups.map(([hd, xs]) => [h("div", { class: "sr-h" }, hd), xs.map((x) => {
    const a = h("a", { class: "sr-item", href: x.href, onclick: () => { if (x.ask) S.askNow = x.ask; closeSearch(); } }, h("span", { class: "mono" }, x.m), h("span", { class: "tx" }, x.t, x.sub ? h("small", {}, x.sub) : null));
    items.push(a); return a;
  })]));
  if (!groups.length) out.replaceChildren(h("div", { class: "sr-empty" }, "Nothing matches."));
  if (items[0]) items[0].classList.add("on");
}
function closeMenu() { const m = $("#menu"); if (m && !m.hidden) { m.hidden = true; $("#menu-btn").setAttribute("aria-expanded", "false"); } }

// ------------------------------------------------------------------ start
function setDev(on) { document.body.classList.toggle("devmode", on); $("#dev-box").checked = on; store("dev", on); }
async function main() {
  const params = new URLSearchParams(location.search);
  setDev(params.has("dev") ? params.get("dev") !== "0" : !!store("dev"));
  if (params.has("yt")) store("yt", params.get("yt") !== "0");
  $("#dev-box").addEventListener("change", (e) => setDev(e.target.checked));
  $("#menu-btn").addEventListener("click", (e) => { e.stopPropagation(); const m = $("#menu"); m.hidden = !m.hidden; $("#menu-btn").setAttribute("aria-expanded", String(!m.hidden)); });
  $("#menu").addEventListener("click", (e) => e.stopPropagation());
  document.addEventListener("click", closeMenu);
  $("#yt-box").addEventListener("change", (e) => { store("yt", e.target.checked); if (S.view) { S.view.stop(); S.view = null; render(); } });
  $("#notes-btn").addEventListener("click", () => openNotes(S.view && S.view.lecture));
  $("#notes-close").addEventListener("click", closeNotes);
  $("#scrim").addEventListener("click", closeNotes);
  $("#search-btn").addEventListener("click", openSearch);
  $("#search").addEventListener("click", (e) => { if (e.target === $("#search")) closeSearch(); });
  $("#search-input").addEventListener("input", (e) => searchFill(e.target.value));
  $("#search-input").addEventListener("keydown", (e) => {
    const items = [...document.querySelectorAll("#search-results .sr-item")], i = items.findIndex((x) => x.classList.contains("on"));
    if (e.key === "ArrowDown" || e.key === "ArrowUp") { e.preventDefault(); const j = Math.max(0, Math.min(items.length - 1, i + (e.key === "ArrowDown" ? 1 : -1))); items.forEach((x, k) => x.classList.toggle("on", k === j)); if (items[j]) items[j].scrollIntoView({ block: "nearest" }); }
    else if (e.key === "Enter" && items[Math.max(0, i)]) { e.preventDefault(); items[Math.max(0, i)].click(); location.hash = items[Math.max(0, i)].getAttribute("href"); }
  });
  document.addEventListener("keydown", (e) => {
    if (e.key === "Escape") { if (!$("#search").hidden) closeSearch(); else if (!$("#notes").hidden) closeNotes(); else closeMenu(); return; }
    const typing = e.target && e.target.closest && e.target.closest("input, textarea, select, [contenteditable]");
    if (((e.key === "k" && (e.ctrlKey || e.metaKey)) || (e.key === "/" && !typing)) && !document.body.classList.contains("immersive")) { e.preventDefault(); openSearch(); }
  });
  S.course = await getJSON("/api/home");
  if (!S.course) { $("#app").replaceChildren(h("div", { class: "empty" }, "The course could not be loaded.")); return; }
  S.goals = Object.fromEntries((S.course.goals || []).map((g) => [g.id, g]));
  $("#yt-box").checked = preferYouTube();
  document.title = S.course.title;
  $("#brand-t").textContent = S.course.title;
  const nn = notesAll().length; $("#notes-count").hidden = !nn; $("#notes-count").textContent = nn;
  noteListeners.add(() => { const n = notesAll().length; $("#notes-count").hidden = !n; $("#notes-count").textContent = n; });
  if (!S.course.layers.knowledge) document.querySelectorAll('.nav a[data-page="map"], .nav a[data-page="concepts"]').forEach((a) => (a.hidden = true));
  window.addEventListener("hashchange", render);
  render();
}
main();
