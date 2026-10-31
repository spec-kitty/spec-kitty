# Tracer: approach

One entry per finding: `YYYY-MM-DD · actor · <text>`.

---

2026-10-31 · pi/deepseek-v4.1-flash-1017 · Surveyed src/specify_cli/decisions/: store.py::_render_artifact is the sole producer of DM markdown including the '## Change log' bullet; emit.py writes JSONL events, service.py/fork.py/index_fold.py/verify.py only read or mutate the ledger. The other em dashes in the package are docstrings and error messages, not artifact content, so the fix has one home.
