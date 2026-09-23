---
work_package_id: WP01
title: Baseline capture (3.11) + FR-005 pre-existing-failure issue
dependencies: []
requirement_refs:
- FR-005
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
- kitty-specs/interpreter-matrix-3-13-env-and-divergence-01M34HVD/evidence-baseline-3.11.md
execution_mode: planning_artifact
model: ''
owned_files:
- kitty-specs/interpreter-matrix-3-13-env-and-divergence-01M34HVD/evidence-baseline-3.11.md
role: implementer
tags: []
tracker_refs: []
---

# WP01 — Baseline capture (3.11) + FR-005 pre-existing-failure issue

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

Establish the recorded, falsifiable Python 3.11 `fast or unit` baseline
**before any implementation change lands** in this mission, and discharge the
charter's Pre-existing Failure Reporting Rule by opening a fresh GitHub issue
for the 21 pre-existing 3.11 failures (spec FR-005, plan IC-01).

## Context

This WP makes **zero source or test-file changes** — it owns exactly one new
planning-artifact file,
`kitty-specs/interpreter-matrix-3-13-env-and-divergence-01M34HVD/evidence-baseline-3.11.md`
(new file — declared under `create_intent` in this WP's frontmatter), which
records the read-only measurement plus the FR-005 GitHub issue reference. It
exists so every later WP (especially WP05's post-fix re-measurement) has a
recorded, falsifiable point of comparison instead of relying on memory or the
readiness report's prose figure. Per plan.md's "The baseline" section, the expected figure is
**21 failed / 34659 passed**, but this WP's job is to *record the real,
freshly-run* numbers — treat the 21/34659 figure as an expectation to
confirm, not a value to copy without running the command.

WP01 itself has `dependencies: []` in `wps.yaml` and is not blocked by any
other WP — it is this mission's root node. WP02/WP03/WP04 must each wait
for WP01: the 3.11 baseline must be captured before any change lands, so
pre-existing reds are not misattributed to this mission. **Per ledger
SK-25**, that ordering is an ordering constraint, not a data dependency —
nothing in WP02/WP03/WP04's own work consumes an artifact this WP produces
— so it is enforced by the orchestrator's **dispatch sequencing** (do not
dispatch WP02/WP03/WP04 until this WP is `approved`/`done`) and by prose in
each of their own task files, *not* by a `dependencies:` edge in
`wps.yaml` or `dependency_readiness_for_wp`: WP02/WP03/WP04's frontmatter
carries `dependencies: []`. (An earlier version of `wps.yaml` did encode
this as `dependencies: [WP01]` on all three; that edge produced a false
lane cycle — `lane-a -> lane-planning -> lane-a`, since this WP bundles
into `lane-planning` with WP05/WP06/WP07 — and was removed in the SK-25
remediation. See `tracer-tooling-friction.md`'s "Correction: SK-25" entry
for the full record.) This WP's output (the baseline failure-ID set) is
also the reference every later re-measurement diffs against — WP05 in
particular reads this WP's evidence file as a genuine data input (see
`tracer-tooling-friction.md`'s follow-up entry for why that edge is not
yet expressible as a `dependencies:` entry either).

