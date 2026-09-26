# Post-plan squad — debugger-debbie (WP03 brownfield: full override resync)

Verdict: PROCEED-WITH-CARE (HOLD on expected-artifacts.yaml → resolved by operator: delete).
Baseline before resync: 524 passed, 1 skipped, 0 failed over tests/dossier/test_manifest.py,
tests/prompts/test_tasks_prompt_ownership_metadata.py, tests/doctrine/test_shipped_profiles.py,
tests/runtime/test_project_resolver.py, tests/specify_cli/missions/test_mission_template_consistency.py,
tests/specify_cli/test_org_mission_type_resolution.py, tests/doctrine/test_resolver.py,
tests/runtime/test_template_source_consolidation.py, tests/doctrine/test_template_discovery.py.

| # | Sev | Finding | Disposition |
|---|-----|---------|-------------|
| 1 | CRITICAL | `expected-artifacts.yaml` override is intentionally DEPRECATED/INERT (Decision 4, expected-artifacts-manifest-repair) and pinned by `tests/dossier/test_manifest.py::TestOverrideMirrorDeprecation`; resync breaks it | changed — operator: DELETE the software-dev override and drop its entry from the pinning test (DM-01M3EXVSGFRQ8YKVFCCBWVSVZD); research/documentation mirrors untouched |
| 2 | HIGH | `actions/{implement,review}/guidelines.md` overrides are NEWER than built-in (disambiguated "repository root checkout" / "mission's target branch" vs built-in "main repository" / "merged to main") | accepted — WP03 first ports those lines into `packs/built-in/.../guidelines.md`, then resyncs |
| 3 | MEDIUM | `mission-runtime.yaml` override is LIVE (runtime reads project override tier); resync moves this repo from v2.1.0 `tasks_*` DAG to v2.2.0 single `tasks` step; legacy ids normalised | accepted — intended alignment; WP03 runs tests/runtime/test_bridge_*, tests/next/, runtime bridge unit tests; no resync while another mission is mid-tasks |
| 4 | MEDIUM | Built-in prompts carry `spdd:reasons-block` markers that `runtime/next/prompt_builder.py` inserts unprocessed | deferred_with_rationale — pre-existing for every consumer; follow-up issue at closeout |
| 5 | LOW | Mapping `command-templates/<cmd>.md` ← `mission-steps/software-dev/<cmd>/prompt.md` verified against resolver | accepted |
| 6 | LOW | Orphans `command-templates/{README,constitution,dashboard}.md` | accepted — untouched; follow-up issue |
