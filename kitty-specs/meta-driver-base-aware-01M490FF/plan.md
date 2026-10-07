# Implementation Plan: meta.json merge driver honours the merge base

**Branch**: `fix/meta-driver-base-aware` | **Date**: 2026-10-06 | **Spec**: [spec.md](spec.md)
**Input**: Mission specification from `kitty-specs/meta-driver-base-aware-01M490FF/spec.md`

**Note**: This template is filled in by the `/spec-kitty.plan` command. See `packs/built-in/missions/mission-steps/software-dev/plan/prompt.md` for the execution workflow.

The planner will not begin until all planning questions have been answered—capture those answers in this document before progressing to later phases.

Planning answers (confirmed by the operator on 2026-10-06): one work package; stack is the existing driver module with no new dependencies; the consolidation pipeline opts out of base-awareness (Decision `01M493BC3KPSC4FT6XSC7ESNDN`); target-authoritative keys win only on a genuine conflict in ordinary merges (Decision `01M490FHTGTH51TAD3KNPVMG8H`); red-first `p0_repro` tests land before the fix.

## Summary

`spec-kitty merge-driver-meta` (`src/specify_cli/consolidation/drivers.py::reconcile_meta_payloads` / `run_meta_driver`) reconciles `kitty-specs/**/meta.json` two-way and discards git's `%O` ancestor, so an ordinary `git pull` after `mission close --discard` silently takes the teammate's record and reverts the discard (#5460, P0). The fix adds a base-aware per-key three-way merge for ordinary merges/pulls/rebases (one-sided change or deletion wins, equal changes collapse, genuine conflicts keep today's precedence, coupled key groups move as one unit, `acceptance_history` unioned, empty ancestor = today's two-way rule, corrupt ancestor fails loud and named) while the mission→target squash (whose ancestor is unreliable after a reopen, since a squash records no ancestry) keeps the two-way rule through an explicit opt-out set only on the squash subprocess; every merge with real ancestry, including the lane→mission merges and auto-rebases inside consolidation, is base-aware.

## Technical Context

**Language/Version**: Python 3.13 (project `requires-python` per `pyproject.toml`; the editable dev venv at `.venv` runs 3.13)
**Primary Dependencies**: standard library `json`; existing in-module seams `_load_json_object`, `_union_acceptance_history`, `_TARGET_AUTHORITATIVE_META_FIELDS`, `_META_JSON_KWARGS`, `MergeDriverError`/`MergeDriverOutcome`; `specify_cli.acceptance.ACCEPTANCE_PROVENANCE_FIELDS`; `specify_cli.consolidation.mission_number.is_assigned_mission_number`. No new third-party dependency (DIRECTIVE_051 supply-chain controls: not triggered — nothing added, upgraded or removed).
**Storage**: files only — the three merge-blob paths git materialises (`%O %A %B`) and the committed `meta.json`
**Testing**: pytest; `unit`+`fast` reconciler/file-level tests in `tests/consolidation/`, one `git_repo`+`non_sandbox` real-git merge test, the golden harness `tests/consolidation/test_merge_driver_goldens.py` (+`merge_driver_goldens/_capture.py`), red-first `@pytest.mark.p0_repro(issue=5460)` on the new tests until the fix commit (marker removed in the fix commit; the tests then run per PR as ordinary guards). Targeted local runs only — no full suites locally (charter `NO_FULL_HEAVY_SUITES_IN_MISSION`).
**Target Platform**: Linux/macOS developer machines and CI; the driver is a git subprocess entry point (`spec-kitty merge-driver-meta %O %A %B`) and an in-process body (`MERGE_DRIVER_BODIES`)
**Project Type**: single project (CLI library)
**Performance Goals**: driver invocation on a `meta.json` under 4 KiB stays well under 1 s including interpreter start (NFR-003); the three-way pass is O(keys)
**Constraints**: byte-stable output via the unchanged `_META_JSON_KWARGS` (NFR-001); the five existing golden directories must show zero diff (SC-002); surface limited to `drivers.py`, the shell `cli/commands/merge_driver.py` (reads the opt-out), one overlay line in `lanes/consolidation.py::_run_squash_merge` (sets it), tests, goldens, docs (C-001); no change to `.gitattributes` writers, `init`, migrations, strategy selection
**Scale/Scope**: one module, ~120 lines of product change, 3 new golden cases, 1 new test module, 1 changelog entry

## Charter Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

- **Single canonical authority** — pass: the reconciliation rule lives in `reconcile_meta_payloads` only; the shell and the in-process body call the same function; the opt-out is one named constant read in one place.
- **Architectural alignment** — pass: `consolidation/drivers.py` stays importable without `typer` (the `TestMergeCliBoundary` scan); the env read happens in the CLI shell, which is the reviewed adapter layer.
- **ATDD-first (C-011)** — pass by construction: the red tests are committed before the fix commit on the lane; the reviewer verifies red on the planning base and green on the final commit.
- **Test remediation & bug-fix discipline (Standing Order 4, DIRECTIVE_041/034)** — pass: reproduced red-first through the pre-existing entry points (`run_meta_driver(O, A, B)` and git itself via `.gitattributes`); the real-git test asserts the driver fired, so it cannot be red for the wrong reason.
- **Architectural gate discipline (Standing Order 5)** — pass: no allowlist, no baseline bump; the golden count pin (7 config keys) is untouched; the ruff-format exclude list is shrink-only and not touched.
- **Campsite cleaning (DIRECTIVE_025)** — scoped: the meta section of `drivers.py` is small; the only tidy-first enabler is extracting the two-way rule into a named helper so the three-way path composes it (behaviour-preserving, covered by the existing tests).
- **Terminology canon** — pass: Mission, work package, target branch; no "feature".
- **Regression vigilance** — pass: NFR-002 pins the merge suites; the dry run during grounding was 2270/2270.

No violations → Complexity Tracking is empty.

## Project Structure

### Documentation (this mission)

```
kitty-specs/meta-driver-base-aware-01M490FF/
├── plan.md              # This file
├── research.md          # Phase 0: grounding + post-spec review dispositions
├── data-model.md        # Phase 1: the merge-side model and the per-key rule table
├── quickstart.md        # Phase 1: how to reproduce, run the targeted tests, re-capture goldens
├── traces/              # tracer files (approach, design-decisions, tooling-friction)
└── tasks.md             # Phase 2 output (/spec-kitty.tasks) — not created here
```

`contracts/`: none — the mission adds no interface, endpoint or payload; the driver's external contract (argv `%O %A %B`, exit codes, stderr naming) is unchanged. `meta.json` carries `"contracts": "none"` with a rationale so strict `accept` waives the directory.

### Source Code (repository root)

```
src/specify_cli/
├── consolidation/
│   └── drivers.py                     # reconcile_meta_payloads(base=…), run_meta_driver(two_way=…), MISSING sentinel, coupled groups, opt-out constant
├── cli/commands/
│   └── merge_driver.py                # merge-driver-meta shell: reads the opt-out and passes two_way=True
└── lanes/
    └── consolidation.py               # _run_squash_merge(): sets the opt-out on its one merge subprocess; _make_merge_env() strips it

tests/consolidation/
├── test_meta_driver_base_aware_5460.py        # NEW: unit (file-level via run_meta_driver) + real-git merge/rebase tests
├── test_merge_drivers.py                      # existing meta section unchanged
├── test_squash_reconcilers_2709.py            # existing two-argument calls unchanged
├── test_mission_number_truthful_4900.py       # existing; one new base-aware mission_number case may join
├── test_merge_driver_goldens.py               # existing harness, discovers new cases automatically
└── merge_driver_goldens/merge-driver-meta/
    ├── base-absent/case.json                  # note refreshed
    ├── base-one-sided-delete/                 # NEW (the #5460 shape)
    ├── base-both-changed-precedence/          # NEW
    └── base-empty-file/                       # NEW (zero-byte %O)

docs/changelog/CHANGELOG.md                    # [Unreleased] Fixed entry
```

**Structure Decision**: single project; all product change inside `src/specify_cli/consolidation/drivers.py` plus the two one-line seams named above; tests beside the existing driver tests in `tests/consolidation/`.

## Complexity Tracking

*Fill ONLY if Charter Check has violations that must be justified*

None.

## Implementation Concern Map

> **Note**: Implementation concerns are NOT work packages and are NOT executable units.
> `/spec-kitty.tasks` translates these into executable WPs — one concern may become
> multiple WPs; multiple small concerns may merge into one WP. Do not label concerns
> with WP-style IDs or sequencing language.

### IC-01 — Red-first reproduction and fixtures

- **Purpose**: pin the P0 through the pre-existing entry points before any product change, so the fix is proven rather than asserted (FR-008, FR-009, C-004).
- **Relevant requirements**: FR-001, FR-002, FR-008, FR-009, SC-001, SC-003
- **Affected surfaces**: `tests/consolidation/test_meta_driver_base_aware_5460.py` (new; `p0_repro(issue=5460)` on the two red cases: file-level `run_meta_driver(O, A, B)` on the captured #5460 blobs, and a real-git two-branch `git merge` through `.gitattributes` + `merge.spec-kitty-meta.driver` pointing at a recording wrapper around `python -m specify_cli merge-driver-meta`, asserting exit 0, driver invoked, `discarded_at` present, `topology` absent; plus the `git rebase` positive control and the two-way-vs-three-way squash-opt-out fixture), the three new golden directories with hand-authored correct `expected_A` (red on the pre-fix driver), the refreshed `base-absent/case.json` note.
- **Sequencing/depends-on**: none (first commit on the lane).
- **Risks**: the real-git test must not depend on a stale global install — the driver command must point at `sys.executable -m specify_cli`; the recording wrapper must live under `tmp_path` and be executable on CI; the golden harness has a cold-HOME bootstrap timeout (`COLD_HOME_TIMEOUT_SECONDS`).

### IC-02 — Base-aware reconciliation rule

- **Purpose**: the product fix (FR-001–FR-007, FR-010, NFR-001).
- **Relevant requirements**: FR-001, FR-002, FR-003, FR-004, FR-005, FR-006, FR-007, FR-010, NFR-001, C-002
- **Affected surfaces**: `src/specify_cli/consolidation/drivers.py` — a module-level `_MISSING` sentinel; `_META_COUPLED_KEY_GROUPS` (flatten triple; `merged_*` block; acceptance stamp group = `ACCEPTANCE_PROVENANCE_FIELDS` minus `vcs`/`vcs_locked_at`); `_reconcile_meta_two_way(ours, theirs)` extracted from today's body unchanged; `reconcile_meta_payloads(ours, theirs, base=None)` → two-way when `base` is `None`/`{}`, else the three-way pass over `base ∪ ours ∪ theirs` keys with group members handled as one composite value; precedence helper (`ours` for target-authoritative keys/groups, `theirs` otherwise); the `mission_number` guard applied to the chosen value regardless of ancestor; `acceptance_history` union last; `run_meta_driver(base_path, ours_path, theirs_path, *, two_way=False)` loading `%O` through `_load_json_object` (so a corrupt ancestor raises the named `EventLogMergeError` → `MergeDriverError`); docstrings in `drivers.py` and `cli/commands/merge_driver.py`.
- **Sequencing/depends-on**: IC-01 (red tests exist and are red).
- **Risks**: `_merge_field` conflates `None` and absent — do not reuse it; use the sentinel. Keep `_META_JSON_KWARGS` serialisation untouched. Function complexity ≤ 15: split the three-way pass into "collect candidate keys/groups", "resolve one unit", "apply guards".

### IC-03 — Lane-merge pipeline opt-out

- **Purpose**: keep consolidation results byte-identical (FR-011, US2) by opting the pipeline's own merges out of base-awareness.
- **Relevant requirements**: FR-011, NFR-002, C-001, C-002
- **Affected surfaces**: `drivers.py` exports `META_DRIVER_TWO_WAY_ENV = "SPEC_KITTY_META_MERGE_TWO_WAY"`; `cli/commands/merge_driver.py` meta command reads `os.environ.get(META_DRIVER_TWO_WAY_ENV) == "1"` and passes `two_way=True` (via `run_meta_driver` directly, since the `MERGE_DRIVER_BODIES` callable type carries no keyword); `lanes/consolidation.py`: only the `git merge --squash` subprocess calls (the real integration in `_merge_branch_into` and the dry-run preview) take `env = _make_merge_env(); env[META_DRIVER_TWO_WAY_ENV] = "1"`. `_make_merge_env` itself is untouched, so `tests/architectural/test_merge_pipeline_ratchets.py` (which pins its exact value) stays green, and every real-ancestry merge in the pipeline (lane→mission `--no-ff`, auto-rebase, dependency merges) becomes base-aware. The in-process replay (`git_probes`) excludes `meta.json`, so no change there.
- **Sequencing/depends-on**: IC-02.
- **Risks**: scout result — `auto_rebase.py`, `worktree_allocator.py` and `coordination/coherence.py` all route through `_make_merge_env`; because the opt-out is applied only at the squash calls, those real-ancestry merges become base-aware (intended). The `_make_merge_env` equality ratchet (`test_merge_pipeline_ratchets.py:214-223`) must not be touched.

### IC-04 — Documentation and changelog

- **Purpose**: make the rule discoverable (FR-009, SC-004).
- **Relevant requirements**: FR-009, SC-004
- **Affected surfaces**: `docs/changelog/CHANGELOG.md` `[Unreleased]` → Fixed (bold impact-first lead with `(#5460)`, before→after); module docstrings; the `base-absent` golden note; `docs/architecture` only if it describes the driver (grep first — grounding found no page).
- **Sequencing/depends-on**: IC-02, IC-03.
- **Risks**: terminology guard and docs-freshness gates after any prose touch; markdownlint budget for the long changelog file.
