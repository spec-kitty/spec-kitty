---
work_package_id: WP05
title: Re-measure fast or unit on 3.13 post-fix (FR-004)
dependencies:
- WP02
- WP04
requirement_refs:
- FR-004
- NFR-001
planning_base_branch: issue-4866-interpreter-matrix-3-13
merge_target_branch: issue-4866-interpreter-matrix-3-13
branch_strategy: Planning artifacts for this mission were generated on issue-4866-interpreter-matrix-3-13. During /spec-kitty.implement this WP may branch from a dependency-specific base, but completed changes must merge back into issue-4866-interpreter-matrix-3-13 unless the human explicitly redirects the landing branch.
subtasks:
- T001
- T002
- T003
history: []
agent_profile: python-pedro
authoritative_surface: kitty-specs/interpreter-matrix-3-13-env-and-divergence-01M34HVD/
create_intent:
- kitty-specs/interpreter-matrix-3-13-env-and-divergence-01M34HVD/evidence-remeasurement-3.13.md
execution_mode: planning_artifact
model: ''
owned_files:
- kitty-specs/interpreter-matrix-3-13-env-and-divergence-01M34HVD/evidence-remeasurement-3.13.md
role: implementer
tags: []
tracker_refs: []
---

# WP05 — Re-measure fast or unit on 3.13 post-fix (FR-004)

## ⚡ Do This First: Load Agent Profile

Use the `/ad-hoc-profile-load` skill to load the agent profile specified in the
frontmatter, and behave according to its guidance before parsing the rest of
this prompt.

- **Profile**: `python-pedro`
- **Role**: `implementer`
- **Agent/tool**: `claude`

If no profile is specified, run `spec-kitty agent profile list` and select
the best match for this work package's `task_type` and `authoritative_surface`.

---

## Objective

Replace the distrusted "429 failing/erroring only on 3.13" figure with a
clean, freshly-measured re-run of the `fast or unit` selector on 3.13,
**after** WP04's venv-corruption fix (or documented fallback) has landed, so
any further scoping decision (WP06) is made against real, uncontaminated
data — not the original figure, which the spec explicitly distrusts (it was
measured against an environment known to have been silently rebuilt
mid-run).

## Context

**This WP depends on WP04** (the venv-corruption fix/fallback must be on the
mission branch first — re-measuring against a still-unstable environment
would just reproduce the same contamination this WP exists to eliminate) and
**naturally also depends on WP02** (so the re-measurement reflects the
mission's best current state, including the kernel `dir_fd` fix — WP05's
failure-ID diff against WP02's 4 fixed IDs is exactly what WP06 needs).

**This WP also has a genuine data dependency on WP01 that `wps.yaml` does
not currently declare.** T003 below reads WP01's recorded 3.11 baseline
(`evidence-baseline-3.11.md`) as an actual input for its failure-ID diff —
unlike WP02/WP03/WP04's WP01 ordering requirement (an SK-25 scheduling
constraint, not a data dependency), this WP genuinely *consumes* WP01's
output artifact. `wps.yaml`'s WP05 entry currently declares
`dependencies: [WP02, WP04]` only; adding `WP01` was attempted during
analyze-phase remediation and reverted, because `finalize-tasks`'s
disagree-loud gate (`_detect_dependency_conflicts`, T004,
`mission_finalize.py`) unconditionally rejects any `wps.yaml`
dependency change whose newly-parsed set is non-empty and differs from the
already-materialized WP frontmatter, before any regeneration write can
happen — there is currently no way to land this specific edge through the
CLI without hand-editing generated frontmatter, which is forbidden. See
`tracer-tooling-friction.md`'s follow-up entry (after the SK-25 correction)
for the full record. **This is currently safe only because WP02 and WP04 —
WP05's own declared dependencies — both transitively wait on WP01 via
dispatch sequencing and their own prose (per SK-25's remediation)**, so WP01
is always already `approved`/`done` by the time WP05 can be claimed, not
because the declared dependency graph says so directly. Before starting
T003, confirm WP01 has in fact reached `approved`/`done` and that
`evidence-baseline-3.11.md` exists and is complete, even though no
`dependencies:` edge enforces it.

**This WP owns exactly one new planning-artifact file** —
`kitty-specs/interpreter-matrix-3-13-env-and-divergence-01M34HVD/evidence-remeasurement-3.13.md`
(new file, `create_intent`-declared) — like WP01, it makes no source or test
change. Its deliverable is the recorded command, counts, and failure-ID diff
written into that file, consumed by WP06's disposition decision and by the
mission's PR body evidence section.

**Charter full-suite-run exemption applies here explicitly** (spec.md Edge
Case (b)): this run is licensed as the charter's "explicit cross-cutting
change" exemption to the "run only affected test packages" default — the
venv-corruption fix changes how the *shared test environment itself* behaves
during a broad parallel run, which is exactly the class of shared-
infrastructure change the exemption contemplates. This licenses the
`fast or unit` selector specifically (the same selector `ci-nightly.yml`'s
own job uses, ~35k items) — **not** an unscoped `pytest tests/` run. Do not
broaden this WP's command beyond the `fast or unit` selector.

## Subtask T001: Fresh sync of a 3.13 `.venv`

**Purpose**: Ensure the re-measurement runs against a cleanly-synced
environment, not a leftover state from an earlier WP's investigation.

**Steps**:
1. `uv sync --frozen --all-extras --python 3.13` — a fresh sync, not a reuse
   of whatever `.venv` state WP04's investigation left behind (WP04 may have
   used an isolated `UV_PROJECT_ENVIRONMENT` venv for its own reproduction
   attempts; this WP measures against the checkout's normal, freshly-synced
   `.venv`).
