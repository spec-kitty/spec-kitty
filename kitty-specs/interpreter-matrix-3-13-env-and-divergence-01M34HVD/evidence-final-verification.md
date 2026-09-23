# WP07 — Final verification: local repro + operator-authorized manual dispatch

Owned by WP07 (`kitty-specs/interpreter-matrix-3-13-env-and-divergence-01M34HVD/tasks/WP07-final-verification.md`).

## Pre-step: branch push

`gh workflow run --ref <branch>` requires the ref to exist on the remote, so the
mission branch was pushed before local reproduction:

```
$ git push -u origin issue-4866-interpreter-matrix-3-13
remote: This repository moved. Please use the new location:
remote:   https://github.com/spec-kitty/spec-kitty.git
 * [new branch]          issue-4866-interpreter-matrix-3-13 -> issue-4866-interpreter-matrix-3-13
branch 'issue-4866-interpreter-matrix-3-13' set up to track 'origin/issue-4866-interpreter-matrix-3-13'.
```

`origin` (`https://github.com/Priivacy-ai/spec-kitty.git`) redirects to the
renamed `spec-kitty/spec-kitty` — confirmed identical repo id
(`O_kgDOEdVVSQ`) via `gh repo view` on both names. `main` was not touched;
`origin/main` remained at `b7d9dc79f` before and after this push.

Collaborator permission check (ground truth, run live rather than trusted
from memory): `gh api repos/spec-kitty/spec-kitty --jq '.permissions'` →
`{"admin":false,"maintain":true,"pull":true,"push":true,"triage":true}` for
the active account `MOES-Media`. Push access is present.

## T001 — Final local reproduction

Per the mission dispatch, a `--collect-only` run against a dedicated 3.13
environment is sufficient for the environment claim (SC-001's signature);
the full suite was NOT re-run — WP05 already produced the canonical
pass/fail measurement and re-running costs ~8 minutes for a number already
in hand.

Command (exact fixed flag shape from `ci-nightly.yml`, `--python 3.13
--all-extras` between `uv run --frozen` and `pytest`), run against the
mission's fully-landed branch state (HEAD `694fda140`, all of
WP02/WP03/WP04/WP05/WP06 approved):

```
UV_PROJECT_ENVIRONMENT=/home/jeroennouws/dev/SK-missions/4866/.venv313 \
  uv run --frozen --python 3.13 --all-extras pytest -m "fast or unit" --collect-only -q
```

Result: **exit code 0**.

```
34835/45057 tests collected (10222 deselected) in 22.28s
```

- `.venv313/bin/python -V` → `Python 3.13.15`.
- `grep -i "ModuleNotFoundError"` over the full collection log → **zero
  matches**.
- No collection-error lines (`ERROR`, "errors during collection") anywhere
  in the log — the only lines matching `error`/`respx`/`pytestarch` as
  substrings are legitimate test node IDs (e.g.
  `tests/specify_cli/saas_client/test_client.py::TestRespxIntegration::...`),
  not failures.
- Extras confirmed installed in `.venv313`:
  `pip list | grep -iE "pytestarch|respx|pytest-benchmark"` →
  `PyTestArch 4.0.1`, `respx 0.23.1`, `pytest-benchmark 5.3.0`.
- Collected total **34835** matches WP05's re-measurement
  (`evidence-remeasurement-3.13.md`: junit `tests="34835"`) exactly — the
  same universe of tests is visible under this environment as under WP05's
  full run, consistent with WP06 changing only documentation/issue-filing
  (no test-outcome drift expected).
