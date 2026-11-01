# Tracer: design-decisions

One entry per finding: `YYYY-MM-DD · actor · <text>`.

---

2026-11-01 · claude · D1/D2: the fold goes into _resolve_from_index (the one ladder shared by FsMissionResolver and FakeMissionResolver), not a new function and not the CLI wrapper — so implement and every other resolve_mission caller inherit one answer.

2026-11-01 · claude · D3: strip the trailing -<mid8> only when it equals that Mission's own mid8 (ResolvedMission.mid8), mirroring branch_naming._human_slug_for_mid8_branch. A coincidental eight-character tail is not an identity marker. Sharing the symbol would invert the import layer, so the rule is shared, not the function.
