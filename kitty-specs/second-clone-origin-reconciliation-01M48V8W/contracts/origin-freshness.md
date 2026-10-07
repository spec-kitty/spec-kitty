# Contract: `specify_cli.git.origin_freshness` and `specify_cli.git.origin_gate` (as shipped)

`origin_freshness` (verdicts and policy; data-only):
- `ORIGIN_CHECK_ENV = "SPEC_KITTY_ORIGIN_CHECK"`; `resolve_origin_check_mode(flag: str | None) -> OriginCheckSetting(mode, source, warning)`, `source` in `default | flag | environment | read-only`; `READ_ONLY_ORIGIN_CHECK` for `accept --no-commit / --diagnose`.
- `check_mission_branches(repo_root, mission_slug, *, lane_branches, owned=None) -> MissionFreshness(evidence, lanes)` — ONE `ls-remote` + ONE `fetch` per resolved remote for the evidence branch and the lanes together; evidence branch = `placement_seam(...).write_target(STATUS_STATE).ref`; evidence `behind` scoped to every `mission_dir_aliases` alias + `/status.events.jsonl` (ADR 2026-10-05-1).
- `approved_lane_branches(repo_root, mission_slug, lanes_manifest, *, completed_wps=frozenset(), owned=None) -> list[str]` — code lanes not fully canceled; over-selects when status is unreadable.
- `enforce_merge_gate(*, evidence, lanes, setting, merge_record_exists, evidence_checkout) -> list[str]` — returns warnings (warn mode) or raises `OriginFreshnessRefused(.error_code, .error_codes, .verdicts)`.
- `plan_review_lane(repo_root, lane_branch) -> ReviewLaneAction(kind, verdict, remote_sha, remote_ref, code, message)`.
- `FreshnessVerdict(branch, remote, state, behind, ahead, scope, detail, remote_sha)`; states `up_to_date | behind | ahead | diverged | local_missing | remote_missing | unreachable | no_remote`.
- Refusal text: first line `<CODE>: <branch> is <state> (<n> behind / <m> ahead of <remote>/<branch>)`, then remedy lines (`git -C <checkout> pull <remote> <branch>` when a checkout holds the branch, else `git fetch <remote> <branch>:<branch>`; `consolidate --abort` first when a merge record exists), then `Opt out (not recommended): --origin-check warn, or SPEC_KITTY_ORIGIN_CHECK=warn.`

`origin_gate` (the single shared gate authority):
- `run_origin_gate(repo_root, slug, *, setting, lane_branches, owned, merge_record_exists)` — combined contact, coordination `local_missing` pass-through via `routes_through_coordination(resolve_topology(...))`, `enforce_merge_gate`; used by `accept`, `orchestrator-api accept-mission / consolidate-mission` and (through `consolidation.origin_gate`) `consolidate`.
