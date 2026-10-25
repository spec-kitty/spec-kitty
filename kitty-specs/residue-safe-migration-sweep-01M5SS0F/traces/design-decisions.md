# Design decisions: residue-safe-migration-sweep-01M5SS0F

- **[2026-10-25][specify] Git-aware residue rule** (operator). In git-aware mode, residue means `is_mission_dir` rejects the folder and no `spec.md`/`meta.json` is on disk. Committed tasks-only folders are an accepted cost.
- **[2026-10-25][specify] Git-aware mode only when kitty-specs/ is tracked** (operator). An ignored `kitty-specs/` and a nested untracked project keep the file-presence rule.
- **[2026-10-25][specify] Supersede rather than edit** (operator; DIRECTIVE_044). The four successors sit in their predecessors' slots, gated off where the predecessor is settled in the selection view.
- **[2026-10-25][specify] Doctor finding: all three signals, report only** (operator, #6668).
- **[2026-10-25][plan] Notice collapse in the runner** (DM 01M5SVE8QC28KRAZM25PR2N4PT). One shared notice text; the runner shows each residue folder once per run.
- **[2026-10-25][plan] No contracts/.** The Mission adds no interface; `meta.json` records `contracts: none` with a rationale.
