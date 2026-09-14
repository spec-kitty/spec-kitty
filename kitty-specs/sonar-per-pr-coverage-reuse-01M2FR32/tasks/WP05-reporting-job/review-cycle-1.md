---
affected_files: []
cycle_number: 1
mission_slug: sonar-per-pr-coverage-reuse-01M2FR32
reproduction_command:
reviewed_at: '2026-09-14T16:38:00Z'
review_status: acknowledged
reviewer_agent: user
wp_id: WP05
---

# WP05 review feedback — reviewer: architect-alphonso (security posture and seams)

**Verdict: REJECT.** Two assertions are vacuous in exactly the way this mission's contract §C5
non-vacuity floor forbids — and one of them guards NFR-008, the revision binding that is this WP's
security-critical seam. Both fixes are mechanical. **Everything else in this WP is sound**, including
every security property I attacked; the detail is in §"What holds" below so the next cycle does not
re-litigate it.

---

## Required changes (2)

### R1 — `test_report_job_binds_the_fetched_revision_to_the_measured_revision` is comment-satisfiable

`tests/release/test_sonar_workflow.py`. The assertion is a substring check over the whole step script:

```python
assert "verify-revision" in script
```

**Proven vacuous.** I deleted the entire invocation from `.github/workflows/ci-aggregate.yml` —

```
          python3 scripts/ci/sonar_pr_analysis.py verify-revision \
            --source out/aggregate/source/source.json \
            --fetched "$(git rev-parse FETCH_HEAD)"
```

— and replaced it with `# verify-revision intentionally skipped by this mutation`. Result:
**39 passed**. The NFR-008 binding can be removed from the shipped job and nothing reds.

The docstring makes this an overclaim, not just a weak test: it says the fetched ref "must be
**proven** to equal `tested_sha` before anything is analysed". The test greps; it proves nothing.

**Fix**: strip comment lines before asserting — the technique is already in this file, ~30 lines
away, in `test_report_job_passes_the_publication_settings_explicitly_from_trusted_content`:

```python
live = "\n".join(line for line in script.splitlines() if not line.strip().startswith("#"))
```

Assert against `live`, and prefer pinning the invocation line the way
`test_report_job_replaces_only_the_two_analysed_trees` pins the checkout line-list (that one is
strong — see §"What holds"). `set -euo pipefail` in the same test has the same weakness; fix both.

### R2 — the skipped-tolerance half of `test_verdict_job_is_skipped_tolerant_and_excludes_the_report` is keyed on prose

Same file. `assert "skipped" in script` is satisfied by the step's own `print(...)` string, not by
the tolerance logic.

**Proven vacuous.** Mutating only the predicate —

```python
if result.get("result") not in {"success"}          # was: {"success", "skipped"}
```

— passes **80/80**, because `print(f"... (skipped is not red)")` still contains the word. Reword that
print as well and the test finally reds, which confirms the assertion is bound to the prose.

This matters on your own stated grounds: the comment two lines up records that `diff-cover` **was
observed skipped in run 34842534281**, so a strict verdict would fail `aggregate-gate` on every such
run — and the assertion written to prevent that does not detect it.

**Fix**: assert the predicate, e.g. behaviourally (extract the `<<'PY'` evaluator and drive it with
`{"collect": {"result": "success"}, "diff-cover": {"result": "skipped"}}`, asserting exit 0), which
is the same harness `_run_gate_script` already establishes in this file. A structural
`'"skipped"' in script` keyed on the set literal is the weaker but acceptable alternative.

---

## What holds — do not redo this work

I mutation-tested the security surface hard. Every one of these is **confirmed red on removal**;
none needs revisiting.

