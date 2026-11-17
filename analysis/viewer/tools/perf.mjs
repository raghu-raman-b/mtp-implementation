// Headless Chrome (CDP over Node's built-in WebSocket) timings for the viewer.
// node perf.mjs http://127.0.0.1:PORT [label] [cpuRate]
import { spawn } from "node:child_process";
import { mkdtempSync } from "node:fs";
import { tmpdir } from "node:os";
import { join } from "node:path";

const BASE = process.argv[2];
const LABEL = process.argv[3] || "run";
const RATE = Number(process.argv[4] || 1);
const NET = process.argv[5] || "";  // "tunnel": 20 Mbit/s down, 5 up, 60 ms RTT
const PORT = 9300 + Math.floor(Math.random() * 500);
const dir = mkdtempSync(join(process.env.SP || tmpdir(), "chr-"));
const chrome = spawn("google-chrome", ["--headless=new", `--remote-debugging-port=${PORT}`, `--user-data-dir=${dir}`,
  "--no-first-run", "--no-default-browser-check", "--window-size=1440,900", "--disable-extensions", "about:blank"], { stdio: "ignore" });
const sleep = (ms) => new Promise((r) => setTimeout(r, ms));
let ver;
for (let i = 0; i < 50; i++) { try { ver = await (await fetch(`http://127.0.0.1:${PORT}/json/list`)).json(); if (ver.length) break; } catch (e) { /* not up */ } await sleep(200); }
const page = ver.find((t) => t.type === "page");
const ws = new WebSocket(page.webSocketDebuggerUrl);
await new Promise((r) => (ws.onopen = r));
let id = 0; const pend = new Map(); const listeners = [];
ws.onmessage = (m) => { const d = JSON.parse(m.data); if (d.id && pend.has(d.id)) { const p = pend.get(d.id); pend.delete(d.id); d.error ? p.rej(new Error(JSON.stringify(d.error))) : p.res(d.result); } else listeners.forEach((f) => f(d)); };
const send = (method, params = {}) => new Promise((res, rej) => { const i = ++id; pend.set(i, { res, rej }); ws.send(JSON.stringify({ id: i, method, params })); });
const ev = async (expr) => { const r = await send("Runtime.evaluate", { expression: expr, awaitPromise: true, returnByValue: true }); if (r.exceptionDetails) throw new Error(JSON.stringify(r.exceptionDetails).slice(0, 400)); return r.result.value; };

let bytes = 0, reqs = 0;
listeners.push((d) => { if (d.method === "Network.loadingFinished") { bytes += d.params.encodedDataLength; reqs++; } });
await send("Page.enable"); await send("Runtime.enable"); await send("Network.enable");
if (!process.env.YT) await send("Network.setBlockedURLs", { urls: ["*youtube.com*", "*ytimg.com*", "*googlevideo.com*", "*doubleclick*", "*google.com*", "*gstatic*"] });
await send("Network.setCacheDisabled", { cacheDisabled: false });
if (NET === "tunnel") await send("Network.emulateNetworkConditions", { offline: false, latency: 60, downloadThroughput: 20e6 / 8, uploadThroughput: 5e6 / 8 });
if (RATE > 1) await send("Emulation.setCPUThrottlingRate", { rate: RATE });
await send("Page.addScriptToEvaluateOnNewDocument", { source: `
  window.__lt = [];
  try { new PerformanceObserver((l) => { for (const e of l.getEntries()) window.__lt.push([e.startTime, e.duration]); }).observe({ type: "longtask", buffered: true }); } catch (e) {}
  window.__wait = (sel, t0, timeout = 30000) => new Promise((res) => {
    const f = () => { const el = typeof sel === "function" ? sel() : document.querySelector(sel); if (el) return res(performance.now() - t0); if (performance.now() - t0 > timeout) return res(-1); requestAnimationFrame(f); };
    f();
  });
  window.__ltSince = (t0) => { const x = window.__lt.filter(([s]) => s >= t0 - 1); return { n: x.length, total: Math.round(x.reduce((a, [, d]) => a + d, 0)), max: Math.round(Math.max(0, ...x.map(([, d]) => d))) }; };
  window.__paint2 = () => new Promise((r) => requestAnimationFrame(() => requestAnimationFrame(r)));
` });

const rows = [];
const rec = (name, ms, extra = {}) => { rows.push({ name, ms: Math.round(ms), ...extra }); console.log(`${LABEL}\t${name}\t${Math.round(ms)} ms\t${JSON.stringify(extra)}`); };

// a step: run JS that triggers it at t0, wait for sel, settle two frames, report time + long tasks + bytes
async function step(name, trigger, sel) {
  bytes = 0; reqs = 0;
  // a CSS selector must match an element that did not exist before the trigger; a function must return truthy
  const fn = sel.startsWith("() =>");
  const mark = fn ? "" : `document.querySelectorAll(${JSON.stringify(sel)}).forEach((e) => e.setAttribute("data-old", "1"));`;
  const fresh = fn ? sel : JSON.stringify(sel.split(",").map((x) => x.trim() + ":not([data-old])").join(", "));
  const r = await ev(`(async () => { await __paint2(); ${mark} const t0 = performance.now(); ${trigger}; const ms = await __wait(${fresh}, t0); await __paint2(); const done = performance.now() - t0; return { ms, done, lt: __ltSince(t0) }; })()`);
  await sleep(150);
  rec(name, r.ms, { settled: Math.round(r.done), longtasks: r.lt, kB: Math.round(bytes / 1024), reqs });
  return r;
}

