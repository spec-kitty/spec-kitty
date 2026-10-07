---
work_package_id: WP03
title: 'origin_freshness: verdicts, policy, opt-out'
dependencies:
- WP01
requirement_refs:
- FR-006
- FR-007
- FR-009
- FR-010
- NFR-003
planning_base_branch: claude/happy-keller-r38xig
merge_target_branch: claude/happy-keller-r38xig
branch_strategy: Planning artifacts for this mission were generated on claude/happy-keller-r38xig. During /spec-kitty.implement this WP may branch from a dependency-specific base, but completed changes must merge back into claude/happy-keller-r38xig unless the human explicitly redirects the landing branch.
base_branch: kitty/mission-second-clone-origin-reconciliation-01M48V8W
base_commit: 823ac378c636a6483fbae6f99a4941508de9b8ba
created_at: '2026-10-06T16:12:41.308376+00:00'
subtasks:
- T013
- T014
- T015
- T016
- T017
- T018
phase: Phase 2 - Intent
history:
- at: '2026-10-06T15:30:00Z'
  actor: system
  action: Prompt generated via /spec-kitty.tasks
agent_profile: python-pedro
authoritative_surface: src/specify_cli/git/origin_freshness.py
create_intent:
- src/specify_cli/git/origin_freshness.py
- tests/specify_cli/git/test_origin_freshness.py
execution_mode: code_change
model: ''
owned_files:
- src/specify_cli/git/origin_freshness.py
- tests/specify_cli/git/test_origin_freshness.py
role: implementer
tags: []
task_type: implement
tracker_refs: []
---

# Work Package Prompt: WP03 – origin_freshness: verdicts, policy, opt-out

## ⚡ Do This First: Load Agent Profile

Use the `/ad-hoc-profile-load` skill to load the agent profile specified in the frontmatter, and behave according to its guidance before parsing the rest of this prompt.

- **Profile**: `python-pedro`
- **Role**: `implementer`
- **Agent/tool**: `claude`

---

## ⚠️ IMPORTANT: Review Feedback

Check `review_ref` in the event log; address every feedback item before handing back.

---

## Objectives & Success Criteria

Create `src/specify_cli/git/origin_freshness.py`, the ONE application module every evidence gate calls (consolidate, accept, orchestrator-api, review). It turns kernel ref facts into freshness verdicts, applies the per-gate policy, resolves the operator opt-out, and produces the refusal data + text. It is data-only toward rendering: it never imports `consolidation.entry_preflight` or prints rich markup itself beyond plain strings (callers render).

Done when the contract `contracts/origin-freshness.md` is implemented, the verdict matrix is pinned by real-git tests (committed red first), and FR-006/FR-007/FR-009/FR-010/FR-017 hold at this layer.

## Context & Constraints

- Read `spec.md` (Domain Language, FR-001..FR-010, FR-017, edge cases), `plan.md` (policy table, "Where each gate calls the check"), `data-model.md`, `contracts/origin-freshness.md`, `research.md` R-3/R-4/R-7, `traces/design-decisions.md` (operator rulings — settled).
- Uses ONLY `kernel.git.remote` for git (WP01): `resolve_remote`, `tracking_ref`, `remote_heads`, `fetch_branches`, `divergence`, `RemoteUnreachable`. No raw subprocess. (`lanes._git.ref_exists` / `branch_exists` may be reused for `local_missing`.)
- Status evidence branch: `mission_runtime.placement_seam(repo_root, slug, owned=owned).write_target(MissionArtifactKind.STATUS_STATE).ref` (side-effect free; do NOT call `write_dir` — it seeds). Path scope: `specify_cli.missions._read_path_resolver.mission_dir_aliases(repo_root, slug)` (ADR 2026-10-05-1) → `kitty-specs/<alias>/status.events.jsonl` for every alias.
- Env var: `SPEC_KITTY_ORIGIN_CHECK` ∈ {`enforce`, `warn`}; model the tiny resolver on `retrospective/mode.py` (allowed-values frozenset). No generic env framework.
- Interim arch reds: `test_no_dead_symbols` / `test_no_dead_modules` see `origin_freshness` without a `src/` importer until WP04-WP06 land — document in the Activity Log; expected.
- Size: this WP is larger than its estimate (verdict engine + policy + text + review plan + real-git matrix); keep helpers small and commit per subtask.
- C-006: never "sync" in identifiers, codes or text. Terms: "origin freshness check", "freshness verdict", "evidence gate".

