---
work_package_id: WP08
title: Registry gate, ADR, docs
dependencies:
- WP02
- WP04
- WP05
- WP06
- WP07
requirement_refs:
- FR-014
- SC-005
- C-005
- C-006
- NFR-005
planning_base_branch: claude/happy-keller-r38xig
merge_target_branch: claude/happy-keller-r38xig
branch_strategy: Planning artifacts for this mission were generated on claude/happy-keller-r38xig. During /spec-kitty.implement this WP may branch from a dependency-specific base, but completed changes must merge back into claude/happy-keller-r38xig unless the human explicitly redirects the landing branch.
base_branch: kitty/mission-second-clone-origin-reconciliation-01M48V8W
base_commit: 823ac378c636a6483fbae6f99a4941508de9b8ba
created_at: '2026-10-06T20:25:27.456561+00:00'
subtasks:
- T038
- T039
- T040
- T041
- T042
phase: Phase 4 - Close the class
history:
- at: '2026-10-06T15:30:00Z'
  actor: system
  action: Prompt generated via /spec-kitty.tasks
agent_profile: python-pedro
authoritative_surface: docs/adr/4.x/
create_intent:
- tests/architectural/test_evidence_gates_check_origin.py
- docs/adr/4.x/2026-10-06-3-evidence-gates-check-origin-freshness.md
execution_mode: code_change
model: ''
owned_files:
- tests/architectural/test_evidence_gates_check_origin.py
- docs/adr/4.x/2026-10-06-3-evidence-gates-check-origin-freshness.md
- docs/adr/4.x/index.md
- docs/api/environment-variables.md
- docs/api/orchestrator-api.md
- docs/context/orchestration.md
- docs/changelog/CHANGELOG.md
- AGENTS.md
- src/specify_cli/cli/commands/_env_file_doctor.py
- src/specify_cli/git/origin_gate.py
- src/specify_cli/consolidation/origin_gate.py
- docs/development/page-inventory.yaml
- docs/development/docs-retrieval-index.yaml
role: implementer
tags: []
task_type: implement
tracker_refs: []
---

# Work Package Prompt: WP08 – Registry gate, ADR, docs

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

Close the defect class and record it:
1. `tests/architectural/test_evidence_gates_check_origin.py` (FR-014, C-004, SC-005): every registered evidence-gate entry point calls `specify_cli.git.origin_freshness` (directly or via `consolidation.origin_gate`); floor ≥ 5 registered entries; a planted omission fails; EMPTY allowlist; `consolidate --dry-run` is the one recorded exemption (it never reaches the executor) — record it as a reasoned `NOT_AN_EVIDENCE_GATE` entry with rationale, not an allowlist.
2. ADR `docs/adr/4.x/2026-10-06-3-evidence-gates-check-origin-freshness.md` (C-005).
3. Docs: env var, orchestrator-api contract 1.11.0, glossary terms, CHANGELOG, AGENTS.md note.

## Context & Constraints

- Read `spec.md`, `plan.md`, `research.md`, `traces/design-decisions.md` (all squad dispositions + residuals), and the merged code of WP01-WP07 (this WP depends on all of them).
- Registered entry points (verify names in the merged code): `consolidation.executor._run_lane_based_consolidation`, `cli.commands.accept.accept`, `orchestrator_api.consolidation.accept_mission`, `orchestrator_api.consolidation.consolidate_mission`, `cli.commands.agent.workflow._prepare_review_workspace`. Model the AST walk on `tests/architectural/test_single_rollback_authority.py` / `test_destructive_op_routing.py` (call-graph reachability within the module is enough: the entry function or a same-module helper it calls must reference an `origin_freshness` / `origin_gate` symbol).
- ADR format: copy the section structure of a recent 4.x ADR (e.g. `2026-10-04-5-approval-stamp-bounds-the-approved-claim.md`); frontmatter fields as the docs gates require. Content:
  - Context: #5780, #5758, #5759; prior probe-only fixes #4969, #4979.
  - Decision: amend ADR 2026-06-05-1 Decisions 1 and 2 — remote contact has one owner (`kernel.git.remote`); push safety stays with `push_preflight`; evidence freshness is a named pre-mutation preflight in the evidence gates. The remote rule (FR-017). The policy table and operator rulings (refuse status evidence, fast-forward review lane, fail closed on unreachable with `--origin-check warn` / `SPEC_KITTY_ORIGIN_CHECK`).
  - Cite ADRs 2026-09-24-2 (remote-only coordination refusal reused), 2026-10-04-5 (lane check runs before the approval-stamp check and only refuses), 2026-10-04-3 (upgrade reports the merge-driver install in its one outcome), 2026-09-30-1 (empty allowlists), 2026-10-05-1 (alias-scoped status log).
  - Pre-existing drift recorded: `remote_probes` and `protection_policy` already contacted remotes outside `push_preflight` (now drained).
  - Residuals: literal `origin` in push safety and push (`push_preflight` default, `phase_finalize` push, `consolidation/preflight.py:307`, `orchestrator_api/consolidation.py:170`, `mission_branch_context.py:228`, `coordination/policy.py:112`, `core/git_ops.py:331`); `--push` refreshes the target twice in lanes topology; `write_target`'s #4979 probe; follow-ups listed in spec Out of Scope.