| Mutation | Result |
|---|---|
| Extend the checkout line: `-- src tests sonar-project.properties` | RED — `test_report_job_replaces_only_the_two_analysed_trees` |
| Add a *second* `git checkout` line instead (the naive dodge) | RED — same test; it pins the whole line-list, not a substring |
| Remove the same-origin conjunct from the job `if:` | RED — `test_report_job_condition_carries_a_gating_same_origin_conjunct` |
| Neuter the evaluator's `same-origin` conjunct | RED — 3 tests, incl. the missing-origin fail-closed case |
| Remove `resolve_pull_request`'s foreign-head refusal | RED — `test_resolve_pull_request_refuses_a_foreign_head_repository` |
| Drop conjunct 1 / 4 / 5 individually | RED — each reds its own named test |
| `aggregate-gate` gains `sonar-pr` in `needs:` | RED — 2 tests |
| Remove `continue-on-error` from `sonar-pr` | RED — `test_report_job_declares_both_non_blocking_guarantees` |

**The triplicated same-origin guard is sound defence-in-depth, not redundancy.** The three points are
not three copies of one check — they are three *different* checks that happen to agree: the job `if:`
is a cheap pre-gate on the event payload; the evaluator re-decides it non-short-circuiting so the log
names it; `resolve_pull_request` refuses on the **authenticated API payload**, which is a different
and more trustworthy source than the event. Drift between them is therefore informative rather than
dangerous, and the middle one fails *closed* on an absent origin signal
(`isinstance(head_repository, str) and ...`), which is the property that actually earns the third
copy. Keep all three.

**Conjunct 5's placement is a real constraint, not a rationalisation.** Corroborated two ways:
GitHub's context-availability table excludes `secrets` from `jobs.<job_id>.if`, and both sibling
Sonar surfaces in this repo solve it the same way — `sonar.yml:94-96` and `ci-quality.yml:152-154`
both inject the secret into a step `env:` and test `[ -n "$SONAR_TOKEN" ]` in shell. No workflow in
the repo uses `secrets.` in any `if:`. Your variant is *stronger* than both siblings: it passes the
boolean `secrets.SONAR_TOKEN != ''` rather than the value, so the credential never enters the
evaluator's environment (DIR-050). That is an improvement on the precedent; say so.

**I could not make the analysis lie.** Fifteen minutes against it:

- *Argument injection via the branch name* — closed by construction. `_REF_RE` excludes whitespace,
  `;`, `$`, backtick, and the glob metacharacters `* ? [`, so neither the word-splitting nor the
  pathname-expansion the scanner action's unquoted `$INPUT_ARGS` would perform can be reached. The
  `-Dsonar.projectKey=attacker_project` parametrisation is the right test to have written.
- *Injection via coverage filenames* — closed upstream: `collect` writes `resolved_dir / name` from
  registry-derived names already validated to `[A-Za-z0-9._-]`, so the glob in
  `coverage_report_paths` cannot see a hostile name. (Defence-in-depth note, not a required change:
  `coverage_report_paths` itself does not re-validate; the whitespace check in `build_scanner_args`
  catches spaces but not a `*`. Cheap to harden if you touch the file anyway.)
- *`$GITHUB_OUTPUT` breakout* — closed. `_emit` uses the delimiter form, and whitespace-free values
  cannot carry the delimiter line.
- *Attributing the report to a different change* — closed, and elegantly. Pointing
  `referenced_workflows` at another PR's `refs/pull/N/merge` is refused upstream by
  `aggregate_source.py`'s `parents[1] != head` check; `verify-revision` then binds the fetched tree
  to `tested_sha`; `resolve_pull_request` refuses a payload answering for a different number.
- *Ordering* — correct and load-bearing. `scanner-args` (which reads `sonar-project.properties`,
  `pyproject.toml` and `scripts/`) runs **before** `rm -rf src tests`, and none of those paths is
  replaced. Nothing reads the replaced trees before replacement.
- *Least privilege* — correct. `pull-requests: read` (not write) means the scan action cannot post PR
  decoration, which is consistent with informational-only; `collect`/`diff-cover` blast radius is
  unchanged and asserted.
