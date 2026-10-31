# Tracer: approach

One entry per finding: `YYYY-MM-DD · actor · <text>`.

---

2026-10-31 · s7-agent · Grounded on main dfe9efb0e8: built a project at 4.0.0rc8 with .kittify/overrides/missions/software-dev/templates/{spec,plan}-template.md (spec byte-identical to the shipped file, plan deliberately outdated). Real 'spec-kitty upgrade --project --yes' kept both, printed '2.0.7_fix_stale_overrides not needed' and '4.0.0rc8_retire_stale_mission_template_forks not needed', and resolve_template answered OVERRIDE for both. Residual reproduced, so the issue's third acceptance item is confirmed.

2026-10-31 · s7-agent · Reproduction evidence on a 4.0.0rc8 project (ledger 124 records; 2.0.6_consistency_sweep, 2.0.7_fix_stale_overrides and 4.0.0rc8_retire_stale_mission_template_forks all recorded 'success', so none is ever revisited): spec-template.md override sha256 004273f2... == shipped packs/built-in copy (identical); plan-template.md 56733d8f... != shipped 43516885... (differs). After the new step: overrides/ holds only plan-template.md, ledger records 4.0.0rc8_repair_historical_sweep_overrides 'success' and 'migrate ledger' reads 'already in place', spec-template.md resolves GLOBAL_MISSION (tier 2) instead of OVERRIDE (tier 1), plan-template.md stays OVERRIDE, and a second upgrade changes nothing.