// cold home load (empty cache: a fresh profile)
async function load(name, url, sel) {
  await send("Page.navigate", { url: "about:blank" }); await sleep(300);
  bytes = 0; reqs = 0;
  await send("Page.navigate", { url });
  const r = await ev(`(async () => { const ms = await __wait(${JSON.stringify(sel)}, 0, 60000); await __paint2(); return { ms, done: performance.now(), lt: __ltSince(0), fcp: (performance.getEntriesByName("first-contentful-paint")[0] || {}).startTime }; })()`);
  await sleep(300);
  rec(name, r.ms, { settled: Math.round(r.done), fcp: Math.round(r.fcp || 0), longtasks: r.lt, kB: Math.round(bytes / 1024), reqs });
}

await load("home cold (first visit)", BASE + "/#/", ".lec-card");
await load("home again (warm HTTP cache)", BASE + "/#/", ".lec-card");
await load("lecture 5 direct load", BASE + "/#/lecture/5", ".watch .seg");
await step("lecture 5 -> home", `location.hash = "#/"`, ".lec-card");
await step("home -> lecture 5", `location.hash = "#/lecture/5"`, ".watch .seg");
await step("lecture 5 -> lecture 6 (switch)", `location.hash = "#/lecture/6"`, ".watch .seg");
await step("lecture 6 -> lecture 62", `location.hash = "#/lecture/62"`, ".watch .seg");
await step("lecture 62: map tab (key view)", `location.hash = "#/lecture/62/map"`, `() => { const e = document.querySelector("svg.cmap g.node"); return e && e.getBoundingClientRect().width > 0; }`);
await step("lecture 62: 'all, by part' view", `[...document.querySelectorAll(".seg-ctl button")].find((b) => /^All/.test(b.textContent)).click()`, "svg.cmap g.panel");
await step("lecture 62 parts: click a concept", `document.querySelector("svg.cmap g.node").dispatchEvent(new MouseEvent("click", { bubbles: true }))`, `() => [...document.querySelectorAll(".map-card:not([hidden])")].some((e) => e.getBoundingClientRect().width > 0)`);
await step("lecture 62 parts: back to key view", `[...document.querySelectorAll(".seg-ctl button")].find((b) => /^Key/.test(b.textContent)).click()`, `() => { const e = [...document.querySelectorAll("svg.cmap")].find((x) => x.getBoundingClientRect().width > 0); return e && !e.querySelector("g.panel") && e.querySelector("g.node"); }`);
await step("lecture 62: overview tab", `location.hash = "#/lecture/62/overview"`, `() => { const e = document.querySelector(".objs"); return e && e.getBoundingClientRect().width > 0; }`);
await step("lecture 62: map tab again", `location.hash = "#/lecture/62/map"`, `() => { const e = document.querySelector("svg.cmap g.node"); return e && e.getBoundingClientRect().width > 0; }`);
await step("lecture 62: seek within lecture", `location.hash = "#/lecture/62/t/900"`, `() => { const s = document.querySelectorAll(".seg"); return [...s].some((x, i) => i > 0 && x.classList.contains("on")); }`);
await step("lecture 2: activities tab", `location.hash = "#/lecture/2/activities"`, ".act");
await step("course concept map", `location.hash = "#/map"`, "svg.cmap g.node");
await step("course map: click a lecture", `document.querySelector("svg.cmap g.node").dispatchEvent(new MouseEvent("click", { bubbles: true }))`, `() => [...document.querySelectorAll(".map-card:not([hidden])")].some((e) => e.getBoundingClientRect().width > 0)`);
await step("concept explorer", `location.hash = "#/map/concepts"`, "svg.cmap g.node");
await step("glossary", `location.hash = "#/glossary"`, ".gl-item");
await step("glossary: type a search", `{ const i = document.querySelector(".gl-search"); i.value = "display"; i.dispatchEvent(new Event("input")); }`, `() => document.querySelectorAll(".gl-item").length < 300`);
await step("concept card", `location.hash = "#/concept/" + (document.querySelector(".gl-item a.nm").getAttribute("href").split("/").pop())`, ".defn, .card .muted");
await step("back to home", `location.hash = "#/"`, ".lec-card");
const heap = await ev(`performance.memory ? Math.round(performance.memory.usedJSHeapSize / 1048576) : null`);
rec("JS heap after the tour (MB)", heap || 0);
console.log("JSON " + JSON.stringify({ label: LABEL, rate: RATE, rows }));
ws.close(); chrome.kill();
process.exit(0);
