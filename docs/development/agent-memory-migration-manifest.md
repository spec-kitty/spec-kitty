---
title: Agent-Memory Migration Manifest
description: Audit manifest mapping every migrated agent-memory entry to its repo-native home, tracker issue, or retirement, with the completeness test that enforces it.
doc_status: deprecated
updated: '2026-09-30'
audience: docs/context/audience/internal/maintainer.md
type: reference
related:
- docs/development/index.md
- docs/development/reference/known-friction-points.md
- docs/development/how-to/manage-issue-tracker.md
- docs/development/how-to/create-a-doctrine-artifact.md
- docs/operations/coord-off-main-addadd.md
---

# Agent-Memory Migration Manifest

> **Historical record (2026-08 memory-migration audit).** Kept as a record of a one-off audit; not current guidance. The active cycle is 4.0.0 — see the [4.0.0 roadmap](../plans/4-0-0-milestone-roadmap.md).

Mission `self-documenting-repo-01M0287X` audited the operator's local
agent-memory file (`~/.claude/projects/.../memory/MEMORY.md`) — a personal,
gitignored scratchpad of hard-won operational lessons — against the repo's
own doctrine, docs, tests, and gates. The thesis: a lesson an agent had to
learn the hard way and write down by hand is either (a) something the repo
should say for itself (a doc, a gate remedy, a runbook) so the next agent
never has to relearn it, (b) a genuine behavior bug that belongs in the
tracker, or (c) already obsolete because the mechanism it describes has
since changed or been retired.

This manifest is the **committed authority** for that migration. The
working file the audit was actually run against
(`work/memory-gap-filler-analysis.md`) is gitignored and does not exist in
this worktree or in CI — a committed test cannot read it. So the six
gap-filler clusters (**G1–G6**) below, and their resolutions, are the
result, not a pointer to one. The companion test,
[`tests/docs/test_migration_manifest_complete.py`](../../tests/docs/test_migration_manifest_complete.py),
parses these tables directly and enforces that every row is resolved and
every `home:` path exists on disk — it is the enforcement half of this
audit, not just a report of it.