2. Confirm `.venv/bin/python --version` reports 3.13.

**Files**: none yet — create
`kitty-specs/interpreter-matrix-3-13-env-and-divergence-01M34HVD/evidence-remeasurement-3.13.md`
in T002 once you have output to record; T001 is confirmation only.

**Validation**: A confirmed-fresh 3.13 `.venv`.

> **Mission-closing correction (appended after the fact — see
> `plan.md`'s matching correction on its IC-05 section for the full
> rationale).** T001 as written above instructs re-syncing the
> checkout's own `.venv` to 3.13. **Do not follow this literally**: this
> checkout's `.venv` is WP01's authoritative 3.11 baseline-measurement
> environment (`evidence-baseline-3.11.md`), and re-syncing it to 3.13
> here would silently destroy that baseline for any later reader running
> `.venv/bin/python -V`. This WP's actual dispatch overrode T001 to use a
> dedicated `UV_PROJECT_ENVIRONMENT=.venv313` project environment
> instead, confirming `.venv/bin/python -V` stayed `Python 3.11.15`
> throughout — recorded in full in
> `evidence-remeasurement-3.13.md`'s opening discrepancy note. The
> corrected instruction: use a dedicated `UV_PROJECT_ENVIRONMENT` (e.g.
> `.venv313`) for a second-interpreter measurement run, never the
> checkout's own `.venv`. The original T001 text above is left
> unmodified, per this mission's append-only correction convention.

## Subtask T002: Run the re-measurement

**Purpose**: Produce the clean, post-fix 3.13 figure.

**Steps**:
1. Run, in the **foreground**, with an **explicit bounded timeout of 900s**
   (per plan.md's "Re-measurement (FR-004, Edge Case (b))" section —
   comfortably above the ~411s baseline, per NFR-001/SK-99 — never relying
   on a shell/tool default):
   ```bash
   .venv/bin/python -m pytest -m "fast or unit" -q -n auto \
     --junitxml=out/reports/xunit-remeasure-3.13.xml
   ```
2. Do not retry-to-green and do not re-run repeatedly hoping for a
   different number — this is a single, recorded measurement. If the run
   itself fails to complete (e.g. a genuine environment problem, not a test
   failure), diagnose and fix the environment issue, then re-run once and
   record that as the measurement — do not average or discard runs.

**Files**: `out/reports/xunit-remeasure-3.13.xml` (build artifact — not a
tracked repo file; do not commit it). Create
`kitty-specs/interpreter-matrix-3-13-env-and-divergence-01M34HVD/evidence-remeasurement-3.13.md`
and write the command and raw summary line into it now.