- Update `docs/adr/4.x/index.md`.
- Terminology: run `tests/architectural/test_no_legacy_terminology.py`; Mission not feature; no "sync".

## Branch Strategy

- **Strategy**: lanes; worktree allocated by `spec-kitty implement WP08`.
- **Planning base / merge target**: `claude/happy-keller-r38xig`.

## Subtasks

### T038 — Registry gate (first commit: red on a planted omission)

Write the gate with its self-test; show it detects a planted entry point that skips the check; then green on the real code.

### T039 — ADR

As above. One Divio type (explanation/decision), `updated:` freshness date.

### T040 — Docs

- `docs/api/environment-variables.md`: `SPEC_KITTY_ORIGIN_CHECK` (`enforce` default | `warn`), what it does, the risk of setting it in a committed `.kitty.env` tier (every clone inherits it; the warning names the source). Add it to the `doctor env-file` printable allowlist if one exists (`_env_file_doctor.py:65`) (one-line edit; owned here).
- `docs/api/orchestrator-api.md`: contract 1.11.0, `data.preflight_error_code` values for freshness, `data.origin_freshness` shape, `--origin-check`.
- `docs/context/orchestration.md`: glossary entries "evidence gate", "origin freshness check", "status evidence branch", each with a "Do NOT use when" guard (e.g. not "terminus gate", not "origin reconciliation", not "sync").

### T041 — CHANGELOG + AGENTS.md

- `docs/changelog/CHANGELOG.md`: entry under the current unreleased rc section (find the top-most unreleased heading; never bump the version): bold impact-first lead `(#5780, #5758, #5759)`, then Before → After for a teammate on a second clone. Follow `tests/docs/test_changelog_style.py`.
- `AGENTS.md` (CLAUDE.md is a symlink to it): one short paragraph under the consolidation patterns section naming the freshness check, the codes, the opt-out and the ADR.

### T042 — Docs gates

```bash
PYTHONPATH=. .venv/bin/python scripts/docs/inventory_lockfile.py --write docs/development/page-inventory.yaml
PYTHONPATH=. .venv/bin/python scripts/docs/docs_index.py --write
PYTHONPATH=. .venv/bin/python scripts/docs/check_docs_freshness.py --ci     # errors=0
.venv/bin/python -m pytest -q tests/architectural/test_evidence_gates_check_origin.py tests/architectural/test_remote_contact_owner.py tests/architectural/test_no_legacy_terminology.py
.venv/bin/python -m pytest -q tests/docs/test_changelog_style.py tests/docs/test_adr_content_invariance.py tests/docs/test_docs_structural_lint.py tests/docs/test_check_docs_freshness.py
```

## Definition of Done

- [ ] Registry gate: floor ≥ 5, planted omission fails, no allowlist.
- [ ] ADR + index; docs gates green; terminology guard green.
- [ ] CHANGELOG entry follows the style test.

## Risks

- Docs freshness/index drift findings — regenerate, commit both YAMLs.

## Reviewer Guidance

Mutate one entry point (comment out its call) and confirm the gate fails. Read the ADR against the residual list in `traces/design-decisions.md`.

## Post-tasks squad folds (binding — supersede conflicting text above)

- Registry strength: require an `ast.Call` to an `origin_freshness` / `origin_gate` function reachable from the entry point (not just a name reference / import). DERIVE the registered set where possible: the `review` command, plus every function in `src/specify_cli/cli/commands/` and `src/specify_cli/orchestrator_api/` that calls `_run_lane_based_consolidation`, `_execute_lane_merge` or `collect_feature_summary`; assert the derived set ⊇ the 5 known entry points (floor) and that each reaches the check. Planted omission must fail.
- NFR-003 (<200 ms no-remote) is review-checked, not timed in CI (no `timing` test); say so in the ADR.

- DEDUP FOLD (binding, from WP05 review): `src/specify_cli/git/origin_gate.py::run_origin_gate` is the single shared authority. Fold WP04's `src/specify_cli/consolidation/origin_gate.py` onto it as its own commit before T038: the consolidation module keeps only lane selection (`approved_lane_branches` + `completed_wps`), `merge_record_exists`, rendering and `typer.Exit`; remove its copies of `_evidence_checkout` and its `read_topology` path (use the shared `resolve_topology` route). Prove behaviour unchanged with WP04's tests (`tests/terminus/test_consolidate_sees_teammate_rejection.py`, `tests/consolidation/test_origin_gate.py`). Ownership extended to both origin_gate modules for this fold.
- The registry gate must recognise calls into `specify_cli.git.origin_gate.run_origin_gate` (and `origin_freshness`) as the freshness check.

## Activity Log

- 2026-10-06 — prompt generated.
