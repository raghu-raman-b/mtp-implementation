// Headless Chrome screenshots of every viewer page, developer mode off and on.
// node shots.mjs http://127.0.0.1:PORT OUTDIR [prefix]
import { spawn } from "node:child_process";
import { mkdtempSync, writeFileSync } from "node:fs";
import { tmpdir } from "node:os";
import { join } from "node:path";

const BASE = process.argv[2], OUT = process.argv[3], PFX = process.argv[4] || "";
const PORT = 9300 + Math.floor(Math.random() * 500);
const dir = mkdtempSync(join(process.env.SP || tmpdir(), "chr-"));
const chrome = spawn("google-chrome", ["--headless=new", `--remote-debugging-port=${PORT}`, `--user-data-dir=${dir}`,
  "--no-first-run", "--no-default-browser-check", "--window-size=1280,900", "--disable-extensions", "about:blank"], { stdio: "ignore" });
const sleep = (ms) => new Promise((r) => setTimeout(r, ms));
let ver;
for (let i = 0; i < 50; i++) { try { ver = await (await fetch(`http://127.0.0.1:${PORT}/json/list`)).json(); if (ver.length) break; } catch (e) { /* not up */ } await sleep(200); }
const ws = new WebSocket(ver.find((t) => t.type === "page").webSocketDebuggerUrl);
await new Promise((r) => (ws.onopen = r));
let id = 0; const pend = new Map();
ws.onmessage = (m) => { const d = JSON.parse(m.data); if (d.id && pend.has(d.id)) { const p = pend.get(d.id); pend.delete(d.id); d.error ? p.rej(new Error(JSON.stringify(d.error))) : p.res(d.result); } };
const send = (method, params = {}) => new Promise((res, rej) => { const i = ++id; pend.set(i, { res, rej }); ws.send(JSON.stringify({ id: i, method, params })); });
const ev = async (expr) => { const r = await send("Runtime.evaluate", { expression: expr, awaitPromise: true, returnByValue: true }); return r.result && r.result.value; };
await send("Page.enable"); await send("Runtime.enable"); await send("Network.enable");
await send("Network.setBlockedURLs", { urls: ["*youtube.com*", "*ytimg.com*", "*googlevideo.com*", "*doubleclick*", "*google.com*", "*gstatic*"] });

const PAGES = [
  ["home", "#/"], ["lec5-overview", "#/lecture/5"], ["lec5-concepts", "#/lecture/5/concepts"], ["lec5-map", "#/lecture/5/map"],
  ["lec5-before", "#/lecture/5/before"], ["lec5-activities", "#/lecture/5/activities"],
  ["lec62-map", "#/lecture/62/map"], ["lec62-map-parts", "#/lecture/62/map", `[...document.querySelectorAll(".seg-ctl button")].find((b) => /^All/.test(b.textContent))?.click()`],
  ["coursemap", "#/map"], ["explorer", "#/map/concepts"], ["glossary", "#/glossary"], ["review", "#/review"],
  ["ask", "#/lecture/5", `document.querySelector("#ask-input").value = "What is an HMD?"; document.querySelector("#ask-form button").click()`],
  ["ask-done", "#/lecture/5", `new Promise((r) => setTimeout(r, 3000))`],
];
if (process.env.PAGES_JSON) PAGES.splice(0, PAGES.length, ...JSON.parse(process.env.PAGES_JSON));  // [[name, hash, js]]
const extra = (process.env.CONCEPT ? [["concept", "#/concept/" + process.env.CONCEPT]] : []);
for (const dev of [0, 1]) {
  await send("Page.navigate", { url: `${BASE}/?dev=${dev}#/` }); await sleep(1500);
  for (const [name, hash, act] of [...PAGES, ...extra]) {
    await ev(`location.hash = ${JSON.stringify(hash)}`); await sleep(1200);
    if (act) { await ev(act); await sleep(1500); }
    if (name.endsWith("activities")) { await ev(`(async () => { for (let y = 0; y < document.body.scrollHeight; y += 600) { scrollTo(0, y); await new Promise((r) => setTimeout(r, 60)); } scrollTo(0, 0); })()`); await sleep(800); }
    const top = act && act.includes("scrollIntoView") ? await ev("scrollY") : 0;
    const { data } = await send("Page.captureScreenshot", { format: "png", captureBeyondViewport: true, clip: { x: 0, y: top, width: 1280, height: Math.min(4000, (await ev("document.documentElement.scrollHeight")) - top), scale: 0.6 } });
    const f = join(OUT, `${PFX}${name}-dev${dev}.png`);
    writeFileSync(f, Buffer.from(data, "base64"));
    console.log(f);
  }
}
ws.close(); chrome.kill();
process.exit(0);
