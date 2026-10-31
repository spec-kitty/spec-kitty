---
schema_version: 1
artifact_type: spec-kitty.analysis-report
command: /spec-kitty.analyze
mission_slug: reject-invalid-forced-status-rewind-01M68J8B
mission_id: 01M68J8B3G2N6W1D4Y1FADR15Z
generated_at: '2026-10-31T10:07:48.815649+00:00'
analyzer_agent: pi
input_artifacts:
  spec.md:
    path: kitty-specs/reject-invalid-forced-status-rewind-01M68J8B/spec.md
    sha256: d58939b2cc9882e7df3efdec0526b4e181545ec8b49d4ada7211e6574297db90
  plan.md:
    path: kitty-specs/reject-invalid-forced-status-rewind-01M68J8B/plan.md
    sha256: 0b853ef7cfbe1ff22faa18fe0e3a83572c075c2bc51fdafd34fb78f39315d383
  tasks.md:
    path: kitty-specs/reject-invalid-forced-status-rewind-01M68J8B/tasks.md
    sha256: 75cbea180897d875fbccf409bb512d98bd8d01d53e69f489b0fb1f659c54d973
  charter:
    path: .kittify/charter/charter.yaml
    sha256: 83874f7451d21cf0615682164d7bb883844ee032e7622bb1359a343fd0e6fb03
verdict: unknown
issue_counts:
  high:
  medium:
  critical:
  info:
  low:
findings: []
---

# Analysis report: reject-invalid-forced-status-rewind-01M68J8B

Cross-artifact consistency check over `spec.md`, `plan.md`, `tasks.md` and the three WP
prompts, against the charter. Run after the tasks step and applied before implementation.

## Verdict

**ready** — no critical or high findings. Two low findings were accepted and fixed in place;
one low finding is recorded as a limit, not a gap.

## Coverage

| Requirement | Owning WP(s) | Note |
|---|---|---|
| FR-001, FR-002, FR-003, FR-005, FR-006 | WP01 | the rule + the refusal footprint + the message |
| FR-004, FR-007, FR-008, FR-009 | WP02 | the pointer path and the untouched neighbours |
| FR-010 | WP03 | the documented position |
| NFR-001, NFR-002, NFR-003 | WP01 | byte-identical refusal, no added round trips, `--json` observability |
| C-001, C-003 | WP01, WP02 | one definition; no force widening |
| C-002, C-004 | WP03 | no byte rewriting; release scope untouched |
| SC-001, SC-002, SC-006 | WP01 | |
| SC-003 | WP01, WP02 | the positive control, asserted at both the CLI and the second door |
| SC-004, SC-005 | WP02 | |

Every FR, NFR, C and SC is owned. `finalize-tasks` reports zero unmapped FRs and zero
success-criteria gaps.

## Findings

### L1 — `NFR-002` had no owning work package — **fixed**

