// window.renderMath(el): renders the formulas inside el with the vendored KaTeX (vendor/katex/, offline).
// Delimiters: $$...$$, \[...\], \(...\) as in KaTeX's auto-render, and $...$ for inline math with a guard so that
// money and plain text survive: the opening $ must be followed by a non-space, non-digit character and the closing
// $ must follow a non-space and not be followed by a digit ("costs $5 and $10" stays text; "$\theta$" and "$x+1$"
// render). Text in <code>, <pre>, <script>, <style>, <textarea> is never touched. throwOnError is false (a broken
// formula shows as red source). A no-op when KaTeX or auto-render did not load. Safe to call twice on one element.
(function () {
  const SKIP = new Set(["CODE", "PRE", "SCRIPT", "STYLE", "TEXTAREA", "NOSCRIPT"]);
  const INLINE = /(^|[^\\$])\$(?![\s\d$])((?:[^$\\\n]|\\.)+?)(?<![\s\\])\$(?!\d)/g;
  const DELIMS = [
    { left: "$$", right: "$$", display: true },
    { left: "\\[", right: "\\]", display: true },
    { left: "\\(", right: "\\)", display: false },
  ];
  // single-$ spans become \(...\) so auto-render, which has no guard of its own, never sees a bare $
  function guard(el) {
    const w = document.createTreeWalker(el, NodeFilter.SHOW_TEXT, {
      acceptNode(n) {
        if (!n.nodeValue.includes("$")) return NodeFilter.FILTER_REJECT;
        for (let p = n.parentNode; p && p !== el.parentNode; p = p.parentNode)
          if (p.nodeType === 1 && (SKIP.has(p.tagName) || (p.classList && p.classList.contains("katex")))) return NodeFilter.FILTER_REJECT;
        return NodeFilter.FILTER_ACCEPT;
      },
    });
    const nodes = [];
    while (w.nextNode()) nodes.push(w.currentNode);
    for (const n of nodes) {
      const v = n.nodeValue;
      // keep $$...$$ as it is; rewrite the single-$ spans around it
      const out = v.split(/(\$\$[\s\S]+?\$\$)/).map((part, i) =>
        i % 2 ? part : part.replace(INLINE, (_, pre, body) => pre + "\\(" + body + "\\)")).join("");
      if (out !== v) n.nodeValue = out;
    }
  }
  window.renderMath = function (el) {
    if (!el || typeof window.renderMathInElement !== "function" || !window.katex) return;
    try {
      guard(el);
      window.renderMathInElement(el, {
        delimiters: DELIMS, throwOnError: false, ignoredTags: [...SKIP].map((t) => t.toLowerCase()),
      });
    } catch (e) { /* the text stays as it was */ }
  };
})();
