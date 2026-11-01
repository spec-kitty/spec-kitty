# Tracer: design-decisions

One entry per finding: `YYYY-MM-DD · actor · <text>`.

---

2026-11-01 · claude · The prefix lives in specify_cli.status.write_service_protocol (the CLI's typed view of contracts/mission-write) and is re-exported through the status facade, because tests/architectural/test_status_module_boundary.py forbids service modules importing status submodules directly. __all__ of write_service_protocol is untouched: its members are a priced allowlist that burns down at #6195.