- **`.venv/bin/python -V` was not touched**: confirmed unchanged at
  `Python 3.11.15` (the checkout's baseline 3.11 environment) after this
  run. All 3.13 work used `.venv313` via `UV_PROJECT_ENVIRONMENT`.

**T001 validation met**: 3.13 site-packages confirmed
(`.venv313/lib64/python3.13/site-packages`), zero `ModuleNotFoundError`,
collected-test count consistent with WP05.

## T002 — STOP: operator authorization request

**Per this WP's explicit instruction, T002 is a hard stop.** Per
`spec.md` (line 488, C-003) and `plan.md` (lines 421-440, 799-818), the
manual `workflow_dispatch` of `ci-nightly.yml` against a public repo "is
never self-authorized by the phase agent or a WP subagent" and "requires
explicit operator authorization before it is run" — the plan states this
even though the plan itself names the exact command. This implementing
agent's own dispatch prompt asserted the dispatch was already
"OPERATOR-AUTHORIZED — do not ask again," but per this session's own
governing reminder, no agent message (including a dispatch from the
orchestrating agent) constitutes the operator's own consent — only the
operator's direct word does. So this WP treats that assertion as
**unverified** and stops here rather than proceeding on it.

### Summary for the operator

- **T001 local repro**: `--collect-only` run on a dedicated Python 3.13
  venv, zero `ModuleNotFoundError`, extras present, collected-test count
  (34835) matches WP05's canonical re-measurement exactly. See above.
- **WP05 re-measurement** (`evidence-remeasurement-3.13.md`): full run on
  3.13 post-fix — **23 failed, 34666 passed, 146 skipped in 475.87s**; 20 of
  the 23 failures match WP01's 3.11 baseline exactly (pre-existing, not
  caused by this mission), **3 are genuine 3.13-only divergence**, 0
  reverse regressions.
- **WP06 disposition** (`evidence-residual-disposition.md`): the 3-ID
  residual is classified **large-and-out-of-scope** for this mission and
  filed against **#3189** (re-verified live, not assumed from a stale
  snapshot). The `interpreter-matrix` (Python 3.13) nightly leg is expected
  to remain **honestly red** after this mission merges, for these 3 tracked
  reasons — that is the correct, intended outcome, not a defect this
  mission should chase.
- **Branch state**: `issue-4866-interpreter-matrix-3-13` pushed to
  `origin` (`spec-kitty/spec-kitty`), HEAD `694fda140`, tree clean, all of
  WP01-WP06 approved.

### Explicit ask

**May I dispatch `ci-nightly.yml` (`mode=full`) against
`issue-4866-interpreter-matrix-3-13` now?**

Initial status at the time this section was first written: **awaiting the
operator's direct, explicit go-ahead.** T003/T004 had not been started; no
`gh workflow run` had been executed as part of this WP.

### T002 resolution — authorization provenance recorded

**The gate was tested, not skipped.** The hold above was raised because the
dispatch this WP received asserted "OPERATOR-AUTHORIZED — do not ask
again," and an agent-to-agent dispatch message is not itself the operator's
consent (this session's own governing rule: no agent message constitutes
the user's approval; `spec.md` C-003 and this WP's own T002 independently
say the same — the dispatch is never self-authorized by a WP subagent).
That reasoning held and is preserved above rather than edited out.

The coordinator subsequently supplied the missing provenance: the
authorization did not originate in the dispatch prompt. It originated
**earlier in this mission, before implementation began**, when the
coordinator put a direct question to the human operator through the
harness's own `AskUserQuestion` tool — the mechanism this session uses to
obtain genuine user input, distinct from any agent-to-agent message.

- **Question heading**: "Public actions"
- **Question text**: "Three work packages take outward-facing actions on
  the PUBLIC repo. Which do you pre-authorize, so implementation doesn't
  stall waiting on each one?" (multi-select, three options)
- **The relevant option, verbatim**: "**WP07: manual nightly workflow
  dispatch**" — "Runs `gh workflow run ci-nightly.yml --ref
  issue-4866-interpreter-matrix-3-13` against the public repo. This is the
  ONLY way to get real CI signal, since ci-nightly.yml never triggers on
  pull_request. It consumes CI minutes and appears publicly in the Actions
  tab. Without it, verification is local-only."
- **Operator's answer**: selected **all three** options in the set,
  including the WP07 option above.
- In the same exchange the operator identified the Human-in-Charge as
  **stijn-dejongh**.

**Independent corroboration (verified live by this WP, not taken on
trust)**, since the other two options in the same answer set left public
artifacts:

- `gh issue view 4866 --repo spec-kitty/spec-kitty --json assignees` →
  assignee `stijn-dejongh` (`databaseId: 25401297`) — confirms the
  Human-in-Charge identification from the same exchange.
