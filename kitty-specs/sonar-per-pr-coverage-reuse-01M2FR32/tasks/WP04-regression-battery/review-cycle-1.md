---
affected_files: []
cycle_number: 1
mission_slug: sonar-per-pr-coverage-reuse-01M2FR32
reproduction_command:
reviewed_at: '2026-09-14T15:43:22Z'
review_status: acknowledged
reviewer_agent: user
wp_id: WP04
---

# WP04 review — REJECT (architect-alphonso, independent of implementer per C-007)

Commit reviewed: `9fdbf2352d`. Battery runs green (24 passed, 1.70s). The craft here is
high and most claims verified true. One blocking finding, one overclaim to correct.

## Verified TRUE (no action)

- Mutations 1-4 are genuinely non-vacuous. The negative control discriminates through the
  *same code path*: `make lint` -> `{}`, `make test-fast` -> `{'sonarcloud': 1}`. Not a
  rule keyed on the job name.
- Directory enumeration is real; mutation 4 confirmed red on a copy of the live tree.
- Both ledgers' "rows must stay earned" guards mutation-tested and correctly RED on a
  stale row and on an empty rationale (all four cases).
- The WP06 flip seam is LIVE: emptying `KNOWN_LIVE_DUPLICATES` today reds
  `test_live_tree_duplicate_set_is_exactly_the_known_set`.
- Diff stays strictly inside ownership (only the two owned files). Declining to patch
  `_gate_coverage.py` / `.github/` and reporting instead was the CORRECT call under
  ownership discipline. Lane hygiene clean: empty `kitty-specs/` delta, nothing untracked.
- Shard-map registration correct and well-reasoned.

## BLOCKING — F1: `change_triggered()` fails OPEN; 6 evasions walk straight through

`_on_section()` returns `{}` for any `on:` block that is not a mapping, and
`CHANGE_TRIGGER_EVENTS` is a 2-element allow-list. A workflow that is not classified
change-triggered is invisible to **every assertion in the module**. I planted
`- run: make test-fast` in a net-new workflow and got it past the rule 6 ways:

| # | Trigger spelling | `change_triggered` | Real? |
|---|---|---|---|
| 1 | `on: [push, pull_request]` (list form) | False | **idiomatic GHA; no adversary needed** |
| 2 | `on:\n  pull_request_target:` | False | standard trigger for jobs needing secrets on fork PRs |
| 3 | `on: push` (bare scalar) | False | runs on every push |
| 4 | `on:\n  push:\n    paths: [...]` | False | per-change |
| 5 | `on:\n  push:\n    branches-ignore: [...]` | False | per-change |
| 6 | `on:\n  merge_group:` | False | merge queue, per-change |

Plus 2 command-layer escapes inside an ordinary `pull_request` workflow: `env: CMD: make
test-fast` + `run: $CMD`, and `run: ${{ matrix.cmd }}`.

Why this is blocking rather than a note:

1. The task's Reviewer Guidance is an explicit acceptance bar: *"If you can get the
   duplicate past the rule in under ten minutes, the battery is not done."* I did, 8 ways,
   in well under it. Case 1 is the most ordinary `on:` spelling in GitHub Actions.
2. It is **fail-open in WP04's own code**, not inherited from `_gate_coverage`. The honest
   -disclosure defence that legitimately covers the four blind surfaces does not reach it:
   the docstring's "Known residual gaps" lists four *command-layer* gaps and says nothing
   about trigger classification.
3. It is the exact defect class this WP exists to close — a gate that stays green while the
   tree violates the property — recurring one layer up.
4. §C5's non-vacuity floor does not catch it: it asserts the scanned set is non-empty and
   contains `ci-aggregate.yml`, which stays true while an arbitrary number of workflows are
   silently dropped.
5. WP05 is next and wires the reporting job. `pull_request_target` is a plausible spelling
   there (secrets on fork PRs), so the hole is reachable by the very next work package.

No live workflow uses these spellings today, so nothing is currently mis-gated — this is a
latent hole in a **permanent** gate, not an active miss.

### Fix (cheap, entirely inside your owned file — I prototyped it)

Make the classifier fail **closed**: normalise the scalar and list forms of `on:`, add
`pull_request_target` and `merge_group`, treat a `push` with `branches`/`paths`/
`branches-ignore` or an unknown shape as per-change (keep tags-only = not per-change), and
return True for an unrecognised event or an unparseable block. ~15 lines.

Measured: **zero classification drift across all 15 live workflows** (`ci-nightly`,
`sonar`, `release`, `module-tests` still correctly excluded), and all 6 evasions caught.
So it is behaviour-preserving on the real tree.

