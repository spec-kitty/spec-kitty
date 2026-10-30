# Tracer: design-decisions

One entry per finding: `YYYY-MM-DD · actor · <text>`.

---

2026-10-30 · python-pedro · Kept the loop's name-pairing test loop-wide over collected values (append/add/extend args) because the existing 'paired-loop' fixture pins that semantics; added only the subscript keys as extra evidence, plus a key-only exemption for DictComp so {p.effective_root(r): p.name ...} still reds.