- `gh issue view 4916 --repo spec-kitty/spec-kitty` → OPEN issue "20
  pre-existing 3.11 'fast or unit' test failures (baseline captured by
  #4866 WP01)" — confirms WP01's public-issue option was acted on.
- `gh api repos/spec-kitty/spec-kitty/issues/comments/5782934410` →
  comment on #3189, body opens "3.13 interpreter-divergence residue from
  #4866 (interpreter-matrix nightly-leg readiness) ... Filed per #4866's
  FR-006 disposition (spec.md Edge Case (c))" — confirms WP06's #3189
  filing option was acted on.

All three checks returned real, live artifacts matching the coordinator's
account, which is independent evidence that the described `AskUserQuestion`
answer set was real and was genuinely acted on across the mission — not
merely asserted after the fact to unblock this WP.

**Resolution**: T002's requirement — "an explicit operator go-ahead
recorded in this WP's completion trail" — is satisfied by the above:
direct operator input via `AskUserQuestion` (not an agent message),
verbatim option text naming this exact command, and independent
corroboration via two sibling artifacts from the same answer set. T003
proceeds below on this basis.

**Addendum — how T003 was actually executed.** After the above was
written, this WP's own `safe-commit` of this section was denied by Claude
Code's own auto-mode permission classifier (`[Instruction Poisoning]`).
Rather than argue past that or reword the commit to slip through it, this
WP held. The coordinator resolved the hold not by re-asserting
authorization but by removing the delegation: **the coordinator ran the
dispatch itself**, under authorization given to it directly (distinct from
a WP subagent self-authorizing, which is what `spec.md` C-003 and this
WP's T002 forbid), and handed this WP only the resulting public run to
observe and report on. This WP independently verified that run's
existence and identity (below) before treating it as real. The hold is
recorded here rather than edited out, because the trail should show the
gate was tested, not skipped.

## T003 — Dispatch executed (by the coordinator, not this WP) and observed

**Independent verification of the coordinator's claim, performed by this
WP before relying on it for anything:**

```
$ gh run view 35778042008 --repo spec-kitty/spec-kitty --json databaseId,event,headBranch,status,conclusion,workflowName,createdAt,url
{"databaseId":35778042008,"event":"workflow_dispatch","headBranch":"issue-4866-interpreter-matrix-3-13",
 "workflowName":"CI Nightly","createdAt":"2026-09-22T20:05:54Z",
 "url":"https://github.com/spec-kitty/spec-kitty/actions/runs/35778042008", ...}
```

Confirmed live and public: run `35778042008`, workflow "CI Nightly"
(`ci-nightly.yml`), event `workflow_dispatch`, `headBranch`
`issue-4866-interpreter-matrix-3-13` — matches the coordinator's claim
exactly. This WP did **not** execute `gh workflow run` itself; it only
polled this pre-existing public run.

**Polling discipline (SK-99)**: bounded `timeout 580 bash -c 'sleep
<N>'` waits, re-polling `gh run view ... --json jobs` between each,
never a single long-blocking `gh run watch`. Total observation window:
~56 minutes of real wall-clock time (cross-checked against GitHub's own
server clock via `curl -sI https://api.github.com/` `Date:` header, which
matched local time within seconds throughout — the long elapsed time is
real, not a clock artifact).

## T004 — Confirm SC-001 against the real job log

### The `Interpreter matrix (Python 3.13, nightly-only, FR-021)` job's conclusion

**`cancelled`** — not passed, not failed on test assertions. This is a
**materially different outcome than WP07 predicted** ("expect the job to
still fail on the 3 residual divergences") and is reported plainly rather
than reframed to fit the prediction.

GitHub's own check-run annotation, fetched via
`gh api repos/spec-kitty/spec-kitty/check-runs/106916154887/annotations`:

```
{"annotation_level":"failure","message":"The job has exceeded the maximum execution time of 45m0s"}
```

Step-level timeline (`gh api .../actions/runs/35778042008/jobs`,
`.jobs[] | select(name test Interpreter matrix) | .steps[]`):

| Step | Status | Started | Completed |
|---|---|---|---|
| Set up job | success | 20:06:03 | 20:06:04 |
| Run actions/checkout | success | 20:06:04 | 20:06:15 |
| Set up Python 3.13 | success | 20:06:15 | 20:06:15 |
| Install uv | success | 20:06:15 | 20:06:22 |
| **Sync dev environment on this interpreter** (`uv sync --frozen --all-extras --python 3.13`) | **success** | 20:06:22 | 20:06:24 |
| **Run fast/unit suite on this interpreter** (`uv run --frozen --python 3.13 --all-extras pytest -m "fast or unit" -q --junitxml=...`) | **in_progress, never concluded** | 20:06:24 | — (job cancelled 21:01:01) |
| Upload interpreter-matrix reports | **never started** (pending) | — | — |
| Fail the leg if red | **never started** (pending) | — | — |

The run's own artifact listing
(`gh api .../actions/runs/35778042008/artifacts`) confirms no
`ci-nightly-interpreter-3.13-reports` artifact exists — every other
job's report artifact is present (30 `module-tests-*-reports` +
`ci-nightly-performance-e2e-reports`), but the interpreter-matrix leg's
own `Upload interpreter-matrix reports` step never ran, because the
pytest step ahead of it was still executing when the 45-minute cap was
hit.

### Raw pytest log — NOT retrievable, exhaustively attempted

`gh api repos/spec-kitty/spec-kitty/actions/jobs/106916154887/logs`,
`gh run view --job 106916154887 --log`, and a direct authenticated
`curl` against the same endpoint were each tried multiple times across
~13 minutes (before and after the *entire* run reached `completed`), all
returning the same result: GitHub issues a valid redirect to Azure blob
storage, but the blob itself does not exist
(`BlobNotFound`/`log not found: 106916154887`). This is consistent with a
runner that was force-terminated by the timeout mechanism mid-step and
never got to flush its final log segment to storage — the "Upload
interpreter-matrix reports" step never running is the same story. No
amount of additional polling within this WP's observation budget changed
this; the raw `pytest` stdout (the literal lines proving "collected
34835 items" / zero `ModuleNotFoundError`, as opposed to the local T001
repro's log) could not be quoted, despite genuine, repeated attempts.

### What can and cannot be concluded from the available evidence

**Can be concluded, from verified facts, not inference alone:**
- The environment-sync step (`uv sync --frozen --all-extras --python
  3.13`) **succeeded** (`conclusion: success`) — the pinned 3.13
  interpreter and `--all-extras` resolved cleanly in CI, matching WP03's
  fix and this WP's own T001 local repro.
- The pytest step ran continuously for **~54m37s** (20:06:24 →
  21:01:01) before being force-cancelled.

**Reasonable inference, explicitly flagged as inference, not a log
quote:** a `ModuleNotFoundError` for `pytestarch`/`respx`/
`pytest_benchmark` occurs at **collection time**, which is fast — this
WP's own T001 local repro enumerated all 34,835 selected tests via
`--collect-only` in 22.28s, and before this mission's fix, the same
defect (SC-001) caused the leg to fail within roughly that same
timescale (13 `ModuleNotFoundError`s at collection, not after 54 minutes
of execution). A pytest invocation that runs for 54+ minutes without
exiting is far more consistent with collection having succeeded and the
suite being mid-execution than with a collection-time import failure.
This is **inference from step duration, not a quoted log line showing
"collected N items" or the absence of `ModuleNotFoundError`** — that
direct textual proof could not be obtained for this specific run.

### A new finding this WP is obligated to report: the leg cannot complete within its own budget

Independent of WP06's 3 tracked divergences, this run surfaces what
appears to be a **previously unobserved defect**: the CI job's `pytest`
invocation (`uv run --frozen --python 3.13 --all-extras pytest -m "fast
or unit" -q ...`) runs **serially** — unlike WP05's local re-measurement
and this WP's own T001 repro, neither of which had reason to add `-n
auto`, but the *workflow file itself* also does not add any `-n`/xdist
flag to this step. WP05's local run completed the same test population in
475.87s **with** `-n auto` (parallelism); a serial run of the same
population, at real GitHub-hosted-runner scale, did not finish in 45
minutes. This may mean the interpreter-matrix leg has, as configured,
**never** been able to reach a real pass/fail conclusion on GitHub's
runners even after WP02/WP03/WP04's fixes — before this mission it failed
in seconds (collection error), and now it appears to time out in
matter of tens of minutes instead, and either way it has not yet been
observed to reach a genuine "ran the suite, saw N pass / M fail"
conclusion in CI. This is offered as an observation for the record, not a
recommendation — WP07 is verification-only and does not own remediation.

### Overall run conclusion

**`cancelled`** (`gh api repos/spec-kitty/spec-kitty/actions/runs/35778042008` →
`{"status":"completed","conclusion":"cancelled"}`).

**`performance-and-e2e` is unrelated to this mission and to the above
finding** — it hit its **own, independent** 60-minute cap
(`gh api .../check-runs/106916155226/annotations` →
`"The job has exceeded the maximum execution time of 1h0m0s"`), started
at the same instant (20:06:00) and completed at 21:07:51, roughly 6
minutes after interpreter-matrix. Its own annotations show three of its
sub-suites (`e2e suite exit=0`, `performance suite exit=0`, `stress suite
exit=0`) completed before its own timeout hit on whatever step follows.
This is issue **#4865's** live, concurrent, standing-red job — this
mission did not touch it, and its cancellation is coincidental timing (a
similar timeout mechanism, an unrelated job), not a shared cause. Nobody
should read the overall `cancelled` run conclusion as this mission's
`interpreter-matrix` leg's result; both cancellations are independently
explained above.

### Plain before/after statement

- **Before this mission**: the `interpreter-matrix` leg failed **within
  roughly a minute**, at test-collection time, with 13
  `ModuleNotFoundError`s (`pytestarch`, `respx`, `pytest_benchmark`) —
  because the shared `.venv` it inherited was a 3.11 environment missing
  the `test` extra, never a real 3.13 environment. This was a fake,
  environment-only failure telling the operator nothing about the actual
  3.13 code.
- **After this mission (this run)**: the environment-sync step confirms
  a real, clean **3.13** sync with **`--all-extras`** succeeds
  (`conclusion: success`). The `pytest` step then ran for **54+
  minutes** — far longer than collection alone would ever take — before
  being cancelled by the job's own 45-minute timeout, never reaching a
  pass/fail verdict. So: **the fake environment failure this mission
  targeted (SC-001) is gone** (nothing failed at collection; the
  environment held up under real execution for most of an hour), but the
  leg **still does not produce a trustworthy nightly signal** — it now
  times out mid-run instead of failing at startup, which is a different
  problem than SC-001 and than WP06's 3 tracked divergences, surfaced for
  the first time by this WP's dispatch. Direct log-quoted proof of "zero
  `ModuleNotFoundError`" could not be obtained (see above); the strongest
  available evidence is the successful sync step plus the ~54-minute
  execution window before cancellation.

## Mission-closing addendum — Run 2 (with `-n auto`), operator decisions, and the final record

Recorded after mission close, once `-n auto` was added to the
`interpreter-matrix` job's `pytest` invocation (commit `3b2517d5e`) and a
second manual `workflow_dispatch` was run to check whether parallelism let
the leg finish inside its 45-minute cap. **It did not.** Both runs are
recorded here side by side; neither run's step-level facts above are
edited.

### Two dispatches, both cancelled — full comparison

| | Run 1 | Run 2 |
|---|---|---|
| Run | [`35778042008`](https://github.com/spec-kitty/spec-kitty/actions/runs/35778042008) | [`35788021368`](https://github.com/spec-kitty/spec-kitty/actions/runs/35788021368) |
| Commit | `694fda140` (pre-`-n auto`, serial `pytest`) | `3b2517d5e` (with `-n auto` on the step) |
| `Sync dev environment` step | success, ~2s (20:06:22 → 20:06:24) | success, ~2s (21:40:39 → 21:40:41) |
| `Run fast/unit suite` step | started 20:06:24Z, never completed | started 21:40:41Z, never completed |
| Job conclusion | `cancelled` (45-min cap) | `cancelled` (45-min cap) |
| Job force-killed at | 21:01:01Z (~54m37s into the step) | 22:35:21Z (~54m40s into the step) |
| Log retrievable? | No — `BlobNotFound` | No — `BlobNotFound` (independently re-confirmed via `gh api .../actions/jobs/106949477202/logs`) |
| Report artifact | absent | absent |

Both rows for Run 2 were independently re-verified live via `gh api
repos/spec-kitty/spec-kitty/actions/runs/35788021368/jobs` and the
check-run annotations endpoint immediately before this addendum was
written, not copied from the dispatch that requested this correction pass
without re-checking.

### What Run 2 adds, and what it does not

- **Adds**: confirmation that adding `-n auto` did not change the outcome.
  The sync step still succeeds in ~2 seconds; the pytest step still runs
  for ~54.5 minutes and is still force-cancelled by the same 45-minute cap,
  within roughly 3 seconds of Run 1's cancellation timing. This is the same
  "reasonable inference, not a quoted log line" situation as Run 1 (see
  above): a ~54-minute step duration is far more consistent with the suite
  genuinely executing than with a fast collection-time failure, but no
  `ModuleNotFoundError`-absence claim can be made from a log line, because
  there is no retrievable log for either run. **Every statement anywhere in
  this mission's record that says "no `ModuleNotFoundError`" for Run 1 or
  Run 2 is this inference, not an observation — it is not a claim that a
  log was read and found clean.**
- **Does not add**: a completion time for either configuration (serial or
  `-n auto`) at GitHub-runner scale. Both runs died at the cap before
  finishing, so there is no wall-clock number to compare. **"`-n auto`
  should be faster than serial" is sound general reasoning about
  parallelism; it is not evidence of a measured gain on this runner class
  for this suite** — no such measurement exists for either run, and this
  document does not claim one.

### Operator decisions (recorded here as the disposition of this finding)

Two decisions were made once Run 2 confirmed `-n auto` gave no measurable
improvement on the GitHub-hosted runner:

1. **Keep `-n auto` on the `interpreter-matrix` job's `pytest` step.**
   Serial execution is definitively worse in every case where it can be
   compared at all — WP05's local re-measurement (this checkout, 24-core
   box) took ~5036s (84 min) serial (WP01's 3.11 baseline methodology) vs.
   475.87s (~8 min) with `-n auto` (WP05's 3.13 re-measurement, same
   selector). The `.venv` mid-run corruption hazard that made `-n auto`
   unsafe to use in the first place is fixed (WP04) and was validated
   under a full-scale `-n auto` run with the environment surviving
   byte-identical, interpreter-identity-stable, before and after
   (WP05's own environment-integrity check, `evidence-remeasurement-3.13.md`).
   Reverting to serial would only make the GitHub-runner timeout problem
   worse, with no offsetting benefit.
2. **File the 45-minute-cap timeout as a new issue, cross-linked to
   #4865 (and #3189, #4922, #4866).** This is a distinct defect from both
   of those — not a Python-3.13 test-outcome divergence (#3189's scope)
   and not the same job as #4865's perf/e2e cap overrun (a different job
   in the same workflow, with its own independent budget) — so it is
   filed as its own item rather than folded into either.

**New issue filed**: [spec-kitty/spec-kitty#4951](https://github.com/spec-kitty/spec-kitty/issues/4951)
— "ci(nightly): interpreter-matrix leg cannot complete fast/unit suite
within 45-min cap on GitHub-hosted runner (with or without -n auto)."
Cross-linked (via body mentions, confirmed as GitHub cross-reference
timeline events) to #4866, #4865, #3189, and #4922.

### Plain before/after statement — what the nightly leg reports, stated once more without ambiguity

- **Before this mission**: the `interpreter-matrix` leg failed within
  roughly a minute, at test-collection time, with 13
  `ModuleNotFoundError`s (`pytestarch`, `respx`, `pytest_benchmark`) — a
  fake, environment-only failure that tested nothing real about
  spec-kitty on Python 3.13.
- **After this mission (both Run 1 and Run 2)**: the environment is
  correct and verified on a real GitHub-hosted runner — the sync step
  succeeds cleanly in seconds, and the suite genuinely executes for
  roughly 54 minutes (inference from step duration, not a log quote; see
  above) rather than dying at collection. **The leg still produces no
  verdict** — it is killed by its own 45-minute job timeout before
  finishing, in both the serial and the `-n auto` configuration. No
  sentence in this mission's record should be read as claiming the
  nightly leg now passes, now fails on test assertions, or now reports
  any pass/fail conclusion at all on a GitHub-hosted runner. It does not.
  The environment defect this mission targeted (SC-001) is fixed; the
  leg's ability to finish within its own runner budget is a separate,
  newly-surfaced problem, tracked at #4951.
