---
work_package_id: WP19
title: ADR amendments, contract reference, docs, inventories
dependencies:
- WP01
- WP02
- WP03
- WP04
- WP05
- WP06
- WP07
- WP08
- WP09
- WP10
- WP11
- WP12
- WP13
- WP14
- WP15
- WP16
- WP17
- WP18
requirement_refs:
- FR-013
- FR-014
planning_base_branch: issue-5510-ci-runtime-stabilisation
merge_target_branch: issue-5510-ci-runtime-stabilisation
branch_strategy: Planning artifacts for this mission were generated on issue-5510-ci-runtime-stabilisation. During /spec-kitty.implement this WP may branch from a dependency-specific base, but completed changes must merge back into issue-5510-ci-runtime-stabilisation unless the human explicitly redirects the landing branch.
subtasks:
- T077
- T078
- T079
- T080
- T081
- T082
phase: Phase 8 - Documentation and decision records
history:
- at: '2026-10-01T07:30:00Z'
  actor: system
  action: Prompt generated via /spec-kitty.tasks
agent_profile: scribe-sally
authoritative_surface: docs/
create_intent:
- tests/docs/test_ci_runtime_adr_amendments.py
execution_mode: code_change
model: claude-sonnet-5-5
owned_files:
- docs/adr/3.x/2026-09-23-1-auto-merge-required-checks-gate.md
- docs/adr/3.x/2026-09-26-1-ci-coverage-honesty.md
- docs/development/testing/testing-parallel.md
- docs/development/reference/ci-gate-mechanics.md
- docs/development/reference/known-friction-points.md
- docs/development/how-to/pr-landing.md
- docs/development/docs-retrieval-index.yaml
- tests/release/pinning_rule_inventory.json
- tests/release/coverage_breadth_evidence.md
- tests/docs/test_ci_runtime_adr_amendments.py
role: implementer
tags: []
task_type: implement
tracker_refs: []
---

# Work Package Prompt: WP19 – ADR amendments, contract reference, docs, inventories

## ⚡ Do This First: Load Agent Profile

Use the `/ad-hoc-profile-load` skill to load the agent profile specified in the frontmatter (or any user-defined profile), and behave according to its guidance before parsing the rest of this prompt.

- **Profile**: `scribe-sally`
- **Role**: `implementer`
- **Agent/tool**: `claude`

If no profile is specified, run `spec-kitty agent profile list` and select the best match for this work package's `task_type` and `authoritative_surface`.

---

## ⚠️ IMPORTANT: Review Feedback

**Read this first if you are implementing this task!**

- **Has review feedback?**: Check the `review_ref` field in the event log (via `spec-kitty agent tasks status` or the Activity Log below).
- **You must address all feedback** before your work is complete. Feedback items are your implementation TODO list.
- **Report progress**: As you address each feedback item, update the Activity Log explaining what you changed.

---

## Review Feedback

*[If this WP was returned from review, the reviewer feedback reference appears in the Activity Log below or in the status event log.]*

---

## Markdown Formatting

Wrap HTML/XML tags in backticks: `` `<div>` ``, `` `<script>` ``
Use language identifiers in code blocks: ````python`,````bash`

---

## Objectives & Success Criteria

Make the decision records and developer docs describe the CI that WP01–WP18 **actually
shipped**, and regenerate the derived inventories once, last (D-19, D-25, D-33). This WP writes
prose and runs generators, and adds exactly one red-first static test that pins the two ADR
amendments (charter ATDD-First Discipline binds every implementation WP). It changes no
workflow, script or existing test logic.

Done means:

1. ADR `2026-09-26-1-ci-coverage-honesty.md` has an appended, dated amendment. It covers the
   nightly architectural backstop, the always-on fast gate plus the two-leg battery, the
   partition proof, and the CI worker policy. It **corrects** the false Consequences claim at
   line 59 ("A green **nightly** now means the full suite ran"), which was untrue for
   `tests/architectural` (18.6% coverage, SC-003 baseline). The accepted text stays untouched.
2. ADR `2026-09-23-1-auto-merge-required-checks-gate.md` has an appended, dated amendment for
   skip-if-green on `ready_for_review`. It states that a required gate may pass on matched
   prior-run evidence **under exactly the tested key** `(workflow, PR, head SHA, merge-commit
   first parent)`. The accepted text stays untouched.