**Out of scope (C-004):** deleting the resolved entries from the operator's
live `MEMORY.md` file is a manual, per-operator checklist tracked on
[#3448](https://github.com/Priivacy-ai/spec-kitty/issues/3448). This mission
produces the resolution map; the operator applies it to their own memory
file at their own pace.

## Resolution vocabulary

Each row below carries exactly one resolution token:

| Token | Meaning |
|---|---|
| `home:` | The lesson now lives at this repo path — a doc, gate remedy, or runbook that says it for itself. |
| `issue:` | The lesson describes a genuine behavior bug, filed and tracked at this issue. |
| `retired` | The mechanism the memory entry described no longer exists or has been superseded; the memory entry is stale. |
| `not-remedy-bearing` | Classified and kept as-is: the referenced gate is real but narrowly scoped and does not carry an enrichable remedy string. |

## G1 — Gate-fix guidance (WP01, commit family `7488ab819`)

| Memory entry | Resolution |
|---|---|
| `reference_arch_gate_campsite_fixes` (shard-registration half) | **retired** — superseded by #2671's auto-cover shard registry (`tests/_arch_shard_map.py`, `default_fallback=True`); no repo home remains for the manual-registration lesson. |
| `reference_write_side_rederivation_gate_grammar` | **home:** [`tests/architectural/test_no_write_side_rederivation.py`](../../tests/architectural/test_no_write_side_rederivation.py) — the remedy is content-anchored directly in the assertion message. |
| `reference_docs_move_relative_link_gate` | **home:** [`tests/docs/test_relative_link_fixer.py`](../../tests/docs/test_relative_link_fixer.py) — the remedy names the `relative_link_fixer` CLI and its `_KNOWN_GAPS` allow-list. |
| `feedback_schema_slot_needs_producer_and_gate` | **home:** [`tests/architectural/test_no_inert_schema_slots.py`](../../tests/architectural/test_no_inert_schema_slots.py) — the remedy names the live-producer store-site pattern. |
| `reference_gate_coverage_two_baselines` | **retired** — the "two baselines" (`gc2b`/`gc3b`) model lived in `tests/architectural/test_gate_coverage.py`, deleted whole in the test-sanitation pass (`177e06269`, #3285) along with its baseline file (`_gate_coverage_baseline.json`) and CLI. The surviving oracle, [`tests/architectural/test_ci_collection_completeness.py`](../../tests/architectural/test_ci_collection_completeness.py), is explicitly **baseline-free** by design ("Sanitation removes the legacy orphan-file baseline and its update/check CLI rather than leaving a mutable, unenforced second authority beside this oracle"). The memory describes a mechanism the repo no longer has. |
| `reference_analysis_report_staleness_gate` | **home:** [`tests/specify_cli/test_analysis_report_charter_yaml_staleness.py`](../../tests/specify_cli/test_analysis_report_charter_yaml_staleness.py) — classified **not-remedy-bearing**: a narrow correctness test with no enrichable remedy string, deliberately left as-is by WP01. |
| `reference_mission_gate_artifacts` | **retired** — grepped `src/`, `tests/`, `docs/`, `packs/`: zero hits for `mission-gate-artifact` or `mission_gate_artifact`. No such gate exists; the memory names a phantom. The real requirement it was trying to describe — that `implement` needs an analysis-report artifact — is enforced by `expected-artifacts.yaml`: [`packs/built-in/missions/software-dev/expected-artifacts.yaml`](../../packs/built-in/missions/software-dev/expected-artifacts.yaml) declares `evidence.analysis-report` (`analysis-report.md`) as `blocking: true` at the `implement` step. Neither `accept` nor `done` carries a comparable blocking-artifact declaration in that manifest, and no `contracts/` artifact requirement was located — the memory over-stated the gate surface. |

## G2 — CLAUDE.md stale (WP02, commit `ab25bacfe`)

| Memory entry | Resolution |
|---|---|
| `reference_prompt_template_regen_and_source_location` (source-location half) | **home:** [`AGENTS.md`](../../AGENTS.md) (the real target of the `CLAUDE.md` symlink) plus the guard [`tests/architectural/test_claudemd_template_source.py`](../../tests/architectural/test_claudemd_template_source.py). The regen-workflow half of this entry is G4. |

## G3 — Recovery runbooks (WP03)

| Memory entry | Resolution |
|---|---|
| `reference_coord_off_main_splitbrain_recovery` | **home:** [`docs/operations/coord-off-main-addadd.md`](../operations/coord-off-main-addadd.md) |
| `reference_prbound_coord_topology_splitbrain` | **home:** [`docs/operations/start-branch-coord-divergence.md`](../operations/start-branch-coord-divergence.md) |
| `reference_lane_seed_splitbrain_and_sparse_guard` | **home:** [`docs/operations/stale-lane-seed.md`](../operations/stale-lane-seed.md) |
| `project_flatten_mission_coord_worktree_missing` | **home:** [`docs/operations/coord-worktree-missing.md`](../operations/coord-worktree-missing.md) |
| `reference_cutover_flip_fails_in_linked_worktree` | **home:** [`docs/operations/cutover-flip-linked-worktree.md`](../operations/cutover-flip-linked-worktree.md) |
| `reference_coord_branch_base_strand_fix` | **home:** [`docs/operations/coord-branch-base-strand.md`](../operations/coord-branch-base-strand.md) |

## G4 — Discoverable commands (WP04, commit `d0ee639f6`)

| Memory entry | Resolution |
|---|---|
| `reference_docs_inventory_freshen` | **home:** [`docs/development/index.md`](index.md) — the page-inventory rollup is refreshed via `scripts/docs/inventory_lockfile.py --write <path>` (a path-valued flag), and the retrieval index via `scripts/docs/docs_index.py --write` (a bare boolean flag) — two **separate** scripts with two different `--write` shapes, which is exactly the confusion the original memory entry was guarding against. Also noted: `inventory_lockfile.py --write`'s own help string ("Optional path to write the regenerated lockfile (never docs/)") is stale — its own `DEFAULT_INVENTORY_PATH` is `docs/development/3-2-page-inventory.yaml`, i.e. under `docs/`. Left as a campsite nit, not fixed in this pass. |
| `reference_mission_wrapup_pr_doctrine` | **home:** [`docs/development/index.md`](index.md), which points to [`packs/built-in/procedures/mission-wrap-up-sequence.procedure.yaml`](../../packs/built-in/procedures/mission-wrap-up-sequence.procedure.yaml) and [`packs/built-in/directives/046-readable-consistent-prs.directive.yaml`](../../packs/built-in/directives/046-readable-consistent-prs.directive.yaml). |
| `reference_prompt_template_regen_and_source_location` (regen half) | **issue:** [#3447](https://github.com/Priivacy-ai/spec-kitty/issues/3447) (deferred, tracked as a follow-up to automate the 12-agent-copy + codex/vibe snapshot regen), plus a pointer from [`docs/development/index.md`](index.md). |

## G5 — Behavior quirks filed as bugs (WP05 / T014)

| Memory entry | Resolution |
|---|---|
| `reference_finalize_clobbers_issue_matrix` | **issue:** [#3450](https://github.com/Priivacy-ai/spec-kitty/issues/3450) — `finalize-tasks` clobbers issue-matrix verdicts. |
| `reference_review_cycle_counter_double_increment` | **issue:** [#3451](https://github.com/Priivacy-ai/spec-kitty/issues/3451) — `move-task` double-increments the review-cycle counter. |
| `feedback_status_daemon_stale_autocommit` | **issue:** [#3452](https://github.com/Priivacy-ai/spec-kitty/issues/3452) — the status daemon auto-commits staged files with the previous commit message. |

## G6 — Env/tracker conventions (WP04, commit `d0ee639f6`)

| Memory entry | Resolution |
|---|---|
| `reference_pyenv_editable_reappears` | **home:** [`docs/development/reference/known-friction-points.md`](reference/known-friction-points.md) |
| `project_commit_hook_pins_interpreter` | **home:** [`docs/development/reference/known-friction-points.md`](reference/known-friction-points.md) |
| `reference_bug_label_retired_native_type` | **home:** [`docs/development/how-to/manage-issue-tracker.md`](how-to/manage-issue-tracker.md) |
| `reference_at_tension_with_ticket` | **home:** [`docs/development/how-to/create-a-doctrine-artifact.md`](how-to/create-a-doctrine-artifact.md) — **corrected** this run: `opposed_by` is itself **retired** (legacy-pack-only, migrated via `spec-kitty migrate rewrite-opposed-by`); the canonical relation pair is `in_tension_with` / `reconciles_tension`. The original memory entry's ticket numbers (#2537/#2538) predate that migration. |

## Corrections surfaced this run

Running this audit against the live repo (rather than trusting the memory
entries' own text) surfaced four cases where the memory was itself stale —
which is the mission's thesis proven in miniature:

1. **`reference_docs_inventory_freshen`** understated that `inventory_lockfile.py`
   and `docs_index.py` are two separate scripts with two different `--write`
   argument shapes (path-valued vs. boolean flag).
2. **`reference_at_tension_with_ticket`** pointed at `opposed_by`, which has
   since been retired in favor of `in_tension_with` / `reconciles_tension`.
3. **`reference_mission_gate_artifacts`** named a gate (`mission-gate-artifact`)
   that does not exist anywhere in `src/`, `tests/`, `docs/`, or `packs/` —
   a phantom. The real, narrower requirement it gestured at (analysis-report
   required at `implement`) is enforced by `expected-artifacts.yaml`, not by
   a gate of that name.
4. **`reference_gate_coverage_two_baselines`** described a two-baseline
   (`gc2b`/`gc3b`) gate-coverage model that was deleted wholesale in the
   `#3285` test-sanitation pass; its replacement,
   `test_ci_collection_completeness.py`, is deliberately baseline-free.

Each of these is recorded as `retired` or corrected above rather than
carried forward silently.
