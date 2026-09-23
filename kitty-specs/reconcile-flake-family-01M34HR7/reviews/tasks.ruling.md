# Operator ruling — tasks phase HALT

**Mission**: `reconcile-flake-family-01M34HR7` (epic #4882)
**Phase**: tasks
**HALT raised at**: commit `d2f2afc81`, findings in `reviews/tasks-fresh-2.yaml`
**Ruled**: 2026-09-22
**Ruled by**: operator, relayed by the mission orchestrator

## Ruling

**All four surviving findings are ACCEPTED. Additionally, `plan.md` IS AUTHORIZED to be
amended** — see the scope and constraints below. Fix, verify, resume.

### TASKS-FRESH2-001 (severity 4) — ACCEPTED; plan.md amendment AUTHORIZED

The orchestrator independently verified this against the checkout before escalating, and the
finding is stronger than "stale prose": **the claim in `plan.md:424-428` is structurally
impossible.**

That paragraph states the `elif evidence["state"] != "red"` branch "is untouched; the retry
loop only wraps the *unstable-evidence* path, not this already-benign early return." But the
branch's condition **reads `evidence`** — the variable bound by the first `snapshot()` call
(`scripts/ci/fleet_main.py:100`). Once `_attempt()` re-snapshots per attempt, `evidence` is
per-attempt by construction, so the `elif` is re-evaluated on every attempt whether or not
anyone intends it. A branch cannot be held outside a retry that redefines the variable it
tests. Live code supports the tasks-phase reading; `plan.md` carries the incorrect claim.

**Authorized remediation**: amend the `plan.md` "`fleet_main.py::report()` rewiring" paragraph
so it describes what the code and the WP02 task actually require.

**Constraints on that amendment — it is a frozen, already-PASSED artifact:**

1. **Scope is exactly this paragraph.** The amendment corrects the `elif`/retry-boundary
   description. It does not touch the architecture, the retry seam, the gate set, the campsite
   decision, or the WP split. Any other edit to `plan.md` is out of scope and is itself a
   finding.
2. **Separate, clearly-labelled commit.** Do not fold it into a tasks fix commit. Message must
   make plain it is a post-PASSED correction to a plan artifact made on operator authority —
   e.g. `fix(plan): correct elif retry-boundary claim superseded by live code (ruling-authorized)`.
3. **Verify against the code, not against this ruling.** The corrected text must match what
   `scripts/ci/fleet_main.py:99-138` actually does. A verifier confirming the text matches this
   document has verified nothing.
4. **Recorded consequence, stated here so it is not discovered later**: `plan.md`'s original
   R1–R6 verdict no longer covers its current text. This ruling is the authority for the
   delta, and the amendment commit plus this file are the audit trail. `sk-review` should read
   both.

### TASKS-FRESH2-002 (severity 4) — ACCEPTED

Verified: `scripts/ci/fleet_main.py:100-104` places the `dry_run` check immediately after the
first `snapshot()` and before the incident lookup — inside the exact span T009 claims
`_attempt()` wraps — while the shared Context says `dry_run` "stays exactly where it is,
outside the retry loop." A literal implementation routes `dry_run` through
`retry_with_backoff` (real sleeps, wrong/duplicate stdout) and breaks
`tests/ci/test_fleet_main.py:260::test_main_cli_dry_run_is_read_only`, which exists today.

**Remediation**: apply the reviewer's stated fix — an explicit T009 clause that the `dry_run`
check stays in `report()` itself, evaluated before `retry_with_backoff`/`_attempt()` is called,
using its own single pre-loop `snapshot()` exactly as today.

### TASKS-FRESH2-003 (severity 3) — ACCEPTED

Reconcile the new fourth outcome (`_NothingToReport()`) against the Context's "tri-state"
framing of `_attempt()`'s contract, and show it in the wrapper pseudocode. A documented
contract that omits a real outcome is the silent-success class this repo is worst at.

### TASKS-FRESH2-004 (severity 2) — ACCEPTED

Relabel the `elif` terminal outcome so it is not conflated with `_Ready`'s publish-worthy
success. `_NothingToReport` publishes nothing; calling it "SUCCESS" invites an implementer to
treat the two identically.

## Constraints on the fix round

1. **Fresh subagents.** The fixer must not be the author; the verifier must not be the fixer.
   Independence is the property under protection.
2. **Commit the review trail.** `reviews/tasks*.yaml` is currently uncommitted; commit the
   WHOLE trail — merged, refute, confirmed, verify, both fresh sweeps — plus this ruling.
3. Do **not** reopen the two binding operator decisions in `spec.md`
   (`## Clarifications / Decision Record`): epic scope, and unit-tests-plus-post-merge-watch
   verification. Settled.
4. Do **not** self-authorize additional rounds beyond this one, and do not characterize this
   ruling as granting latitude it does not state. Another HALT comes back to the operator.
5. Public-repo hygiene: add no new absolute `/home/<user>/...` paths to any artifact.

---

# Operator ruling #2 — tasks phase, round-3 HALT

**HALT raised at**: commit `68205dde6`, findings in `reviews/tasks-fresh-3.yaml`
**Ruled**: 2026-09-22
**Ruled by**: operator, relayed by the mission orchestrator

## Orchestrator's error, stated first

**TASKS-FRESH3-002 and TASKS-FRESH3-003 were caused by ruling #1, not by the tasks phase.**
Ruling #1 constrained the `plan.md` amendment to "exactly this paragraph" in order to protect
a frozen, already-PASSED artifact. That constraint was wrong: the stale tri-state claim had
siblings at `plan.md:198` ("same shape as (3)") and in the "Existing Test That Must Change"
section (`plan.md:589`). Scoping the correction to one paragraph *guaranteed* `plan.md` would
end up contradicting itself. The tasks phase agent complied with the constraint exactly as
written and then correctly reported the resulting contradiction. No fault attaches to it.

The correct scope, applied now: **every statement in `plan.md` about the `_attempt()` outcome
contract, the elif/retry boundary, and the terminal paths of the `fleet_main.py` re-pin.**

## Ruling

**All three findings ACCEPTED. Widened plan.md amendment AUTHORIZED. This is the FINAL round
of the tasks phase.**

### TASKS-FRESH3-001 (severity 4) — ACCEPTED; remediation (b)

Verified independently: `tests/ci/test_fleet_main.py:239-243`'s `RerunAPI` keys its mutation
on `self.head_reads == 1` — the *second* head read. It is call-order-sensitive, so round 3's
new pre-loop `snapshot()` shifts which call that is, and with it what the test exercises. A
test re-pinned to prove a two-snapshot comparison that no longer drives two attempts has lost
the property it exists for. Charter standing order 4 treats that as a severity-4, correctly.

**Take remediation (b), with a boundary**: WP02 carries a **binding requirement** that the
re-pinned test must genuinely exercise two attempts, and the "likely routes into elif on the
second attempt" language is corrected to match whatever is actually true. **The exact mock
reshaping is deliberately NOT specified in tasks prose** — it is settled during WP02
implementation against real code, and WP02 says so explicitly. Writing precise mock internals
for code that does not yet exist is what generated the last three HALTs; this ruling declines
to do more of it.

Remediation (a) — accepting the coverage loss — is explicitly REJECTED.

### TASKS-FRESH3-002 (severity 3) and TASKS-FRESH3-003 (severity 2) — ACCEPTED

Fix by widening the `plan.md` amendment as described above. Sweep the whole document for
statements about the `_attempt()` outcome contract and the elif terminal paths; correct every
one, not only the two the sweep happened to name. After the fix, `plan.md` must not contradict
itself anywhere on this subject.

## Constraints on this FINAL round

1. **No further fresh sweep. Stated explicitly so it is not left to interpretation.** Run the
   fixes, then ONE anchored verification against live code. If that verification passes, the
   phase is PASSED — commit the trail and report. This is a deliberate, operator-owned
   termination of the R4→R5 loop, made with the convergence data in hand (severity≥3
   survivors per round: 3, then 2) and with the recognition that findings have shifted from
   design defects to consistency-of-prose-about-unwritten-code.
2. **The anchored verification checks the artifacts against the CODE**
   (`scripts/ci/fleet_main.py`, `scripts/ci/fleet_verdict.py`, `tests/ci/test_fleet_main.py`),
   not against this ruling. A verifier confirming that a correction matches the document that
   authorized the correction has verified nothing.
3. **Fresh subagents.** Fixer must not be the author; verifier must not be the fixer.
4. **Commit the whole review trail** — all rounds, merged/refute/confirmed/verify/all three
   fresh sweeps — plus both rulings in this file.
5. Do **not** reopen `spec.md`'s two binding operator decisions (epic scope;
   unit-tests-plus-post-merge-watch).
6. **If the anchored verification FAILS**, that is a HALT back to the operator — not a
   self-authorized round 5. Unchanged from ruling #1.
7. Public-repo hygiene: no new absolute `/home/<user>/...` paths.

## Note for sk-review

`plan.md` has now been amended twice after its own R1–R6 PASSED verdict, both times on
operator authority recorded here. The plan's original squad verdict does not cover its current
text. Read this file alongside commits `20d72d086` and the round-4 amendment before assessing
plan fidelity.
