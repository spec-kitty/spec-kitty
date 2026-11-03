# Implementation Plan: Analysis freshness ignores claim-time runtime fields

**Branch**: `issue-7106-analysis-freshness-claim-fields` | **Date**: 2026-11-03 | **Spec**: `kitty-specs/analysis-freshness-claim-fields-01M6G9PP/spec.md`
**Input**: Mission specification from `kitty-specs/analysis-freshness-claim-fields-01M6G9PP/spec.md`
**Issue**: spec-kitty/spec-kitty#7106 (P0)

## Summary

`collect_material_inputs` fingerprints three surfaces that a claim (or a rework
cycle) rewrites with pure runtime bookkeeping: `tasks/WP##-*.md` frontmatter minus
`MUTABLE_FIELDS` (the claim's `base_branch`/`base_commit`/`created_at`), the whole
of `meta.json` (the first claim's `vcs`/`vcs_locked_at` lock), and every descendant
of `tasks/` (a rejection's `review-cycle-N.md` / `review-feedback-N.md` /
`baseline-tests.json`). Claiming a work package therefore invalidates a report
recorded with `record-analysis --report-only`, and the next claim — and every
rework re-claim — is refused with `analysis_report_required`. The fix excludes
exactly those declared runtime sets and nothing else: the claim's provenance
triple is declared once (`frontmatter.WP_CLAIM_PROVENANCE_FIELDS`) and consumed by
the writer, `meta.json`'s VCS backend is normalised away (absent == `git`) with its
lock timestamp dropped, and `tasks/` is fingerprinted as the flat planning surface
it is. Every authored field, unknown legacy keys included, and every body byte
still gates freshness.

## Technical Context

**Language/Version**: Python 3.11 (repo runtime)
**Primary Dependencies**: `ruamel.yaml` (already in the closure's path), `kernel.vcs_lock`, `specify_cli.frontmatter`
**Storage**: N/A — filesystem content hashes inside `analysis-report.md` frontmatter
**Testing**: `pytest`; targeted module suites plus one end-to-end CLI integration test that drives the real claim path
**Target Platform**: Linux/macOS CLI
**Project Type**: single Python package (`src/specify_cli`)
**Performance Goals**: unchanged — the closure stays one pass over the declared paths, no git or network calls added
**Constraints**: no strict re-parse of legacy WP prompts; no change to what the gate requires; one declared field-set authority
**Scale/Scope**: 3 source modules changed (`analysis_inputs.py`, `frontmatter.py`, `lanes/implement_support.py`), 2 test modules

## Charter Check

*GATE: passed before Phase 0 research; re-checked after Phase 1 design.*

- **Single canonical authority** — the excluded provenance triple is declared once
  (`frontmatter.WP_CLAIM_PROVENANCE_FIELDS`, beside the canonical WP field-name
  owner) and consumed by the writer that stamps it; `VCS_LOCK_META_FIELDS` stays the
  single VCS-lock authority, and `MUTABLE_FIELDS` stays the stripper's.
- **Locality of change (DIRECTIVE_024)** — three call-sites in one subsystem (the
  closure, the field-name owner, the writer), one behavioural change; no new
  abstraction, no new CLI surface, no migration.
- **ATDD-first / test-first-bug-fixing** — red-first reproduction through
  `check_analysis_report_current` and the real claim entry point before the fix.
- **DIRECTIVE_040 / 043 (close the class)** — this is the third instance of the
  same class (#1764 `tasks.md` checkboxes, #2493 pipe-table cells, #7106 WP
  prompts + `meta.json` + `tasks/<wp>/`). The class is closed at the *declaration*
  the claim writes from: extending the stamp now means extending one tuple the
  fingerprint already excludes. The wider alternative (fingerprint only an
  allow-list) was rejected in review as a gate-policy change, not a repair.
- **DIRECTIVE_041 (tests as scaffold)** — the positive controls assert the gate's
  contract (planning edits refused), not the fingerprint's internal shape.
- **NO_FULL_HEAVY_SUITES_IN_MISSION** — targeted modules plus the one integration
  file; CI owns the full sweep.

## Project Structure

### Documentation (this mission)

```
kitty-specs/analysis-freshness-claim-fields-01M6G9PP/
├── plan.md              # This file
├── research.md          # Phase 0 output (discovery grounding)
├── spec.md              # Mission specification
└── tasks.md             # /spec-kitty.tasks output
```

No `data-model.md`, `quickstart.md` or `contracts/` — this mission changes no
domain entity, no public contract and no user-facing workflow; it restores the
fingerprint's stated contract.

### Source Code (repository root)

```
src/specify_cli/
├── analysis_inputs.py           # CHANGED — runtime-set exclusion for WP prompts, meta.json, tasks/
├── frontmatter.py               # CHANGED — declares WP_CLAIM_PROVENANCE_FIELDS (the one authority)
├── analysis_report.py           # unchanged — records/compares the fingerprint
├── dossier/hasher.py            # unchanged — not this gate's field classification
├── migration/strip_frontmatter.py  # unchanged — MUTABLE_FIELDS stays the stripper's list
└── lanes/implement_support.py   # CHANGED — builds the provenance stamp from the declared tuple

src/kernel/vcs_lock.py           # unchanged — source of VCS_LOCK_META_FIELDS

tests/specify_cli/test_analysis_inputs.py            # CHANGED — unit-level red-first + positive controls
tests/integration/test_analysis_freshness_claim_7106.py  # NEW — end-to-end CLI reproduction

docs/changelog/unreleased/<pr>.fixed.md               # NEW — per-PR fragment (PR number assigned at
                                                      # `gh pr create`; never an edit of CHANGELOG.md)
```

## Implementation Concern Map

| IC | Concern | Owner surface | Work package |
|----|---------|---------------|--------------|
| IC-01 | Runtime-set exclusion in the material closure, with one declared field-set authority | `src/specify_cli/analysis_inputs.py`, `frontmatter.py`, `lanes/implement_support.py` | WP01 |
| IC-02 | Red-first proof that a claim no longer stales the report, and that planning edits still do | `tests/specify_cli/test_analysis_inputs.py`, `tests/integration/test_analysis_freshness_claim_7106.py` | WP01 |

The two concerns are one work package: they cannot be delivered apart (an exclusion
without its positive controls is an unproven gate; the controls cannot pass before
the exclusion exists).

## Phase 0: Outline & Research

Completed in `research.md` (discovery step): the reproduction on `main` @
`d18c4f1d58`, the exact claim diff, the write points, decisions D1–D4, and the
design revision forced by the independent planning review (R1 rework artifacts
under `tasks/<wp>/`, R2 allow-list would widen the gate's blindness, R3 normalise
`vcs` instead of dropping it). No `NEEDS CLARIFICATION` items remain.

## Phase 1: Design

### D-1 Exclude the declared runtime sets, and only those — `src/specify_cli/analysis_inputs.py`

Revised after the independent planning review (see `research.md`, "Design revision"):
the first draft projected the WP prompt onto `WP_STATIC_PROJECTION_FIELDS`, which
would have stopped watching 17 keys the gate watches today, unknown legacy keys
included, and would have re-opened the rework path through `tasks/<wp>/`. The
shipped design is the issue's first option — exclude the declared runtime/claim
keys — and touches three surfaces:

1. **WP prompts** (`_wp_prompt_fingerprint`): the exclusion is
   `MUTABLE_FIELDS | set(WP_CLAIM_PROVENANCE_FIELDS)`, where
   `WP_CLAIM_PROVENANCE_FIELDS = ("base_branch", "base_commit", "created_at")` is
   *newly declared in `frontmatter.py`* — beside the canonical field-name owner —
   and consumed by the writer: `create_lane_workspace` now builds its provenance
   dict with `dict(zip(WP_CLAIM_PROVENANCE_FIELDS, (base_branch, base_commit_sha,
   created_at), strict=True))`. The exclusion and the claim's stamp cannot drift.
   Everything else (authored planning fields, `planning_base_branch`,
   `merge_target_branch`, `branch_strategy`, `status`, `agent_profile`, `model`,
   `role`, unknown legacy keys) and the body stay watched.
2. **`meta.json`** (`_meta_fingerprint`): `vcs` is normalised — absent and `git`
   (the only supported backend) are the same state, any other value is
   fingerprinted as written — and the lock timestamp that remains in
   `VCS_LOCK_META_FIELDS` is dropped. Every other key still gates freshness.
3. **`tasks/`** (`_include_work_package_tasks`, `_include`): planning content under
   `tasks/` is flat, so the closure includes the directory sentinel plus every
   non-directory entry and never follows a per-WP sub-directory. `tasks/<wp>/`
   holds the review cycle's generated artifacts (`review-cycle-N.md`,
   `review-feedback-N.md`, `baseline-tests.json`); following them meant a rejected
   work package could never be re-claimed (#7106's rework symptom).

Parsing stays tolerant (`FrontmatterManager`, the same read the closure uses
today; a malformed prompt is still `Invalid WP definition`), and the exclusion is a
key filter over the raw mapping — never a strict `WPMetadata` re-parse, whose
`extra="forbid"` would turn retired keys into a new refusal class (C-002).
`_mapping()` still loads `meta.json`, so a malformed file stays the existing
fail-closed `MaterialInputError`.

Both new fingerprint branches are extracted as small helpers so each is directly
unit-testable; `include`/`_include_work_package_tasks` moved to module scope so
`collect_material_inputs` stays under the `C901` complexity ceiling (15).

#### What still stales the report

- WP prompt: every frontmatter key except `MUTABLE_FIELDS` and the claim's
  provenance triple — including `subtasks`, `dependencies`, `requirement_refs`,
  `owned_files`, the planning-branch trio, `phase`, `title`, any unknown key — plus
  any body byte, plus an added/removed WP prompt (the closure's key set).
- `meta.json`: every key except `vcs` (normalised) and `vcs_locked_at`.
- `spec.md`, `plan.md`, `tasks.md` (status-normalised), the charter and the rest of
  the declared closure: unchanged.

What stops staling: `base_branch`, `base_commit`, `created_at` and the VCS lock —
i.e. exactly the runtime bookkeeping a claim writes.

### D-3 Verification plan

1. **Red, unit** (`tests/specify_cli/test_analysis_inputs.py`): a WP prompt
   carrying the claim's provenance triple, and a `meta.json` carrying the VCS lock,
   must produce the *same* material keys as without them — fails on `main`, passes
   after the fix.
2. **Positive controls** (same file): each of `subtasks`, `dependencies`,
   `requirement_refs`, `owned_files`, an added/removed WP prompt and an unexpected
   `vcs` value changes the key; a per-WP review-cycle artifact directory does not.
3. **Red, end-to-end** (`tests/integration/test_analysis_freshness_claim_7106.py`):
   three cases on a finalized two-WP `lanes` mission, `record-analysis --report-only`,
   real `agent action implement` claims — (a) claim WP01 then WP02: WP02 claims, is
   `in_progress`, the report bytes are untouched, and the claim's stamp really
   appeared in both files; (b) edit WP01's `subtasks` after the analysis: the next
   claim is refused with `stale_analysis_report` naming `tasks/WP01-*.md`; (c) a full
   rework cycle (for_review → review claim → rejection with feedback): the re-claim
   succeeds and the review-cycle artifact really was written.
4. **Mutation check**: separately re-add `created_at` to the WP exclusion and revert
   the `meta.json` normalisation; each must turn exactly its own test red. Output
   recorded under the PR's `## Tests run` / `Self-review:` block.
5. **Changelog**: `docs/changelog/unreleased/<pr>.fixed.md` with the impact-first
   lead and the `(#7106)` reference, written once the PR number exists (the
   repository assembles the changelog from fragments; `check_changelog_style`
   rejects the old `[Unreleased]`-entry shape).
6. **Blast radius**: `tests/specify_cli/test_analysis_inputs.py`,
   `tests/git/test_report_transaction.py`,
   `tests/specify_cli/cli/commands/agent/test_analysis_report_transaction.py`,
   `tests/integration/test_owned_analysis_currency.py`,
   `tests/integration/test_owned_analysis_recording.py`,
   `tests/dossier/` (the classification this reuses), plus `make test-fast`.

## Risks & mitigations

| Risk | Mitigation |
| --- | --- |
| The exclusion silently grows: a new runtime field is added to the stamp without the fingerprint knowing | The excluded triple is *declared* (`WP_CLAIM_PROVENANCE_FIELDS`) and the writer consumes the same tuple via a strict zip, so a new stamped field cannot appear without this decision being revisited; the unit test asserts the exact excluded set |
| `meta.json` normalisation hides a real change | Absent and `git` are genuinely the same state (git is the only supported backend); any other value is fingerprinted as written, and every non-lock key stays watched |
| Excluding `tasks/<wp>/` hides authored content | Planning content under `tasks/` is flat by layout rule (sub-directories are explicitly not the planning layout); the directory sentinel plus every non-directory entry stay in the closure, so a prompt's appearance or removal still counts |
| One-time re-record needed for reports recorded before this lands | The material manifest of an existing report will not match the new projection once; a re-record is the documented recovery, and it is a one-off, not once per claim |
| A *future* runtime writer of a new key re-opens this bug | Accepted and recorded in `research.md`: the recurrence is loud (the gate names the file) whereas an allow-list would silently stop watching authored fields, which is a maintainer decision, not a repair |

## Phase 2: Task generation

`/spec-kitty.tasks` turns IC-01/IC-02 into work packages. This plan stops here.
