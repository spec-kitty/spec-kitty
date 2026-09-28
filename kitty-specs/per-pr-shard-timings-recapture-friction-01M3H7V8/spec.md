# Mission Specification: Per-PR charter shard-timings recapture friction

**Mission Branch**: `issue-5189-per-pr-shard-timings-recapture-friction`
**Created**: 2026-09-27
**Status**: Draft
**Input**: GitHub issue [#5189](https://github.com/spec-kitty/spec-kitty/issues/5189) — "Per-PR `test_module_length_agreement` forces a full ~18-min charter shard-timings recapture on any test-count change"

## Provenance

This mission is issue-directed. GitHub issue #5189 documents the friction (evidenced twice, on
PRs #5164 and #5175) and its owner, `MOES-Media`, claimed the mission and named the remedy
directly in an issue comment: *"Claiming: mission per-pr-shard-timings-recapture-friction in
progress. Direction chosen: remedy (d) — demote the per-PR exact-count assertion to non-blocking
and add a scheduled recapture workflow that opens a PR."* The operator subsequently resolved two
design forks the issue itself left open (recapture scope; PR-authoring auth). Both rulings are
recorded verbatim below as binding decision records, per the same pattern used by
`kitty-specs/up-mission-type-seam-01KZY1JB/spec.md`'s `## Clarifications` section.

## Clarifications / Operator Decisions

The following decisions were made by the operator before this spec was written. They are
**binding decision records**, not options for a reviewer or implementer to re-litigate.

### CL-001 — Remedy (d) + a real nightly

Demote the per-PR exact-count assertion for `charter` in
`tests/architectural/test_module_length_agreement.py`
(`test_charter_is_not_allowlisted_and_agrees`) from a hard, blocking failure to a **non-blocking
warning** — the per-PR architectural-battery shard no longer reds on a charter test-count change
alone. Add a **SCHEDULED** workflow that runs `scripts/ci/capture_shard_timings.py` and **opens a
PR** with the recapture (`main` is PR-only; `.github/workflows/protect-main.yml` flags direct
pushes to `main`).

### CL-002 — Auth: a dedicated PAT / GitHub App token, named and fail-loud

Authentication for the scheduled job's PR-open step is a **dedicated PAT / GitHub App token**
stored as a repository secret, mirroring the existing `RELEASE_NIGHTLY_DISPATCH_TOKEN` pattern
documented in `.github/workflows/release.yml`'s `nightly-gate` job. The operator will create the
secret. The design must **name** the secret explicitly and **fail loudly** (a clear, non-zero-exit
error naming the missing secret) if it is absent — it must **never** silently fall back to the
default `GITHUB_TOKEN`, because a PR opened with `GITHUB_TOKEN` does not trigger other workflows'
`pull_request` events (GitHub's documented anti-recursion behavior; the same limitation
`release.yml`'s own comment records for its `workflow_dispatch` case) — a silent fallback would be
a silent CI-gate bypass on the very PR meant to restore the invariant.

### CL-003 — Scope: `charter` only

This mission's scope is **`charter` only**. The other 19 modules tracked by ledger entry SK-247
(the operator's cross-mission ledger, "the module shard-timing authority is the WRONG LENGTH for
20 of 21 modules") stay **out of scope**. This spec states that explicitly as
a non-goal (see Non-Goals below) and does not contradict SK-247: SK-247's broader defect remains
open as separate follow-up work, not folded into this mission.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Land a trivial charter test-count change without a full recapture (Priority: P1)

A maintainer adds, removes, splits, or renames one test under `tests/charter/` or
`tests/doctrine/` (the module `charter`'s dual test tree). Today this reds the per-PR
architectural-battery shard via `test_charter_is_not_allowlisted_and_agrees` and forces a
mandatory, serial, ~18-minute local recapture
(`python scripts/ci/capture_shard_timings.py --module charter --write`) plus a ~5-6k-line JSON
diff before the PR can land — landing friction wholly disproportionate to a +1/-1 test-count
change, and the mechanism `module-tests.yml` protects (shard-balance quality, not test
correctness or coverage — see NFR-001 below) does not require same-PR remediation.

**Why this priority**: This is the concrete, evidenced pain (#5164, #5175) the issue exists to
fix. Without it, every future charter test-count change repeats the same forced recapture.

**Independent Test**: Add one test under `tests/charter/`, open a PR, and confirm the
architectural-battery shard's `test_module_length_agreement.py` tests do not fail the job/shard
because of the resulting charter length disagreement — the PR is not blocked from merging by this
gate alone.

**Acceptance Scenarios**:

1. **Given** a PR that adds one test under `tests/charter/` (or `tests/doctrine/`) with no
   recapture performed, **When** the architectural-battery shard runs
   `tests/architectural/test_module_length_agreement.py`, **Then** the run does not fail the job
   because of the charter committed/collected length disagreement, and the disagreement is
   reported visibly in the job's output (not a silent pass — see FR-004).
2. **Given** the same PR, **When** a maintainer inspects `_MISMATCH_ALLOWLIST` in
   `tests/architectural/test_module_length_agreement.py`, **Then** `charter` is still **not**
   present in it (the exact-count invariant is relocated to the scheduled recapture described in
   User Story 2, never dropped by silently exempting `charter` the same way the 19 pre-existing
   mismatches are exempted).

---

### User Story 2 - Charter's shard timings self-heal on a schedule, without a maintainer in the loop (Priority: P1)

Because `charter`'s per-PR exact-count assertion is now advisory, something else must keep
`.github/ci-shard-timings.json`'s charter entry converging on truth, or the demotion in User
Story 1 just defers the SK-247-class decay indefinitely. A new scheduled workflow checks whether
a recapture PR from a fixed head branch is already open and, if so, does nothing further;
otherwise it runs `scripts/ci/capture_shard_timings.py --module charter --write` on a cadence
and — only when the recapture actually changes the committed data — opens a PR carrying the
update, so a human reviews and merges it through the normal PR-only path.

**Why this priority**: Without this, remedy (d) is just gate-removal — the exact-count invariant
would have nowhere to be restored, which the charter's Standing Order #5 (architectural gate
discipline: never disable a gate to get green without relocating what it protected) forbids.

**Independent Test**: Manually dispatch the new workflow (`workflow_dispatch`) against a
checkout where `charter`'s committed length has been made stale (e.g. one test added without
recapture); confirm it opens exactly one PR carrying an updated
`.github/ci-shard-timings.json` whose committed charter length matches live collection. Merge
(or close) that PR so no PR from the fixed head branch remains open, then re-run the workflow
with no further drift; confirm it opens no PR this time because the committed and collected
lengths already agree (see FR-006) — not because a PR is still open, which is FR-007's
skip-if-open path, exercised separately by Acceptance Scenario 3 below.

**Acceptance Scenarios**:

1. **Given** `charter`'s committed shard-timings length disagrees with live collection, **When**
   the scheduled workflow runs (on its cron, or via manual `workflow_dispatch`), **Then** it
   recaptures `charter`'s timings, commits the change on the fixed recapture head branch (see Key
   Entities), and opens exactly one PR targeting `main` (never a direct push — `main` is PR-only
   per `protect-main.yml`).
2. **Given** `charter`'s committed shard-timings length already agrees with live collection
   (no drift, per FR-006's length-only definition — even though `--write` still rewrites
   `run_id`/`captured_at`/per-test duration values on this run, producing a routine file diff
   that must **not** itself be treated as drift), **When** the scheduled workflow runs, **Then**
   it opens **no** PR (see FR-006 — a no-drift run must not produce an empty/no-op PR).
3. **Given** a prior recapture PR from this workflow is still open — identifiable by its head
   branch being the single fixed branch this workflow is permanently pinned to (used whenever it
   does push; see Key Entities), never by incidentally touching the same file — **When** the
   scheduled workflow runs again, **Then**
   it does **not** push, force-push, comment, or open anything; it writes one line to the job
   summary naming the open PR's number and exits successfully (see FR-007), never opening a
   second, duplicate recapture PR, and an unrelated open PR that also happens to touch
   `.github/ci-shard-timings.json` (e.g. the #5175/#5177 pattern under Reflexivity) is not
   mistaken for one, because its head branch differs.
4. **Given** the named auth secret (CL-002) is absent from the repository, **When** the scheduled
   workflow runs, **Then** the job fails loudly with an error naming the missing secret **before**
   any recapture, commit, or push occurs, and does **not** fall back to opening the PR with the
   default `GITHUB_TOKEN` (see FR-005 / CL-002).
5. **Given** the recapture script's own MECHANISM fails (e.g. a collection crash or an uncaught
   exception inside `capture_shard_timings.py`'s own machinery — **not** an ordinary failing test
   inside the measured `tests/charter`/`tests/doctrine` run, which `DurationRecorder` still
   records completely and which is not itself a mechanism failure), **When** the scheduled
   workflow runs, **Then** the job fails (visible as a failed Actions run) and does **not** commit
   or open a PR with partial/corrupt data (see FR-008).

---

### User Story 3 - The demoted gate stays honest, not silently green (Priority: P2)

A maintainer or reviewer looking at a PR (or at the scheduled workflow's run history) can tell,
without reading source, whether `charter`'s committed/collected lengths currently agree or have
drifted — the demotion in User Story 1 must not make drift invisible, per the charter's dominant
failure-mode warning ("silent success").

**Why this priority**: Standing Order #5 requires a gate-unmask (turning a hard failure into a
non-failure) to remain observable; an assertion that just stops asserting, with no visible trace,
is exactly the silent-success anti-pattern the charter warns against.

**Independent Test**: Introduce a charter length disagreement (e.g., add a test under
`tests/charter/` without recapturing) and run
`tests/architectural/test_module_length_agreement.py::test_charter_is_not_allowlisted_and_agrees`
locally; confirm the test run's own output (not just its exit code) surfaces the mismatch,
distinguishable from the case where lengths agree.

**Acceptance Scenarios**:

1. **Given** a charter length disagreement, **When**
   `test_charter_is_not_allowlisted_and_agrees` runs, **Then** its result is visibly distinct
   from the agreeing case (e.g., reported as `xfailed`/a captured warning/an emitted
   `::warning::`-class annotation carrying the committed/collected counts) — never a plain
   `PASSED` indistinguishable from genuine agreement.
2. **Given** `charter`'s lengths agree, **When** the same test runs, **Then** it reports a clean
   pass with no warning noise.
3. **Given** the timings/registry artefact is missing, or live collection crashes (a genuine
   infrastructure/collection break, distinct from an ordinary length mismatch), **When** the
   demoted test runs, **Then** it fails/errors visibly — never `xfailed`, never a captured
   warning — distinguishable from both the length-mismatch-warn case (Scenario 1) and the
   clean-pass case (Scenario 2). See FR-004.

### Edge Cases

- What happens when the scheduled job's own recapture leaves `charter` still disagreeing (e.g.
  the capture script errors partway, or a race lands a new charter test between collection and
  commit)? → Covered by FR-008: the job must fail rather than commit/open a PR with data it
  cannot verify is now correct.
- What happens when two open PRs (see Reflexivity below) both touch
  `.github/ci-shard-timings.json` at the same time as a new recapture PR? → Not this mission's
  problem to solve structurally (ordinary git conflict/rebase, not a design defect this mission
  introduces); called out explicitly under Reflexivity so implementers and reviewers do not
  mistake ordinary rebase churn for a regression.
- What happens if the demotion mechanism chosen at plan time (e.g. `pytest.mark.xfail`) makes the
  test collection-time marked rather than result-time marked, and a genuine collection/tooling
  break (missing registry file, subprocess crash) gets silently swallowed as "expected failure"
  instead of surfacing as an infrastructure error? → FR-004's acceptance criteria require the
  demoted test to still distinguish "length mismatch" (expected, warn) from "could not determine
  the lengths at all" (must still error/fail loudly) — plan/implementation must not fold both into
  one blanket non-blocking outcome.

## Requirements *(mandatory)*

### Functional Requirements

| ID | Title | User Story | Priority | Status | Delivery | No-op passable? |
|----|-------|------------|----------|--------|----------|-----------------|
| FR-001 | Demote `test_charter_is_not_allowlisted_and_agrees` to non-blocking | As a maintainer, I want a charter test-count change to stop reding the per-PR architectural-battery shard so that a trivial change doesn't force a mandatory 18-minute recapture. | High | Open | [ratchet] | no — the fixture must exercise both a disagreeing and an agreeing charter state on the same assertion path |
| FR-002 | Keep `charter` out of `_MISMATCH_ALLOWLIST` | As a maintainer, I want `charter`'s exact-count invariant relocated, not dropped, so that Standing Order #5 (never disable a gate without relocating what it protected) is honored. | High | Open | [ratchet] | yes — a static check that `"charter" not in _MISMATCH_ALLOWLIST` remains an unconditional assertion |
| FR-003 | Leave the three allowlist-ratchet tests and the 19-entry allowlist untouched; the demotion mechanism itself covers both live-collection gates, not charter alone | As a maintainer, I want `test_allowlist_does_not_exceed_baseline`, `test_allowlisted_modules_still_genuinely_mismatch`, and `test_allowlist_entries_are_real_registry_modules` to keep their current (hard, blocking) behavior so that this mission cannot be read as weakening SK-247's other 19 tracked mismatches. Separately, the per-PR demotion mechanism (FR-001-class: warn by default, hard-fail under `SPEC_KITTY_STRICT_SHARD_TIMINGS=1`, landed by PR #5240 and absorbed by this mission's WP01) covers **both** live-collection gates — `test_charter_is_not_allowlisted_and_agrees` (this mission's own subject) **and** the cross-module `test_non_allowlisted_modules_agree_with_live_collection` — never charter alone. The *recapture* mechanism (FR-005-FR-010) stays **charter only** (CL-003/C-001); that narrower scope is unaffected and must not be confused with the demotion's broader scope. | High | Open | [ratchet] | yes — the three allowlist-ratchet tests' assertions are unchanged; diff review confirms no edit to their bodies. The demotion-scope statement itself is confirmed by reading the merged production code (a WP01 verification subtask), not a new fixture |
| FR-004 | Demoted assertion still visibly reports drift, and still fails loudly on a genuine infrastructure break | As a reviewer, I want a charter length disagreement to be visibly reported (not a silent pass) so that drift is never invisible per the charter's silent-success warning, and I want a genuine collection/infrastructure break (missing artefact, live-collection crash) to still fail/error visibly rather than collapse into the same warn/xfail outcome as an ordinary length mismatch. | High | Open | [build] | no — requires three fixtures: one proving the disagreeing case emits a distinguishable signal, one proving the agreeing case emits none, and one proving a genuine infrastructure/collection break (missing timings/registry artefact, live-collection crash) fails/errors visibly, distinguishable from both the length-mismatch-warn case and the clean-pass case (see User Story 3, Acceptance Scenario 3) |
| FR-005 | New scheduled workflow authenticates via a named, required secret; fails loudly if absent, before any recapture, commit, or push | As a maintainer, I want the recapture-PR job to name its auth secret explicitly and refuse to run (rather than silently falling back to `GITHUB_TOKEN`) when that secret is missing, so that a missing operator prerequisite cannot silently become a CI-gate bypass. This check must run and fail the job **before** the recapture-and-commit steps execute — not merely before the PR-open call — so a missing secret can never leave a pushed branch+commit in the remote with no PR and no failure signal at the moment of the mutation, and so `capture_shard_timings.py` is never even invoked when the secret is absent. | High | Open | [build] | no — requires a fixture/dry-run proving the job errors (not warns-and-continues) when the secret is unset, and a fixture proving no recapture-script invocation occurred at all (not merely that no branch/commit exists in the remote afterward — that weaker check cannot distinguish "recapture ran, then the check failed before commit" from "the check failed before recapture ran") |
| FR-006 | Scheduled workflow opens no PR when there is no drift | As a maintainer, I want the recapture job to skip opening a PR when the recapture produces no substantive change — defined as the committed and freshly-collected `module_test_durations["charter"]` list **length** agreeing (mirroring `test_charter_is_not_allowlisted_and_agrees`'s own comparison), never "the recapture script produced any file diff" — so that the recapture workflow never spams an empty/no-op PR from `--write`'s routine rewrite of `run_id`/`captured_at`/per-test duration values (which change on every invocation even when the test count is unchanged). The plan phase must specify a length-only or noise-stripped comparison for this decision, never a raw file-diff/`git diff` check. | High | Open | [build] | no — requires a fixture proving both the drift case (length disagrees → PR opened) and the no-drift case (length agrees, even though `--write` still rewrote timestamp/duration-value noise → no PR) |
| FR-007 | Scheduled workflow skips entirely when a recapture PR is already open, instead of opening a duplicate | As a maintainer, I want the recapture job to push its capture to one constant, fixed head branch (e.g. `ci/recapture-charter-shard-timings`; see Key Entities) whenever no PR from that branch is currently open, and to detect "already open" as an open PR whose head is that branch and whose base is `main` — GitHub permits only one open PR per head branch into a given base, so a duplicate recapture PR from this workflow is structurally impossible. When such a PR exists, the job does **not** push, force-push, comment, or open anything — it writes one line to the job summary naming the open PR's number and exits successfully (never force-pushes, in any case); when none exists, the job proceeds to run the recapture, and FR-006's independent, length-only drift check then decides whether it actually pushes and opens one (no drift ⇒ nothing pushed, nothing opened). An unrelated PR that also happens to touch `.github/ci-shard-timings.json` is never matched, because its head branch differs. | High | Open | [build] | no — requires a fixture proving a second run, with the fixed branch's PR already open, performs no push/force-push/comment/open and only writes the job-summary line naming that PR's number, and a fixture proving an unrelated open PR that also touches `.github/ci-shard-timings.json` on a different head branch (e.g. the #5175/#5177 pattern) is never matched by the open-PR search |
| FR-008 | Scheduled workflow fails (does not commit or open a PR) when the recapture MECHANISM itself fails — never merely because the measured suite has failing tests | As a maintainer, I want a genuine `capture_shard_timings.py` mechanism failure (a collection crash, an uncaught exception, or another tooling/environment failure in the script's own machinery) to fail the job outright, so that a broken or partial recapture never gets committed and opened as a PR that looks trustworthy. An ordinary failing test inside the measured `tests/charter`/`tests/doctrine` run is explicitly **not** this failure mode: `DurationRecorder` records every reported test regardless of outcome, so the captured duration data stays complete and trustworthy even when `pytest.main()` itself returns non-zero because a measured test failed — exactly the case already accepted in the currently-committed `module_capture_provenance.charter` entry (`exit_code: 1`). | High | Open | [build] | no — requires two fixtures: one proving a genuine mechanism crash aborts before any commit/PR step, and one proving an ordinary failing measured test (non-zero `pytest.main()` exit with complete `DurationRecorder` output) does **not** abort the commit/PR step |
| FR-009 | Scheduled workflow recaptures `charter` only | As a maintainer, I want the new workflow's `--module` scope pinned to `charter`, so that the mission's scope stays bounded to CL-003 and does not silently expand into the other 19 SK-247 modules or an allowlist-mutation feature. | High | Open | [build] | yes — the workflow's invocation names `--module charter` explicitly; no loop over the registry's other modules |
| FR-010 | Recapture PR carries a bot identity and a clear body | As a reviewer, I want the recapture PR's committer identity, commit message, and PR body to plainly state — in fixed, falsifiable-by-inspection text — that the change is a single-purpose, automated recapture produced by the scheduled workflow, so that it is trivially distinguishable from a human-authored change during review. | Medium | Open | [build] | yes — a fixed commit-author identity and PR-body/commit-message convention that states plainly the change is an automated recapture by the scheduled workflow, independently verifiable by inspection of the fixed text |

### Non-Functional Requirements

| ID | Title | Requirement | Category | Priority | Status |
|----|-------|-------------|----------|----------|--------|
| NFR-001 | Gate protects shard balance, not correctness | The spec and its acceptance criteria must not claim or imply that demoting `test_charter_is_not_allowlisted_and_agrees` risks masking a test-coverage or correctness regression: `module-tests.yml`'s positional pairing degrades to a uniform-weight fallback (verified at `.github/workflows/module-tests.yml`'s "Select this shard's tests" step) on any length mismatch, so the gate's sole protected property is shard-balance quality (bounded inter-shard skew), never which tests run. | Correctness-of-claim | High | Open |
| NFR-002 | Scheduled job stays within the module registry's per-shard time ceiling | The new workflow, recapturing `charter` alone, must complete within a bounded, documented runtime budget (the issue's own ~18-minute local figure is the reference point; the plan phase must record the actual measured in-Actions runtime once dispatched) and must not be scoped to run unbounded across all 21 registry modules (that would risk exceeding `module-tests.yml`'s per-shard ceiling with no measured baseline — see CL-003 / readiness report Open Question 2). | Performance | Medium | Open |
| NFR-003 | No credential leakage | The named auth secret (CL-002) must never be echoed, logged, or written into workflow output, commit messages, or the opened PR's body — consistent with the charter's `DIRECTIVE_050` credential-handling requirement. | Security | High | Open |

### Constraints

| ID | Title | Constraint | Category | Priority | Status |
|----|-------|------------|----------|----------|--------|
| C-001 | Charter-only *recapture* scope | The *recapture* script/logic (WP02/WP03's `scripts/ci/recapture_charter_shard_timings.py` and its triggering job) touches only `charter`'s handling in `tests/architectural/test_module_length_agreement.py`; it does not recapture, allowlist-edit, or otherwise touch any of the other 19 modules tracked by SK-247. The demotion mechanism (absorbed from #5240) and the new strict-mode CI job added to the same scheduled workflow (WP03 T020) are **not** charter-scoped — they cover every non-allowlisted registry module (today: `charter` and `agent`); see FR-003. | Technical | High | Open |
| C-002 | No allowlist-mutation feature | This mission does not add tooling that programmatically edits `_MISMATCH_ALLOWLIST` or `_BASELINE_ALLOWLIST_COUNT`. Per the test file's own docstring, only a human edits that ratchet today, and this mission does not change that. | Technical | High | Open |
| C-003 | `main` is PR-only | The scheduled workflow must never push directly to `main`. It commits to the fixed recapture head branch (see Key Entities) and opens a PR from it only when both hold: no PR from that branch is already open (FR-007), and the recapture shows drift (FR-006). It commits and opens nothing in either of the other two cases — a PR from that branch is already open (per ruling 2, skips entirely) or no PR is open but the recapture shows no drift (FR-006) — consistent with `.github/workflows/protect-main.yml` and the charter's Programme PR Workflow / Agent Push Authorization sections. | Technical | High | Open |
| C-004 | No silent auth fallback | The scheduled workflow must never fall back to the default `GITHUB_TOKEN` for the PR-open step when the named secret (CL-002) is absent, and the presence check for that secret must run and fail **before** any recapture, commit, or push occurs — never merely immediately before the PR-open call, and never after the recapture script has already been invoked. | Technical | High | Open |
| C-005 | Public repo — no absolute local paths, no credentials | No artifact this mission commits may contain a literal `/home/<user>` path, a credential value, or private-repo/readiness-report detail. `.venv/bin/spec-kitty` internals, the readiness report, and this dispatch are background context only, never cited verbatim in committed files. | Technical | High | Open |
| C-006 | Scheduled workflow is concurrency-guarded | The new scheduled workflow must carry a `concurrency:` group (mirroring `.github/workflows/ci-stale-running-sweep.yml`'s own `concurrency: {group: ci-stale-running-sweep, cancel-in-progress: false}` block) so that overlapping invocations — a cron run racing a manual `workflow_dispatch`, or two manual dispatches close together — queue rather than race FR-007's open-PR check, where both could otherwise observe "no PR is open" at the same instant, each proceed to run the recapture and independently evaluate FR-006's drift check, and — only if both find drift — each attempt to push and open its own PR against the fixed branch. | Technical | High | Open |

### Key Entities

- **`.github/ci-shard-timings.json`**: the committed measured-duration authority for the CI
  module-test shard matrix; `module_test_durations["charter"]` is the list this mission's
  scheduled job re-measures and commits.
- **`_MISMATCH_ALLOWLIST`** (`tests/architectural/test_module_length_agreement.py`): the
  frozen, shrink-only debt ledger of 19 modules whose committed/collected lengths are known to
  disagree; `charter` must never enter it (FR-002).
- **The scheduled recapture workflow** (new file under `.github/workflows/`, name TBD at plan
  time): runs on `schedule` + `workflow_dispatch` only (no `pull_request`/`push` trigger,
  mirroring `.github/workflows/ci-stale-running-sweep.yml`'s pattern), and on every run follows a
  three-step sequence, not a two-way branch: (1) it checks FIRST, before invoking the recapture
  script at all, whether a PR from the single fixed head branch defined below is already open
  against `main` (FR-007); if so, it skips entirely — no recapture script invocation, no push, no
  PR — and instead writes one line to the job summary naming the open PR's number and exits
  successfully; (2) only when no such PR is open does it invoke
  `scripts/ci/capture_shard_timings.py --module charter --write`; (3) it then applies FR-006's
  independent, length-only drift check to the result — when the committed and freshly-collected
  `charter` lengths agree (no drift), it pushes nothing and opens no PR, even though `--write`
  still rewrote routine `run_id`/`captured_at`/duration noise; when they disagree (drift found), it
  pushes the fresh capture to the fixed head branch and opens a PR from it. FR-006's no-drift gate
  is independent of, and additional to, FR-007's open-PR check — it is evaluated only in the
  no-open-PR branch (step 3, after step 2), never subsumed by the open-PR check. The workflow also
  carries a `concurrency:` group serializing overlapping runs (C-006) so a same-instant race
  between two invocations cannot both observe "no PR is open" and both attempt to push/open one.
- **The recapture head branch** (FR-007): a single, constant, reused branch name that the
  plan pins (e.g. `ci/recapture-charter-shard-timings`) — **not** freshly generated per run (no
  timestamp/run-id suffix, unlike `capture_shard_timings.py`'s own `generate_run_id()` convention
  used for provenance elsewhere). Because GitHub permits only one open PR per head branch into a
  given base, a duplicate recapture PR from this workflow is structurally impossible. FR-007's
  detection mechanism is "an open PR exists with head = this branch and base = `main`", and it is
  evaluated FIRST, before the recapture script ever runs: when one exists, the job never invokes
  the recapture script and never pushes, force-pushes, comments, or opens anything against it — it
  only writes one line to the job summary naming that PR's number and exits successfully (**skip if
  open**, per operator ruling 2; while a PR from this branch is open, the job never force-pushes,
  in any case); when none exists, the job
  runs the recapture and then applies FR-006's independent, length-only drift check — only when
  that check finds drift does it push the fresh capture to the branch and open a PR; a no-drift
  result pushes nothing and opens nothing (FR-006). FR-006's drift check applies only in this
  no-open-PR branch, and is additional to — never subsumed by — FR-007's open-PR check. An
  unrelated PR that also happens to touch
  `.github/ci-shard-timings.json` (e.g. the #5175/#5177 pattern under Reflexivity) is never
  matched, because its head branch differs from this fixed one. If the fixed branch exists with no
  open PR (e.g. a previously closed PR), the plan phase decides how that stale branch is replaced
  before the next push — this is a plan-time choice deferred here the same way FR-004's Charter
  Tension point 4 defers the exact demotion mechanism, with one fixed, falsifiable observable
  requirement: the stale branch's prior content is fully replaced by the fresh capture, whatever
  git mechanism (delete-and-recreate the ref, force-push, or another approach) accomplishes that.
  Because no PR is open at that point, this replacement is never a force-update of a PR under
  review — the specific case operator ruling 2 forecloses — and is a distinct scenario from the
  skip-if-open path above, whose "never force-pushes, in any case" guarantee is scoped to while a
  PR from this branch is open. **Accepted cost (ruling 2, point 5):** because a still-open recapture PR
  is never refreshed, its captured content can go stale relative to `main` while it sits open; this
  is tolerable because the per-PR `test_charter_is_not_allowlisted_and_agrees` check is now a
  warning only (FR-001), never a merge blocker, and closing a stale open PR lets the next scheduled
  run open a fresh one against current `main`. FR-010's bot-identity/PR-body convention is
  independent of this branch-based detection mechanism — it only needs to state plainly, in fixed
  text, that the change is an automated recapture by the scheduled workflow; it carries no
  identity-matching relationship to FR-007's check.
- **The named auth secret** (CL-002): a dedicated PAT / GitHub App token repository secret,
  named explicitly by the plan, mirroring `RELEASE_NIGHTLY_DISPATCH_TOKEN`.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: A PR that changes only a charter test count (no recapture performed) no longer
  fails the architectural-battery shard because of
  `test_charter_is_not_allowlisted_and_agrees` — [ratchet] · no-op passable: no.
- **SC-002**: `charter` is absent from `_MISMATCH_ALLOWLIST` both before and after this mission's
  change — [ratchet] · no-op passable: yes.
- **SC-003**: A manually-dispatched run of the new scheduled workflow against a deliberately
  stale `charter` entry produces exactly one PR whose merged content makes
  `test_charter_is_not_allowlisted_and_agrees` pass without warning — [build] · no-op passable:
  no.
- **SC-004**: A manually-dispatched run of the new scheduled workflow against an already-agreeing
  `charter` entry (per FR-006's length-only definition of agreement, not the presence/absence of
  a raw file diff) produces zero PRs — [build] · no-op passable: no.
- **SC-005**: A manually-dispatched run of the new scheduled workflow with the named secret unset
  fails the job with an error naming the missing secret before any recapture, commit, or push
  occurs, and no PR is opened using `GITHUB_TOKEN` — [build] · no-op passable: no.
- **SC-006**: The other 19 `_MISMATCH_ALLOWLIST` entries and the three unrelated untouched
  allowlist-ratchet tests (FR-003) are byte-identical in behavior before and after this mission
  (diff review) — [ratchet] · no-op passable: yes.
- **SC-008**: A manually-dispatched run of the new scheduled workflow against the fixed
  recapture head branch that already has an open PR pushes nothing, force-pushes nothing,
  comments nothing, and opens no new PR — it only writes one job-summary line naming that PR's
  number — [build] · no-op passable: no.
- **SC-009**: A manually-triggered or simulated failure inside `capture_shard_timings.py`'s own
  mechanism (a collection crash or uncaught exception in the script's machinery, not an ordinary
  failing measured test) produces a failed Actions run with no commit and no PR opened —
  [build] · no-op passable: no.

## Non-Goals

- **The other 19 SK-247 modules** (`merge`, `missions`, `post_merge`, `release`, `status`,
  `review`, `next`, `lanes`, `dashboard`, `upgrade`, `cli`, `kernel`, `glossary`,
  `execution_context`, `core_misc`, `unit`, `specify_cli_runtime`, `ci`, `auth`, and any other
  entry in `_MISMATCH_ALLOWLIST`) are **not** recaptured, allowlisted, or otherwise touched by
  this mission. SK-247 remains open as separate follow-up work; this spec does not contradict it.
- **No allowlist-mutation feature.** This mission does not build tooling to programmatically add,
  remove, or resize `_MISMATCH_ALLOWLIST` / `_BASELINE_ALLOWLIST_COUNT`. That remains a manual
  edit, per the test file's existing docstring convention.
- **No change to `ci-router.yml`'s `architectural-heavy` job trigger conditions.** The path-filter
  logic that selects when `tests/architectural/**` runs on a PR is unchanged; only the assertion
  behavior inside two existing tests in that suite changes (the demotion mechanism absorbed from
  #5240, covering both `test_charter_is_not_allowlisted_and_agrees` and the cross-module
  `test_non_allowlisted_modules_agree_with_live_collection`; the *recapture* itself still touches
  only `charter`).
- **No retroactive fix to already-open PRs.** #5175 and #5177 (see Reflexivity) are not modified
  by this mission; they are only affected by rebasing against whichever of this mission's PR,
  #5175, or #5177 merges first (ordinary git history churn on a shared file, not a design change
  this mission must engineer around).

## Reflexivity — Impact on In-Flight Work

This mission changes machinery that other in-flight PRs depend on.

- **#5175** ("Merge-seam relocation, test-isolation sweep & model-slot verdict") and **#5177**
  ("fix(review): rejection feedback survives to the implementer's regenerated prompt") both
  currently list `.github/ci-shard-timings.json` as a changed file. Neither touches
  `tests/architectural/test_module_length_agreement.py`, `.github/workflows/module-tests.yml`,
  `scripts/ci/capture_shard_timings.py`, or `.github/ci-module-registry.yml`, so there is **no
  direct code collision** with this mission's diff. Whichever of {this mission, #5175, #5177}
  merges first, the others rebase against a changed `.github/ci-shard-timings.json` — an ordinary
  git-history sequencing concern, not a blocker, and not something this mission's design needs to
  prevent.
- **Any PR mid-flight when this mission's demotion lands**: before merge, such a PR is still
  bound by the current hard assertion (if it happens to touch charter test counts, it must
  recapture as today). After merge, the demotion applies to every subsequent CI run on that PR's
  branch once it is rebased/re-run against the new `main` — it does not retroactively change a
  run already completed. This confirms the readiness report's characterization: rebase churn, not
  a blocker.
- **Docs**: PR #5190 (merged, docs-only) recorded this friction as a known-friction-points bullet
  and explicitly stated it does not close #5189. This mission is the actual fix; at
  implementation/review time, the PR should note in its body that the doc bullet in
  `docs/development/reference/known-friction-points.md` is now superseded (leaving the specific
  doc-file edit, if any, to implementation's judgment — not prescribed here).

## Charter Tension — Standing Order #5 (Architectural Gate Discipline)

Standing Order #5 requires: a NON-VACUOUS call-site gate (concrete floor + self-mutation test +
shrink-only allowlist), and explicitly forbids disabling a gate merely to get green. Demoting
`test_charter_is_not_allowlisted_and_agrees` is an **operator ruling** (CL-001/CL-002/CL-003), not
a green-wash, for the following reasons — each is a testable property of this mission's design,
not an assertion to take on faith:

1. **Relocated, not dropped.** The exact-count invariant is not deleted; it is moved from a
   per-PR blocking check to a scheduled, automatic recapture (FR-005–FR-009) that restores
   agreement on a bounded cadence. FR-006/FR-007/FR-008 make that automatic path itself
   non-vacuous: it must actually change the committed data when drift exists (not a no-op PR),
   must not spam duplicates, and must fail rather than commit bad data on script failure.
2. **`charter` stays out of `_MISMATCH_ALLOWLIST`.** FR-002 keeps the absence of `charter` from
   that allowlist a hard, unconditional assertion — the mechanism the 19 pre-existing mismatches
   use to be exempted is explicitly **not** applied to `charter`. This preserves the file's own
   stated invariant (`test_charter_is_not_allowlisted_and_agrees`'s docstring: "a count-preserving
   swap (fix one module, sneak `charter` in) cannot mask a real regression").
3. **The three allowlist-ratchet tests are unchanged (FR-003); the demotion itself covers both
   live-collection gates, not charter alone.** `test_allowlist_does_not_exceed_baseline`,
   `test_allowlisted_modules_still_genuinely_mismatch`, and
   `test_allowlist_entries_are_real_registry_modules` keep their current, fully-blocking behavior,
   untouched by this mission. The demotion mechanism (warn by default, hard-fail under
   `SPEC_KITTY_STRICT_SHARD_TIMINGS=1`, landed by PR #5240 and absorbed by WP01) covers **both**
   live-collection gates — `test_charter_is_not_allowlisted_and_agrees` (this mission's subject)
   and the cross-module `test_non_allowlisted_modules_agree_with_live_collection` — never charter
   alone. This is not a general weakening of the gate file: the three allowlist-ratchet tests stay
   hard, and the *recapture* mechanism (the part that actually restores agreement) stays scoped to
   `charter` only (CL-003/C-001), a distinct and narrower scope than the demotion.
4. **Drift stays visible, not silent (FR-004, User Story 3).** The demoted assertion must still
   produce a distinguishable signal on disagreement (e.g., `xfailed` rather than `passed`, or an
   emitted warning/annotation carrying the committed/collected counts) — this repo's dominant
   failure mode is silent success, and a demotion that just stops asserting with no visible trace
   would reproduce exactly that failure mode. The exact mechanism (pytest `xfail`,
   `warnings.warn`, a GitHub Actions `::warning::` annotation, or a combination) is a plan-time
   choice; the observable requirement — visibly distinct from a genuine pass — is fixed here.
5. **Silent-success failure modes for the scheduled job are explicitly specified** (FR-005
   through FR-008 / Acceptance Scenarios under User Story 2): a missing auth secret fails loudly
   and never falls back to `GITHUB_TOKEN` (FR-005/CL-002); a no-drift run opens no PR (FR-006); an
   already-open recapture PR is never touched — the job does not push, force-push, comment, or open
   anything, and only writes one job-summary line naming that PR's number (FR-007, operator ruling
   2: skip if open, never force-update); a recapture-script failure aborts before any commit/PR
   step rather than committing partial data (FR-008). The one accepted, explicitly-stated cost of
   the skip-if-open behavior (ruling 2, point 5) is that a still-open recapture PR's capture can go
   stale relative to `main` while it sits open — tolerable because the per-PR check it feeds is
   only a warning (FR-001), never a merge blocker, and closing a stale PR lets the next scheduled
   run open a fresh one.

## Ledger Cross-Reference

The operator's cross-mission ledger's **SK-247** entry documents that 20 of
21 registry modules mismatch and that the prior mission (`ci-nightly-wallclock-budget-01M34HNZ`)
recaptured `charter` only, "scoped the rest out" by operator ruling, and left SK-247 open with a
suggested fix of running the length-agreement check in CI per module and hardening the
selection-marker-expression mismatch between the capture script and its consumer. This mission
does not contradict that entry: the *recapture* stays `charter`-only (CL-003 / C-001) — a
narrower scope than the per-PR demotion mechanism, which covers both live-collection gates and is
not charter-scoped (FR-003) — leaves the 19-entry allowlist untouched (FR-003), and does not
attempt SK-247's broader per-module CI-config-path gap
(the readiness report's cited `#3241`-class issue) or the `SELECTION_MARKER_EXPR` alignment SK-247
separately flags. Both remain open follow-up work.