**Why FR-005 needs a *fresh* issue**: `#3284` is **closed** (verify live with
`gh issue view 3284` — do not trust this prompt's paraphrase) and therefore
cannot serve as the "open report" the charter's Pre-existing Failure
Reporting Rule requires ("the agent MUST open a GitHub issue reporting them
before treating those failures as accepted baseline context"). `#4866` (this
mission's own issue) reports the *environment* defect (the `uv run` flags
bug), not these 21 pre-existing failures as their own tracked item. Spec.md's
FR-005 acceptance criterion already commits to opening a fresh issue as
option (a); this WP executes that commitment.

## Subtask T001: Run and record the 3.11 baseline

**Purpose**: Produce the authoritative, freshly-measured 3.11 `fast or unit`
figure this mission's later re-measurements are diffed against.

**Steps**:
1. Confirm you are on a Python 3.11 interpreter / synced `.venv`
   (`.venv/bin/python --version`; re-sync with
   `uv sync --frozen --all-extras --python 3.11` first if the checkout's
   `.venv` is not currently 3.11 — see SK-94 in
   `kitty-specs/interpreter-matrix-3-13-env-and-divergence-01M34HVD/tracer-tooling-friction.md`:
   a bare `uv sync` installs neither the `test` nor `lint` extra).
2. Run, in the **foreground**, with an **explicit bounded timeout of at
   least 600s** (per NFR-001 / SK-99 — the readiness report measured ~485s
   for this exact command on 3.11; never rely on a shell/tool default
   timeout):
   ```bash
   .venv/bin/python -m pytest -m "fast or unit" -q
   ```
3. Record the exact summary line (`N failed, M passed, ...`) and the full
   list of failing/erroring test node IDs. Expect approximately
   **21 failed / 34659 passed** per plan.md's "The baseline" — if your real
   run differs materially, record the real numbers and flag the
   discrepancy in your WP completion report; do not silently substitute the
   plan's expected figure for what you actually observed.

**Files**: `kitty-specs/interpreter-matrix-3-13-env-and-divergence-01M34HVD/evidence-baseline-3.11.md`
(new file — create it in this subtask). Write the exact command, the exact
summary line, and the full failure/error node-ID list into this file. T002
and T003 append to the same file rather than creating their own.

**Validation**: The command completed within the timeout, exit code and
summary line captured verbatim.

## Subtask T002: Confirm the pre-existing classification

**Purpose**: Satisfy the charter's "why they're believed pre-existing"
requirement with live evidence, not assumption.

**Steps**:
1. Verify `#3284` is closed: `gh issue view 3284` (unset `GITHUB_TOKEN`
   first if it errors on scope — `unset GITHUB_TOKEN && gh issue view 3284`;
   see AGENTS.md's "GitHub CLI Authentication" section).
2. Per AGENTS.md's baseline-red gotcha classification, confirm these are
   genuinely pre-existing by checking they also fail at the merge-base /
   `upstream/main` — since this mission has made no code changes yet at
   this point in the WP graph, the current branch tip **is** the merge-base
   for this purpose; note that explicitly rather than re-deriving a separate
   comparison run (a second full `fast or unit` run would cost another
   ~485s for no additional grounding value here).
3. Confirm none of the 21 failures are one of the charter's named honestly-red
   P0s (`#2736`, `#2772`, `#1834`) that should NOT be "fixed" — this is
   informational cross-referencing, not an action item; if any of the 21
   IDs match, note it, but do not attempt to fix them (out of this mission's
   C-001 blast radius regardless).

**Files**: append the `#3284`-closed confirmation and the pre-existing
rationale to `evidence-baseline-3.11.md` (same file as T001).

**Validation**: `#3284`'s closed state is confirmed live (not assumed from
this prompt), and the reasoning for "pre-existing" is grounded in the actual
command output from T001, not copied from the readiness report.

## Subtask T003: Open the FR-005 GitHub issue

**Purpose**: Discharge the charter's Pre-existing Failure Reporting Rule.

**Steps**:
1. Open a fresh GitHub issue (`gh issue create`) reporting the 21
   pre-existing 3.11 `fast or unit` failures. The issue body MUST include,
   per the charter's rule:
   - The exact command run (`​.venv/bin/python -m pytest -m "fast or unit" -q`).
   - The relevant failure summary (the exact `N failed, M passed` line from
     T001).
   - The full list of failing/erroring test node IDs from T001.
   - Why these are believed pre-existing rather than introduced by this
     mission's own change (T002's reasoning: this WP runs before any
     implementation change in this mission lands; `#3284`'s closed state
     means it cannot discharge this obligation on its own).
   - A cross-link to `#4866` (this mission's own issue) and a note that
     `#4866` itself covers the *environment*-pinning defect, not these 21
     failures.
2. Record the new issue's number/URL — this mission's PR-prep step links it
   from the mission's PR body (WP07 or PR-prep, not this WP, since the PR
   does not exist yet at this point in the WP graph). Carry the issue
   number forward in your completion report so PR-prep can find it without
   re-deriving it.
3. If, on inspection, some other currently-open issue already covers these
   21 specific failures (re-verify — do not assume `#3284` reopened or a
   duplicate already exists without checking), do not open a duplicate;
   instead record which existing issue covers them and why, matching FR-005's
   alternative option (b) — but per spec.md's own resolution, option (a) (a
   fresh issue) is the expected path, since the spec author already checked
   this and found no such issue at spec-authoring time. Re-verify only to
   catch drift between spec-authoring time and this WP's execution time.

**Files**: append the new issue's number/URL to `evidence-baseline-3.11.md`
(same file as T001/T002) — the deliverable itself is the GitHub issue, but
this file is where PR-prep finds its number without re-deriving it.

**Validation**: The issue exists, is publicly visible, and contains the
command, failure summary/list, and pre-existing rationale required by the
charter's Pre-existing Failure Reporting Rule and by spec.md's FR-005
acceptance criterion.

## Definition of Done

- [ ] T001: 3.11 `fast or unit` baseline run to completion within a ≥600s
      bounded foreground timeout; exact failed/passed counts and failure-ID
      list recorded (`spec-kitty agent tasks mark-status T001 --status done`).
- [ ] T002: pre-existing classification confirmed live against `#3284`'s
      closed state and the charter's baseline-red gotcha reasoning
      (`spec-kitty agent tasks mark-status T002 --status done`).
- [ ] T003: fresh GitHub issue opened (or an existing-issue exemption
      justified) with command, failure summary/list, and pre-existing
      rationale; issue number recorded for PR-prep
      (`spec-kitty agent tasks mark-status T003 --status done`).

## Risks

- **None material.** The only risk is skipping this WP (or running it after
  other WPs have already changed test behavior), which would make it
  impossible to cleanly distinguish pre-existing red from introduced red
  later in the mission. Running it first, as designed, avoids this.
- If the real T001 numbers differ materially from the plan's expected
  21/34659, do not silently reconcile them to match the plan — record what
  you actually observed and flag the discrepancy; it may indicate drift
  since the readiness report was captured.

## Reviewer Guidance

- Confirm the T001 command was actually run (not copied from the plan) —
  ask for the raw pytest summary line and a sample of failure IDs.
- Confirm `#3284`'s closed state was checked live, not assumed.
- Confirm the FR-005 issue exists, is linked to `#4866`, and contains all
  four required elements (command, summary, failure list, pre-existing
  rationale) — a stub issue without the failure list does not discharge the
  charter's rule.
- Confirm no source or test file was modified by this WP (it should be a
  pure read + one GitHub issue).

Implementation command: `spec-kitty agent action implement WP01 --agent claude`
