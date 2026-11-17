
"use strict";
(function () {
  const $ = (s, r = document) => r.querySelector(s);
  const $$ = (s, r = document) => Array.from(r.querySelectorAll(s));
  const store = {
    get(k, d) { try { const v = localStorage.getItem(k); return v == null ? d : JSON.parse(v); } catch (e) { return d; } },
    set(k, v) { try { localStorage.setItem(k, JSON.stringify(v)); } catch (e) {} },
  };
  const esc = (s) => s.replace(/[&<>"]/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" }[c]));

  /* ---------------- theme */
  $("#theme").addEventListener("click", () => {
    const root = document.documentElement;
    const cur = root.getAttribute("data-theme") || (matchMedia("(prefers-color-scheme: dark)").matches ? "dark" : "light");
    const next = cur === "dark" ? "light" : "dark";
    root.setAttribute("data-theme", next);
    try { localStorage.setItem("v3docs-theme", next); } catch (e) {}
  });

  /* ---------------- table of contents (from h2 / h3 with ids) */
  const toc = $("#toc");
  let lastPart = null;
  const heads = $$(".doc h2[id], .doc h3[id], .doc .part-head[data-part]");
  for (const h of heads) {
    if (h.classList.contains("part-head")) {
      const p = document.createElement("div"); p.className = "part"; p.textContent = h.dataset.part; toc.appendChild(p); lastPart = p; continue;
    }
    const a = document.createElement("a");
    a.href = "#" + h.id; a.textContent = h.dataset.toc || h.textContent;
    if (h.tagName === "H3") a.className = "l3";
    a.dataset.for = h.id;
    toc.appendChild(a);
  }
  const links = new Map($$("#toc a").map((a) => [a.dataset.for, a]));
  let current = null;
  const spy = new IntersectionObserver((ents) => {
    for (const e of ents) if (e.isIntersecting) { current && current.classList.remove("on"); current = links.get(e.target.id); current && current.classList.add("on"); }
  }, { rootMargin: "0px 0px -75% 0px" });
  $$(".doc h2[id], .doc h3[id]").forEach((h) => spy.observe(h));
  const rail = $("#rail");
  $("#tocbtn").addEventListener("click", () => rail.classList.toggle("open"));
  toc.addEventListener("click", (e) => { if (e.target.tagName === "A") rail.classList.remove("open"); });

  /* ---------------- syntax highlighting (no library) */
  function paint(text, re, cls) {
    let out = "", last = 0, m;
    re.lastIndex = 0;
    while ((m = re.exec(text))) {
      if (m[0] === "") { re.lastIndex++; continue; }
      out += esc(text.slice(last, m.index));
      let c = null;
      for (const [g, k] of Object.entries(cls)) if (m.groups && m.groups[g] !== undefined) { c = typeof k === "function" ? k(m, text) : k; break; }
      out += c ? `<span class="${c}">${esc(m[0])}</span>` : esc(m[0]);
      last = m.index + m[0].length;
    }
    return out + esc(text.slice(last));
  }
  const LANG = {
    json: [/(?<str>"(?:\\.|[^"\\\n])*")|(?<kw>\b(?:true|false|null)\b)|(?<num>-?\b\d+(?:\.\d+)?(?:[eE][+-]?\d+)?\b)|(?<p>[{}\[\],:])/g,
      { str: (m, t) => (/^\s*:/.test(t.slice(m.index + m[0].length)) ? "tk-key" : "tk-str"), kw: "tk-kw", num: "tk-num", p: "tk-p" }],
    bash: [/(?<com>(?:^|(?<=\s))#.*$)|(?<str>"(?:\\.|[^"\\\n])*"|'[^'\n]*')|(?<var>\$\{?[A-Za-z_][A-Za-z0-9_]*\}?)|(?<flag>(?<=\s)--?[A-Za-z][\w-]*)|(?<cmd>^\s*(?:python3?|bash|ssh|rsync|git|tmux|curl|cd|export|pip|ffmpeg|node|ls|mkdir|time|vllm|QA_CONFIG=\S+|QA_OUTPUT=\S+)\b)/gm,
      { com: "tk-com", str: "tk-str", var: "tk-var", flag: "tk-flag", cmd: "tk-cmd" }],
    python: [/(?<com>#.*$)|(?<str>"""[\s\S]*?"""|"(?:\\.|[^"\\\n])*"|'(?:\\.|[^'\\\n])*')|(?<kw>\b(?:from|import|def|return|for|in|if|else|elif|with|as|None|True|False|print|lambda|class|yield)\b)|(?<num>\b\d+(?:\.\d+)?\b)/gm,
      { com: "tk-com", str: "tk-str", kw: "tk-kw", num: "tk-num" }],
    prompt: [/(?<head>^(?:### .*|[A-Z][A-Z0-9 ,'’()\/:-]{2,}[A-Z):])$)|(?<ph>\{[a-z_]+\})|(?<li>^\s*(?:\d+\.|-|[a-z]\.)(?=\s))|(?<str>"[^"\n]{1,160}")/gm,
      { head: "tk-head", ph: "tk-ph", li: "tk-li", str: "tk-str" }],
    text: [/(?<ph>\{[a-z_]+\})|(?<id>\b\d+[a-z]?\/(?:S\d+(?:\/[FCR]\d+)?|\d+)\b|\bC\d{4}\b|\bR\d{4}\b)/g, { ph: "tk-ph", id: "tk-key" }],
  };
  for (const pre of $$("pre[data-lang]")) {
    const L = LANG[pre.dataset.lang]; if (!L) continue;
    pre.innerHTML = paint(pre.textContent, L[0], L[1]);
  }

  /* ---------------- reader highlights */
  const KEY = "v3docs-highlights";
  const BLOCKS = "p, li, td, th, h2, h3, h4, figcaption, pre, dt, dd, blockquote, summary";
  const doc = $("#doc");
  $$(BLOCKS, doc).forEach((el, i) => { el.dataset.hk = i; });
  let saved = store.get(KEY, []);
  const btn = $("#hlbtn");

  function textNodes(el) {
    const w = document.createTreeWalker(el, NodeFilter.SHOW_TEXT); const out = []; let n;
    while ((n = w.nextNode())) out.push(n);
    return out;
  }
  function offsetOf(block, node, off) {
    if (node.nodeType !== 3) {                  // an element: offset counts its children
      let total = 0; const kids = node.childNodes;
      for (let i = 0; i < off && i < kids.length; i++) total += kids[i].textContent.length;
      node = node; off = total;
      let t = 0; for (const n of textNodes(block)) { if (node.contains(n)) break; t += n.data.length; }
      return t + off;
    }
    let t = 0; for (const n of textNodes(block)) { if (n === node) return t + off; t += n.data.length; }
    return -1;
  }
  function wrap(block, s, e, id) {
    let t = 0; const parts = [];
    for (const n of textNodes(block)) {
      const a = t, b = t + n.data.length; t = b;
      if (b <= s || a >= e) continue;
      parts.push([n, Math.max(s, a) - a, Math.min(e, b) - a]);
    }
    for (const [n, x, y] of parts) {
      let node = n;
      if (y < node.data.length) node.splitText(y);
      if (x > 0) node = node.splitText(x);
      const m = document.createElement("mark"); m.className = "rh"; m.dataset.hid = id;
      node.parentNode.insertBefore(m, node); m.appendChild(node);
    }
    return parts.length > 0;
  }
  function unwrap(id) {
    for (const m of $$(`mark.rh[data-hid="${id}"]`)) { const p = m.parentNode; while (m.firstChild) p.insertBefore(m.firstChild, m); p.removeChild(m); p.normalize(); }
  }
  function where(block) {
    let el = block, h = null;
    while (el && el !== doc) {
      let s = el.previousElementSibling;
      while (s) { if (/^H[23]$/.test(s.tagName)) { h = s; break; } s = s.previousElementSibling; }
      if (h) break; el = el.parentElement;
    }
    return h ? (h.dataset.toc || h.textContent).trim() : "";
  }
  function apply(h) {
    const block = doc.querySelector(`[data-hk="${h.k}"]`); if (!block) return false;
    const txt = block.textContent;
    let s = h.s, e = h.e;
    if (txt.slice(s, e) !== h.t) { const i = txt.indexOf(h.t); if (i < 0) return false; s = i; e = i + h.t.length; h.s = s; h.e = e; }
    return wrap(block, s, e, h.id);
  }
  function render() {
    const list = $("#hllist"); list.innerHTML = "";
    const live = saved.filter((h) => doc.querySelector(`mark.rh[data-hid="${h.id}"]`));
    live.sort((a, b) => a.k - b.k || a.s - b.s);
    $("#hlcount").textContent = live.length ? `(${live.length})` : "";
    if (!live.length) { list.innerHTML = '<li class="muted" style="list-style:none;margin-left:-1.2em">No highlights yet.</li>'; return; }
    for (const h of live) {
      const li = document.createElement("li");
      li.innerHTML = `<a href="#" data-go="${h.id}"><q>${esc(h.t.length > 180 ? h.t.slice(0, 177) + "…" : h.t)}</q><span class="where">${esc(h.w || "")}</span></a><button type="button" data-del="${h.id}">Remove</button>`;
      list.appendChild(li);
    }
  }
  saved = saved.filter(apply); render();

  function selectionInfo() {
    const sel = getSelection(); if (!sel || sel.isCollapsed || !sel.rangeCount) return null;
    const r = sel.getRangeAt(0);
    const startEl = r.startContainer.nodeType === 3 ? r.startContainer.parentElement : r.startContainer;
    if (!doc.contains(startEl)) return null;
    const block = startEl.closest("[data-hk]"); if (!block || !doc.contains(block)) return null;
    const s = offsetOf(block, r.startContainer, r.startOffset);
    let e = block.contains(r.endContainer) ? offsetOf(block, r.endContainer, r.endOffset) : block.textContent.length;
    if (s < 0 || e <= s) return null;
    const t = block.textContent.slice(s, e); if (!t.trim()) return null;
    return { block, s, e, t, rect: r.getBoundingClientRect() };
  }
  function showBtn() {
    const info = selectionInfo();
    if (!info) { btn.style.display = "none"; return; }
    btn.style.display = "block";
    const x = Math.min(window.scrollX + info.rect.left + info.rect.width / 2 - 45, window.scrollX + document.documentElement.clientWidth - 110);
    btn.style.left = Math.max(window.scrollX + 8, x) + "px";
    btn.style.top = (window.scrollY + info.rect.top - 44 < window.scrollY + 4 ? window.scrollY + info.rect.bottom + 8 : window.scrollY + info.rect.top - 44) + "px";
  }
  document.addEventListener("mouseup", () => setTimeout(showBtn, 0));
  document.addEventListener("keyup", (e) => { if (e.shiftKey) showBtn(); });
  document.addEventListener("selectionchange", () => { if (matchMedia("(pointer: coarse)").matches) setTimeout(showBtn, 50); });
  btn.addEventListener("mousedown", (e) => e.preventDefault());
  btn.addEventListener("click", () => {
    const info = selectionInfo(); if (!info) return;
    const h = { id: Date.now().toString(36) + Math.random().toString(36).slice(2, 6), k: +info.block.dataset.hk, s: info.s, e: info.e, t: info.t, w: where(info.block) };
    getSelection().removeAllRanges(); btn.style.display = "none";
    if (wrap(info.block, h.s, h.e, h.id)) { saved.push(h); store.set(KEY, saved); render(); }
  });
  doc.addEventListener("click", (e) => {
    const m = e.target.closest("mark.rh"); if (!m || !getSelection().isCollapsed) return;
    const id = m.dataset.hid;
    if (confirm("Remove this highlight?")) { unwrap(id); saved = saved.filter((h) => h.id !== id); store.set(KEY, saved); render(); }
  });
  const panel = $("#hlpanel");
  $("#hlopen").addEventListener("click", () => panel.classList.toggle("open"));
  $("#hlclose").addEventListener("click", () => panel.classList.remove("open"));
  $("#hlclear").addEventListener("click", () => {
    if (!saved.length || !confirm("Remove every highlight on this page?")) return;
    for (const h of saved) unwrap(h.id); saved = []; store.set(KEY, saved); render();
  });
  $("#hllist").addEventListener("click", (e) => {
    const go = e.target.closest("[data-go]"), del = e.target.closest("[data-del]");
    if (go) {
      e.preventDefault();
      const m = doc.querySelector(`mark.rh[data-hid="${go.dataset.go}"]`); if (!m) return;
      let d = m.closest("details"); while (d) { d.open = true; d = d.parentElement.closest("details"); }
      m.scrollIntoView({ block: "center" }); m.classList.add("flash"); setTimeout(() => m.classList.remove("flash"), 1400);
    }
    if (del) { unwrap(del.dataset.del); saved = saved.filter((h) => h.id !== del.dataset.del); store.set(KEY, saved); render(); }
  });
})();
