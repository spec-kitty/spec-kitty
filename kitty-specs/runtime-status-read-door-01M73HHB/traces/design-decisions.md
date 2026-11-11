# Design decisions: runtime-status-read-door-01M73HHB

Append-only. Each entry: date, phase, decision, rationale, source.

- [2026-11-10][plan] Read the door once per decision into a frozen BoardStatus value; dual-typed `Path | surface` parameters rejected (Decision Moment `01M73HSF99TDJK8ESTDF1H7NAG`; research R-1).
- [2026-11-10][specify] DM-1: owned coordination query and progress read the committed branch; dispatch refusal stays (`01M73HKG7WSR4VDRFXG9JWTGM8`).
- [2026-11-11][plan] DM-2 corrected: advancing `next` already materializes the coordination worktree in bootstrap, so there is no `--auto-remediate` flag; report the materialization instead (`01M73J4X57HKNF5RK7WVN8QHC5`; research R-4).
- [2026-11-10][specify] DM-3: pass the placement seam explicitly to artifact presence (`01M73HKTCYP1WB4VEQF39VEC74`).
- [2026-11-10][specify] DM-4: #7507 filed and fixed in this Mission (`01M73HKZF40ECKK6SK69NRWSS3`).
- [2026-11-11][analyze] FR-006 is a ratchet of today's owned advancing outcome, characterised before change (analysis finding I1).
