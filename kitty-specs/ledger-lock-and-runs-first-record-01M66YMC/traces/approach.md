# Tracer: approach

One entry per finding: `YYYY-MM-DD · actor · <text>`.

---

2026-10-30 · maintainer-agent P19 (pi/deepseek-v4.1-flash-1017) · Grounded #6613 on main 512567e: ledger.append/append_many read-modify-write with no lock (matches the issue); base.py still reselects runs_first on structural_detect. ADR 2026-10-17-1 already names kernel.locks as the extension point, so the mission builds that, not a new mechanism.
