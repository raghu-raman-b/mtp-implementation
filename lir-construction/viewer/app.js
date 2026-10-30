/* Lecture Planner viewer: renders a whole course LIR (lir/<course>/course.json + Lxx.json).
 *
 * Routes:  #/                      course home (roadmap)
 *          #/L03/p/4               lecture L03, phase 4
 *          #/L03/p/4/t/123.4       ... and seek the video to 123.4 s
 *
 * Learner state (progress, highlights, quiz picks, answers, concept maps) is kept in localStorage per course.
 * Open answers and concept maps are scored by serve.py on the CPU; without it, a keyword-only scorer runs here.
 */
"use strict";

const S = { index: null, course: null, cid: null, lec: {}, order: [], timers: [] };
const REVIEW = new URLSearchParams(location.search).has("review");  // shows intents and rule IDs for the final check

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
  for (const k of kids.flat()) if (k != null && k !== false) el.append(k.nodeType ? k : document.createTextNode(String(k)));
  return el;
}
const svgNS = "http://www.w3.org/2000/svg";
function s(tag, attrs, ...kids) {
  const el = document.createElementNS(svgNS, tag);
  for (const [k, v] of Object.entries(attrs || {})) if (v != null) el.setAttribute(k, v);
  for (const k of kids.flat()) if (k != null) el.append(k.nodeType ? k : document.createTextNode(String(k)));
  return el;
}
function clock(t) {
  t = Math.max(0, Math.floor(t));
  const hh = Math.floor(t / 3600), m = Math.floor((t % 3600) / 60), sec = t % 60;
  return (hh ? hh + ":" + String(m).padStart(2, "0") : m) + ":" + String(sec).padStart(2, "0");
}
const mins = (t) => `${Math.max(1, Math.round(t / 60))} min`;
function toast(msg) {
  const t = h("div", { class: "toast" }, msg);
  document.body.append(t);
  setTimeout(() => t.remove(), 2200);
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
function clearTimers() { S.timers.forEach(clearInterval); S.timers = []; }

// ------------------------------------------------------------------ theme
function applyTheme() {
  const t = prefs.get("theme", "auto");
  if (t === "auto") document.documentElement.removeAttribute("data-theme");
  else document.documentElement.setAttribute("data-theme", t);
}
function themeButton() {
  const label = { auto: "Theme: auto", light: "Theme: light", dark: "Theme: dark" };
  const b = h("button", { class: "ghost", title: "Theme" }, label[prefs.get("theme", "auto")]);
  b.onclick = () => {
    const next = { auto: "light", light: "dark", dark: "auto" }[prefs.get("theme", "auto")];
    prefs.set("theme", next); applyTheme(); b.textContent = label[next];
  };
  return b;
}

// ------------------------------------------------------------------ loading
async function getJSON(url) {
  const r = await fetch(url);
  if (!r.ok) throw new Error(`${url}: ${r.status}`);
  return r.json();
}
async function boot() {
  applyTheme();
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

function route() {
  clearTimers();
  const p = location.hash.replace(/^#\/?/, "").split("/").filter(Boolean);
  if (!p.length || !S.lec[p[0]]) return renderHome();
  const lid = p[0];
  const idx = p[1] === "p" ? Number(p[2]) : firstOpenPhase(lid);
  const t = p[3] === "t" ? Number(p[4]) : null;
  renderLecture(lid, Math.min(Math.max(0, idx || 0), S.lec[lid].phases.length - 1), t);
}
function go(lid, idx, t) { location.hash = `#/${lid}/p/${idx}` + (t != null ? `/t/${t.toFixed(1)}` : ""); }
function jump(lid, t) {
  const lec = S.lec[lid];
  if (!lec) return toast("That lecture is not in this build");
  const i = lec.phases.findIndex((ph) => ph.type === "segment" && t >= ph.start - 0.01 && t < ph.end);
  go(lid, i >= 0 ? i : 1, t);
}

// ------------------------------------------------------------------ progress
const doneSet = (lid) => new Set(store.get(`done:${lid}`, []));
function markDone(lid, idx) {
  const d = doneSet(lid); d.add(idx); store.set(`done:${lid}`, [...d]);
  const st = document.querySelector(`.step[data-i="${idx}"]`);
  if (st) st.classList.add("done");
  updateLectureBar(lid);
}
function lectureProgress(lid) { return doneSet(lid).size / S.lec[lid].phases.length; }
function firstOpenPhase(lid) {
  const d = doneSet(lid);
  const i = S.lec[lid].phases.findIndex((_, k) => !d.has(k));
  return i < 0 ? 0 : i;
}
function courseResume() {
  for (const lid of S.order) if (lectureProgress(lid) < 1) return [lid, firstOpenPhase(lid)];
  return [S.order[0], 0];
}

// ------------------------------------------------------------------ home
function renderHome() {
  document.title = S.course.title;
  const done = S.order.reduce((a, l) => a + lectureProgress(l), 0) / S.order.length;
  const [rl, rp] = courseResume();
  const started = done > 0;
  const courseSel = S.index.courses.length > 1
    ? h("select", { onchange: async (e) => { await loadCourse(e.target.value); location.hash = "#/"; renderHome(); } },
      S.index.courses.map((c) => h("option", { value: c.course_id, selected: c.course_id === S.cid }, c.title)))
    : null;
  const top = h("div", { class: "topbar" }, h("span", { class: "title" }, S.course.title), h("span", { class: "spacer" }),
    courseSel, themeButton());
  const hero = h("div", { class: "hero" },
    h("div", {},
      h("div", { class: "kicker" }, started ? "Welcome back" : "Welcome"),
      h("h1", { style: "margin-top:6px" }, S.course.title),
      started ? h("div", { class: "row", style: "margin-top:14px" }, ring(done),
        h("div", {}, h("b", {}, `${Math.round(done * 100)}% complete`),
          h("div", { class: "small muted" }, `Up next: ${lectureName(rl)} · ${S.lec[rl].title}`))) : null),
    h("div", {}, h("button", { class: "primary big", onclick: () => go(rl, rp) }, started ? "Continue ▸" : "Start the course ▸")));
  const goals = S.course.course_goals.length ? h("div", { class: "card goals" },
    h("h3", {}, "What you will be able to do"),
    h("ul", {}, S.course.course_goals.map((g) => h("li", {}, g.text)))) : null;
  const road = h("div", { class: "roadmap" }, S.order.map((lid, i) => lectureCard(lid, i)));
  $("#app").replaceChildren(top, h("div", { class: "wrap" }, hero, goals,
    h("h2", { style: "margin:8px 0 14px" }, "Your path through the course"), road));
}
function lectureName(lid) { return "Lecture " + String(S.order.indexOf(lid) + 1); }
function lectureCard(lid, i) {
  const L = S.lec[lid];
  const p = lectureProgress(lid);
  const d = doneSet(lid);
  const body = h("div", { class: "lec-body", hidden: true },
    L.roadmap.objectives.map((o) => h("div", { class: "obj" },
      h("div", { class: "obj-title" }, o.text),
      o.segment_ids.map((sid) => {
        const seg = L.segments.find((x) => x.id === sid);
        const pi = L.phases.findIndex((ph) => ph.type === "segment" && ph.segment_id === sid);
        return h("div", { class: "seg-line" }, h("span", { class: "check" }, d.has(pi) ? "✓" : "·"),
          h("a", { href: `#/${lid}/p/${pi}` }, seg.subgoal));
      }))),
    h("div", { class: "row", style: "margin-top:10px" },
      h("button", { class: "primary", onclick: () => go(lid, firstOpenPhase(lid)) },
        p >= 1 ? "Review lecture" : p > 0 ? "Continue lecture" : "Start lecture")));
  const toggle = h("button", { class: "ghost small", onclick: (e) => {
    e.stopPropagation(); body.hidden = !body.hidden; toggle.textContent = body.hidden ? "Show parts ▾" : "Hide parts ▴";
  } }, "Show parts ▾");
  return h("div", { class: "card lec" + (p >= 1 ? " done" : "") },
    h("div", { class: "lec-head", onclick: () => go(lid, firstOpenPhase(lid)), title: "Open this lecture" },
      h("div", { class: "lec-num" }, p >= 1 ? "✓" : i + 1),
      h("div", {}, h("div", { class: "lec-title" }, L.title), h("div", { class: "lec-goal" }, L.roadmap.lecture_goal),
        h("div", { style: "margin-top:4px" }, toggle)),
      h("div", { class: "lec-meta" },
        h("button", { class: p > 0 && p < 1 ? "primary" : "", onclick: (e) => { e.stopPropagation(); go(lid, firstOpenPhase(lid)); } },
          p >= 1 ? "Review ▸" : p > 0 ? `Continue · ${Math.round(p * 100)}% ▸` : "Open ▸"))),
    body);
}

// ------------------------------------------------------------------ lecture shell
function phaseLabel(L, ph) {
  if (ph.type === "primer") return "Before you start";
  if (ph.type === "segment") return ph.subgoal;
  if (ph.type === "active") return "Quiz and summary";
  return "Concept map and questions";
}
function renderLecture(lid, idx, t) {
  const L = S.lec[lid];
  document.title = `${lectureName(lid)} · ${L.title}`;
  const d = doneSet(lid);
  const steps = [];
  const objOf = Object.fromEntries(L.segments.map((x) => [x.id, x.objective_id]));
  let lastObj = null;
  L.phases.forEach((ph, i) => {
    if (ph.type === "primer") steps.push(h("div", { class: "group" }, "Start"));
    const o = ph.segment_id ? objOf[ph.segment_id] : null;
    if (o && o !== lastObj) {
      const obj = L.roadmap.objectives.find((x) => x.id === o);
      steps.push(h("div", { class: "group", title: obj ? obj.text : "" }, `Objective ${o.slice(1)}`));
      lastObj = o;
    }
    if (ph.type === "constructive") steps.push(h("div", { class: "group" }, "Wrap-up"));
    steps.push(h("div", { class: "step" + (i === idx ? " current" : "") + (d.has(i) ? " done" : ""), "data-i": i,
      tabindex: 0, onclick: () => go(lid, i) },
      h("span", { class: "ic" }, d.has(i) ? "✓" : ""),
      h("span", {}, ph.type === "active" ? h("span", { class: "faint" }, "Practice · ") : null,
        ph.type === "segment" ? h("span", { class: "faint" }, "Watch · ") : null, phaseLabel(L, ph))));
  });
  const li = S.order.indexOf(lid);
  const top = h("div", { class: "topbar" },
    h("button", { class: "ghost", onclick: () => { location.hash = "#/"; } }, "← Roadmap"),
    h("select", { class: "lec-switch", title: "Go to another lecture",
      onchange: (e) => go(e.target.value, firstOpenPhase(e.target.value)) },
      S.order.map((x, k) => h("option", { value: x, selected: x === lid }, `Lecture ${k + 1} · ${S.lec[x].title}`))),
    h("div", { class: "progress", style: "width:140px", id: "lecbar" }, h("div", { style: `width:${lectureProgress(lid) * 100}%` })),
    h("span", { class: "spacer" }), themeButton());
  const main = h("div", { class: "main" });
  $("#app").replaceChildren(top, h("div", { class: "lecture" }, h("nav", { class: "side" }, steps), main));
  const ph = L.phases[idx];
  const content = { primer: renderPrimer, segment: renderSegment, active: renderActive, constructive: renderConstructive }[ph.type](L, ph, idx, t);
  const prev = idx > 0 ? () => go(lid, idx - 1) : li > 0 ? () => go(S.order[li - 1], S.lec[S.order[li - 1]].phases.length - 1) : null;
  const nextLec = li < S.order.length - 1 ? S.order[li + 1] : null;
  const next = idx < L.phases.length - 1 ? () => { markDone(lid, idx); go(lid, idx + 1); }
    : nextLec ? () => { markDone(lid, idx); go(nextLec, 0); } : () => { markDone(lid, idx); location.hash = "#/"; };
  main.append(content, h("div", { class: "nav" },
    h("button", { onclick: prev, disabled: !prev }, "◂ Back"),
    h("button", { class: "primary", onclick: next },
      idx < L.phases.length - 1 ? "Next ▸" : nextLec ? `Next: ${lectureName(nextLec)} ▸` : "Finish course ✓")));
  document.querySelector(".step.current")?.scrollIntoView({ block: "nearest" });
  window.scrollTo(0, 0);
}
function updateLectureBar(lid) { const b = $("#lecbar > div"); if (b) b.style.width = lectureProgress(lid) * 100 + "%"; }

function head(kicker, title, intent) {
  const why = intent && REVIEW ? h("div", { class: "why" }) : null;
  if (why) {
    const pop = h("div", { class: "card why-pop", hidden: true },
      h("div", { class: "small" }, h("b", {}, "Why this activity? "), intent.rationale),
      h("div", { class: "row small", style: "margin-top:8px" },
        intent.principle.map((p) => h("span", { class: "tag" }, p.replaceAll("_", " "))),
        h("span", { class: "tag ok" }, intent.icap_mode), h("span", { class: "tag warn" }, "Bloom: " + intent.bloom_level)),
      h("div", { class: "faint small", style: "margin-top:6px" }, "rule: " + intent.rule_id));
    why.append(h("button", { class: "ghost small", onclick: () => { pop.hidden = !pop.hidden; } }, "ⓘ Why"), pop);
  }
  return h("div", { class: "phase-head" }, h("div", { style: "flex:1" }, h("div", { class: "kicker" }, kicker), h("h2", {}, title)), why);
}

// ------------------------------------------------------------------ primer
function renderPrimer(L, ph, idx) {
  const out = h("div", {}, head("Before you start", L.title, ph.intent));
  out.append(h("div", { class: "card section" }, h("h3", {}, "Goal of this lecture"), h("p", { style: "margin:0" }, ph.lecture_goal),
    h("ul", { class: "objectives" }, ph.objectives.map((o) => h("li", {}, o.text)))));
  if (ph.recall.length) {
    out.append(h("div", { class: "card section" }, h("h3", {}, "Remember these?"),
      h("p", { class: "muted small", style: "margin-top:0" }, "This lecture builds on ideas from earlier lectures. Try to answer before you reveal."),
      ph.recall.map((r) => {
        const ans = h("div", { class: "answer", hidden: true }, r.recap, " ",
          h("button", { class: "ghost small", onclick: () => jump(r.jump_to.lecture_id, r.jump_to.t) },
            `▶ Rewatch (${lectureName(r.jump_to.lecture_id)}, ${clock(r.jump_to.t)})`));
        return h("div", { class: "recall" }, h("div", {}, h("b", {}, r.question)),
          h("button", { class: "ghost small", onclick: (e) => { ans.hidden = false; e.target.remove(); } }, "Show answer"), ans);
      })));
  }
  if (ph.key_terms.length) {
    out.append(h("div", { class: "card section" }, h("h3", {}, "New key terms"),
      h("div", { class: "terms" }, ph.key_terms.map((k) => h("div", { class: "term" }, h("b", {}, k.term), h("span", { class: "small muted" }, k.definition))))));
  }
  setTimeout(() => markDone(L.lecture_id, idx), 4000);
  return out;
}

// ------------------------------------------------------------------ segment (video)
function videoAvailable(url) {
  return fetch(url, { method: "HEAD" }).then((r) => r.ok).catch(() => false);
}
function renderSegment(L, ph, idx, seekTo) {
  const sents = L.sentences.slice(ph.sentence_range[0], ph.sentence_range[1] + 1);
  const hl = new Set(store.get(`hl:${L.lecture_id}`, []));
  const out = h("div", {}, head("Watch", ph.subgoal, ph.intent));
  const player = h("div", { class: "player" });
  const cc = h("div", { class: "cc", hidden: true });
  const fill = h("div", { style: "width:0%" });
  const range = h("div", { class: "seg-range", title: "Seek within this part" }, fill);
  const time = h("span", { class: "time" }, `0:00 / ${clock(ph.end - ph.start)}`);
  let ccOn = prefs.get("cc", true), hlMode = false, video = null;
  const ccBtn = h("button", { class: "toggle" + (ccOn ? " on" : ""), title: "Captions" }, "CC");
  const hlBtn = h("button", { class: "toggle", title: "Click sentences to highlight them" }, "✎ Highlight");
  const speed = h("select", {}, [0.75, 1, 1.25, 1.5, 1.75, 2].map((v) => h("option", { value: v, selected: v === prefs.get("speed", 1) }, v + "×")));
  const transcript = h("div", { class: "card transcript" }, sents.map((x) =>
    h("div", { class: "sent" + (hl.has(x.id) ? " hl" : ""), "data-id": x.id, title: clock(x.start) }, x.text)));
  const banner = h("div", { class: "card done-banner", hidden: true },
    h("span", {}, "✓ Part complete."), h("span", { class: "spacer" }),
    h("button", { onclick: () => { if (video) { video.currentTime = ph.start; video.play(); } } }, "Replay"),
    h("button", { class: "primary", onclick: () => { markDone(L.lecture_id, idx); go(L.lecture_id, idx + 1); } }, "Practice ▸"));
  ccBtn.onclick = () => { ccOn = !ccOn; prefs.set("cc", ccOn); ccBtn.classList.toggle("on", ccOn); cc.hidden = !ccOn || !cc.textContent; };
  hlBtn.onclick = () => { hlMode = !hlMode; hlBtn.classList.toggle("on", hlMode); toast(hlMode ? "Click sentences to highlight them" : "Highlighting off"); };
  const toggleHl = (id, el) => {
    hl.has(id) ? hl.delete(id) : hl.add(id);
    el.classList.toggle("hl", hl.has(id)); store.set(`hl:${L.lecture_id}`, [...hl]);
  };
  transcript.addEventListener("click", (e) => {
    const el = e.target.closest(".sent"); if (!el) return;
    const id = Number(el.dataset.id);
    if (hlMode) return toggleHl(id, el);
    if (video) { video.currentTime = L.sentences[id].start + 0.01; video.play(); }
  });
  transcript.addEventListener("dblclick", (e) => { const el = e.target.closest(".sent"); if (el) toggleHl(Number(el.dataset.id), el); });
  out.append(player, h("div", { class: "vbar" }, range, time, ccBtn, hlBtn, speed), banner,
    h("div", { class: "row small muted", style: "margin-top:12px" }, "Transcript · click a sentence to jump, double-click (or ✎) to highlight"),
    transcript);

  const src = L.video ? "/" + L.video : null;
  (src ? videoAvailable(src) : Promise.resolve(false)).then((ok) => {
    if (!ok) {
      const yt = L.youtube_id;
      player.replaceChildren(yt
        ? h("iframe", { src: `https://www.youtube-nocookie.com/embed/${yt}?start=${Math.floor(seekTo ?? ph.start)}&end=${Math.ceil(ph.end)}&rel=0`,
          allow: "autoplay; encrypted-media; fullscreen", allowfullscreen: true })
        : h("div", { class: "empty" }, "No video available for this lecture."));
      out.insertBefore(h("div", { class: "small faint" }, "The local video is not downloaded yet, so it plays from YouTube (captions and highlights still work in the transcript)."), player.nextSibling);
      return;
    }
    video = h("video", { src, controls: true, preload: "auto", playsinline: true });
    player.replaceChildren(video, cc);
    video.playbackRate = Number(speed.value);
    speed.onchange = () => { video.playbackRate = Number(speed.value); prefs.set("speed", Number(speed.value)); };
    video.addEventListener("loadedmetadata", () => { video.currentTime = seekTo ?? ph.start; });
    range.onclick = (e) => {
      const r = range.getBoundingClientRect();
      video.currentTime = ph.start + (ph.end - ph.start) * ((e.clientX - r.left) / r.width);
    };
    let lastId = -1;
    const tick = () => {
      const t = video.currentTime;
      fill.style.width = Math.min(100, Math.max(0, (t - ph.start) / (ph.end - ph.start) * 100)) + "%";
      time.textContent = `${clock(t - ph.start)} / ${clock(ph.end - ph.start)}`;
      const cur = sents.find((x) => t >= x.start && t < x.end) || null;
      const id = cur ? cur.id : -1;
      if (id !== lastId) {
        lastId = id;
        cc.textContent = cur ? cur.text : "";
        cc.hidden = !ccOn || !cur;
        transcript.querySelectorAll(".sent.now").forEach((el) => el.classList.remove("now"));
        const el = transcript.querySelector(`.sent[data-id="${id}"]`);
        if (el) { el.classList.add("now"); el.scrollIntoView({ block: "nearest", behavior: "smooth" }); }
      }
      if (t >= ph.end - 0.05 && !video.paused) {
        video.pause(); banner.hidden = false; markDone(L.lecture_id, idx);
      }
    };
    video.addEventListener("timeupdate", tick);
    S.timers.push(setInterval(() => video && !video.paused && tick(), 200));
  });
  return out;
}

// ------------------------------------------------------------------ quiz + summary
function renderActive(L, ph, idx) {
  const seg = L.segments.find((x) => x.id === ph.segment_id);
  const out = h("div", {}, head("Practice", seg.subgoal, ph.intent));
  out.append(renderQuiz(L, ph, idx), renderSummary(L, ph, seg));
  return out;
}
function renderQuiz(L, ph, idx) {
  const key = `quiz:${L.lecture_id}:${ph.segment_id}`;
  const st = store.get(key, { picks: {}, checked: false });
  const items = ph.quiz.items;
  const wrap = h("div", {});
  const draw = () => {
    const nRight = items.filter((q) => st.picks[q.id] === q.correct_index).length;
    const all = items.every((q) => st.picks[q.id] != null);
    const scoreBox = st.checked ? h("div", { class: "card quiz-score" }, ring(nRight / items.length),
      h("div", {}, h("b", {}, `${nRight} of ${items.length} correct`),
        h("div", { class: "small muted" }, nRight === items.length ? "Great — every answer right." : "Read the explanations below each item.")),
      h("span", { class: "spacer" }),
      h("button", { onclick: () => { st.picks = {}; st.checked = false; store.set(key, st); draw(); } }, "Try again")) : null;
    wrap.replaceChildren(h("h3", { style: "margin:4px 0 12px" }, "Quick check"), scoreBox || "",
      items.map((q, qi) => h("div", { class: "card qcard" },
        h("div", { class: "row" }, h("span", { class: "qnum" }, `Question ${qi + 1} · ${{ multiple_choice: "Multiple choice", true_false: "True or false", yes_no: "Yes or no" }[q.item_type]}`),
          q.interleaved_from ? h("span", { class: "tag warn" }, `Review from ${lectureName(q.interleaved_from.lecture_id)}`) : null),
        h("div", { class: "stem" }, q.stem),
        h("div", { class: "opts" }, q.options.map((o, oi) => {
          let cls = "opt";
          if (st.checked) cls += oi === q.correct_index ? " right" : st.picks[q.id] === oi ? " wrong" : "";
          else if (st.picks[q.id] === oi) cls += " picked";
          return h("button", { class: cls, disabled: st.checked, onclick: () => { st.picks[q.id] = oi; store.set(key, st); draw(); } },
            h("span", { class: "letter" }, q.options.length > 2 ? "ABCD"[oi] : o[0]),
            h("span", {}, o, st.checked ? h("span", { class: "expl" }, q.explanations[oi]) : null));
        })))),
      st.checked ? "" : h("div", { class: "row" }, h("button", { class: "primary", disabled: !all,
        onclick: () => { st.checked = true; store.set(key, st); markDone(L.lecture_id, idx); draw(); } }, "Check answers"),
        h("span", { class: "small muted" }, all ? "" : "Answer all questions to see the explanations.")));
  };
  draw();
  return wrap;
}
function ring(frac) {
  const r = 22, c = 2 * Math.PI * r;
  const col = frac >= 0.75 ? "var(--ok)" : frac >= 0.5 ? "var(--accent)" : "var(--warn)";
  return s("svg", { class: "ring", viewBox: "0 0 52 52" },
    s("circle", { cx: 26, cy: 26, r, fill: "none", stroke: "var(--line)", "stroke-width": 6 }),
    s("circle", { cx: 26, cy: 26, r, fill: "none", stroke: col, "stroke-width": 6, "stroke-linecap": "round",
      "stroke-dasharray": `${c * frac} ${c}`, transform: "rotate(-90 26 26)" }),
    s("text", { x: 26, y: 31, "text-anchor": "middle", "font-size": 14, "font-weight": 700, fill: "var(--text)" }, Math.round(frac * 100) + "%"));
}
function renderSummary(L, ph, seg) {
  const sm = ph.summary;
  const box = h("div", { class: "card section", style: "margin-top:22px" }, h("h3", {}, "Summary"), h("p", { style: "margin-top:0" }, sm.recap));
  if (sm.key_concepts.length) {
    const ex = h("div", {});
    box.append(h("div", { class: "small muted", style: "margin:12px 0 8px" }, "Key concepts · click for an explanation"),
      h("div", { class: "chips" }, sm.key_concepts.map((k) => h("button", { class: "chip", onclick: (e) => {
        const open = e.target.classList.contains("open");
        box.querySelectorAll(".chip.open").forEach((c) => c.classList.remove("open"));
        ex.replaceChildren(open ? "" : h("div", { class: "explain" }, h("b", {}, k.name + ": "), k.explanation));
        if (!open) e.target.classList.add("open");
      } }, k.name))), ex);
  }
  if (sm.key_terms.length) {
    box.append(h("div", { class: "small muted", style: "margin:14px 0 6px" }, "Key terms"),
      h("div", { class: "terms" }, sm.key_terms.map((t) => h("div", { class: "term" }, h("b", {}, t.term), h("span", { class: "small muted" }, t.definition)))));
  }
  if (sm.earlier_links.length) {
    box.append(h("div", { class: "small muted", style: "margin:14px 0 4px" }, "Builds on"),
      sm.earlier_links.map((l) => h("div", { class: "link-row" },
        h("span", {}, h("b", {}, l.name), " ", h("span", { class: "muted" }, l.label), " ",
          h("b", {}, (S.concepts[l.to_concept_id] || {}).name || "")),
        h("span", { class: "spacer" }),
        h("button", { class: "ghost small", onclick: () => jump(l.jump_to.lecture_id, l.jump_to.t) },
          `▶ ${lectureName(l.jump_to.lecture_id)}, ${clock(l.jump_to.t)}`))));
  }
  const hl = store.get(`hl:${L.lecture_id}`, []).filter((id) => id >= seg.sentence_range[0] && id <= seg.sentence_range[1]).sort((a, b) => a - b);
  box.append(h("div", { class: "small muted", style: "margin:14px 0 4px" }, "Your highlights"),
    hl.length ? hl.map((id) => h("div", { class: "hl-quote" }, L.sentences[id].text))
      : h("div", { class: "small faint" }, "None yet. Highlight sentences in the transcript while watching; they collect here."));
  return box;
}

// ------------------------------------------------------------------ open questions
const TIER_ICON = { excellent: "★", good: "✓", acceptable: "◐", try_again: "↻" };
function keywordScore(oq, answer, cfg) {  // offline fallback: keywords only
  const stem = (w) => { for (const suf of ["ization", "isation", "ations", "ation", "ings", "ing", "ies", "ied", "ers", "er", "es", "ed", "s", "ly"]) if (w.length > suf.length + 2 && w.endsWith(suf)) return w.slice(0, -suf.length) + (suf === "ies" || suf === "ied" ? "y" : ""); return w; };
  const STOP = new Set("a an the of to in on for and or with by from is are be as at this that these those its it".split(" "));
  const words = (t) => (t.toLowerCase().match(/[a-z0-9]+/g) || []).filter((w) => !STOP.has(w)).map(stem);
  const a = new Set(words(answer));
  const kps = oq.key_points.map((kp) => {
    const set = new Set(words(kp.keywords.join(" ")).filter((w) => w.length >= 3));
    const hits = [...set].filter((w) => a.has(w)).length;
    return { text: kp.text, covered: set.size > 0 && hits >= Math.min(cfg.m, set.size) };
  });
  const sc = kps.filter((k) => k.covered).length / kps.length;
  const tiers = cfg.tiers || [];
  const t = tiers.find((x) => sc >= x.min) || { id: "try_again", label: "Try again" };
  return { score: sc, tier: { id: t.id, label: t.label }, key_points: kps, missed: kps.filter((k) => !k.covered).map((k) => k.text), offline: true };
}
function renderOQ(L, oq) {
  const key = `oq:${L.lecture_id}:${oq.id}`;
  const st = store.get(key, { answer: "", result: null, attempts: 0, showRef: false });
  const ta = h("textarea", { placeholder: "Write your answer in your own words…" });
  ta.value = st.answer;
  ta.oninput = () => { st.answer = ta.value; store.set(key, st); };
  const fb = h("div", {});
  const ref = h("div", {});
  const btn = h("button", { class: "primary" }, st.attempts ? "Check again" : "Check my answer");
  const drawFb = () => {
    const r = st.result;
    if (!r) return fb.replaceChildren();
    fb.replaceChildren(h("div", { class: "feedback" },
      h("div", { class: "row" }, h("span", { class: `tier ${r.tier.id}` }, TIER_ICON[r.tier.id] || "", " ", r.tier.label),
        h("span", { class: "small muted" }, `${Math.round(r.score * 100)}% of the key points`),
        r.offline ? h("span", { class: "tag warn" }, "keywords only (scoring server offline)") : null),
      r.missed.length ? h("div", { class: "small", style: "margin-top:10px" }, h("b", {}, "Hint: "), "think about this — ", r.missed[0]) : null,
      h("div", { style: "margin-top:10px" }, r.key_points.map((k) => h("div", { class: "kp " + (k.covered ? "hit" : "miss") },
        h("span", { class: "mark" }, k.covered ? "✓" : "✗"), h("span", {}, k.text,
          k.covered ? null : h("span", { class: "faint" }, " — missed")))))));
  };
  const drawRef = () => ref.replaceChildren(st.showRef ? h("div", { class: "reference" }, h("b", {}, "Reference answer"),
    h("p", { style: "margin:6px 0 0" }, oq.reference_answer)) : "");
  btn.onclick = async () => {
    if (!ta.value.trim()) return toast("Write an answer first");
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
    drawFb();
  };
  drawFb(); drawRef();
  return h("div", { class: "card oq" },
    h("div", { class: "row" }, h("span", { class: "tag" }, { fill_in_steps: "Fill in the steps", compare_contrast: "Compare and contrast", self_explanation: "Explain why", apply_new_case: "Apply it", troubleshooting: "Troubleshoot", explain_to_someone: "Explain it to a friend" }[oq.question_type] || oq.question_type),
      h("span", { class: "spacer" }),
      whyMini(oq.intent)),
    h("div", { class: "prompt" }, oq.prompt), ta,
    h("div", { class: "row", style: "margin-top:10px" }, btn,
      h("button", { class: "ghost", onclick: () => { st.showRef = !st.showRef; store.set(key, st); drawRef(); } }, "Show reference answer")),
    fb, ref);
}
function whyMini(intent) {
  if (!REVIEW) return null;
  return h("button", { class: "ghost small", title: `${intent.rationale}\n\nprinciple: ${intent.principle.join(", ")} · ${intent.icap_mode} · Bloom: ${intent.bloom_level}` }, "ⓘ");
}

// ------------------------------------------------------------------ concept map
function renderConstructive(L, ph, idx) {
  const out = h("div", {}, head("Wrap-up", "Connect the ideas", ph.intent));
  out.append(renderConceptMap(L, ph.concept_map, idx));
  out.append(h("h3", { style: "margin:26px 0 12px" }, "Questions to think about"),
    ph.open_questions.map((q) => renderOQ(L, q)));
  const hl = store.get(`hl:${L.lecture_id}`, []).sort((a, b) => a - b);
  out.append(h("div", { class: "card section", style: "margin-top:10px" }, h("h3", {}, "Your highlights from this lecture"),
    hl.length ? hl.map((id) => h("div", { class: "hl-quote" }, L.sentences[id].text, " ",
      h("button", { class: "ghost small", onclick: () => jump(L.lecture_id, L.sentences[id].start) }, "▶ " + clock(L.sentences[id].start))))
      : h("div", { class: "small faint" }, "You did not highlight anything in this lecture.")));
  setTimeout(() => markDone(L.lecture_id, idx), 4000);
  return out;
}
const W = 900, HGT = 460;
function nodeW(name) { return Math.min(220, 26 + name.length * 7.4); }
function renderConceptMap(L, cm, idx) {
  const key = `cmap:${L.lecture_id}`;
  let st = store.get(key, null);
  if (!st) {
    st = { nodes: cm.seeds.map((n, i) => {
      const a = (i / cm.seeds.length) * 2 * Math.PI - Math.PI / 2;
      return { name: n.name, x: W / 2 + 290 * Math.cos(a), y: HGT / 2 + 160 * Math.sin(a), seed: true };
    }), links: [], result: null };
  }
  const save = () => store.set(key, st);
  let sel = null, drag = null;
  const svg = s("svg", { class: "cmap", viewBox: `0 0 ${W} ${HGT}` });
  const wrap = h("div", { class: "cmap-wrap" });
  const status = h("div", { class: "small muted" });
  const res = h("div", {});
  const refBox = h("div", {});
  const input = h("input", { type: "text", placeholder: "Add a concept…" });
  const addNode = () => {
    const name = input.value.trim();
    if (!name) return;
    if (st.nodes.some((n) => n.name.toLowerCase() === name.toLowerCase())) return toast("Already on the map");
    st.nodes.push({ name, x: 80 + Math.random() * (W - 160), y: 60 + Math.random() * (HGT - 120) });
    input.value = ""; save(); draw();
  };
  input.onkeydown = (e) => { if (e.key === "Enter") addNode(); };
  const pt = (e) => { const p = svg.createSVGPoint(); p.x = e.clientX; p.y = e.clientY; return p.matrixTransform(svg.getScreenCTM().inverse()); };
  function draw() {
    svg.replaceChildren();
    st.links.forEach((l, i) => {
      const a = st.nodes.find((n) => n.name === l.a), b = st.nodes.find((n) => n.name === l.b);
      if (!a || !b) return;
      const ls = st.result && st.result.links.find((x) => x.a === l.a && x.b === l.b);
      const g = s("g", { class: "edge" + (ls ? (ls.in_reference ? " ok" : " extra") : ""), style: "cursor:pointer" },
        s("line", { x1: a.x, y1: a.y, x2: b.x, y2: b.y }),
        s("text", { x: (a.x + b.x) / 2, y: (a.y + b.y) / 2 - 4, "text-anchor": "middle" }, l.label || ""));
      g.addEventListener("click", () => { st.links.splice(i, 1); st.result = null; save(); draw(); toast("Link removed"); });
      svg.append(g);
    });
    st.nodes.forEach((n) => {
      const w = nodeW(n.name);
      const ok = st.result && st.result.nodes[n.name] && st.result.nodes[n.name].concept_id;
      const g = s("g", { class: "node" + (n.seed ? " seed" : "") + (sel === n ? " sel" : "") + (ok ? " ok" : ""), transform: `translate(${n.x},${n.y})` },
        s("rect", { x: -w / 2, y: -17, width: w, height: 34, rx: 9 }),
        s("text", { "text-anchor": "middle", y: 5 }, n.name.length > 28 ? n.name.slice(0, 27) + "…" : n.name));
      g.addEventListener("pointerdown", (e) => {
        e.preventDefault();
        const p = pt(e); drag = { n, dx: n.x - p.x, dy: n.y - p.y, moved: false };
        svg.setPointerCapture(e.pointerId);
      });
      svg.append(g);
    });
    status.textContent = sel ? `Selected “${sel.name}”: click another concept to link them (Esc to cancel).`
      : `${st.nodes.length} concepts, ${st.links.length} links. Click one concept, then another, to link them. Drag to move. Click a link to remove it.`;
  }
  svg.addEventListener("pointermove", (e) => {
    if (!drag) return;
    const p = pt(e); drag.n.x = Math.max(60, Math.min(W - 60, p.x + drag.dx)); drag.n.y = Math.max(20, Math.min(HGT - 20, p.y + drag.dy));
    drag.moved = true; draw();
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
  document.addEventListener("keydown", (e) => { if (e.key === "Escape" && sel) { sel = null; draw(); } });
  function askLabel(a, b) {
    const box = h("div", { class: "card label-box", style: `left:20px; top:20px` });
    const li = h("input", { type: "text", placeholder: `${a.name} … ${b.name}` });
    const done = (keep) => {
      if (keep) { st.links.push({ a: a.name, b: b.name, label: li.value.trim() }); st.result = null; save(); draw(); }
      box.remove();
    };
    li.onkeydown = (e) => { if (e.key === "Enter") done(true); if (e.key === "Escape") done(false); };
    box.append(h("div", { class: "small", style: "margin-bottom:6px" }, h("b", {}, "Label the link"), " (e.g. “is part of”)"), li,
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
      save(); draw(); drawResult(); markDone(L.lecture_id, idx);
    } catch (e) { toast("The scoring server is not running (python3 serve.py)"); }
    check.disabled = false;
  };
  function drawResult() {
    const r = st.result;
    if (!r) return res.replaceChildren();
    res.replaceChildren(h("div", { class: "feedback" },
      h("div", { class: "row" }, h("span", { class: `tier ${r.tier.id}` }, TIER_ICON[r.tier.id] || "", " ", r.tier.label),
        h("span", { class: "small muted" }, `You found ${r.found} of the ${r.reference_edges_reachable} reference links between the concepts on your map.`)),
      r.missing.length ? h("div", { class: "small", style: "margin-top:10px" }, h("b", {}, "Links you could add: "),
        r.missing.slice(0, 6).map((m) => `${m.src} — ${m.label} — ${m.dst}`).join(" · ")) : null,
      r.links.some((l) => !l.in_reference) ? h("div", { class: "small faint", style: "margin-top:6px" },
        "Dashed links are not in the reference map. That does not make them wrong.") : null));
  }
  let refShown = false;
  const refBtn = h("button", { onclick: () => { refShown = !refShown; refBtn.textContent = refShown ? "Hide reference map" : "Show reference map"; refBox.replaceChildren(refShown ? referenceMap(cm) : ""); } }, "Show reference map");
  wrap.append(svg);
  draw(); drawResult();
  return h("div", {}, h("p", { class: "muted", style: "margin-top:0" }, cm.instructions),
    h("div", { class: "cmap-tools" }, input, h("button", { onclick: addNode }, "Add"), h("span", { class: "spacer" }),
      h("button", { class: "ghost", onclick: () => { if (confirm("Start the map over?")) { store.set(key, null); renderLecture(L.lecture_id, idx); } } }, "Reset"),
      refBtn, check),
    wrap, status, res, refBox);
}
function referenceMap(cm) {
  const nodes = cm.reference_nodes.map((n, i) => ({ ...n, x: W / 2 + 300 * Math.cos(i * 2.4), y: HGT / 2 + 170 * Math.sin(i * 2.4), vx: 0, vy: 0 }));
  const by = Object.fromEntries(nodes.map((n) => [n.concept_id, n]));
  const edges = cm.reference_edges.filter((e) => by[e.src] && by[e.dst]);
  for (let it = 0; it < 300; it++) {  // small force layout
    for (const a of nodes) for (const b of nodes) {
      if (a === b) continue;
      const dx = a.x - b.x, dy = a.y - b.y, d2 = dx * dx + dy * dy + 0.01, f = 9000 / d2;
      a.vx += f * dx / Math.sqrt(d2); a.vy += f * dy / Math.sqrt(d2);
    }
    for (const e of edges) {
      const a = by[e.src], b = by[e.dst], dx = b.x - a.x, dy = b.y - a.y, d = Math.sqrt(dx * dx + dy * dy) + 0.01, f = (d - 170) * 0.02;
      a.vx += f * dx / d; a.vy += f * dy / d; b.vx -= f * dx / d; b.vy -= f * dy / d;
    }
    for (const n of nodes) {
      n.vx += (W / 2 - n.x) * 0.004; n.vy += (HGT / 2 - n.y) * 0.004;
      n.x = Math.max(90, Math.min(W - 90, n.x + Math.max(-20, Math.min(20, n.vx)))); n.y = Math.max(24, Math.min(HGT - 24, n.y + Math.max(-20, Math.min(20, n.vy))));
      n.vx *= 0.5; n.vy *= 0.5;
    }
  }
  const svg = s("svg", { class: "cmap", viewBox: `0 0 ${W} ${HGT}`, style: "margin-top:12px" });
  edges.forEach((e) => {
    const a = by[e.src], b = by[e.dst];
    svg.append(s("g", { class: "edge ok" }, s("line", { x1: a.x, y1: a.y, x2: b.x, y2: b.y }),
      s("text", { x: (a.x + b.x) / 2, y: (a.y + b.y) / 2 - 4, "text-anchor": "middle" }, e.label)));
  });
  nodes.forEach((n) => {
    const w = nodeW(n.name);
    svg.append(s("g", { class: "node" + (n.is_seed ? " seed" : ""), transform: `translate(${n.x},${n.y})` },
      s("rect", { x: -w / 2, y: -17, width: w, height: 34, rx: 9 }),
      s("text", { "text-anchor": "middle", y: 5 }, n.name.length > 28 ? n.name.slice(0, 27) + "…" : n.name)));
  });
  return h("div", {}, h("div", { class: "small muted", style: "margin-top:14px" }, "Reference map (blue outline = seed concept)"), svg);
}

boot();
