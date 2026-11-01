# Tracer: design-decisions

One entry per finding: `YYYY-MM-DD · actor · <text>`.

---

2026-11-01 · claude · The floor reader lives in scripts/service_platform.py: src/kernel would trip the no-dead-modules gate (its only caller is release tooling), and the companion package's wheel.py is copied into every wheel and the sdist, so a build-time-only module there would either ship or silently not ship. Unreadable floors are refusals, not fallbacks: the defect being fixed is an unchecked claim, and the fixtures became real ELF/Mach-O/PE headers rather than shell scripts to match.
