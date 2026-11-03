# Tracer: design-decisions

One entry per finding: `YYYY-MM-DD · actor · <text>`.

---

2026-11-03 · pi/deepseek-v4.1 · Chose ASCII-by-construction in the template constant over sanitising at the write boundary, on the #6579 precedent: a blanket transliteration would silently rewrite authored prose. The pin therefore asserts over the rendered CORE text only and a companion test proves authored non-ASCII survives the create path verbatim (NFR-001, FR-004).