## Branch Strategy

- **Strategy**: lanes; worktree allocated by `spec-kitty implement WP03`.
- **Planning base / merge target**: `claude/happy-keller-r38xig`.

## Subtasks

### T013 — Red-first verdict-matrix tests

`tests/specify_cli/git/test_origin_freshness.py` (marker `git_repo`; isolated git env via `tests/terminus/two_clone_support.isolated_git_env`). Use real repos: a bare remote + clone A + clone B (helper from WP01). Cases:
- `check_branches`: `no_remote` (no remotes); `remote_missing` (remote answered, branch absent); `up_to_date`; `ahead` (local commit unpushed); `behind` (B pushed); `diverged`; `local_missing` (remote has it, A has no local branch); `unreachable` with a pushed-but-never-fetched branch and a dead remote URL → `unreachable`, NOT `remote_missing` (FR-006 edge case — the key fail-open guard).
- Non-`origin` remote: A's only remote is `upstream` → verdict's `remote == "upstream"`.
- `check_status_evidence`: build a minimal mission dir layout committed on `main` (`kitty-specs/<slug>/status.events.jsonl` + `meta.json` with topology `lanes`) — or reuse `tests/terminus/lanes_fixture.py` if it fits; B appends an event line and pushes → `behind`; B pushes a commit touching only `src/x.py` → `up_to_date` (scoped, FR-015 positive control on the same fixture).
- Mode: flag beats env; env `warn` → warn/`environment`; unset → enforce/`default`; env `bogus` → enforce + a warning string.
- `enforce_merge_gate`: each refusal code; `warn` mode returns warnings and does not raise; refusal text names branch, counts, remote, remedy, and the opt-out line; with `merge_record_exists=True` the remedy starts with `spec-kitty consolidate --abort`.
- `plan_review_lane`: keep / fast_forward(sha) / create_from(ref) / refuse(ORIGIN_LANE_DIVERGED) / warn(unreachable).
Commit red.

### T014 — Mode

```python
ORIGIN_CHECK_ENV = "SPEC_KITTY_ORIGIN_CHECK"
class OriginCheckMode(StrEnum): ENFORCE = "enforce"; WARN = "warn"
@dataclass(frozen=True) class OriginCheckSetting: mode: OriginCheckMode; source: Literal["default","flag","environment","read-only"]; warning: str | None = None
def resolve_origin_check_mode(flag: str | None) -> OriginCheckSetting
```
Flag values validated by typer at call sites (Choice); still validate here (unknown flag → ValueError).

### T015 — `check_status_evidence(repo_root, mission_slug, *, owned=None) -> FreshnessVerdict`

1. Evidence branch from the seam (above). 2. `resolve_remote` → None ⇒ `no_remote`. 3. `remote_heads` (raise → `unreachable` with detail). 4. Absent ⇒ `remote_missing`. 5. `fetch_branches`. 6. Local branch missing ⇒ `local_missing`. 7. `behind` = `divergence(..., paths=<alias status logs>).behind`; `ahead` = unscoped `divergence(...).ahead`. 8. State: behind>0 and ahead>0 ⇒ `diverged`; behind>0 ⇒ `behind`; else `up_to_date` (local-only commits never refuse — that is the merge record / own bookkeeping, spec US1-3).

### T016 — `check_branches(repo_root, branches) -> list[FreshnessVerdict]`

Group branches by resolved remote; ONE `remote_heads` and ONE `fetch_branches` per remote (NFR-001). Unscoped divergence. Keep input order in the output.

Also `approved_lane_branches(repo_root, mission_slug, lanes_manifest, *, completed_wps: frozenset[str] = frozenset()) -> list[str]` — the single selection both consolidate (WP04) and orchestrator-api (WP05) use: code lanes only (skip planning lanes), skip fully canceled lanes (`lanes.compute.lane_fully_canceled` over the reduced status snapshot read from the status read surface), skip lanes whose WPs are all in `completed_wps` (resume); branch names via `lanes.compute.lane_created_branch`. Test it.

### T017 — `enforce_merge_gate`, `OriginFreshnessRefused`, text

