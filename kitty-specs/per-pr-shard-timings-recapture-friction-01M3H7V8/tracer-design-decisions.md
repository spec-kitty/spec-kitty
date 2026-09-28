# Tracer: design decisions and drift

## Branch-naming drift (charter vs. sk-skill doctrine) — MUST record per dispatch

The charter's Collaboration Strategy section mandates `issue-<n>-<slug>` branches:

> "Issue branch first. Completed mission work is opened from an `issue-<n>-<slug>` branch as a
> pull request targeting `main`, with compact history."

The `sk` skill's own doctrine text (the hermes `sk-design`/`sk-implement` skill family this
mission's orchestrator invokes) separately documents a `<type>/<slug>-<issue>` branch-naming
convention for mission branches.

**These two are in direct tension for this mission's branch name.** Per the operator dispatch's
own instruction, and per the charter's own resolution rule ("If the charter and this file [or any
other doctrine text] ever disagree, the charter wins — flag the drift instead of picking
silently"), **the charter wins**: this mission's branch is
`issue-5189-per-pr-shard-timings-recapture-friction` (charter's `issue-<n>-<slug>` shape), not a
`<type>/<slug>-<issue>` shape the sk-skill doctrine text would otherwise suggest. This drift is
deliberate and is recorded here rather than silently resolved.

## Mission-slug auto-suffix (mid8) vs. dispatch's plain-slug path guidance

See `tracer-tooling-friction.md` item 1: the scaffold produced
`kitty-specs/per-pr-shard-timings-recapture-friction-01M3H7V8/` rather than the plain
`kitty-specs/per-pr-shard-timings-recapture-friction/` the dispatch's own path references assumed.
This is the documented Mission Identity Model (083+) behavior (`mission_slug` carries the `mid8`
disambiguator; `mission_id`/`mid8` are the real identity, `mission_number` is display-only and
null pre-merge) — not a drift from doctrine, just a mismatch between the dispatch's illustrative
path and the tool's actual, documented output shape. No override was applied; all tracer/spec
files were written to the actual scaffolded directory.

## Spec section shape: `## Clarifications / Operator Decisions` matched to existing precedent

The dispatch required a `## Clarifications / Operator Decisions` section carrying the operator's
decisions verbatim. Rather than inventing a new format, this spec follows the
`## Clarifications` + `CL-00N` decision-record pattern already established in
`kitty-specs/up-mission-type-seam-01KZY1JB/spec.md` (canonical-sources / no-improvise discipline,
charter Standing Order #6) — each decision gets an ID, the operator's own words, and (where the
dispatch supplied one) the rationale tying it back to the charter tension it resolves.

## Charter-tension section placed as its own top-level section, not folded into FR prose

The dispatch's "CHARTER TENSION the spec MUST address explicitly" block asked for five specific
properties (relocated-not-dropped; charter stays out of the allowlist; other ratchet tests
untouched; visible warning; silent-success modes for the scheduled job). Rather than scattering
these across FR rows, they are collected into one `## Charter Tension — Standing Order #5` section
that cross-references the FRs proving each property, so a reviewer checking Standing Order #5
compliance has one place to look, with traceability back to the falsifiable requirement.

## No new naming decided for the workflow file or the secret

Deliberately left to plan phase — see `tracer-approach.md`'s "Design choices deliberately left
open" section. Naming these here, without the plan phase's fuller pass over existing
`.github/workflows/*.yml` naming conventions and secret-naming conventions across the repo, risked
picking a name that collides with or drifts from an existing convention this spec-authoring pass
did not have reason to fully survey.

## Operator ruling (2026-09-27): the recapture-PR marker is a single fixed head branch, not a plan-time three-way choice

The original spec left "how a recapture PR from this workflow is identified" as a plan-time choice
among three equally-legitimate alternatives (a label, a branch-name prefix, or a bot
commit-author identity — see the pre-ruling Key Entities text), and had FR-007's duplicate-PR
check separately required to stay "consistent with, and never contradicted by" FR-010's
bot-identity/PR-body convention, without pinning which of the three FR-007 itself would use. A
post-spec adversarial review raised two findings against this shape:

- **SPEC-FRESH3-001** (severity 4): the three-way marker choice is deferred past spec into plan,
  but FR-010 already tries to constrain an unchosen marker with a "consistent with, never
  contradicting" clause — a requirement that cannot be verified until the plan makes the choice
  FR-007 needs, and that leaves room for the plan to pick two markers that are not actually
  reconcilable.
- **SPEC-FRESH3-002** (severity 3): the spec's own reconciliation claim was mechanistically false
  — it asserted "FR-010's mechanism can only ever produce a bot-commit-author identity/PR-body,"
  which forecloses two of the three markers the same spec had just called "equally legitimate,"
  contradicting itself.

The operator ruled (`reviews/spec.ruling.md`, 2026-09-27) that this REPLACES the acceptance bar
for both findings, with a fixed mechanism rather than a plan-time choice:

1. The scheduled recapture job always pushes to **one constant, reused head branch** that the spec
   itself now names (e.g. `ci/recapture-charter-shard-timings`), not a freshly-generated
   per-run branch. GitHub permits only one open PR per head branch into a given base, so a
   duplicate recapture PR is structurally impossible by construction — no marker-matching logic
   is needed to prevent it.
2. FR-007's detection mechanism is exactly "an open PR exists with head = that branch and base =
   `main`." When one exists, the job **force-updates that branch** with the fresh capture
   (never skips, never opens a second PR); when none exists, it opens one. An unrelated PR that
   also touches `.github/ci-shard-timings.json` (the #5175/#5177 pattern) is never matched,
   because its head branch differs.
3. The label / branch-name-prefix / bot-commit-author three-way choice is removed from FR-007
   and Key Entities entirely — there is no longer a plan-time marker decision to make.
4. FR-010 no longer carries any identity-matching or "consistent with, never contradicting"
   relationship to FR-007. It stands alone: the PR body and commit message must plainly state,
   in fixed text, that the change is an automated recapture by the scheduled workflow —
   falsifiable by inspection, with no cross-requirement coupling to police.
5. SPEC-FRESH3-002's false mechanism claim was deleted outright, not reworded — the ruling was
   explicit that the correct fix is removing the false claim, not patching its wording, since the
   claim it made had no valid restatement under the old three-way framing.

Why this is the more resolvable shape: the original design tried to keep two independently
plan-chosen conventions (a duplicate-detection marker and a bot-identity signal) mutually
consistent by written constraint alone, which is exactly the kind of cross-cutting invariant that
drifts silently when the plan or a later change touches only one side. Pinning the marker to a
GitHub-enforced structural property (one open PR per head branch) removes the invariant instead of
asking two future authors to keep honoring it. `spec.md`'s FR-007, FR-010, Key Entities, User
Story 2 Acceptance Scenario 3, and the C-003/C-006 constraints were swept for consistency with this
ruling as part of the same fix; `tracer-approach.md` is left untouched as a frozen historical
record of the original (superseded) three-way framing.

## Operator ruling 2 (2026-09-27): "force-update the open PR" replaced with "skip if open"

Ruling 1 (above) fixed the duplicate-detection marker but kept its point 2 as "when an open PR
exists, force-update its branch." That force-update clause immediately spawned three more
requirements to keep it non-vacuous — FR-011 (lease-guarded force push), FR-012 (an explicit
review-state outcome after the force-update), and an Edge Case entry about what happens to inline
review-comment threads across repeated force-update cycles — plus User Story 2's Acceptance
Scenarios 6 and 7, which exercised FR-011's tip-mismatch abort and FR-012's approval-dismissal/
notice outcome respectively. A second post-spec adversarial review (`spec-fresh-5.yaml`) raised
three findings against this shape, all ruled on together in `reviews/spec.ruling.md`'s "Spec HALT
ruling 2":

- **SPEC-FRESH5-001** (severity 4): FR-012's option (a) — "the repository requires 'dismiss stale
  reviews on push' for this branch/PR path" — is infeasible on this repository in any scope: this
  repo carries no branch protection, so the GitHub API returns 404 rather than offering that
  setting. A requirement whose primary option cannot exist on the target repo is not a real
  requirement.
- **SPEC-FRESH5-002** (severity 2): the Charter Tension section's FR range for "silent-success
  failure modes for the scheduled job" had drifted to include FR-011/FR-012 without those IDs'
  content being re-verified against the actual surviving FR set — a stale cross-reference.
- **SPEC-FRESH5-003** (severity 3): the stale-review-thread Edge Case was plan-deferred with no
  falsifiable acceptance bar ("the plan phase must state the accepted behavior explicitly —
  e.g. ... or ..." is a menu, not a requirement), making it unfalsifiable as written.

The operator ruled that this root cause — ruling 1's "force-update" clause itself — is what should
be withdrawn, not merely its unfalsifiable downstream requirements. **Ruling 1 point 2 is amended;
points 1, 3, 4, 5 stand.** The replacement mechanism, applied throughout `spec.md`:

1. The fixed head branch (ruling 1 point 1) is unchanged.
2. If an open PR with head = that branch and base = `main` exists, the job does **not** push,
   force-push, comment, or open anything. It writes one line to the job summary naming the open
   PR's number and exits successfully. The job never force-pushes, in any case.
3. When no such PR is open, the job pushes the fresh capture and opens the PR. If the fixed branch
   exists with no open PR (e.g. a previously closed PR), the plan decides how that stale branch is
   replaced — that is not a force-update of a PR under review, since no PR is open at that point.
4. **Deleted outright** (no replacement text, no "withdrawn" stub row — this spec has no prior
   precedent for a withdrawn-but-retained FR/SC row, so the fallback convention applies: remove
   the row, leave the ID gap, do not reuse the ID): FR-011, FR-012, SC-007, the stale-review-thread
   Edge Case bullet, and User Story 2's Acceptance Scenarios 6 and 7 (renumbered 1–5, no gap).
   FR-001 through FR-010 keep their original numbers unchanged; FR-011/FR-012 are retired IDs, not
   available for reuse. (Surveyed precedent before choosing: `doc-quality-hardening-2245-01KW9AKV/
   spec.md` removes withdrawn FR rows outright with a prose note ("their table rows are removed;
   the numbers are retired, not reused") while keeping a stub row for a withdrawn *constraint*;
   `doctrine-silence-guards-01KYFV7Q/spec.md` instead keeps a strikethrough **WITHDRAWN** stub row
   for a withdrawn FR. Neither is *this* spec's own established convention — this spec had never
   withdrawn anything before this ruling — so per the dispatch's fallback instruction the simpler,
   no-stub removal was used, applied identically to both the FR rows and SC-007 for consistency.)
5. **The accepted cost is now stated in prose**, in the Key Entities "recapture head branch" entry
   and again in Charter Tension item 5: an unmerged recapture PR's capture can go stale relative to
   `main` while it sits open; tolerable because the per-PR `test_charter_is_not_allowlisted_and_
   agrees` check is now a warning only (FR-001), never a merge blocker, and closing a stale PR lets
   the next scheduled run open a fresh one against current `main`.

## Design amendment (2026-09-28): absorb #5240, correct demotion scope, add strict-mode home

**Trigger.** After `/spec-kitty.analyze` recorded `verdict: ready` for this design (analyze run
`423463a10`), the operator discovered that `main` already carried PR #5240
("ci(tests): make shard-timings count drift non-blocking per PR (#5189 interim)", commit
`5469c4d777833e8010115ed7048c53ae2bb642b6`, merged 2026-09-27) — an independently-authored,
already-merged change to the exact file this mission's WP01 was designed to edit
(`tests/architectural/test_module_length_agreement.py`). #5240's author explicitly scoped it as
"interim relief that your mission can delete or absorb" and left review notes on issue #5189 for
this mission. The mission branch was then merged with `origin/main` (per the operator's own ruling
instruction, point 1), so #5240's code is now what is actually on disk in this checkout — meaning
this design's `ready` verdict was reached against a code state that no longer matches reality by
the time implementation would start. The operator issued a binding ruling
(`reviews/amendment.ruling.md`) rather than letting the design silently drift from the merged code,
or letting an implementer discover and improvise around the collision mid-WP.

**The ruling's 6 substantive points, and what changed as a result:**

1. *(Housekeeping — not itself a design point.)* The mission branch was merged with `origin/main`
   before this amendment was written, so every file this amendment describes (spec.md, plan.md,
   tasks.md, WP01, WP03) is written against the actual merged code, not a stale pre-merge state.
2. **WP01 becomes "absorb #5240."** The `_charter_disposition`/`pytest.xfail` mechanism WP01
   originally specified is dead — #5240 pre-empted it with a `ShardTimingsDriftWarning`/
   `_report_drift`/`_strict_mode` mechanism that is, if anything, a closer match to spec.md's
   original CL-001 wording ("non-blocking warning") than `xfail` ever was. `tasks/WP01-*.md`'s
   T002-T008 were rewritten: T002 is now a documented verification pass (confirm the merged
   mechanism actually satisfies FR-001/FR-002/FR-004 for `charter`), and T003-T006 are new red-first
   tests closing the exact gap #5240's own 3 unit tests leave open — those 3 tests exercise
   `_report_drift`/`_strict_mode` in isolation, never the two production gate functions themselves,
   so a revert of either function's mismatch branch back to a bare hard `assert` would not be
   caught today. T007 (an optional, non-gating `mypy` `no-any-return` fix in `_resolve_test_dirs`,
   ruling point 6) was added. WP01's frontmatter (`dependencies`, `owned_files`, `create_intent`,
   `authoritative_surface`, `requirement_refs`) is unchanged; only the `subtasks` content changed
   (same 8 IDs).
3. **Spec.md's scope statement was corrected.** FR-003, SC-006, and Charter Tension point 3 all
   previously claimed "the other four untouched tests" (naming `test_non_allowlisted_modules_
   agree_with_live_collection` as one of the four). This was true of the original
   `_charter_disposition` design (which touched only `test_charter_is_not_allowlisted_and_agrees`)
   but is false of the merged #5240 code, which demotes BOTH live-collection gates via the same
   `_report_drift` mechanism. All three spec.md locations were rewritten to state precisely: the
   **demotion** covers both live-collection gates (new, from #5240); the **recapture** (WP02/WP03's
   mechanism) stays charter-only (CL-003/C-001, genuinely unaffected by this amendment). Only three
   tests are now correctly described as untouched:
   `test_allowlist_does_not_exceed_baseline`, `test_allowlisted_modules_still_genuinely_mismatch`,
   `test_allowlist_entries_are_real_registry_modules`.
   **Correction (fix round, 2026-09-28):** the first amendment pass swept FR-003, SC-006, and
   Charter Tension point 3 but missed two further spec.md locations making the same now-false
   "charter-only demotion"/"workflow scoped to charter" claim — C-001's own constraint text and
   the Ledger Cross-Reference section's "it stays `charter`-only" sentence. Both were rewritten in
   the fix round to state the same recapture/demotion distinction FR-003 already states; CL-003
   itself was not touched (operator ruling point 3: that decision is unchanged).
4. **A strict-mode home for the exact-count invariant was added to WP03's own workflow.** Plan.md
   gained a new subsection, item (a2), and `tasks/WP03-*.md` gained Subtask T020: a second,
   independent job (no `needs:` to the recapture job) in the SAME `ci-charter-shard-recapture.yml`
   file, running `tests/architectural/test_module_length_agreement.py` under
   `SPEC_KITTY_STRICT_SHARD_TIMINGS=1`, `timeout-minutes: 10` (justified against the file's own
   ~36s-measured-locally docstring figure). This gives the exact-count invariant a real, scheduled,
   hard-failing home — verified directly that nothing in `ci-nightly.yml` runs
   `tests/architectural` today (its `full-module-matrix` job only expands the module registry's
   `modules[]` rows, and that registry's own `out_of_matrix_test_dirs` block explicitly excludes
   `tests/architectural`). Plan.md and WP03 both state the job's relation to the recapture job
   explicitly (charter-drift double-signal; other-module-drift visible-but-unfixed) and confirm this
   addition changes neither WP03's `create_intent` nor `owned_files` (still the one workflow file).
5. **Allowlist-ratchet interplay was stated explicitly.** Plan.md item (a2) and WP01's Objectives
   section now state: a charter-only recapture can never trip
   `test_allowlisted_modules_still_genuinely_mismatch`, because that test iterates only
   `_MISMATCH_ALLOWLIST`'s own keys and `charter` is never a member — pinned by the unconditional
   `assert "charter" not in _MISMATCH_ALLOWLIST"`, unchanged by #5240. The forward-looking,
   out-of-scope case (a future allowlisted-module recapture would need to prune
   `_MISMATCH_ALLOWLIST`/`_BASELINE_ALLOWLIST_COUNT` in the same PR) is recorded for future readers,
   verbatim from the ruling.
6. **The `mypy` `no-any-return` finding in `_resolve_test_dirs`** is recorded as admissible,
   domain-matched, optional campsite debt (WP01's T007) — a distinct, behaviour-preserving commit if
   the implementer chooses to do it, never gating.

**What did NOT change**: spec.md's CL-001/CL-002/CL-003, User Story 1/2 text, FR-005 through
FR-010, and plan.md's recapture-mechanism design (items (b), (c), the mechanism-vs-ordinary-failure
resolution) — all confirmed unaffected by this amendment and left untouched. `tasks/WP02-*.md` was
checked for any reference to the retired xfail mechanism and found to have none (its one mention of
`test_charter_is_not_allowlisted_and_agrees` is a comparison-semantics reference for `has_drift`,
unrelated to the demotion mechanism) — left untouched, per ruling point 7 ("every prior operator
decision and ruling stands, except where points 2-4 supersede them").

Every remaining cross-reference was swept: FR-007's table row and its Key Entities description,
User Story 2 Acceptance Scenario 3, C-003 ("opens or force-updates a PR" → "opens a PR, or ...
skips entirely"), C-006's race description (recast as "both observe 'no PR is open' and both
attempt to open one" instead of "corrupt a concurrent force-update push"), the "scheduled recapture
workflow" Key Entities bullet, and Charter Tension item 5's FR range and prose (dropped FR-011/
FR-012, restated as skip-if-open + the accepted staleness cost). Charter Tension item 1's FR range
(`FR-005–FR-009`) already excluded FR-011/FR-012 and needed no change. Ordinary-English uses of
"forces"/"forced" (the issue title, User Story 1's prose, FR-001's rationale) describe the ~18-
minute local recapture burden, not the FR-007 mechanism, and were left untouched.

## Fix round 2 (2026-09-28): FR-004's dropped agreeing-case fixture restored; Non-Goals' stale "one test" claim corrected

A fresh-eyes sweep run after the amendment's first fix round (`reviews/amendment.confirmed-2.yaml`,
findings AMENDMENT-FRESH-002 and AMENDMENT-FRESH-003) found two further real, in-scope defects in
the amendment's own delta.

**AMENDMENT-FRESH-002 (severity 4).** FR-004 requires three mandatory fixtures ("no-op passable:
no") — disagreeing, agreeing, and infra-break — and User Story 3 Acceptance Scenario 2 is its own
falsifiable criterion about the agreeing case ("Given charter's lengths agree ... it reports a
clean pass with no warning noise"). The pre-amendment design had a dedicated fixture for exactly
this (`test_charter_disposition_is_none_on_agreement`), but the amendment's replacement subtask set
(T002-T006) only covered the disagreeing case (T003/T004), the strict-mode-fail case (T005), and
the infra-break case (T006) — the agreeing-case fixture was dropped entirely. T008's incidental
observation of whatever today's live repo state happens to be is not a substitute: it can silently
never exercise the agreeing branch at all and never fails specifically because that branch went
unexercised. Fixed by adding two new WP01 subtasks, **T003b** and **T004b**, one per production
gate function, each constructing a deterministic AGREEING fixture (`committed == collected`) and
asserting via the `recwarn` fixture that **zero** `ShardTimingsDriftWarning` instances are recorded
and that the function returns normally. `tasks/WP01-*.md`'s frontmatter `subtasks` list grew from 8
IDs to 10 (T001, T002, T003, T003b, T004, T004b, T005, T006, T007, T008) — a frontmatter change,
though `dependencies`/`owned_files`/`create_intent` are unaffected, so it does not by itself compel
a `finalize-tasks` re-run; the orchestrator still makes that call explicitly. `tasks.md`'s FR-004
traceability row, Subtask Index, and WP01's subtask-count summary/rationale prose were all updated
to name T003b/T004b and the new count of 10; WP01's own Success Criteria (SC-001), Test Strategy,
Risks, and Review Guidance sections were updated so none of them still enumerate a stale T003-T008
set.

**AMENDMENT-FRESH-003 (severity 2).** Spec.md's Non-Goals section still closed with "...only the
assertion behavior inside one test in that suite changes" — the same "charter-only demotion"/
"single-test" claim class that FR-003, SC-006, Charter Tension point 3 (the original amendment
pass), and C-001/Ledger Cross-Reference (this fix round's first pass) had already been corrected
for, at a third location both passes missed. Reworded to: "only the assertion behavior inside two
existing tests in that suite changes (the demotion mechanism absorbed from #5240, covering both
`test_charter_is_not_allowlisted_and_agrees` and the cross-module
`test_non_allowlisted_modules_agree_with_live_collection`; the *recapture* itself still touches
only `charter`)" — consistent with FR-003/C-001's already-corrected language. The rest of that
Non-Goals bullet (the `ci-router.yml` trigger-condition claim) was left as-is; only the trailing
clause was stale.

A quick sweep of the six amendment-touched files (spec.md, plan.md, tasks.md, WP01, WP03,
`tracer-design-decisions.md`) for any further "one test"/"only one assertion" phrasing found no
other instance of this exact defect class; plan.md's unrelated "one test-file edit"/"one
test-assertion edit" phrasing (Project Structure / Structure Decision) describes file counts and
edit-type, not a claim about how many tests or assertions the demotion mechanism touches, so it was
left untouched per this round's narrow scope.

## Fix round 3 (2026-09-28): T018's stale `xfail` wording; T004b's overstated Acceptance Scenario citation

A final fix round (`reviews/amendment.confirmed-3.yaml`, both findings severity <= 3) found two
small, precise wording defects the prior two sweeps missed.

**AMENDMENT-FRESH2-001 (severity 3).** WP03's pre-existing Subtask T018 (the docs-supersession
note, unrelated to T020) still told the implementer to write "the per-PR assertion is now
non-blocking (`xfail`)" into the committed `docs/development/reference/known-friction-points.md`
— describing the retired `pytest.xfail` mechanism, not the absorbed `ShardTimingsDriftWarning`/
`_report_drift` mechanism from #5240. Reworded to: "non-blocking (a `ShardTimingsDriftWarning`,
restorable to a hard failure via `SPEC_KITTY_STRICT_SHARD_TIMINGS=1`)", matching spec.md/plan.md/
WP01's language. No other part of T018 changed.

**AMENDMENT-FRESH2-002 (severity 2).** WP01's SC-001 sentence and its Review Guidance checklist
bullet both cited "User Story 3 Acceptance Scenario 2" as covering T003b and T004b together, but
that Acceptance Scenario is charter-specific in spec.md (`test_charter_is_not_allowlisted_and_agrees`
only) and was never amended to mention the cross-module gate. Reworded both spots to attribute the
Acceptance Scenario citation to T003b (charter) only, and to cite FR-004's general third mandatory
fixture as the authority covering T004b's cross-module case. No test code or fixture changed.

## Analyze fix (2026-09-28): T006's wrong exception class; WP01/WP02 header lines missing C-005

A fresh `/spec-kitty.analyze` run found two defects: one HIGH, one LOW.

**I1 (HIGH).** WP01's Subtask T006 code samples used `pytest.raises(Exception)` to catch
`_load_timings()`/`_load_registry()`'s missing-artefact failure, but both functions call
`pytest.fail(...)`, which raises `pytest.fail.Exception` (`_pytest.outcomes.Failed`) — not a subclass
of `Exception`. As written, both tests would themselves fail instead of passing. Changed both
occurrences to `pytest.raises(pytest.fail.Exception)`, matching T005's already-correct pattern.

**I2 (LOW, cosmetic).** `tasks.md`'s `**Requirements**:` summary lines under WP01 and WP02 omitted
`C-005`, even though both WPs' frontmatter `requirement_refs` and the FR/NFR/Constraint
traceability table already include it (WP03's line already did). Added `C-005` to both lines.

## Fresh-sweep fix (2026-09-27): FR-007's "always push" framing corrected

A post-spec fresh-sweep review (`reviews/spec-fresh-6.yaml`, SPEC-FRESH6-001) found that the sweep
above was itself incomplete: FR-007's own "As a maintainer, I want..." want-clause still asserted,
unconditionally, that the job "always push[es] its capture to one constant, fixed head branch" —
directly contradicting the same table cell's skip-if-open sentence two sentences later ("When such
a PR exists, the job does not push, force-push, comment, or open anything"). This was leftover
phrasing from ruling 1's original "always pushes, then optionally force-updates" framing that
ruling 2's "skip if open" edit did not fully catch. A softer echo of the same "always pushes to"
phrasing also survived in User Story 2's Acceptance Scenario 3. Both are corrected: FR-007's
want-clause now reads "...push its capture to one constant, fixed head branch (...) whenever no PR
from that branch is currently open, and to detect..."; AC3 now reads "...the single fixed branch
this workflow is permanently pinned to (used whenever it does push; see Key Entities)...". The
fixed/constant branch identity itself (ruling 1 point 1) and the skip-if-open mechanism (ruling 2)
are unchanged — this is a wording-only fix to stop the FR from contradicting itself, not a design
change. The Key Entities "scheduled recapture workflow" and "recapture head branch" bullets were
checked and already correctly condition the push ("pushes ... when no PR ... is currently open, or
... skips entirely ... when one is already open"); no change was needed there.

## Fresh-sweep fix (2026-09-27): stale-branch-replacement mechanism explicitly deferred to plan; force-push guarantee scoped to the skip-if-open path

A third fresh-sweep review (`reviews/spec-fresh-8.yaml`, SPEC-FRESH8-004) found a genuinely new
ambiguity introduced by rulings 1/2's reused-fixed-branch design, not present before it (the
pre-ruling spec never reused a branch, so this case did not exist). The Key Entities "recapture
head branch" bullet stated "the job never force-pushes, in any case" as an unconditional
guarantee, but the same paragraph's stale-branch-replacement carve-out — triggered when the fixed
branch still exists with no open PR (e.g. a previously closed PR) and a new run finds drift —
only ruled out force-updating a PR *under review*; it never said whether the replacement
mechanism itself may be a force-push. Ruling 2 eliminated force-push specifically because it is
unsafe against a PR under active review, and no PR is under review in the stale-branch case, so
the "in any case" wording and the carve-out's careful "of a PR under review" qualifier were in
real tension. Fixed by (1) scoping "the job never force-pushes, in any case" explicitly to the
skip-if-open path ("while a PR from this branch is open, the job never force-pushes, in any
case"), and (2) explicitly deferring the stale-branch replacement mechanism to the plan phase,
mirroring the FR-004/Charter-Tension-point-4 pattern rather than the FR-011/FR-012 route this
spec already rejected once (ruling 2): the plan may choose any git mechanism (delete-and-recreate
the ref, force-push, or another approach), bound by one fixed, falsifiable observable
requirement — the stale branch's prior content is fully replaced by the fresh capture. No FR/SC
text changed; the fix is confined to the Key Entities "recapture head branch" bullet's two
sentences the finding cited.
