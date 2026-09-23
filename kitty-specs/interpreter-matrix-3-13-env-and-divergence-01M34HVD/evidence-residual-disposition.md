# WP06 — Residual-red disposition + #3189 filing (FR-006)

Owned by WP06 (`kitty-specs/interpreter-matrix-3-13-env-and-divergence-01M34HVD/tasks/WP06-residual-disposition.md`).
Consumes WP05's re-measured evidence (`evidence-remeasurement-3.13.md`, commit
`d6e0e5a5f`) directly, per WP06's own instruction not to re-derive numbers
from raw pytest output. This is a documentation/decision WP — no `src/` or
`tests/` files were touched.

## T001 — Classification of WP05's residual against WP02's fixed `dir_fd` failures

**Input** (WP05's re-measurement, 3.13.15, `.venv313`, `-n auto`,
`-m "fast or unit"`, 2026-09-22):

```
23 failed, 34666 passed, 146 skipped in 475.87s
(junitxml cross-check: errors="0" failures="23" tests="34835")
```

**Step 1 — WP02's fixed IDs confirmed absent.** WP05's own "WP02 validation"
section already checked the fuller 5-ID `dir_fd` set (not just the "4" spec.md
names — see the Inconsistencies section below) against this run's 23-item
failure list and found zero matches; independently re-confirmed here by
grepping WP05's full 23-ID list against the 5 IDs:

```
tests/kernel/test_lock_parity.py::test_naive_second_open_of_a_held_lock_raises_under_simulation
tests/kernel/test_lock_parity.py::test_sync_primitive_never_reopens_the_resource_while_held
tests/kernel/test_lock_parity.py::test_async_primitive_never_reopens_the_resource_while_held
tests/kernel/test_no_follow.py::test_read_rejects_symlink_planted_before_open
tests/specify_cli/core/test_no_follow.py::test_read_rejects_symlink_planted_before_open
```

None appear in WP05's 23-item failure list. WP02's fix held — no
contradiction, this WP proceeds.

