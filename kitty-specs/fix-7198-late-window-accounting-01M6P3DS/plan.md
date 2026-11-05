# Implementation Plan: Account for every late-window change before the coordination branch goes

**Branch**: `issue-7198-late-window-accounting` | **Date**: 2026-11-05 | **Spec**: `kitty-specs/fix-7198-late-window-accounting-01M6P3DS/spec.md`

## Summary

PR #7124 (#6871) made the late window a per-run decision and gave the first run the projection and
the proof the `--resume` already had. What it did not change is **what the proof covers**:
`assert_late_window_landed` walks the window but skips every path that is not a coordination-kind
record — the two status byte-sets by one exemption, `meta.json` and every other primary/unclassified
artifact by another. Everything it skips is then approved: the run advances the approved tip to the
branch tip, the projection teardown gate and the branch-delete compare-and-swap match, and the
coordination branch is deleted at exit 0 even though the change was never landed.

This change replaces the two exemptions with a **disposition per changed path**:

| Disposition | Applies to | Proof |
|---|---|---|
| landed | any path | coordination blob == target branch's committed blob (today's proof) |
| landed by the union | `status.events.jsonl` | every `event_id` in the coordination branch's log is in the target branch's committed log |
| excluded as derived | `status.json` | a reduced snapshot, rematerialized from the unioned log by the projection itself; never an independent record |
| carried by the target's copy | any other path | the coordination document is contained in the target's committed copy (recursive JSON object containment) |
| **refused** | everything else, plus any window deletion | typed `LateProjectionRefused`, triple kept, per-kind remedy |

The assertion keeps its call site and ordering, so "both run kinds" and "nothing is approved that this
assertion did not cover" continue to hold by construction.

## Technical Context

