# Evidence: which SonarCloud reliability findings are on new code

Recorded 2026-11-03 (UTC) against `spec-kitty_spec-kitty` branch `main`, before any change in this
mission. Raw API responses sit beside this file (`quality-gate.json`, `new-code-bugs.json`,
`all-bugs.json`, `measures.json`).

## The new-code window

`/api/qualitygates/project_status` reports the reliability condition with `periodIndex: 1`, and
`periods[1]` is:

```json
{"index": 1, "mode": "previous_version", "date": "2026-10-15T03:11:31+0000", "parameter": "4.0.0rc7"}
```

So "new code" means **every line merged since the `4.0.0rc7` release on 2026-10-15**, not "the last
few commits". `new_reliability_rating = 5` (E) against a threshold of `1` (A).

## The authoritative split

| Query | Result |
| --- | --- |
| `/api/measures/component?…&metricKeys=new_bugs,bugs,new_reliability_rating` | `new_bugs = 4`, `bugs = 18`, `new_reliability_rating = 5.0` |
| `/api/issues/search?…&types=BUG&sinceLeakPeriod=true` | **4** issues |
| `/api/issues/search?…&types=BUG` (all time) | 23 issues |

**4 findings are new code. 19 are not.** The 19 do not enter the rating. `bugs = 18` counts the
open findings: all 23 in `all-bugs.json` are `type=BUG`, 18 `OPEN` and 5 `CLOSED`, which is why it
differs from both totals.

**Landing note (2026-11-04).** The shape guard `tests/architectural/test_new_code_reliability_shapes.py`
named in this Mission's plan, tasks and contract was retired at landing under `DIRECTIVE_041`: it
pinned source shape, not behaviour. The behaviour stays covered by the existing events-tail, compiler
and #6673 backfill tests, and SonarCloud itself re-raises these rules on new code.

### The 4 new-code findings

| Severity | Rule | Location | Sonar `creationDate` | Disposition |
| --- | --- | --- | --- | --- |
| BLOCKER | `python:S5756` | `src/specify_cli/cli/commands/events.py:102` | 2026-11-02 | Resolved at source (FR-001): functional-API `Enum` value lookup rewritten as a name lookup. Analyzer false positive — `_LogKind` *is* callable; Sonar cannot model `Enum("name", members, type=str)`. |
| BLOCKER | `python:S3827` | `src/charter/activation/compiler.py:1153` | 2026-10-29 | Resolved at source (FR-002): the function-local `import` now precedes the annotation that names it. Analyzer false positive — `from __future__ import annotations` is active, so the annotation never evaluates; the name resolves at call time. |
| MAJOR | `pythonbugs:S2583` | `src/specify_cli/migration/backfill_identity.py:132` | 2026-11-01 | Resolved at source (FR-003). **True positive but harmless**: the `None` guard is provably dead because the helper returns `None` only when `tracked.unavailable` is false, and the caller is inside `if tracked.unavailable:`. |
| MAJOR | `java:S5960` | `acceptance-jvm/src/test/java/kitty/acceptance/steps/CharterSteps.java:134` | 2026-10-17 | **Not resolved — maintainer decision.** `sonar.yml` analyses `acceptance-jvm` as MAIN code *on purpose* ("so the full Java rule set, security rules included, applies to it"), so AssertJ assertions in Cucumber step definitions are scored as production-code assertions. Reported, not reversed. |

E is reachable only from a BLOCKER, so the two `S5756`/`S3827` findings are the entire cause of the
rating. Nothing in the set is a behaviour regression: both BLOCKERs are analyzer false positives on
intentional constructs, and the one true positive is a dead branch with no runtime effect.

### The 19 pre-existing findings (out of scope, not modified)

None of these can move `new_reliability_rating`. Each `creationDate` precedes the window start
(2026-10-15), and `git blame` confirms the lines themselves have not been touched since:

| Sites | Rule | Why it is left alone |
| --- | --- | --- |
| `tests/charter_offering/test_pack_clean_digest.py:90`, `tests/contract/test_mission_status_artifacts.py:1078,1080`, `tests/architectural/test_universe_store.py:187`, `tests/architectural/test_battery_partition_proof.py:527`, `tests/ci/test_green_match.py:722`, `tests/charter/test_slug_for.py:54`, `tests/specify_cli/live_work/test_codec.py` | `python:S5863` | Deliberate determinism controls: `assert f(x) == f(x)` twice over one input. `test_universe_store.py:187` says so in its own message ("control: the baseline key is stable"). Deleting them to move a metric would weaken the suite. |
| `src/specify_cli/cli/commands/agent/mission_finalize.py:1497,1498`; `tests/specify_cli/cli/commands/agent/test_issue_5328_refresh_fail_closed.py:782`; `tests/architectural/test_archive_root_byte_identical.py`; `tests/zeitgeist_client/test_live_frame.py` | `python:S5779` | Pre-existing. Two are explicit mypy-narrowing `assert`s after a `NoReturn` call (already commented as such in the source); the test-thread one surfaces worker exceptions through `except BaseException` by design. `tests/zeitgeist_client/test_live_frame.py` no longer exists, so that finding is stale. |
| `src/specify_cli/cli/commands/mission_type.py:1113` | `pythonbugs:S2583` | Pre-existing (2026-10-11), outside the window. |

## Reproduce

```bash
curl -s 'https://sonarcloud.io/api/qualitygates/project_status?projectKey=spec-kitty_spec-kitty&branch=main' \
  | python3 -c 'import json,sys; d=json.load(sys.stdin)["projectStatus"]; print(d["periods"], d["conditions"])'

curl -s 'https://sonarcloud.io/api/issues/search?componentKeys=spec-kitty_spec-kitty&branch=main&types=BUG&ps=100&sinceLeakPeriod=true' \
  | python3 -c 'import json,sys; d=json.load(sys.stdin); print(d["total"]); [print(i["severity"], i["rule"], i["component"].split(":")[-1], i.get("line")) for i in d["issues"]]'
```

`inNewCodePeriod=true` is accepted but does **not** filter this project (it returns all 23);
`sinceLeakPeriod=true` is the parameter that reflects the leak period. Any future reading of this
issue should use `sinceLeakPeriod`.

## After this change

| Remaining on new code | Severity | Why it stays |
| --- | --- | --- |
| `java:S5960` at `acceptance-jvm/src/test/java/kitty/acceptance/steps/CharterSteps.java:134` | MAJOR | `sonar.yml` analyses `acceptance-jvm` as MAIN code on purpose, so an AssertJ assertion in a Cucumber step definition is scored as a production-code assertion. Leaving that scope as it is was a maintainer decision, and only a maintainer can change it. |

With the two BLOCKERs and the `S2583` resolved and the last MAJOR remaining, the worst new-code
severity is MAJOR, so the rating moves **E → C**, not to A. Reaching A needs one of: an
ignore-multicriteria for `S5960` under `acceptance-jvm/src/test/java/**`, a SonarCloud web-UI
adjudication of that finding with a rationale, or moving the tree to `sonar.tests` and accepting
that the full Java rule set (security rules included) no longer applies to it. All three are
maintainer calls; this mission does not make them.

Nothing here was fixed by suppressing a finding: the diff adds no `NOSONAR`, no
`sonar.issue.ignore` rule, and changes neither `sonar-project.properties` nor the scan scope in
`sonar.yml`.

## Caveat

The window is `previous_version`, so it re-anchors at the next release (`4.0.0rc8` was detected
2026-11-03). After that the "new code" set shrinks to whatever lands from then on, and this table
describes the rc7→rc8 window only. The source fixes are durable regardless; the classification is
not.