**Step 2 — subtract the 3.11 baseline (WP01's 20, `evidence-baseline-3.11.md`).**
WP05's own classification (Group 1/2/3 in `evidence-remeasurement-3.13.md`)
already performed this diff:

- **Group 1 — failing on both 3.11 and 3.13: 20/20**, exact 1:1 match with
  WP01's baseline. Pre-existing, already reported at #4916, not interpreter
  divergence.
- **Group 2 — failing only on 3.13: 3.**
- **Group 3 — failing only on 3.11: 0.**

`23 (total 3.13 failures) - 20 (pre-existing, matched to baseline) = 3`
residual. Arithmetic checks out against the raw counts, not asserted from
confidence.

**Step 3 — classification.** The 3-ID residual is **large-and-out-of-scope**,
per WP06's prompt's own skepticism note: none of the 3 are in `src/`, but
fixing them would require diagnosing root cause in test/product code
(`_artifact_path_is_contained` behavior, CLI text-wrapping, or an
`OwnerAssessment` dataclass truthiness/equality edge case) that this
mission's C-001 blast radius does not name and C-002 explicitly forbids
pursuing. This is **not** a "zero residual" outcome and **not**
"small-and-fixable-in-scope" — it is the expected, charter-sanctioned
outcome spec.md's own Edge Case (c) framing anticipated.

## T002 — Filing against #3189

**#3189 re-verified live** (not assumed from the plan/spec's snapshot):

```
$ gh issue view 3189 --repo spec-kitty/spec-kitty --json number,state,title,url
{"number":3189,"state":"OPEN","title":"ci: no pytest job runs above Python
3.12, so interpreter-divergence defects are invisible to the gate",
"url":"https://github.com/spec-kitty/spec-kitty/issues/3189"}
```

Still open, still the workflow's own declared home for above-3.12 divergence.
Its scope ("no CI job runs pytest above 3.12, so interpreter-divergence
defects are invisible to the gate") cleanly absorbs these 3 findings — they
are exactly the class of defect #3189 describes, discovered by the very
nightly leg #4866 stood up. No new issue was needed.

**Comment posted**:
<https://github.com/spec-kitty/spec-kitty/issues/3189#issuecomment-5782934410>

The comment:
- States the correction prominently: the original #4866 issue text's **429**
  3.13-only-failure figure is retracted — it was contaminated by the
  shared-`.venv` corruption defect (fixed under #4866, residual live call
  sites tracked at #4922), not real interpreter divergence.
- Gives the exact re-measurement command, counts, and junitxml cross-check.
- Gives the node-ID diff against the 3.11 baseline: 20/23 pre-existing
  (matched to #4916), 3/23 genuine 3.13-only divergence, 0/23 3.11-only.
- Lists the 3 residual node IDs with their observed symptom each (assertion
  output only — no root cause asserted beyond what the failure shows).
- Cross-links #4866 (this mission), #4916 (the 3.11 baseline issue), and
  #4922 (the venv-corruption follow-up for the two still-live `uv run`
  call sites).
- States the disposition: #4866's `interpreter-matrix` nightly leg will
  continue to report red from these 3 until #3189 (or a future targeted fix)
  addresses them — that red is accurate signal, not a defect in #4866's own
  work.

No third issue was opened for the WP04 venv-corruption finding — that is
already tracked at #4922 (WP04's own follow-up), and the #3189 comment
cross-links it rather than duplicating it, per T002 step 3's instruction.

## T003 — Disposition statement (verbatim for PR-prep / WP07's PR body)

> **FR-006 disposition: large-and-out-of-scope residual, filed against
> #3189.** After all three in-scope fixes landed (kernel `dir_fd` shim fix,
> `uv run` interpreter/extras pinning fix, venv-corruption mitigation) and
> WP05's clean re-measurement was taken (23 failed / 34666 passed / 146
> skipped in 475.87s on Python 3.13.15, `-n auto`, `-m "fast or unit"`), the
> node-ID diff against the 3.11 control baseline (#4916, 20 failures) shows:
> 20/23 failures are pre-existing and already tracked at #4916 (not
> interpreter divergence), and exactly **3** failures are genuine 3.13-only
> divergence, outside this mission's C-001/C-002 scope. Those 3 are filed
> with full re-measured evidence as a comment on #3189
> (<https://github.com/spec-kitty/spec-kitty/issues/3189#issuecomment-5782934410>),
> the workflow's own declared home for above-3.12 divergence. **The
> `interpreter-matrix` nightly leg will continue to report an honest red
> from these 3 residual failures after this mission merges — it does not
> turn green.** That red is correct, disclosed signal under charter Standing
> Order 9, not a defect in this mission's fixes: the leg's own inline
> comment already scopes it to "NOT the full above-3.12 suite burn-down"
> (#3189's deferred scope). This mission's real, load-bearing correction is
> that the originally-reported 429 3.13-only-failure figure was an artifact
> of a separate, now-fixed shared-`.venv` corruption defect (#4866 WP04,
> residual tracked at #4922) — the true interpreter divergence this mission
> surfaces is 3 failures, not 429.

**Explicit non-claim, stated for the reviewer**: this document does **not**
claim or imply the nightly leg turns green. It will still fail 3 of its
`fast or unit` node IDs after this mission's PR merges, by design, per the
disposition above.

## Inconsistencies flagged by other WPs — this WP's read

Per WP06's dispatch, reporting on (not fixing) three artifact
inconsistencies flagged by earlier WPs but outside this WP's `owned_files`:

1. **spec.md's "4 confirmed `dir_fd` failures" vs. the actual 5-ID set** WP02's
   tracer and WP05's check both used. **Does not matter for this WP's
   disposition** — WP05 already checked the fuller, more conservative 5-ID
   set (not spec.md's "4") and confirmed all 5 absent from the 3.13
   re-measurement, so WP02's fix is validated regardless of which count
   spec.md states. It **is** a real, reader-visible inconsistency for the PR
   though: a reviewer comparing spec.md to WP02/WP05's evidence will notice
   the "4" vs "5" mismatch and may (reasonably) ask which is authoritative.
   Recommend PR-prep/the orchestrator note this explicitly in the PR body
   (evidence uses 5, spec.md's prose says 4, the fix covers all 5 either
   way) rather than silently hand-editing spec.md, which is out of scope for
   any implementer WP per governance.

2. **WP05's task file and plan.md's IC-05 instructing a re-sync of the
   checkout's own `.venv` to 3.13.** Already correctly overridden by WP05 on
   my instruction (documented in `evidence-remeasurement-3.13.md`'s opening
   discrepancy note) — `.venv313` was used instead, and `.venv` was
   confirmed still 3.11.15 both before and after WP05's run, and again here
   at the end of WP06 (see below). **Does not bear on this WP's
   disposition** — it's a process-integrity note already fully resolved and
   recorded by WP05. No further action needed from WP06.

3. **WP05's task prompt saying the 3.11 baseline is "21 failed" vs. the
   actual recorded 20.** Also already flagged and correctly resolved by WP05
   (used the real 20-ID artifact, not the prompt's "21" paraphrase).
   **Does not bear on this WP's disposition** — this WP's own T001 arithmetic
   above independently uses WP01's real 20-failure artifact, consistent with
   WP05's resolution. Worth a PR-body mention so a reviewer doesn't think the
   "20" here is a typo for "21", but not a blocker.

None of these three inconsistencies change T001's classification, T002's
filing, or T003's disposition statement — all three were already correctly
navigated by earlier WPs before this WP started, and none touch the 3
residual node IDs this WP's disposition is about.

## Cheap targeted verification run performed by this WP

Per the dispatch's authorization to re-run only the 3 node IDs (not the full
suite), the 3 were re-run standalone against `.venv313` (Python 3.13.15,
`UV_PROJECT_ENVIRONMENT=.venv313`, never the checkout's own 3.11.15 `.venv`):

```
$ UV_PROJECT_ENVIRONMENT=.../.venv313 .venv313/bin/python -m pytest \
    tests/dashboard/test_artifact_containment.py::TestArtifactPathIsContained::test_unresolvable_path_is_not_contained \
    tests/specify_cli/cli/commands/test_glossary_validate.py::TestValidateSingleFileValid::test_human_output_shows_valid \
    "tests/specify_cli/tool_surface/providers/test_command_skills.py::test_wp04_dispatch_config_observation_boundary[loop]" \
    -v
2 failed, 1 passed in 2.87s
```

- `test_unresolvable_path_is_not_contained`: **failed**, deterministically,
  standalone. `AssertionError: assert True is False` —
  `_artifact_path_is_contained(...)` returned `True` for an unresolvable
  path where the test expects `False`.
- `test_human_output_shows_valid`: **passed** standalone (re-run twice more
  to confirm — passed both additional times, 3/3 standalone passes). This
  differs from WP05's full `-n auto` run, where this node ID was in the
  23-item failure set. The failure is therefore **context-sensitive** (only
  observed under the full parallel `fast or unit` run, not reproduced in
  isolation) — recorded as an observed fact, not explained further; no
  cause is asserted for why isolation changes the outcome.
- `test_wp04_dispatch_config_observation_boundary[loop]`: **failed**,
  deterministically, standalone. `assert assessment.complete is not broken`
  → `AssertionError: assert True is not True` — `OwnerAssessment.complete`
  evaluates `True` on both sides of an `is not` comparison the test expects
  to differ.

This does not change T001's classification: WP05's full `-n auto` run (the
canonical re-measurement this mission's numbers are built on) is the
authoritative record of what the nightly leg itself will observe (the real
`ci-nightly.yml` job also runs the full `-n auto` `fast or unit` selector,
not an isolated 3-node subset) — all 3 IDs are confirmed real 3.13-only
divergence relative to the 3.11 baseline regardless of this standalone
re-check's isolation-sensitivity finding for ID 2. The isolation-sensitivity
detail was included in the #3189 comment as additional, honestly-reported
context, not as a reason to discount the finding.

## Environment integrity at WP06 close

```
$ .venv/bin/python -V
Python 3.11.15
```

Still 3.11.15, unchanged by this WP — `.venv313` was used exclusively for
the targeted verification run above, per the dispatch's instruction never
to touch the checkout's own `.venv`.

---

*Recorded by WP06 (`python-pedro`/implementer). PR-prep (WP07) copies T003's
disposition statement verbatim into the mission's PR body.*