- Codes: `ORIGIN_STATUS_STALE`, `ORIGIN_LANE_STALE`, `ORIGIN_LANE_DIVERGED`, `ORIGIN_UNREACHABLE` as module constants.
- `enforce_merge_gate(*, evidence: FreshnessVerdict | None, lanes: Sequence[FreshnessVerdict], setting: OriginCheckSetting, merge_record_exists: bool, evidence_checkout: Path | None) -> list[str]` — returns warnings; raises `OriginFreshnessRefused(error_code, error_codes, verdicts, message)` per the plan's policy table (evidence `local_missing` refuses `ORIGIN_STATUS_STALE` — callers handle the coordination-topology case before calling). In `warn` mode, convert every would-be refusal into a warning naming the verdict and `setting.source`.
- Text shape (contract): first line `<CODE>: <branch> is <state> (<n> behind / <m> ahead of <remote>/<branch>)`; remedy lines (status: `git -C <checkout> pull <remote> <branch>`; with merge record: abort → pull → re-run; lane: `git fetch <remote> <lane>` then `git branch -f <lane> <remote>/<lane>` (or `git -C <lane worktree> merge --ff-only <remote>/<lane>` when checked out), then re-run; unreachable: check network/credentials); last line `Opt out (not recommended): --origin-check warn, or SPEC_KITTY_ORIGIN_CHECK=warn.` Hoist repeated literals to constants (Sonar S1192).
- Keep each function C901 ≤ 15 (split classify / render helpers).

### T018 — `plan_review_lane(repo_root, lane_branch) -> ReviewLaneAction`

Returns a small frozen dataclass: `kind ∈ {keep, fast_forward, create_from, refuse, warn}`, `remote_sha`, `remote_ref`, `code`, `message`, `verdict`. Mapping: up_to_date/ahead/remote_missing/no_remote → keep; behind → fast_forward(remote_sha) (the caller checks checkout cleanliness and locks — that is not this module's job); local_missing → create_from(tracking ref); diverged → refuse(ORIGIN_LANE_DIVERGED); unreachable → warn.

## Test Strategy

```bash
.venv/bin/python -m pytest -q tests/specify_cli/git/test_origin_freshness.py tests/kernel/test_git_remote.py
.venv/bin/python -m pytest -q tests/architectural/test_layer_rules.py tests/architectural/test_no_legacy_terminology.py
.venv/bin/ruff check src/specify_cli/git/origin_freshness.py tests/specify_cli/git/test_origin_freshness.py
.venv/bin/ruff format --check --force-exclude src/specify_cli/git/origin_freshness.py tests/specify_cli/git/test_origin_freshness.py
.venv/bin/mypy src/specify_cli/git/origin_freshness.py
```

## Definition of Done

- [ ] Tests red first, then green; ≥ 90% line coverage of the new module from its own tests.
- [ ] `unreachable` never collapses to `remote_missing`; scoped `behind` ignores unrelated commits.
- [ ] No raw git; no rendering imports from consolidation.

## Risks

- `mission_dir_aliases` and the seam need a real mission layout — prefer the existing terminus fixtures over hand-made meta.json if the seam rejects a minimal one.
- `write_target` may run the #4979 existence probe for a coordination branch with neither a local head nor a tracking ref (pre-existing; acceptable).

## Reviewer Guidance

Check the fail-closed rule (FR-006) with the pushed-never-fetched + dead remote test; check the opt-out source is named; check codes are constants and match the spec.

## Post-tasks squad folds (binding — supersede conflicting text above)

- NFR-001 (one contact per remote per gate): add `check_mission_branches(repo_root, mission_slug, *, lane_branches: Sequence[str], owned=None) -> MissionFreshness(evidence: FreshnessVerdict, lanes: list[FreshnessVerdict])` that issues ONE `remote_heads` + ONE `fetch_branches` per resolved remote for the evidence branch AND the lanes together, then classifies evidence scoped and lanes unscoped. WP04 and WP05's consolidate-mission use it; `check_status_evidence` stays for accept.
- `approved_lane_branches` must read lanes and status only through read-only accessors (`seam.read_dir(LANE_STATE)` / `read_lanes_json`, status read surface) so it can run before `_resolve_run_status_dir`. Document that it selects code lanes that are not fully canceled (not "approved" lanes) and may over-refuse, never under-refuse; it does not reuse the claim's `excluded_canceled_wp_ids`.
- Evidence `local_missing` on a COORDINATION topology must not refuse here: return the verdict and let callers pass it through to the existing `COORDINATION_WORKTREE_UNMATERIALIZED` path; add a test that the fetch's new `refs/remotes/<r>/<coord>` leaves `write_target` / the #4979 probe behaviour benign.

## Activity Log

- 2026-10-06 — prompt generated.
