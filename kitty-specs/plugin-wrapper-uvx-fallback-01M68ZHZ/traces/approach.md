# Tracer: approach

One entry per finding: `YYYY-MM-DD · actor · <text>`.

---

2026-10-31 · pi/claude · Grounding: reproduced the defect on main 6f73b2a98e with the real uvx — 'uvx spec-kitty-cli==4.0.0rc8 --version' resolves the distribution, finds only the 'spec-kitty' executable, and exits 1 with 'Use uvx --from spec-kitty-cli spec-kitty instead'. No prior fix on main (git log -S'uvx --from' touches unrelated files; claude_wrapper.py history ends at #623/#497 probe fixes).
