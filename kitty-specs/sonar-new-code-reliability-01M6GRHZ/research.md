# Research: Sonar new-code reliability rating E on `main` (#7113)

Recorded 2026-11-03 during the mission's `discovery` step, before the spec was finalised.
Raw SonarCloud API responses are committed under `evidence/` and the tabular split lives in
`evidence/README.md`; this file records the reasoning and the decisions that shaped the scope.

## D-001 — The rating is driven by two analyzer false positives, not by a behaviour regression

**Decision**: treat this as analyzer hygiene over intentional constructs, not as a defect hunt.

**Evidence**: `new_reliability_rating` maps the *worst* severity on new code
(`BLOCKER` → E). The new-code set is four findings (`new_bugs = 4`;
`/api/issues/search?...&sinceLeakPeriod=true` on `types=BUG`), of which exactly two are
`BLOCKER`, so those two alone produce the E:

| BLOCKER | site | why the analyzer is wrong |
| --- | --- | --- |
| `python:S5756` | `src/specify_cli/cli/commands/events.py:102` | `_LogKind` is built by the functional API (`Enum("_LogKind", _LOG_KIND_MEMBERS, type=str)`), so it **is** callable; the `_LogKind("status")` value lookup is valid. Sonar's symbolic engine cannot model a dynamically built `Enum`. The line carries `# type: ignore[misc]` on the construction for the same reason mypy needs it. |
| `python:S3827` | `src/charter/activation/compiler.py:1153` | `service: ActiveCharterService = ...` names a class imported 3 lines below. `from __future__ import annotations` is imported at module top, so the annotation is a string and never evaluated; the name resolves at call time. Nothing is used before it is defined at runtime. |

Both lines were merged inside the current release window (`61f74b5145`, 2026-10-30;
`4ce208d13b`, 2026-10-31), which is why they count as "new" at all. Neither changed runtime
behaviour in a way an operator could observe, and neither is what a reliability regression looks
like: no error path, no data loss, no lost exception.

## D-002 — 19 of the issue's implied 23 findings are not on new code at all

**Decision**: leave them alone; report the split instead of editing them.

**Evidence**: the gate's `periods[1]` is `{"mode": "previous_version", "parameter": "4.0.0rc7",
"date": "2026-10-15T03:11:31Z"}`. Everything the issue lists beyond the four above has a Sonar
`creationDate` between 2026-08-22 and 2026-10-12 — before the window opened — and `git blame`
shows the lines untouched since. `sinceLeakPeriod=true` returns 4, not 23.

Two consequences worth stating plainly:

- `inNewCodePeriod=true` is accepted by this project's API but does **not** filter (it returns all
  23). Any earlier reading of the issue that counted 23 as new code most likely used it. The
  parameter that reflects the leak period is `sinceLeakPeriod`.
- The `python:S5863` family is not a defect: every site is a deliberate same-input determinism
  control (`assert f(x) == f(x)`), and `tests/architectural/test_universe_store.py:187` says so in
  its own assertion message ("control: the baseline key is stable"). Deleting them to move a
  metric would weaken real coverage.

## D-003 — The Java `S5960` is a documented scope decision, so it is out of scope

**Decision**: do not reclassify `acceptance-jvm` as test code; report the option to the maintainer.

**Evidence**: `.github/workflows/sonar.yml` states it explicitly — "The Java is analysed as MAIN
code (`sonar.sources`) on purpose, not as test code, so the full Java rule set, security rules
included, applies to it." `java:S5960` ("remove this assertion from production code") on a Cucumber
step definition is the direct consequence. Changing it would reverse a documented decision about
security-rule coverage, which is a maintainer call, not an agent one. The three available
dispositions (ignore-multicriteria for `S5960` under `acceptance-jvm/src/test/java/**`, a UI
adjudication, or moving the tree to `sonar.tests` and losing those rules) are named in the PR.

**Consequence for the done-condition**: `new_reliability_rating` can reach C (the remaining finding
is MAJOR) from inside this repository, not A. Saying "E → A" would be false.

## D-004 — Fix at source, never with a suppression or a config change

**Decision**: each finding is removed by rewriting the construct, not by `NOSONAR`, not by
`sonar.issue.ignore.*`, not by a scan-scope or exclusion change.

**Reasoning**: the issue asks for a SonarCloud-UI adjudication, which this environment cannot do
(no token; it is a web action). A suppression comment would be the in-repo equivalent, but it hides
a known false positive behind a marker rather than removing the misread construct — and it adds
analyzer config to a diff whose whole point is that the code is fine. Each rewrite is smaller than
the suppression comment would be:

- `events.py`: resolve the default **by name** (`_LogKind[...]`) instead of by value
  (`_LogKind(...)`). `_LOG_KIND_MEMBERS` maps `kind.upper() -> kind`, so the name lookup reaches the
  same member; the module stays a single authority over the closed registry.
- `compiler.py`: move the function-local `import` above the `if`, so the annotation's name is bound
  before the line that names it. Import stays function-local (module scope is what the local import
  avoids), and the builder module already imports `resolver`, so no new import edge appears.
- `backfill_identity.py`: the `None` guard is a true positive — provably dead, because
  `tracked_meta_refusal` returns `None` only when `tracked.unavailable` is false, which the caller's
  `if tracked.unavailable:` has excluded. Replace the guard with an explicit narrowing and document
  the helper's precondition; behaviour is identical.

## D-005 — The guard is a source-shape test, because these changes have no behavioural red

**Decision**: one fast-tier module in `tests/architectural/` asserts (a) each flagged construct is
absent and (b) the behaviour each rewrite had to preserve still holds, with a positive control per
probe.

**Reasoning**: red-first needs a test that fails before the fix. None of the three rewrites changes
runtime behaviour, so no behavioural test can be red on the pre-change tree — the vacancy is in the
*shape*, which is exactly what the finding is about. The shape assertion is therefore the honest red,
and the behavioural half (default member value, both branch types returned, both `_tracked_mission_id`
outcomes on one fake) is the part that keeps the rewrite from being a free pass. The positive
control (the AST probe must find a *real* preceding binding for a name it should see) is what stops
the shape probe from passing on an empty match.

## Open questions (for plan / review, not blockers)

1. Should the `S5863` determinism controls carry a marker the analyzer respects, so a future reader
   does not "clean them up"? Out of scope here (C-003), but worth a maintainer decision.
2. Does `acceptance-jvm` keep its MAIN-code scope? If yes, `S5960` needs a UI adjudication or an
   ignore-multicriteria to ever leave the new-code gate; if no, the full Java security rule set is
   lost for that tree. Named in the PR as a decision for the maintainer.
3. `tests/zeitgeist_client/test_live_frame.py` is a live Sonar finding against a file that no longer
   exists — a stale issue entry, not debt. Nothing in this repository can clear it; the next scan
   should drop it on its own.