**Validation**: The command completed within the 900s timeout; exact
pass/fail/error counts captured.

## Subtask T003: Record the failure-ID diff

**Purpose**: Produce the falsifiable comparison WP06 and the PR body need.

**Steps**:
1. Compare this run's failure/error test-ID set against:
   a. WP01's recorded 3.11 baseline (21 failed) — which IDs are new on 3.13
      relative to 3.11?

      > **Mission-closing correction:** this prose paraphrases WP01's
      > baseline as "21 failed." The actual recorded artifact,
      > `evidence-baseline-3.11.md`, records **20 failed** (the count is
      > explained there). WP05's own evidence file
      > (`evidence-remeasurement-3.13.md`) already flagged this
      > discrepancy and used the real 20-ID artifact, not this prompt's
      > "21" paraphrase, per this same subtask's own instruction to diff
      > against "WP01's recorded 3.11 baseline" (the artifact, not a
      > paraphrase of it). This note is appended here so the discrepancy
      > is visible at its source, not only in the evidence file that
      > resolved it. The original "21 failed" text above is left
      > unmodified, per this mission's append-only correction convention.
   b. The 4 `dir_fd` failures WP02 already fixed — confirm they do NOT
      appear in this run's failure set (if they do, WP02's fix did not
      actually land cleanly on this branch state — flag this immediately,
      do not proceed to WP06 with that unresolved).
2. Record: the exact command, the exact `N failed, M passed, ...` summary
   line, and the full failure-ID set with the diff against both comparison
   points from step 1.
3. This recorded evidence is what supersedes the original "429" figure for
   every subsequent scoping decision in this mission (per FR-004's
   acceptance criterion) — make sure it is complete enough that WP06 and
   PR-prep don't need to re-derive anything from your raw pytest output.

**Files**: append the failure-ID diff to
`evidence-remeasurement-3.13.md` (same file as T002) — this is the file WP06
and PR-prep read, so it must be complete before this WP is marked done.

**Validation**: A complete, recorded re-measurement with the two comparison
diffs (vs. 3.11 baseline, vs. WP02's 4 fixed IDs) explicitly stated.

## Definition of Done

- [ ] T001: fresh 3.13 `.venv` sync confirmed
      (`spec-kitty agent tasks mark-status T001 --status done`).
- [ ] T002: `fast or unit` / `-n auto` re-measurement run to completion
      within a 900s bounded foreground timeout
      (`spec-kitty agent tasks mark-status T002 --status done`).
- [ ] T003: failure-ID diff recorded against both the 3.11 baseline (WP01)
      and WP02's 4 fixed `dir_fd` IDs
      (`spec-kitty agent tasks mark-status T003 --status done`).

## Risks

- **Bounded-runtime discipline (NFR-001) is the primary risk** — this is
  exactly the kind of command SK-99 warns about (well over the 120s
  auto-background cliff). The 900s explicit timeout, run in the foreground,
  is mandatory, not optional.
- If WP04 landed the fallback branch (not a named-culprit fix), this
  re-measurement may still show some instability if the fallback mitigation
  doesn't fully eliminate the hazard for every possible call site — record
  what you actually observe; do not assume the environment is now perfectly
  stable just because WP04 completed.

## Reviewer Guidance

- Confirm the command actually ran with `-n auto` against the `fast or
  unit` selector specifically — not a narrower or broader selector.
- Confirm the 900s timeout was genuinely applied (ask how it was invoked —
  a tool-level timeout parameter, not a bare command that happened to finish
  quickly).
- Confirm the recorded failure-ID set is the *complete* set, not a
  truncated sample, and that both comparison diffs (vs. 3.11 baseline, vs.
  WP02's 4 IDs) are present and correctly computed.
- Confirm this WP's only tracked file change is its own
  `evidence-remeasurement-3.13.md` (plus the untracked `out/reports/` build
  artifact, which is not committed).

Implementation command: `spec-kitty agent action implement WP05 --agent claude`