3. Both amendments link to this Mission's contracts:
   `kitty-specs/ci-runtime-stabilisation-01M3TZH6/contracts/router-two-authority-amendment.md`
   and `.../contracts/green-match.md`. This WP does **not** edit anything under `kitty-specs/`.
   The contract amendment already exists, and the original contract is byte-frozen by
   `tests/architectural/test_archive_root_byte_identical.py` (D-10).
4. The testing/CI docs describe the shipped job names, and their `updated:` dates are bumped.
   Stale names are fixed: `tests-corpus`, `integration-tests-core-misc (architectural)`,
   `fast-tests-cli`, and the "run `tests/architectural/` locally" advice that contradicts
   `NO_FULL_HEAVY_SUITES_IN_MISSION`.
5. The docs retrieval index is regenerated. `docs_index.py --strict`,
   `check_docs_freshness.py --ci` (errors=0), spelling, description-length and the terminology
   guard are all green.
6. `tests/release/pinning_rule_inventory.json` is regenerated once, last, and
   `tests/release/test_pinning_inventory_fresh.py` is green. `coverage_breadth_evidence.md`
   carries a dated footnote, not a rewrite.
7. `tests/docs/test_ci_runtime_adr_amendments.py` exists, was committed **red first** (before either ADR
   amendment), and is green on the final tip. It is collected per PR by the router
   `tests (docs)` job (`pytest tests/docs -q`, path group `docs` covers `tests/docs/**` and
   `docs/**`) and nightly by the interpreter sweep (`fast or unit` over `tests/docs`).

Acceptance anchors:

- **FR-014**: the ADR amendments, the contract reference and the docs.
- **FR-013 (prose half)**: the docs describe the registry-held battery truthfully. The registry
  YAML itself is WP05's.
- **C-011 is not this WP's requirement**: the evidence file
  `kitty-specs/ci-runtime-stabilisation-01M3TZH6/evidence/ci-measurements.md` (≥ 3 run IDs per
  NFR-001…006) is written by the **orchestrator at closeout**, after the PR's CI and the
  dispatched runs (tasks.md "Orchestrator closeout"). The amendments only cite it by path and
  quote its run IDs when it exists.
- **#4351 / #4729 (verified-already-fixed, spec §Assumptions)**: T082 records the evidence the
  issue-matrix verdicts point at.

## Context & Constraints

Read, in order:

- `research.md`: the decision log D-01…D-36 (D-19, D-25, D-32, D-33, D-34 govern this WP), then
  R3 §4.1–§4.6 (the amendment convention and per-file guidance).
- `spec.md` (FR-001…FR-014, SC-001…SC-006); `contracts/` (all three files);
  `plan.md` IC-12.
- The **shipped** diffs of WP01–WP18 on the mission branch. Document what merged, not what was
  planned. Where a WP recorded a deviation in its Activity Log, the deviation wins. Examples:
  WP16's A4 attempt binding, WP18's residual lanes, WP04's escalation step on the merged #5521
  triage CLI, WP13's #5503 "verified covered" record (D-37).

Live anchors, verified 2026-10-01 (re-verified post-rebase on `bc826fcbcb`, D-37: only
`ci-gate-mechanics.md`, the retrieval index and `page-inventory.yaml` changed among these files):

- `docs/adr/3.x/2026-09-26-1-ci-coverage-honesty.md`, 83 lines:
  - frontmatter at 1–6 has **no `updated:` field**;
  - its `description` is **177 characters**;
  - `## Decision` is at 30; part 3 (nightly `integration-next`) is at 46–51;
  - `## Consequences` is at 57; the false claim is at 59–60;
  - `## Alternatives Considered` is at 76.
- `docs/adr/3.x/2026-09-23-1-auto-merge-required-checks-gate.md`, 94 lines:
  - `updated: '2026-09-23'` is at line 6; its `description` is **178 characters**;
  - the required-context table is at 40–44;
  - §"Why `CI Aggregate gate` is deliberately NOT required" is at 68–79;
  - `## Consequences` is at 81.
- **Description band**: 50–180 characters, a hard limit (`scripts/docs/description_length_check.py`;
  `ci-gate-mechanics.md` §"A new docs page needs triple registration"). Both ADR descriptions are
  already at 177/178, so **do not extend them**. R3 §4.2 suggests extending, but that would
  breach the band. Leave each `description` unchanged. If you must reword one, re-count it to
  ≤ 180.
