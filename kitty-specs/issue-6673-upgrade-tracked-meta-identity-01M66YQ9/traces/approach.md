# Tracer: approach

One entry per finding: `YYYY-MM-DD · actor · <text>`.

---

2026-10-30 · python-pedro · Ground-truthed #6673 by running the real upgrade on a scratch repo: the 2.0.6 sweep writes a baseline meta.json, then 3.2.0a4 mints a fresh ULID (01REALMIS… -> 01M66YHMT4…). The fix reads the tracked meta from git (HEAD) and refuses when it cannot be read.
