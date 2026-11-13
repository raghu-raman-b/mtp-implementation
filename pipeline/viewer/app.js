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
    const g = s("g", { class: "node" + (n.kind ? " k-" + n.kind : "") + (n.cls ? " " + n.cls : ""), transform: `translate(${P.x},${P.y})`, tabindex: 0, role: "button", "aria-label": n.label });
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
    g.addEventListener("click", (ev) => { ev.stopPropagation(); if (!dragged) select(n.id === sel ? null : n.id); });
    g.addEventListener("dblclick", (ev) => { ev.stopPropagation(); if (opts.onDouble) opts.onDouble(n.id); else { select(n.id); zoomTo(n.id); } });
    g.addEventListener("keydown", (ev) => { if (ev.key === "Enter" || ev.key === " ") { ev.preventDefault(); select(n.id); zoomTo(n.id, true); } });
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
    sel = id && N[id] ? id : null;
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
    if (body && !keepCard) { card.replaceChildren(h("button", { class: "ghost small close", "aria-label": "Close", onclick: () => select(null) }, "✕"), body); card.hidden = false; }
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
    h("button", { class: "small", onclick: () => fit(), title: "Show the whole map" }, "Fit"),
    h("button", { class: "small", onclick: () => { select(null); if (opts.onClear) opts.onClear(); fit(); }, title: "Clear the selection and show the whole map" }, "Reset")));
  wrap.focusNode = (id) => { select(id || null); if (id) zoomTo(id, true); };
  wrap.highlightSet = highlightSet;
  wrap.nodes = N;
  wrap.select = select;
  if (opts.focus && N[opts.focus]) setTimeout(() => select(opts.focus), 0);
  return wrap;
}

