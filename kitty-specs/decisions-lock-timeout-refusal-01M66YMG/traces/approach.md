# Tracer: approach

One entry per finding: `YYYY-MM-DD · actor · <text>`.

---

2026-10-30 · python-pedro · The fix is four call-site swaps onto decisions/service.py::_decisions_lock plus one renderer per command; no local try/except LockAcquireTimeout copies (DIRECTIVE_044).