**Language/Version**: Python 3.12 (`uv run`, `src/specify_cli/`)
**Primary Dependencies**: typer CLI, pytest, real-git fixtures (`tests/coordination/`,
`tests/consolidation/`, `tests/terminus/`), `specify_cli.status.event_log_merge` for event identity
**Storage**: git refs + `kitty-specs/<slug>/` (`status.events.jsonl`, `status.json`, `meta.json`),
`ConsolidationState` JSON
**Testing**: `uv run --frozen pytest` on the five focused suites; no git mocking
**Target Platform**: developer CLI (`spec-kitty consolidate`)
**Project Type**: single Python package + CLI
**Constraints**: same assertion, same call ordering, no new CLI flag/config key/exit code/error code;
no projection of primary artifacts (#5460, #2804); every new refusal keeps branch + worktree + marker
**Scale/Scope**: `consolidation/bookkeeping_projection.py` (the assertion + two helpers),
`consolidation/phase_teardown.py` (remedy routing + docstrings only), their tests, one changelog
fragment, the recovery guide section that states the guarantee

## Charter Check

- **Single canonical authority.** Status-file classification stays with
  `_classify_status_bookkeeping_filename` / `MissionArtifactKind`; event identity stays with the
  canonical `specify_cli.status.event_log_merge` reader/payload merge; "is this a coordination
  record" stays with `is_coordination_kind_file`. No new filename list, no second event parser.
- **ATDD-first / red-first.** Each defect shape gets a failing test through the pre-existing entry
  point (`phase_teardown._teardown_coordination_triple`) *before* the fix, on the #7124 fixtures.
- **No weakening of a gate.** The assertion becomes strictly stronger; the gate-matrix evidence
  guard, the projection teardown gate CAS, the branch-delete CAS and the approved-tip advance rule
  are untouched.
- **Locality of change (DIRECTIVE_024).** One module owns the widening; `phase_teardown.py` gains
  two remedy branches and docstring corrections, no new control flow.
- **Boy Scout (DIRECTIVE_025).** The two exemptions being replaced are also the place where the
  docstrings still describe "exempt" as a property of the file rather than a rule with a reason;
  they are rewritten in place.
- **Mission tracers**: `traces/{approach,design-decisions,tooling-friction}.md`.
- **Test economy (DIRECTIVE_041).** New tests go where they guard the contract: the first-run and
  resume shapes in `tests/coordination/test_projection_teardown.py`, the per-kind remedy mapping in
  `tests/consolidation/test_late_teardown_projection.py`.

## Implementation Concern Map

- **IC-01 — The disposition table.** One place decides, per changed path in the window, which
  disposition applies. Today the decision is two `continue` statements inside the loop; it becomes a
  single helper the loop consults, so a future file kind lands in the refusing bucket by default
  instead of in a silent skip.
- **IC-02 — Event containment.** "Landed" for an append-only, id-keyed log is set containment, not
  byte equality. The proof must be bounded (two blobs, already read) and fail closed on an
  unparseable log on either side.
- **IC-03 — Document containment.** For a target-owned JSON document, "landed" means the coordination
  document is contained in the target's copy — the bake/stamp/flatten case must not manufacture a
  refusal, and a changed or removed field must not pass.
- **IC-04 — Remedy routing.** Two new kinds, each with a repair that actually clears it (the #6791
  invariant: no two kinds share a remedy, and the enum↔remedy bijection test enforces it).
- **IC-05 — Refusal precision.** One refusal must name *all* the offending paths (bounded to 20, as
  today), and mixed windows must project what they can before refusing, as they do now.

## Project Structure

### Documentation (this mission)

```
kitty-specs/fix-7198-late-window-accounting-01M6P3DS/
├── spec.md
├── plan.md              # this file
├── tasks.md             # /spec-kitty.tasks output
├── research.md          # discovery decisions + grounding evidence
├── checklists/requirements.md
├── issue-matrix.json    # one row: #7198
└── traces/{approach,design-decisions,tooling-friction}.md
```

### Source Code (repository root)

```
src/specify_cli/consolidation/
├── bookkeeping_projection.py    # EDIT: assert_late_window_landed dispositions, 2 containment helpers,
│                                #       2 refusal kinds
└── phase_teardown.py            # EDIT: 2 remedy branches + docstring correction (no control flow)
tests/coordination/
└── test_projection_teardown.py  # EDIT: red-first first-run + resume cases for status events and meta.json
tests/consolidation/
└── test_late_teardown_projection.py  # EDIT: remedy table for the 2 new kinds, status-event refusal at the
                                      #       assertion seam
docs/
├── changelog/unreleased/<pr>.fixed.md
└── guides/how-to/recovery/recover-from-interrupted-merge.md  # the guarantee's wording
```

## Design

`assert_late_window_landed` keeps its signature and its position in
`_land_late_coordination_commits` (after the projection commit, before the approved-tip advance).
Its body becomes:

```python
for changed in git_changed_paths(main_repo, checkpoint_sha, coord_ref, renames=True, pathspecs=(mission_prefix,)):
    repo_rel     = str(changed)
    coordinate   = _read_git_blob_bytes(main_repo, coord_ref, repo_rel)
    target_rel   = (target_feature_dir / relpath).relative_to(main_repo).as_posix()
    target       = _read_git_blob_bytes(main_repo, target_ref, target_rel)

    if coordinate == target:                 continue        # landed (may both be None: absent on both)
    if coordinate is None:                   raise DELETION_CANNOT_BE_EXPRESSED   # target still holds it
    if <status.json>:                        continue        # derived snapshot (IC: rule, documented)
    if <status.events.jsonl>:                status_refusals += missing event ids (IC-02)
    elif is_coordination_kind_file(relpath): record_refusals += repo_rel           # RECORD_NOT_LANDED
    elif <document contains>:                continue        # carried by the target's copy (IC-03)
    else:                                    non_coord_refusals += repo_rel        # NEW kind
raise the first non-empty refusal bucket, naming every path in it
```

Refusal precedence: deletions first (they are unrepairable by projection and the existing kind owns
the remedy), then status events, then coordination records, then non-coordination records — each
bucket aggregated so one refusal names every path of that class rather than stopping at the first.

Containment helpers (module-private, beside the assertion):

- `_status_events_missing_from_target(coord_bytes, target_bytes) -> list[str]` — parse both through
  `specify_cli.status.event_log_merge.read_event_log_text` (the canonical reader that requires a
  non-empty `event_id`), return the coordination ids absent from the target's id set. `EventLogMergeError`
  on either side becomes a refusal (fail-closed), not an exception escaping the phase.
- `_json_document_carried_by(coord_bytes, target_bytes) -> bool` — both sides must parse as JSON
  **objects**; recursive containment: every key present in the target, nested objects recursed,
  everything else `==`. Non-object or unparseable → `False` (refuse).

`_late_projection_remedy` gains two branches:

- `STATUS_EVENTS_NOT_LANDED`: the union stage reads the coordination **worktree's working tree**, so
  the repair is to make that copy hold the events (`git -C <coord worktree> checkout <branch> --
  kitty-specs/<slug>/status.events.jsonl`) or to land them on the target, then resume.
- `NON_COORDINATION_RECORD_NOT_LANDED`: the projection cannot carry a primary artifact (#5460), so
  the repair is to land the file on the target from the coordination branch, or revert it there.

Both keep the existing envelope: `COORD_LATE_PROJECTION_REFUSED`, exit 1, triple intact,
`--abort` ruled out.

## Risks

- **A false refusal on a benign resume window.** The resume base reaches back to the merge start, so
  the window can hold commits the merge itself made. Those are byte-identical on the target, and the
  one shape that is not — the target re-authoring `meta.json` — is covered by document containment.
  The five focused suites, including the end-to-end refusal/resume family, are the check.
- **A refusal no operator can clear.** Every new remedy is a git command in a named checkout plus a
  `--resume`; the assertion never asks the operator to do something the machinery forbids (the
  #6791 broken-remedy lesson).
- **Parse cost.** Two blobs are parsed per window that touches the log or `meta.json`; no full-log
  walk beyond those, and no new git call (NFR-001).
- **Fixture coupling.** `test_first_run_does_not_approve_a_tip_that_moved_during_the_projection`
  injects a `meta.json` commit *deliberately as an exempt path* to isolate the gate's CAS. Once
  `meta.json` is judged, that fixture must be re-pinned to a path that is still exempt by rule
  (`status.json`, the derived snapshot) so the case keeps testing the gate. This is a re-pin, not a
  weakened assertion, and the PR says so.
- **Shared file with #7199.** `phase_teardown.py`'s `_land_late_coordination_commits` is also edited
  by #7199 (anchor advance). This Mission does not touch that condition; the lander is told in the PR
  body.

## Out of Scope (reported, not changed)

- #7199 — a `--resume` can still refuse at the gate for a commit made after its own capture although
  its window landed it. Removing `not run.is_resume` from the anchor advance changes resume
  behaviour; that is its own decision and its own PR.
- #7209 — `--skip-lanes` synthesizes a lanes manifest with no planning commit, so the evidence window
  is uncomputable. Different seam (`entry_preflight.py`, `wp_evidence.py`).
- #7121 — a first run with no recorded coordination anchor builds no window at all. Unchanged.
- Projecting primary artifacts onto the target. Neither the union stage nor this assertion may write
  a primary artifact; the exclusion is load-bearing.

## Verification

```bash
uv run --frozen pytest tests/coordination/test_projection_teardown.py \
    tests/consolidation/test_late_teardown_projection.py \
    tests/consolidation/test_teardown_refusal_resume.py \
    tests/terminus/test_coord_teardown_cas_branch_delete.py \
    tests/consolidation/test_wp_evidence.py -q -p no:randomly -n 4
uv run --frozen ruff check src/specify_cli/consolidation/bookkeeping_projection.py src/specify_cli/consolidation/phase_teardown.py
make format-check-files FILES="src/specify_cli/consolidation/bookkeeping_projection.py src/specify_cli/consolidation/phase_teardown.py"
uv run --frozen mypy src/specify_cli/consolidation/bookkeeping_projection.py src/specify_cli/consolidation/phase_teardown.py
uv run --frozen pytest tests/architectural/test_no_legacy_terminology.py -q
uv run --frozen python -m scripts.docs.check_changelog_style
uv run --frozen python -m scripts.docs.check_docs_freshness --ci
```

Red-first: the new first-run status-event case, the resume status-event case, and the `meta.json`
cases are written and run *before* the fix; the expected pre-fix outcome is a clean teardown
(branch deleted, event absent from the target log) rather than a refusal.