// the legend of the node styles a map uses
const MAP_KIND_LABEL = { introduced: "New in this lecture", met_again: "Met in an earlier lecture", defined_later: "Explained in a later lecture", assumed: "Not taught in this course" };
function mapLegend(kinds, hint) {
  const present = Object.keys(MAP_KIND_LABEL).filter((k) => !kinds || kinds.has(k));
  return h("div", { class: "legend" },
    present.map((k) => h("span", {}, h("i", { class: "sw k-" + k }), MAP_KIND_LABEL[k])),
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
    else if (r.page === "map") el = pageMap(r.arg, r.rest);
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
  const groups = segs.map((sg, i) => ({ key: sg.id, title: `Part ${i + 1}`, time: sg.start, sub: sg.subgoal || "", href: timeHref(L.key, sg.start), ids: ids.filter((id) => home[id] === sg.id) }));
  const other = ids.filter((id) => home[id] === "__other");
  if (other.length) groups.push({ key: "__other", title: "Also in this lecture", sub: "", ids: other });
  return groups;
}
function conceptCard(cid, here) {  // the card a map opens for a concept
  const c = concept(cid);
  if (!c) return null;
  const d = (c.defined_in || []).find((x) => x.lecture === here) || (c.defined_in || [])[0];
  const def = c.definition || "";
  return h("div", {},
    h("div", { class: "mc-name" }, cap(c.name), dev(" " + cid)),
    def ? h("div", { class: "mc-def" }, def.length > 320 ? def.slice(0, 300).replace(/\s+\S*$/, "") + " …" : def) : h("div", { class: "mc-def faint" }, "Used in the course without a definition."),
    h("div", { class: "row small", style: "margin-top:8px" },
      d ? timeLink(d.lecture, d.start, here) : null,
      h("a", { href: `#/concept/${cid}` }, "Concept card"),
      h("a", { href: `#/map/concepts/${cid}` }, "Explore its links")));
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
  nodes = nodes.filter((n) => linked.has(n.id)).map((n) => ({ ...n, kind: n.kind || kindOf[n.id] }));
  const kinds = new Set(nodes.map((n) => n.kind).filter(Boolean));
  const big = nodes.length >= CORE_FROM;
  const seeds = o.seeds || nodes.filter((n) => n.kind === "introduced").map((n) => n.id);
  const core = big ? coreOf(nodes, edges, seeds, o.must) : null;
  const groups = big ? partGroups(L, nodes.map((n) => n.id), o.homeOf) : null;
  const key = `mapview:${o.store || "lecture"}`;
  let mode = big ? (store(key) === "all" && !o.keyFirst ? "all" : "key") : "all";
  const holder = h("div", {});
  const seg = big ? h("div", { class: "seg-ctl", role: "tablist" }) : null;
  const hint = h("span", { class: "faint hint" });
  const draw = () => {
    let el;
    const card = o.card === null ? null : o.card || ((id) => conceptCard(id, L.key));
    if (mode === "key") {
      const ns = nodes.filter((n) => core.has(n.id)), es = keyEdges(edges.filter((e) => core.has(e.from) && core.has(e.to)), ns);
      el = drawMap(ns, es, { card, height: 620, aria: "Key concepts of the lecture" });
      hint.textContent = "The key concepts and how they connect. Click a concept to see all its links and its card; double-click to zoom in.";
      if (es.some((e) => e.extra)) hint.textContent += " Some links are shown only when you select a concept.";
    } else if (big && groups) {
      el = drawMap(nodes, edges, { mode: "parts", groups, card, aria: "All the concepts of the lecture, by part" });
      hint.textContent = "Grouped by the part of the lecture that explains them (click a part's title to watch it). Point at or click a concept to see its links.";
    } else {
      const es = edges.length > nodes.length * 1.6 ? keyEdges(edges, nodes) : edges;
      el = drawMap(nodes, es, { card, height: 620, dense: big && edges.length > 60 });
      hint.textContent = "Click a concept to see all its links and its card; double-click to zoom in. Drag to move; Ctrl + scroll to zoom." + (es.some((e) => e.extra) ? " Some links are shown only when you select a concept." : "");
    }
    if (seg) seg.replaceChildren(
      h("button", { class: mode === "key" ? "on" : "", role: "tab", "aria-selected": String(mode === "key"), onclick: () => { mode = "key"; store(key, mode); draw(); } }, "Key concepts"),
      h("button", { class: mode === "all" ? "on" : "", role: "tab", "aria-selected": String(mode === "all"), onclick: () => { mode = "all"; store(key, mode); draw(); } }, `All ${nodes.length} concepts` + (groups ? ", by part" : "")));
    holder.replaceChildren(el);
  };
  draw();
  return h("div", { class: "lecmap" },
    h("div", { class: "map-head" }, seg, o.legend === false ? null : mapLegend(kinds)),
    holder, h("div", { class: "small map-hint" }, hint));
}

function lectureMap(L) {
  const KL = L.knowledge;
  if (!KL || !S.K) return h("p", { class: "muted" }, "Not ready yet for this lecture.");
  const kindOf = lectureKinds(L);
  const rels = (KL.concept_map.relations || []).map((r) => [r, S.K.relations[r]]).filter(([, r]) => r);
  const linked = new Set(rels.flatMap(([, r]) => [r.subject, r.object]));
  const nodes = [...linked].map((c) => ({ id: c, label: cname(c) }));
  const edges = rels.map(([rid, r]) => ({ from: r.subject, to: r.object, label: r.label, rid }));
  const alone = (KL.concept_map.concepts || []).filter((c) => !linked.has(c));
  if (!nodes.length) return h("p", { class: "muted" }, "No relationships were found between this lecture's concepts.");
  return h("div", {}, lectureMapView(L, nodes, edges),
    alone.length ? h("div", { style: "margin-top:14px" }, h("div", { class: "small muted" }, "Also in this lecture:"), h("div", { class: "chips", style: "margin-top:4px" }, alone.map((c) => conceptPill(c, kindOf[c])))) : null);
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

// The course map opens on the lectures (rows of weeks; each lecture's circle grows with the concepts it introduces;
// an arrow means a later lecture builds on concepts an earlier one explains) and opens into the concepts: a concept
// and its nearest neighbours, any concept found by name, one click to walk on to the next.
function pageMap(which, rest) {
  if (!S.K) return h("div", { class: "empty" }, "The concept map is not ready yet for this course.");
  const mode = which === "concepts" ? "concepts" : "lectures";
  const sw = h("div", { class: "seg-ctl", style: "margin-bottom:14px" },
    h("a", { class: mode === "lectures" ? "on" : "", href: "#/map" }, "How the lectures build on each other"),
    h("a", { class: mode === "concepts" ? "on" : "", href: "#/map/concepts" }, "Explore the concepts"));
  return h("div", {}, h("h1", {}, "Concept map"), sw, mode === "lectures" ? courseOverview() : conceptExplorer(rest && rest[0]));
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
function courseOverview() {
  // chapters (runs of lectures that serve one course goal) as bands; in each, its topics as cards; in each topic its
  // lectures as circles that grow with the concepts they introduce; arrows: a later lecture builds on an earlier one
  const C = S.course, G = S.K.graph || {}, kinds = G.concept_kinds || {};
  const intro = (k) => ((kinds[k] || {}).introduced || []);
  const maxI = Math.max(1, ...C.lectures.map((l) => intro(l.key).length));
  const links = (G.links || []).filter((l) => l.kind === "direct");
  const goals = (C.goals && C.goals.course_goals) || {};
  const syl = (C.meta || {}).syllabus || [];
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
  const nodes = C.lectures.map((l) => ({ id: l.key, label: l.key, circle: Math.round(9 + (R - 9) * Math.sqrt(intro(l.key).length / maxI)), cls: "lec", title: `Lecture ${l.key}: ${l.title}` }));
  const edges = links.map((l) => ({ from: l.from, to: l.to, label: l.concepts.slice(0, 3).map(cname).join(", ") + (l.concepts.length > 3 ? ", …" : "") }));
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
    const l = lecInfo(k), pre = ((G.prerequisites || {})[k] || {}).direct || [], after = links.filter((x) => x.from === k).map((x) => x.to);
    const jump = (p) => h("a", { href: `#/lecture/${p}`, title: lecInfo(p).title, onclick: (ev) => { ev.preventDefault(); map.focusNode(p); } }, `Lecture ${p}`);
    const list = (ks) => ks.map((p, i) => [i ? ", " : "", jump(p)]);
    const news = intro(k).slice().sort((a, b) => (((G.concepts || {})[b] || {}).lectures || 0) - (((G.concepts || {})[a] || {}).lectures || 0));
    return h("div", {},
      h("div", { class: "mc-kicker" }, `Lecture ${k}` + (l.week ? ` · Week ${l.week}` : "")),
      h("div", { class: "mc-name" }, l.title),
      l.goal ? h("div", { class: "mc-def" }, l.goal) : null,
      h("div", { class: "small", style: "margin-top:6px" }, pre.length ? [h("span", { class: "muted" }, "Builds on "), list(pre)] : h("span", { class: "muted" }, "Needs no earlier lecture.")),
      after.length ? h("div", { class: "small" }, h("span", { class: "muted" }, "Leads to "), list(after)) : null,
      news.length ? [h("div", { class: "small muted", style: "margin-top:8px" }, "New here:"), h("div", { class: "chips", style: "margin-top:4px" }, news.slice(0, 8).map((c) => h("a", { class: "pill k-introduced", href: `#/map/concepts/${c}`, title: "Explore its links" }, cname(c))))] : null,
      h("div", { class: "row", style: "margin-top:10px" }, h("a", { class: "btn primary small", href: `#/lecture/${k}` }, "Open the lecture"), h("a", { class: "btn small", href: `#/lecture/${k}/map` }, "Its concept map")));
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
      const all = new Set(k ? ((G.prerequisites || {})[k] || {}).all || [] : []);
      for (const [id, g] of Object.entries(map.nodes)) g.classList.toggle("chain", all.has(id));
      if (k && goalOn) { goalOn = null; chips.forEach((x) => x.classList.remove("on")); info.textContent = ""; }
    } });
  map.classList.add("overview");
  return h("div", {},
    h("p", { class: "muted", style: "max-width:900px;margin-top:0" }, "The course in its chapters, week by week. Each circle is a lecture, grouped by topic; the larger the circle, the more new concepts the lecture introduces. An arrow means a later lecture builds on what an earlier one explains. Select a lecture to see what it needs and where it leads; double-click to open it."),
    chips.length ? h("div", { class: "row goal-row" }, h("span", { class: "small muted" }, "Show the lectures of a course goal:"), chips, info) : null,
    map);
}

