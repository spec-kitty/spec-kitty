# Tracer: approach

One entry per finding: `YYYY-MM-DD · actor · <text>`.

---

2026-11-01 · claude · Red-first through the pre-existing entry point: moved the launch-contract stand-in (tests/specify_cli/services/fake_service.py) to serve only /api/v1/*, observed the unchanged client fail with 'GET /handshake answered 404' (5 failed), then introduced the prefix constants and the client change.