- The ADR index `docs/adr/3.x/index.md` rows (210, 212) use the **title**, not the description,
  so no index edit is needed while the titles stay unchanged.
- `docs/development/page-inventory.yaml` is keyed on `tag`, `divio_type`, `owning_workstream`,
  `current_target` and `notes`, not on `updated`. Do not regenerate it unless those keys change.
- Amendment heading precedent: `## Amendment (2026-09-22)` (in `2026-07-23-2-…:176`) and
  `## Amendment (2026-06-21 — mission …)` (in `2026-06-19-1-…:17`). Use
  `## Amendment (YYYY-MM-DD) — <topic> (mission ci-runtime-stabilisation, #5510)`, with the date
  from `date -u +%F` on the day you write it. Precedent for ADRs linking into `kitty-specs/`:
  `2026-07-08-1-mission-resolver-port.md`.
- `docs/development/reference/ci-gate-mechanics.md` (`updated: '2026-10-01'` since #5503):
  - §"How CI is wired" at 27–49; line 47 says "`architectural-heavy` job runs the full battery
    on code PRs";
  - §"New `contracts/*.md` YAML blocks…" at 112; line 114 names `tests-corpus`, deleted by WP09
    (its round-trip file now runs in WP10's `tests (corpus-blocking)`);
  - §"The architectural gate battery" at 150; #5503 replaced its hash-refresh subsection with
    §"Moving or renaming a symbol that is dead-symbol allowlisted" at 186 (ADR
    `docs/adr/4.x/2026-10-01-1-dead-symbol-allowlist-module-name-identity.md`). Leave it as is.

  Headings referenced by tests must **not** be renamed. PR #5503's edits to this file and the
  retrieval index are already on the base (D-37); no pre-edit rebase is needed for it.
- `docs/development/testing/testing-parallel.md` (`updated: '2026-09-30'`): §"The local command"
  at 26; the local `-n auto` recipes at 262 and 271 **stay**, because C-005 leaves local
  parallelism unchanged; §"CI shard-topology mission status" is at 280.
- `docs/development/reference/known-friction-points.md:77` names the `architectural-heavy`
  battery as the CI-only gate.
- `docs/development/how-to/pr-landing.md`:
  - 535–539: `integration-tests-core-misc (architectural)` plus "Run `tests/architectural/`
    locally", which contradicts `NO_FULL_HEAVY_SUITES_IN_MISSION`;
  - 541–543: `fast-tests-cli`;
  - 547–548: a dated 2026-08-04 anecdote naming `fast-tests-agent`. Keep the anecdote as
    history, and mark the name as the then-current one.
- `tests/release/coverage_breadth_evidence.md:348` is a prior Mission's measured evidence naming
  `architectural-heavy`. Its top-of-file footnote (lines 4–10) is the precedent for a dated
  footnote.
- `tests/release/pinning_rule_inventory.json` is derived by `scripts/ci/derive_pinning_inventory.py`
  and gated by `tests/release/test_pinning_inventory_fresh.py`. It is **green on base
  `bc826fcbcb`**: main's `e3794ded2d` added the #3143 entry for
  `tests/architectural/test_pytest_ini_timeout_default.py::<module-docstring>` and #5523 is
  CLOSED (issue-matrix verdict verified-already-fixed; D-37). Your final regeneration therefore
  covers only this mission's own line shifts.

Constraints:

- Amend by appending dated sections only. **Never edit accepted ADR text.**
- Do not edit `kitty-specs/`: not the contracts, not the evidence file, not WP files.
- Terminology: use "Mission", never "feature"; use `status commit`, never "ceremony" or
  "status-writing". Never write bare "routing": write "CI path routing", "gate selection" or
  "selection-step suppression". Name the sense of `primary`/`merge` if you use them.
- `NO_FULL_HEAVY_SUITES_IN_MISSION`: never run `tests/architectural` as a directory, and never
  run `make test-full`.

## Branch Strategy

- **Strategy**: {{branch_strategy}}
- **Planning base branch**: {{planning_base_branch}}
- **Merge target branch**: {{merge_target_branch}}

> These fields are populated automatically by `spec-kitty agent mission finalize-tasks`.
> Do NOT change them manually unless you are certain the branch topology has changed.

## Subtasks & Detailed Guidance

### Subtask T077 – ADR 2026-09-26-1 amendment: backstop, sharded battery, worker policy

- **Purpose**: Record the FR-001–FR-005 and FR-013 decisions and honestly correct the
  Consequences claim (D-19, R3 §4.3). It opens with this WP's red-first test (ATDD-First).
- **Steps**:
  0. **Red-first (commit this before any ADR edit).** Create `tests/docs/test_ci_runtime_adr_amendments.py`
     (`pytestmark = [pytest.mark.fast]`, stdlib + `pathlib` only, reading files relative to the
     repo root). It asserts, as separate tests:
     - `docs/adr/3.x/2026-09-26-1-ci-coverage-honesty.md` contains a dated H2 matching
       `^## Amendment \(\d{4}-\d{2}-\d{2}\)` whose section body names the nightly
       architectural backstop (`architectural-backstop`) and links
       `kitty-specs/ci-runtime-stabilisation-01M3TZH6/contracts/router-two-authority-amendment.md`;
     - `docs/adr/3.x/2026-09-23-1-auto-merge-required-checks-gate.md` contains a dated
       `## Amendment (YYYY-MM-DD)` H2 whose section body records the ready-for-review
       skip-if-green rule (`ready_for_review`, the tested key) and links
       `kitty-specs/ci-runtime-stabilisation-01M3TZH6/contracts/green-match.md`;
     - every linked `contracts/` file resolves to an existing file (relative link resolved from
       the ADR's directory).

     Slice each amendment section from its heading to the next H2 (or end of file), so a link
     elsewhere in the ADR cannot satisfy the test. Run
     `uv run --frozen pytest tests/docs/test_ci_runtime_adr_amendments.py -q`, confirm it is **red** on today's ADRs (no amendment
     sections), and commit it alone with the red output in the commit body. Verify it is
     collected by the router `tests (docs)` job (`pytest tests/docs -q`; the `docs` path group
     covers `tests/docs/**`) — no workflow edit is needed.
  1. Gather the facts from the merged diffs:
     - WP04: the job name `architectural-backstop` in `ci-nightly.yml`; its base command (no
       partition plugin); `-n 4`; the 40-minute timeout; its place in `nightly-summary.needs`
       and the escalation key; how the release nightly gate reads the overall nightly
       conclusion.
     - WP05, WP06, WP12, WP14: the `architectural-fast` always-on roster held in
       `.github/ci-module-registry.yml` `special_tiers.architectural`; `architectural-heavy` as
       one job key with a two-leg `include:` matrix (`--battery-part 1/2`, `2/2`); the static
       partition proof in `_gate_coverage`; the per-file timings seed.
     - WP12: the literal `-n 4` in CI legs, the backstop and the Packs corpus, guarded by
       `tests/ci/test_xdist_worker_policy.py`. The local `Makefile` keeps `-n auto` (C-005).
  2. Append after `## Alternatives Considered`:
     `## Amendment (YYYY-MM-DD) — nightly architectural backstop, sharded battery, CI worker policy (mission ci-runtime-stabilisation, #5510)`.
     Use three sub-paragraphs:
     - **Context**: before this amendment, the nightly ran `tests/architectural` only under the
       `fast or unit` filter, which is 18.6% of the battery. So the line-59 claim "A green
       nightly now means the full suite ran" did not hold for `tests/architectural`. Cite #3265
       (folded) and #4708.
     - **Decision**: the backstop, the fast + two-leg battery with its partition proof, the
       worker policy, and the `ci_config` path group that selects the battery for CI-config
       changes (contract amendment A1). Link to the router-two-authority amendment with the
       relative path
       `../../../kitty-specs/ci-runtime-stabilisation-01M3TZH6/contracts/router-two-authority-amendment.md`.
     - **Consequences**: the line-59 guarantee now holds for the architectural battery,
       because the backstop executes the full per-PR base selection. Main's nightly was red when
       this landed (P0s #5418/#5505/#5506/#5507, D-32), so the backstop is judged on its own
       job conclusion. The battery stays non-required (C-004). Measurements live in the mission
       evidence file (C-011): cite
       `kitty-specs/ci-runtime-stabilisation-01M3TZH6/evidence/ci-measurements.md` by path and
       quote the run IDs it records. If that file does not exist yet, write "recorded in the
       mission evidence file" and flag it to the orchestrator.
  3. Add `updated: 'YYYY-MM-DD'` after `date:` in the frontmatter. ADRs need `date:` and
     `updated:` (ci-gate-mechanics §registration). Leave the 177-character `description`
     unchanged.
- **Files**: `docs/adr/3.x/2026-09-26-1-ci-coverage-honesty.md`.
- **Parallel?**: It can run alongside T078.
- **Notes**: Do not touch lines 1–83 except the new `updated:` line. Correct the claim only
  inside the amendment ("This amends the Consequences bullet at …"). Do not strike it in place.

### Subtask T078 – ADR 2026-09-23-1 amendment: skip-if-green on ready-for-review

- **Purpose**: Record that a required gate may now pass on matched prior-run evidence, and
  bound exactly when (FR-011, D-15, D-16, R3 §4.2).
- **Steps**:
  1. Gather the facts from WP16, WP17 and WP18 as merged: the helper's subcommands; the tested
     key; the artifact names `ci-tested-key-pr<N>-base-<sha>` and
     `ci-green-match-run-<id>-attempt-<n>`; the attempt binding of markers (WP16 row A4, if
     shipped); WP18's recorded residuals; and WP17's fail-closed behaviour.
  2. Append after `## Consequences`:
     `## Amendment (YYYY-MM-DD) — skip-if-green on ready-for-review (mission ci-runtime-stabilisation, #5510)`.
     It needs:
     - **Decision**: on a `pull_request` `ready_for_review` event, the selection jobs of the
       router, CI Modules and Packs suppress their path-filter step when a completed,
       successful, same-workflow run carries a non-expired tested-key marker for the identical
       key. The required contexts (`router gate`, `CI Modules gate`) still post success on the
       PR head, so the required-check model of this ADR is unchanged.
     - **Never suppressed**: push, `workflow_dispatch`, `workflow_call`, schedule, any attempt
       after the first, any other `pull_request` action, a prior run that is failed, cancelled
       or in progress, a moved base, and any lookup error.
     - **Escape hatch**: re-run the workflow. Attempt 2 always executes.
     - **CI Aggregate**: `collect` re-points to the matched CI Modules run after re-verifying
       head, workflow, event, success and tested identity, and fails closed otherwise. Fleet
       Verdict binds by the skip run's display title.
     - **Evidence caveat**: the Aggregate half was verified offline in-mission and live after
       merge (D-16), because `workflow_run` executes `main`'s copy.
     - **Links**: `contracts/green-match.md` and `contracts/router-two-authority-amendment.md`
       (A4: event-level suppression, not a third CI path routing authority), both under
       `../../../kitty-specs/ci-runtime-stabilisation-01M3TZH6/`.
  3. Bump `updated:` (line 6) to the amendment date. Leave the 178-character `description`
     unchanged.
- **Files**: `docs/adr/3.x/2026-09-23-1-auto-merge-required-checks-gate.md`.
- **Parallel?**: It can run alongside T077.
- **Notes**: Do not add `CI Aggregate gate` to any required-context wording. It stays
  deliberately not required (ADR §68–79).

### Subtask T079 – Testing/CI docs: shipped job names, `updated:` bumps, stale names

- **Purpose**: Make the operator-facing docs match the shipped CI (FR-014, FR-013 prose, D-33).
- **Steps**:
  1. **Rebase onto current `main` first** (#5503 is already on the base, D-37; any later
     docs edit on main is handled the same way). Never hand-merge the retrieval index; T080
     regenerates it.
  2. `ci-gate-mechanics.md`:
     - §"How CI is wired": add one compact paragraph or list covering:
       - the always-on `architectural-fast` gate plus the two `architectural-heavy` legs;
       - `ci_config` changes selecting the battery;
       - Packs as the sole, advisory corpus owner, with the orphaned corpus tests (40 on base `bc826fcbcb`; WP10 records the shipped count) blocking in
         `tests (corpus-blocking)`;
       - the removed router `tests (cli|status|consolidation|corpus)` jobs, whose module rows
         are now their homes;
       - skip-if-green on ready-for-review.

       Rewrite line 47's clause to name the fast gate and the two legs.
     - Line 114: `tests-corpus` becomes the WP10 job name. Check the job key and display name
       in `ci-router.yml` and quote them exactly.
     - §"The architectural gate battery" (150): add the fast roster and the shard legs, and
       note that the fast roster's budgets live in the registry.
     - Bump `updated:`.
  3. `testing-parallel.md`: add a section **"CI worker policy and the nightly architectural
     backstop"** before §"CI shard-topology mission status". Cover:
     - literal `-n 4` in CI (battery legs, fast gate, backstop, Packs corpus), with xdist's
       `created: 4/4 workers` line as evidence;
     - `-q` dropped for that reason;
     - the static guard `tests/ci/test_xdist_worker_policy.py`;
     - local `make test-*` keeping `-n auto` (C-005).

     Keep the local `-n auto` recipes. Bump `updated:`.
  4. `known-friction-points.md:77`: name `architectural-fast` (fast, always-on) and the two
     `architectural-heavy` legs. Bump `updated:`.
  5. `pr-landing.md`:
     - 535–539: replace the retired shard name with the shipped battery jobs. Replace "Run
       `tests/architectural/` locally" with "run the specific `tests/architectural/` gate files
       your diff implicates (`NO_FULL_HEAVY_SUITES_IN_MISSION`)", matching
       `known-friction-points.md:82-85`.
     - 541–543: replace `fast-tests-cli` with a current example, for example a module row such
       as `module-tests (cli shard 1/1)`. Verify the name against `ci-modules.yml`'s `test` job
       `name:`.
     - Keep the 2026-08-04 anecdote and qualify the name as the then-current job name.
     - Bump `updated:`.
  6. Write prose in plain declarative sentences: no marketing tone, no em-dash chains, and
     never bare "routing".
- **Files**: the four docs pages above.
- **Parallel?**: After T077 and T078, so the cross-links resolve.
- **Notes**:
  - `docs/development/testing/testing-flakiness.md` changes only if WP12 changed timeout
    guidance. Per D-08 it did not; leave it.
  - Do not edit `.github/ci-module-registry.yml` comments; WP05 owns them.

### Subtask T080 – Retrieval index regeneration and docs gates

- **Purpose**: The new `## Amendment` H2s and the new docs section change heading anchors, so
  the committed retrieval index must be regenerated or the docs gates go red (R3 §4.1).
- **Steps**:
  1. Regenerate. The script path was verified on 2026-10-01; the exact command is the one
     `tests/docs/test_docs_index_freshness.py:104` prints:
     ```bash
     PYTHONPATH=. uv run --frozen python scripts/docs/docs_index.py --write
     PYTHONPATH=. uv run --frozen python scripts/docs/docs_index.py --strict   # expect drift=False
     ```
  2. Run the docs gates:
     ```bash
     PYTHONPATH=. uv run --frozen python scripts/docs/check_docs_freshness.py --ci   # errors=0; external-URL warnings are fine
     PYTHONPATH=. uv run --frozen python scripts/docs/description_length_check.py --strict --changed-from "$(git merge-base HEAD main)"
     uv run --frozen python -m scripts.docs.check_spelling
     uv run --frozen pytest tests/docs/test_docs_index_freshness.py tests/docs/test_docs_index.py -q
     uv run --frozen pytest tests/architectural/test_no_legacy_terminology.py -q
     ```
     The description-length CLI was verified on 2026-10-01. It needs `PYTHONPATH=.`, is
     report-only unless you pass `--strict`, and `--changed-from` scopes it to your diff.
  3. Run `grep -nE '\bfeatures?\b|\brouting\b' <edited files>` over your **added** lines only,
     using `git diff -U0`. Fix any bare "routing" or "feature" you introduced. Pre-existing text
     is out of scope.
  4. If `main` moved after your regeneration and the rebase touches the index, regenerate again.
     The index is always regenerated, never hand-merged.
- **Files**: `docs/development/docs-retrieval-index.yaml` (generated).
- **Parallel?**: After T077, T078 and T079.
- **Notes**: `page-inventory.yaml` needs no regeneration unless an inventory-keyed frontmatter
  field changed. Adding `updated:` to an ADR is not one of those fields. If
  `check_docs_freshness.py --ci` reports `INVENTORY-LOCKFILE-DRIFT` anyway, stop and report it.
  It is not in this WP's owned files.

### Subtask T081 – Final pinning-inventory regeneration and the evidence-file footnote

- **Purpose**: D-25: the pinning inventory is regenerated once more, in the final WP, and never
  hand-merged. D-33: retired job names in prior-Mission evidence get a dated note, not a
  rewrite.
- **Steps**:
  1. After rebasing onto the final mission tip (all of WP01–WP18 merged), run:
     ```bash
     python3 scripts/ci/derive_pinning_inventory.py
     python3 scripts/ci/derive_pinning_inventory.py --check
     uv run --frozen pytest tests/release/test_pinning_inventory_fresh.py -q
     ```
     Then inspect `git diff --stat tests/release/pinning_rule_inventory.json`. Expect:
     - no #3143 row in the diff (it is already on the base since `e3794ded2d`, D-37);
     - line shifts from the pinned-file edits in WP06, WP08, WP09, WP10, WP12 and WP15 (the
       lane-a WPs that regenerate per tasks.md Global rules), plus any deltas the non-regenerating
       WPs recorded in their Activity Logs.

     Any **new rule** carrying a non-`none` disposition needs its reason read, not
     rubber-stamped. List such rules in the PR body.
  2. `tests/release/coverage_breadth_evidence.md`: add a dated footnote block right after the
     existing #4334 slice-count footnote (lines 4–10), headed
     `> **Job-name footnote (#5510, added YYYY-MM-DD).**`. It should say:
     - `architectural-heavy` (cited at §8, line 348) is now a two-leg matrix beside an
       always-on `architectural-fast` job;
     - the battery still emits no coverage artefact, so §8's "0 statements marginal
       contribution" conclusion is unchanged.

     Do not edit the measured prose.
  3. Run the terminology guard over the footnote, as in T080.
- **Files**: `tests/release/pinning_rule_inventory.json` (generated),
  `tests/release/coverage_breadth_evidence.md`.
- **Parallel?**: Last, on the final tip.
- **Notes**:
  - `coverage_breadth_baseline.json` is its machine-readable companion and is not touched.
  - If the regeneration produces a delta from a WP outside this mission (an upstream drift on
    rebase), keep it. The inventory is derived; record the cause in the PR.

### Subtask T082 – Verify and evidence #4351 and #4729 (verified-already-fixed)

- **Purpose**: spec.md records #4351 and #4729 as already fixed. Their issue-matrix verdicts
  (`verified-already-fixed`) need evidence pointers, not a claim. This subtask produces them; it
  changes no code.
- **Steps**:
  1. **#4351 — status-aggregate tests are collected per PR.** Prove
     `tests/unit/status/test_mission_status_aggregate.py` is selected by a CI job on the final
     mission tip: the registry `unit` module row (`.github/ci-module-registry.yml`,
     `test_dirs: [tests/unit]`) runs in `module-tests.yml`. Run that row's exact collection
     (collect-only, allowed under C-009), e.g.
     `uv run --frozen python -m pytest tests/unit -m "not performance and not stress" --collect-only -q | grep test_mission_status_aggregate.py | wc -l`
     — use the marker the module-tests command actually passes (WP01's shared marker constant),
     and record the node-id count (> 0) plus the job/row name. If WP15's `_live_uniqueness.py`
     exposes the per-job node-id sets, cite it instead.
  2. **#4729 — the nightly `integration-next` tier is wired.** Cite commit `1e290b09ae`
     (`feat(ci): nightly integration+next lane …`) and show on the final tip that
     `.github/workflows/ci-nightly.yml` still has job `integration-next` running
     `pytest tests/integration tests/next` and that it is in `nightly-summary.needs` (one `grep`
     each; quote the line numbers). Optionally add the URL of one recent green nightly run's
     `integration-next` job (`gh run list --workflow ci-nightly.yml`).
  3. Append one Activity Log entry per issue: `#4351 verified-already-fixed — <evidence>` and
     `#4729 verified-already-fixed — <evidence>`, quoting the `#` exactly as the issue-matrix
     verdict cites it (the approve gate requires every cited issue to carry a verdict).
- **Files**: none (Activity Log only).
- **Parallel?**: Yes, with T077–T080; read-only.
- **Notes**: If either check fails (the file is no longer collected, or the nightly job was
  removed/renamed by a lane), stop and raise it with the orchestrator — the verdict is then not
  "already fixed".

## Test Strategy

This WP adds one red-first static test, `tests/docs/test_ci_runtime_adr_amendments.py` (T077 step 0), which pins
both dated ADR amendments and their contract links; it is red before T077/T078 and green after.
The rest of FR-014 is prose: its other guards are the docs-freshness checks, the
retrieval-index freshness tests, spelling, description length and terminology. Run these
exactly:

```bash
PYTHONPATH=. uv run --frozen python scripts/docs/docs_index.py --strict
PYTHONPATH=. uv run --frozen python scripts/docs/check_docs_freshness.py --ci
uv run --frozen python -m scripts.docs.check_spelling
uv run --frozen pytest tests/docs/test_ci_runtime_adr_amendments.py tests/docs/test_docs_index_freshness.py tests/docs/test_docs_index.py tests/release/test_pinning_inventory_fresh.py tests/architectural/test_no_legacy_terminology.py tests/architectural/test_archive_root_byte_identical.py -q
uv run --frozen ruff format --check .
make test-fast
```

`test_archive_root_byte_identical.py` proves no frozen `kitty-specs/` contract was edited.
Record the exact commands and counts in the PR's *Tests run* section.

## Risks & Mitigations

- **Generated-file collisions with later main edits** (`ci-gate-mechanics.md`, retrieval index;
  #5503's are already absorbed, D-37). Mitigation: rebase first, and regenerate the index; never
  hand-merge it.
- **Escalation description** — PR #5521 has merged: describe the backstop's escalation exactly as
  WP04 merged it, including the automatic triage (type Bug, `from:ci`, milestone, parent #5106).
- **Description band breach** (both ADR descriptions are at 177/178 of 180). Mitigation: leave
  them unchanged.
- **Documenting the plan rather than the merge.** Mitigation: read each WP's merged diff and
  Activity Log. Deviations, residuals and post-merge follow-ups appear in the docs as they were
  recorded.
- **Editing accepted ADR text.** Mitigation: append only. The reviewer diffs the pre-amendment
  line range.

## Review Guidance

- The first WP19 commit adds only `tests/docs/test_ci_runtime_adr_amendments.py`, and its commit body shows it red
  on the pre-amendment ADRs; the test is green on the final tip and slices each amendment
  section (a link elsewhere in the ADR does not satisfy it).
- `git diff` of each ADR shows additions only below the last pre-existing section, plus the
  `updated:` line.
- The 2026-09-26-1 amendment explicitly corrects the line-59 claim and cites the 18.6%
  baseline.
- The 2026-09-23-1 amendment states the exact tested key, the never-suppressed cases, the escape
  hatch, and that the required-context set is unchanged.
- Both amendments link to the in-mission contracts, and nothing under `kitty-specs/` changed.
- Every edited docs page has a bumped `updated:`. The retrieval index regenerates cleanly
  (`drift=False`). Freshness reports `errors=0`. Terminology and spelling are green.
- T082: the Activity Log carries one evidence entry each for #4351 (collection count + job) and
  #4729 (commit `1e290b09ae` + `integration-next` in `nightly-summary.needs` on the final tip).
- The pinning inventory was regenerated, not hand-edited. The diff carries no #3143 row (fixed on
  main by `e3794ded2d`; #5523 closed, D-37).

## Activity Log

> **CRITICAL**: Activity log entries MUST be in chronological order (oldest first, newest last).

### How to Add Activity Log Entries

**When adding an entry**:

1. Scroll to the bottom of this Activity Log section
2. **APPEND the new entry at the END** (do NOT prepend or insert in middle)
3. Use exact format: `- YYYY-MM-DDTHH:MM:SSZ – agent_id – <action>`
4. Timestamp MUST be current time in UTC (check with `date -u "+%Y-%m-%dT%H:%M:%SZ"`)
5. Agent ID should identify who made the change (claude-sonnet-4-5, codex, etc.)

**Format**:

```
- YYYY-MM-DDTHH:MM:SSZ – <agent_id> – <brief action description>
```

**Example (correct chronological order)**:

```
- 2026-01-12T10:00:00Z – system – Prompt created
- 2026-01-12T10:30:00Z – claude – Started implementation
- 2026-01-12T11:00:00Z – codex – Implementation complete, ready for review
- 2026-01-12T11:30:00Z – claude – Review passed, all tests passing  ← LATEST (at bottom)
```

**Common mistakes (DO NOT DO THIS)**:

- Adding new entry at the top (breaks chronological order)
- Using future timestamps (causes acceptance validation to fail)
- Inserting in middle instead of appending to end

**Why this matters**: The acceptance system reads the LAST activity log entry as the current state. If entries are out of order, acceptance will fail even when the work is complete.

**Initial entry**:

- 2026-10-01T07:30:00Z – system – Prompt generated via /spec-kitty.tasks

---

### Updating Status

Status is managed via `status.events.jsonl`. Use `spec-kitty agent tasks move-task <WPID> --to <status>` to change WP status.

### Optional Phase Subdirectories

For large missions, organize prompts under `tasks/` to keep bundles grouped while maintaining lexical ordering.