function conceptExplorer(cid) {
  const K = S.K;
  const degree = (c) => ((c.relations || {}).out || []).length + ((c.relations || {}).in || []).length;
  const pool = Object.entries(K.concepts).filter(([, c]) => degree(c));
  if (!pool.length) return h("p", { class: "muted" }, "No relationships yet.");
  if (!cid || !concept(cid)) {  // start from the best connected concept the first lecture defines
    const first = (S.course.lectures[0] || {}).key;
    const early = pool.filter(([, c]) => c.first_defined === first);
    cid = (early.length ? early : pool).reduce((a, b) => (degree(b[1]) > degree(a[1]) ? b : a))[0];
  }
  S.trail = (S.trail || []).filter((x) => x !== cid).concat([cid]).slice(-6);
  const c = concept(cid);
  const lec = (n) => ((K.graph.concepts || {})[n] || {}).lectures || 0;
  const rels = [...((c.relations || {}).out || []).map((r) => ({ ...r, dir: "out" })), ...((c.relations || {}).in || []).map((r) => ({ ...r, dir: "in" }))]
    .filter((r) => r.concept !== cid && concept(r.concept));
  const score = (n) => (concept(n).definition ? 3 : 0) + Math.log(1 + lec(n));
  const nbs = [...new Set(rels.map((r) => r.concept))].sort((a, b) => score(b) - score(a));
  const shown = new Set(nbs.slice(0, 12));
  const per = {};
  const edges = [];
  for (const r of rels) {
    if (!shown.has(r.concept) || (per[r.concept] = (per[r.concept] || 0) + 1) > 1) continue;
    edges.push(r.dir === "out" ? { from: cid, to: r.concept, label: r.label } : { from: r.concept, to: cid, label: r.label });
  }
  const nodes = [{ id: cid, label: cname(cid), cls: "centre" }, ...[...shown].map((n) => ({ id: n, label: cname(n) }))];
  const card = (id) => {
    const body = conceptCard(id);
    if (body && id !== cid) body.append(h("div", { style: "margin-top:10px" }, h("a", { class: "btn primary small", href: `#/map/concepts/${id}` }, "Centre the map here")));
    return body;
  };
  const map = drawMap(nodes, edges, { height: 580, card, onDouble: (id) => (location.hash = `#/map/concepts/${id}`), aria: `${cname(cid)} and the concepts it links to` });
  const names = pool.map(([id, x]) => [id, cap(x.name)]).sort((a, b) => a[1].localeCompare(b[1]));
  const find = h("input", { type: "search", class: "map-find", list: "map-names", placeholder: "Find a concept…", "aria-label": "Find a concept" });
  const go = () => {
    const q = find.value.trim().toLowerCase();
    if (!q) return;
    const hit = names.find(([, n]) => n.toLowerCase() === q) || names.find(([, n]) => n.toLowerCase().startsWith(q)) || names.find(([, n]) => n.toLowerCase().includes(q));
    if (hit) location.hash = `#/map/concepts/${hit[0]}`;
  };
  find.addEventListener("change", go);
  find.addEventListener("keydown", (ev) => { if (ev.key === "Enter") { ev.preventDefault(); go(); } });
  const more = rels.filter((r) => !shown.has(r.concept));
  const sentence = (r) => h("li", {}, r.dir === "out" ? [h("b", {}, cname(cid)), " ", h("span", { class: "lbl" }, r.label), " ", h("a", { href: `#/map/concepts/${r.concept}` }, cname(r.concept))]
    : [h("a", { href: `#/map/concepts/${r.concept}` }, cname(r.concept)), " ", h("span", { class: "lbl" }, r.label), " ", h("b", {}, cname(cid))]);
  return h("div", {},
    h("div", { class: "row", style: "margin-bottom:10px" }, find, h("datalist", { id: "map-names" }, names.map(([, n]) => h("option", { value: n }))),
      S.trail.length > 1 ? h("div", { class: "trail small" }, S.trail.map((t, i) => [i ? h("span", { class: "faint" }, " › ") : null, t === cid ? h("b", {}, cname(t)) : h("a", { href: `#/map/concepts/${t}` }, cname(t))])) : null,
      dev(`${cid}: ${rels.length} relationships, ${nbs.length} neighbours`)),
    h("div", { class: "explore-head" }, h("h2", { style: "margin:0" }, cap(c.name)), c.definition ? h("div", { class: "muted" }, c.definition) : null),
    map,
    h("div", { class: "small map-hint faint" }, "Click a concept for its card; double-click to centre the map on it."),
    more.length ? h("details", { class: "card", style: "margin-top:14px" }, h("summary", {}, "More links of ", h("b", {}, cname(cid))), h("ul", { class: "rels", style: "margin-top:8px" }, more.slice(0, 200).map(sentence))) : null);
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
  concept_map(a, L) {
    const d = a.data;
    return lectureMapView(L, (d.nodes || []).map((n) => ({ id: n.id, label: cap(n.label) })),
      (d.edges || []).map((e) => ({ from: e.from, to: e.to, label: e.label })), { store: "activity" });
  },
  complete_map(a, L) {
    // the blanks stay in the key view (with the links around them); a hidden concept becomes a "(n) ?" node
    const d = a.data, edges = (d.edges || []).map((e) => ({ ...e })), nodes = (d.nodes || []).map((n) => ({ id: n.id, label: cap(n.label) }));
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
        nodes.push({ id: nid, label: `${tag} ?`, cls: "blank" });
        e[end] = nid; e.always = true;
        must.push(e.from, e.to);
      }
    });
    const stillUsed = new Set(edges.flatMap((e) => [e.from, e.to]));
    const shown = nodes.filter((n) => !hidden.has(n.id) || stillUsed.has(n.id));
    const sels = (d.blanks || []).map((b, i) => {
      const sel = h("select", {}, h("option", { value: "" }, "Choose…"), (b.options || []).map((o) => h("option", { value: o }, o)));
      const mark = h("span", {});
      return { b, sel, mark, row: h("div", { class: "row" }, h("b", {}, `(${i + 1})`), h("span", { class: "small muted" }, b.hide === "label" ? "the link" : "the concept"), sel, mark) };
    });
    return h("div", {}, lectureMapView(L, shown, edges, { seeds: must, must, card: null, store: "complete", keyFirst: true, homeOf: (id) => stands[id] || id }),
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