Please add fault-injection twins for at least the list form and `pull_request_target`, and
extend the §C5 floor from "the set is non-empty" to "every live workflow is classified and
none is dropped by a parse fallback" — that is the assertion that would have caught this.

Also either guard or explicitly disclose the two command-indirection forms (`env:` var,
`matrix` var) in the docstring's residual-gaps list.

## NON-BLOCKING — F2: the "one edit" seam claim is overclaimed

The commit message and the in-file seam banner both say WP06 flips
`KNOWN_LIVE_DUPLICATES` *"and nothing else in this module"*. I simulated the WP06 world
(retire the `make test-fast` step from `ci-quality.yml::sonarcloud` + empty the dict):
**5 tests red**, not 0.

- `test_mutation1_canonical_retiring_step_is_detected_in_the_live_tree` — asserts
  `RETIRING_JOB in live`; structurally cannot survive the retirement.
- `test_mutation_control_...`, `test_mutation2_...`, `test_mutation3_script_wrapper...`,
  `test_mutation3_make_delegation_hop...` — all four via `mutate_real_ci_quality`'s
  `LIVE_SUITE_STEP_LINE` anchor assertion.

The anchor guard firing loudly is *good design* and the messages are self-describing, and
WP06 co-owns the file per its own task, so this is not a plan violation. But the claim as
written is false and would mislead WP06. Please reword the banner and note that WP06 must
also re-anchor `LIVE_SUITE_STEP_LINE` onto a surviving live suite step and rework
mutation 1 — ideally by parameterising `mutate_real_ci_quality` on the host workflow now,
so mutations 1-3 keep a real-file substrate after the retirement (the battery is permanent;
its post-WP06 shape is in scope).

## Position on the central question — deny-list vs. closing the class

Asked whether "refuse forms rather than understand them" is legitimate or relocated
blindness, my ruling is: **legitimate for the four disclosed surfaces, not legitimate for
the trigger classifier.**

The distinction is where the burden of the unknown falls. `BLIND_RUNNER_RES` /
`BLIND_MAKE_REFS` enumerate known-bad spellings; their failure mode is an unknown spelling
walking through — which is the pre-existing status quo, not a regression. Scoped,
disclosed, each with a fault-injection twin and a negative control, with the real fix
(widen `_gate_coverage`) named and outside this WP's ownership. That is a defensible
holding action and I accept it. Note it does close *instances*, not a *class* — the
class-closing shape is a closed-world allow-list ("any unresolved standalone `pytest` word
in a change-triggered workflow is refused"), which you considered and rejected in the
`BLIND_RUNNER_RES` comment for a real reason (prose lines in workflows you do not own).
That objection is soluble with a shrink-only exception ledger — the pattern you already use
twice in this file — and is the right follow-up, but not a rejection cause.

F1 is different in kind and that is why it blocks: it is not a deny-list at all but an
undisclosed 2-element **allow-list that fails open**, in code this WP wrote, where the
closed-world form costs ~15 lines and provably loses nothing. There the class really can be
closed by construction, so declining to is not a holding action — it is the blindness the
battery exists to remove, one layer up.

## Evidence / test scope

Per the operator's binding ruling the full `tests/architectural/` suite was NOT run (CI owns
it). Targeted only, via the root venv (the lane `.venv` lacks `pytestarch`):

```
cd <lane> && PYTHONPATH=<lane>/src <root>/.venv/bin/python -m pytest \
    tests/architectural/test_no_duplicate_suite_execution.py -q
=> 24 passed in 1.70s
```

Mutation experiments (all reverted; `git status --porcelain` clean at exit):
- WP06 flip applied early -> 2 failed / 22 passed (seam is live)
- WP06 world simulated (step retired + dict emptied) -> 5 failed / 19 passed (F2)
- 4 ledger mutations via direct module monkeypatching -> all 4 correctly RED
- 8 evasion workflows planted into a copy of the live workflow dir -> 8 escaped (F1)
- fixed classifier prototype -> 0 live drift, 6/6 evasions caught, 3/3 negatives preserved

On the `no_coverage` gate report: acceptable as evidence *here*. The injected ScopeSource
had no test command configured, which is a harness gap and not something the implementer
could route around, and the recorded counts are reproducible — I re-ran the battery from a
clean checkout and got the same 24/24. It is not a substitute for CI on the full suite.

Known pre-existing reds (#4365: `test_archive_root_byte_identical`,
`test_pack_manifest_no_author_edit`, `test_ruff_format_exclude_ratchet`) were not run and
are not attributed here.
