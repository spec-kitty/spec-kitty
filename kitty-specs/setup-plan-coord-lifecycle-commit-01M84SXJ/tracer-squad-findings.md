# Tracer: R24 adversarial squad findings (2026-11-24)

Two read-only reviewers on `fix/3933-setup-plan-coord-lifecycle` (commit-path correctness; tests, UX and spec fidelity). No blocking finding. Dispositions:

| Finding | Severity | Disposition |
|---|---|---|
| A concurrent status write (move-task) commits the whole log, setup-plan's lines included; setup-plan's compare-and-swap then loses and refuses falsely | should | Folded: when the branch moved and it now holds every setup-plan event id of the checked log, the result is `unchanged`, not a refusal (`_lifecycle_events_landed`); test added |
| The moved-branch test did not pin the loss-risk wording (reviewer cycle-3 n1) | should | Folded: asserts "moved after setup-plan checked it" and the "Do not commit" remedy; remedy no longer says "follow the remedy above" |
| No test pins the plain remedy on a non-loss refusal (cycle-3 n2) | should | Folded |
| NFR-002 names `lanes`; the regression test lacked it | should | Folded: `lanes` case added |
| A non-UTF-8 log raised UnicodeDecodeError inside the refusal renderer, losing the named code | should | Folded: caught; test added |
| The refusal payload kept `phase_complete: true` | should | Folded: `false` |
| `uncommitted_lifecycle_events` listed events present in the log, not missing ones | should | Folded: key renamed `lifecycle_events_in_log` |
| The refusal did not say the plan commit landed | nit | Folded: "The plan commit <hash> was kept." |
| The run adding PlanCompleted accepted `unchanged` | nit | Folded: requires `committed` |
| `_lifecycle_log_for_plan_commit` docstring still called the case a residual | nit | Folded |
| `_checkout_head(tmp_path)` assumes basetemp outside a checkout | nit | Noted in the test |
| `lifecycle_commit.branch` is null on refusals setup-plan builds | nit | Kept: documented in data-model (`branch` may be null) |
| Inherited divergence text mentions consolidation (cycle-3 n3) | nit | Kept: setup-plan's own lead sentence precedes it; the house text is shared with BookkeepingTransaction |
| PUBLISHED Mission: write location falls back to the primary dir while topology still routes through coordination; a re-run after publish may refuse | nit | Residual, not reproduced; noted in the PR |
| `_lifecycle_write_location` raising ends in the generic error arm after scaffolding | nit | Residual (pre-existing write-location refusals keep their own messages); noted in the PR |
