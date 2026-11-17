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
  "--no-first-run", "--no-default-browser-check", "--window-size=1440,900", "--disable-extensions", "--autoplay-policy=no-user-gesture-required", "about:blank"], { stdio: "ignore" });
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


let media = { n: 0, bytes: 0, urls: new Map() };
listeners.push((d) => {
  if (d.method === "Network.requestWillBeSent" && d.params.request.url.includes("/media/")) { media.n++; media.urls.set(d.params.requestId, d.params.request.headers.Range || d.params.request.headers.range || "-"); }
  if (d.method === "Network.loadingFinished" && media.urls.has(d.params.requestId)) media.bytes += d.params.encodedDataLength;
  if (d.method === "Network.loadingFailed" && media.urls.has(d.params.requestId)) media.bytes += 0;
});
const out = [];
const rec = (name, v) => { out.push([name, v]); console.log(`${LABEL}\t${name}\t${typeof v === "number" ? Math.round(v) + " ms" : JSON.stringify(v)}`); };
await send("Page.navigate", { url: BASE + "/#/lecture/5" });
const r1 = await ev(`(async () => {
  const t0 = performance.now();
  await __wait("video", 0, 30000);
  const v = document.querySelector("video");
  window.__v = v; window.__stall = { n: 0, ms: 0, at: 0 };
  v.addEventListener("waiting", () => { __stall.n++; __stall.at = performance.now(); });
  v.addEventListener("playing", () => { if (__stall.at) { __stall.ms += performance.now() - __stall.at; __stall.at = 0; } });
  if (v.readyState < 1) await new Promise((r) => v.addEventListener("loadedmetadata", r, { once: true }));
  return performance.now();
})()`);
rec("page start -> video metadata", r1);
const playMs = await ev(`(async () => { const v = __v; v.muted = true; const t0 = performance.now(); await v.play(); if (v.readyState < 3) await new Promise((r) => v.addEventListener("playing", r, { once: true })); return performance.now() - t0; })()`);
rec("play -> playing", playMs);
const apiWhile = async (name, key) => rec(name, await ev(`(async () => { const t0 = performance.now(); const r = await fetch("/api/view/${key}", { cache: "no-store" }); await r.json(); return performance.now() - t0; })()`));
await sleep(3000);
await apiWhile("page request (/api/view/30, 14 kB gz) 3 s into playback", 30);
await sleep(10000);
await apiWhile("page request (/api/view/31) 13 s into playback", 31);
await sleep(27000);
rec("40 s of continuous play from 0 (past 4 MB chunks)", await ev(`({ t: Math.round(__v.currentTime), stalls: __stall.n, stall_ms: Math.round(__stall.ms) })`));
async function seek(name, how) {
  const before = media.n, bytes0 = media.bytes;
  const r = await ev(`(async () => {
    const v = __v, t0 = performance.now(), el = v;
    ${how};
    await new Promise((r) => { const ok = () => { if (!v.seeking && v.readyState >= 3) r(); else setTimeout(ok, 10); }; setTimeout(ok, 0); });
    const ready = performance.now() - t0;
    const t1 = v.currentTime; await new Promise((r) => setTimeout(r, 1500));
    return { ready, t: [t1, v.currentTime], paused: v.paused, rs: v.readyState, buf: [...Array(v.buffered.length)].map((_, i) => [Math.round(v.buffered.start(i)), Math.round(v.buffered.end(i))]), advancing: v.currentTime > t1 + 0.5, sameElement: document.querySelector("video") === el, src: v.currentSrc.split("/").pop() };
  })()`);
  rec(name, r.ready);
  rec(name + " (details)", { t: r.t, paused: r.paused, rs: r.rs, buf: r.buf, advancing: r.advancing, sameElement: r.sameElement, newRequests: media.n - before });
}
await seek("seek +5 min (300 s)", `v.currentTime = 300`);
await sleep(3000);
await seek("seek a few s forward (308 s, buffered)", `v.currentTime = 308`);
await sleep(3000);
await seek("seek back (100 s)", `v.currentTime = 100`);
await sleep(3000);
await seek("segment click in the page (part 2)", `document.querySelectorAll(".seg")[1].click()`);
await sleep(3000);
await seek("citation-style link in the lecture (#/lecture/5/t/450)", `location.hash = "#/lecture/5/t/450"`);
await sleep(8000);
const st = await ev(`({ n: __stall.n, ms: Math.round(__stall.ms), t: __v.currentTime })`);
rec("stalls during the whole run", st);
rec("media requests / MB", { requests: media.n, MB: Math.round(media.bytes / 1048576 * 10) / 10 });
ws.close(); chrome.kill();
process.exit(0);