- *Revision binding loudness* — loud. `main()` returns 1 on `SonarPrAnalysisError` under
  `set -euo pipefail`; an empty `git rev-parse` fails the `_SHA_RE` match rather than passing
  silently. Stdout stays empty on error so a `$(...)` capture cannot proceed on a guess.

**T027's judgment is right.** ~14 s against a 900 s budget is a 64× margin; raising the budget would
be noise. Flagging **memory** as the thing for the next reader to watch is the correct call — 2.6 GB
against a 16 GB runner is ~6×, so memory is the binding constraint and would blow first on another
6× growth. Recording it beside the number rather than in a mission doc is right too.

**No overclaiming on the declared limit.** The C-006 statement is accurate and the WP does not claim
an observed run anywhere; the hand-off to WP06/T032 is stated in the workflow, the tests, and the
commit message. Correct.

---

## Not blocking — carry into WP06/T032's observation, please

1. **Does Sonar's new-code attribution survive a dirty working tree?** The corrected §C3 mechanism
   analyses a tree where `src`/`tests` are *uncommitted* modifications against a default-branch
   `HEAD`. `fetch-depth: 0` is present and your comment shows you thought about blame, but if JGit
   blame is unavailable for modified files, Sonar may treat far more than the PR's diff as new code —
   a report that is wrong with no attacker involved. This is the one way I think the analysis could
   still lie, and only a real run can answer it. Worth an explicit line in T032's checklist.
2. **The scanner JVM also parses the 166.6 MiB set.** T027 measured the Python parsers in
   `diff-cover`; `sonar-pr` ingests the same enlarged set through the scanner's JVM (default heap,
   `timeout-minutes: 20`). An OOM there is silent: `continue-on-error: true` keeps the job green and
   no report publishes — a second "green but not published" path alongside #4350. Observe peak
   memory on the first run.
3. **Registry-shrink inflation (mission-level, pre-existing, not WP05's).** A write-access contributor
   can drop modules from `.github/ci-module-registry.yml` in their own PR; conjunct 4 checks
   completeness *relative to that registry*, so fewer shards ⇒ fewer coverage files ⇒ an inflated
   Sonar coverage figure. This is inherent to the FR-002 reuse premise and already affects the
   blocking `diff-cover` gate more severely. Flagging for the record only — do not fix it here.
4. **Residual on R1's fix**: the delivery-step assertions are scoped to the one step matched by name.
   A mutation that restored extra paths from a *different* step would not be caught. Enumerating every
   restore verb is not worth it; noting it so the next reader knows the boundary.

---

## Verification performed

Lane: `.worktrees/sonar-per-pr-coverage-reuse-01M2FR32-lane-b` @ `33687c09ac`. Worktree clean before
and after; all mutations reverted via `git checkout`.

```
pytest tests/release/test_sonar_workflow.py tests/ci/test_sonar_pr_analysis.py   68 passed
pytest tests/architectural/test_coverage_artefact_contract.py \
       tests/architectural/test_dual_mode_contract.py \
       tests/architectural/test_no_duplicate_suite_execution.py \
       tests/ci/ tests/release/                                  554 passed, 6 skipped
pytest tests/architectural/test_arch_shard_marker_completeness.py \
       tests/architectural/test_fast_tier_marker_completeness.py \
       tests/architectural/test_marker_job_completeness.py \
       tests/architectural/test_module_shard_registry.py \
       tests/architectural/test_golden_count_ban.py               36 passed
ruff check <4 owned files>                                        All checks passed
ruff format --check <4 owned files>                               3 files already formatted
mypy --strict scripts/ci/sonar_pr_analysis.py                     Success: no issues
```

Per the operator ruling, the full `tests/architectural/` suite was **not** run; files were selected
via `grep -rl` over the changed surfaces plus the new-test-file gates.

Ownership clean: the diff touches exactly the 4 `owned_files`. `pytestmark = pytest.mark.fast` is
declared on the new test file. The `tests/ci` golden-count advisory is **not** attributable to this
WP — the new file contains no `len(...)` cardinality assertion at all.
