# Approach: runtime-status-read-door-01M73HHB

Append-only notes on how the work is being done.

- Specify and plan were driven from an Op-time grounding squad (two opus lenses) and a Mission-intake squad (architecture + code-grounding); notes in `research/`.
- Decisions were taken as Decision Moments with the operator (DM-1 to DM-4, auto-remediate scope, engineering alignment, DM-2 correction).
- Before writing WPs, the operator's DM-2 premise was verified end to end through the real CLI (`research/repro/advancing_cells.py`). That check overturned the `--auto-remediate` flag before any code was written.
- WPs run as a sequential chain: tidy-first enablers (WP01, WP03) and the door fix (WP02) come before the moves (WP04-WP06). Each move lowers the gate allowlist in the same commit.