`tasks.md` listed `NFR-001, NFR-003` on WP01 and dropped `NFR-002` ("no added round trips on
the legal path"). A binding non-functional requirement with no owner is not tracked by any
prompt. Added `NFR-002` to WP01's `requirement_refs` and to the WP01 requirements line; both
`tasks.md` and the prompt now carry it, and `finalize-tasks --validate-only` still passes.

### L2 — `T011` named docs gates that do not exist — **fixed**

The T011 gate list included `tests/architectural/test_docs_lint.py` and
`tests/architectural/test_docs_links.py` behind `|| true`. Neither file exists in the tree,
and the `|| true` would have hidden their absence — a vacuous gate. Replaced with the gates
that are real and relevant: `scripts.docs.check_docs_freshness --ci`,
`scripts.docs.check_changelog_style` (the entry-shape and length bound for the new
changelog row), and `tests/architectural/test_no_legacy_terminology.py`. Added the rule to
the prompt: do not add a gate that does not exist.

### L3 — `NFR-002` is asserted by construction, not by a timed test — **limit, accepted**

There is no timing assertion anywhere in the mission. That is deliberate: the rule is a
membership test over two already-resolved lanes, evaluated from the request object the write
path already holds, so "no extra file read or subprocess" is a structural property, not a
measurement. Reviewing it is a code-reading task (does the new branch touch the filesystem
or spawn anything?), and the WP01 prompt says so. Recording it here so a later reader does
not mistake the absence of a benchmark for an oversight.

### I1 — the `done -> in_progress` row in contract C-3 is a forced terminal exit

`done` is terminal and `WPState.check_transition` requires force for every outbound edge
from it. C-3's table asserts those rows stay allowed *with* `force` + reason, which matches
the code (`DoneState.allowed_targets()` is empty, so force is the only route). No change
needed; noted so a reader does not read the empty edge set as a contradiction.

### C1 — charter conformance

| Principle | Check |
|---|---|
| Single canonical authority | One predicate (`requires_review_ref`) owns the fact; the writer and the auditor both read it. A second inline copy is named as a review finding in the WP01 prompt. |
| Architectural alignment | No new module, no new package edge; `validate.py -> wp_state.py` already exists. |
| ATDD-first | WP01 T001 is a committed-red CLI acceptance test through the real command, with a same-fixture positive control. |
| Terminology canon | Mission/lane vocabulary only; no `feature*` identifier introduced. |
| Append-only history | No historical event is rewritten; the diff never touches a committed `status.events.jsonl`. |
| No force-policy widening | The change removes one illegal admission; C-003 forbids granting force new reach. |
| No heavy suites | Named files only. |
| Adversarial squad | Not required at this size (a two-module rule plus tests); the review round still runs on the integrated diff. |

## Post-implementation update (re-analysis after WP01)

Implementing WP01 falsified two assumptions in the first pass. Both are now recorded in
`research.md` (§3, D-7) and in the plan; the analysis below is the updated position.

### W1 — `move-task`'s auto-promoted rewind was a SECOND invalid writer — **fixed in WP01**

The first pass (and the original research) said `move-task` already conformed because it
supplies `review_ref="force-override"`. That was only true for an explicit `--force`:
`build_transition_plan` reads the operator's flag, while an unforced `for_review →
in_progress` is auto-promoted to `emit_force=True` further down the same function.
Measured on the pre-fix tree: `move-task WP01 --to in_progress` exited 0 and appended
`force=true, review_ref=null`. Fixed by filling the plan's own existing sentinel after
`emit_force` is final (research D-7). This is not the D-1 anti-pattern — the sentinel is
`move-task`'s declared vocabulary for an operator rewind.

### W2 — `agent action implement`'s review-lane withdrawal was a THIRD writer — **fixed in WP01**

`status/work_package_lifecycle.start_implementation_status` withdraws an implementer of
record (or an operator-forced WP) from the review lane to `in_progress` with `force=True`
and no pointer. This is a documented, tested operator move
(`test_implementer_of_record_withdraws_for_review_with_honest_reason`,
`test_operator_force_with_note_leaves_any_review_lane[for_review]`), so refusing it would
break behaviour the mission never set out to change. It now supplies the same
`force-override` sentinel; both tests assert the pointer.

### W3 — the golden parity baseline needed a deliberate 2-row amendment

`tests/status/fsm_parity_baseline.jsonl` flipped exactly
`for_review->in_progress[force_full]` and its alias `for_review->doing[force_full]`
(True → False) — the intended behaviour change and nothing else. The amendment is dated and
justified in a comment beside the baseline path in `tests/status/test_transitions.py`, so it
reads as a shipped change rather than a regeneration to silence a red.

### W4 — review round 1 (self-run) findings — **fixed in WP01**

1. The "requirement satisfied" expression was duplicated at the two authorities; extracted
   `has_review_ref()` so the writer and the auditor read one definition (strengthens C-001).
2. The auditor would have raised `AttributeError` on a non-string `review_ref` in a corrupt
   log where it previously just reported; `has_review_ref` now requires a non-blank `str`,
   pinned for int/list/dict/float.

Re-checked after the updates: every FR/NFR/C/SC is still owned, `tasks.md` is unchanged in
scope, and `finalize-tasks --validate-only` still passes.

## Re-run

`spec-kitty agent mission finalize-tasks --mission reject-invalid-forced-status-rewind-01M68J8B --validate-only`
after the L1/WP01 edit: `validation_passed`, 3 WPs, no ownership warnings.
