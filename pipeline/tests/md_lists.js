// Checks app.js's mdBlock (nested lists, list numbering, streaming caret) on a tiny fake DOM. Run: node tests/md_lists.js
const fs = require("fs"), path = require("path"), vm = require("vm");
const src = fs.readFileSync(path.join(__dirname, "..", "viewer", "app.js"), "utf8");
class Node_ {
  constructor(tag) { this.tag = tag; this.kids = []; this.attrs = {}; this.nodeType = 1; this.style = {}; }
  append(...k) { for (const x of k.flat(Infinity)) if (x != null && x !== false) this.kids.push(x); }
  setAttribute(k, v) { this.attrs[k] = String(v); }
  set className(v) { this.attrs.class = v; }
  addEventListener() {}
  html() { const a = Object.entries(this.attrs).map(([k, v]) => ` ${k}="${v}"`).join("");
    return `<${this.tag}${a}>${this.kids.map((k) => (k.html ? k.html() : k.text)).join("")}</${this.tag}>`; }
}
const doc = { createElement: (t) => new Node_(t), createTextNode: (t) => ({ nodeType: 3, text: String(t) }), createElementNS: (n, t) => new Node_(t) };
const pick = (from, to) => { const a = src.indexOf(from), b = src.indexOf(to, a); if (a < 0 || b < 0) throw new Error("app.js layout changed: " + from); return src.slice(a, b); };
const code = pick("function h(tag", "const SVG") + pick("const TIME_RE", "function citeChip") +
  "function citeChip(lec, time) { return h('a', {class: 'cite'}, 'L' + lec + ' ' + time); }\n" +
  "function coursePageChip() { return h('span', {class: 'cite'}, 'CP'); }\n" +
  pick("function citeGroup", "/* ----") + "\nthis.mdBlock = mdBlock;";
const ctx = { document: doc, icon: () => null, timeHref: () => "#" };
vm.createContext(ctx);
vm.runInContext(code.replace(/function citeChip\(lec, time\) \{\n[\s\S]*?\n\}\nfunction coursePageChip/, "function coursePageChip"), ctx);
const html = (t, caret) => ctx.mdBlock(t, caret).html();
let bad = 0;
const check = (ok, what) => { console.log(`  ${ok ? "ok  " : "FAIL"} ${what}`); if (!ok) bad++; };

const ans = `The pipeline:

1.  **Object representation** in the local coordinate system [x]
2.  **Modeling transformation** (or geometric transformation)
3.  **Lighting**, which takes place in the world frame
4.  **Viewing pipeline**, which includes several transformations:
    *   Viewing transformation (from world)
    *   Clipping (in the 3D view coordinate system)
    *   Hidden surface removal
5.  **Scan conversion**, which transforms`;
const out = html(ans);
const lis = out.match(/<li>/g) || [];
check((out.match(/<ol/g) || []).length === 1 && (out.match(/<ul/g) || []).length === 1, "one ol, one ul (the bullets are not a top-level list)");
check(/<li><b>Viewing pipeline<\/b>[^]*?<ul><li>Viewing transformation[^]*?Hidden surface removal<\/li><\/ul><\/li>/.test(out), "the ul is inside the 4th li");
check(lis.length === 8 && /<\/ul><\/li><li><b>Scan conversion/.test(out), "the 5th item continues the same ol");
const resumed = html("5. five\n6. six");
check(/<ol[^>]*start="5"[^>]*counter-reset: n 4|<ol[^>]*counter-reset: n 4[^>]*start="5"/.test(resumed), "a list starting at 5 carries start=5 and counter-reset n 4");
check(/counter-reset: n 0/.test(html("1. a\n2. b")), "a list starting at 1 resets to 0");
check(/<ul><li>a<ul><li>b<\/li><\/ul><\/li><li>c<\/li><\/ul>/.test(html("- a\n  - b\n- c")), "two-space nested bullets, then back to the outer list");
check(/<ol[^>]*><li>a<ul><li>b<\/li><\/ul><\/li><\/ol>/.test(html("1. a\n\t- b")), "a tab nests");
check(/<li>a<ol[^>]*><li>b<\/li><\/ol><\/li>/.test(html("- a\n  1. b")), "a nested numbered list under a bullet");
check((html("- a\n\nPara\n\n- b").match(/<ul/g) || []).length === 2, "a paragraph between lists keeps them apart");
const part = html("1. a\n   - b", true);
check(/<li>b<span class="caret"/.test(part), "streaming: the caret sits on the last (nested) item");
check(/<p>hello<span class="caret"/.test(html("hello", true)), "streaming: the caret follows a paragraph");
check(html("(see this) (lecture 56, 2:26)").includes("cite"), "a citation after a parenthesis is still a chip");
console.log(bad ? `FAIL: ${bad}` : "PASS");
process.exit(bad ? 1 : 0);
