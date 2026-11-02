# Validation and independent review

## Executed checks

- Baseline: `PYTEST_XDIST_AUTO_NUM_WORKERS=2 timeout 900 make test-fast` — 2,786 passed, 6 skipped. Workers were bounded on the shared VM.
- Final owning subsystem: `.venv/bin/python -m pytest tests/ci -q` — 2,922 passed, 1 skipped, 3 existing battery-timing drift warnings after rebasing onto `cddaf2618`.
- Final review folds: `.venv/bin/python -m pytest tests/ci/test_packaging_scope.py tests/ci/test_capture_shard_timings.py tests/ci/test_recapture_shard_timings.py tests/ci/test_docs_lint_job.py tests/architectural/test_shard_capture_provenance.py -q` — 304 passed, covering the subsequent rename and capture-completeness fixes.
- Post-rebase guard/fixture check: `.venv/bin/python -m pytest tests/architectural/test_guard_capability_call_sites.py tests/architectural/test_inline_meta_read_gate.py tests/architectural/test_execution_mode_no_redrift.py tests/charter/test_charter_conftest_git_init_criterion.py -q` — 62 passed, 1 existing performance skip. Earlier targeted charter consumers and the new fixture regression file — 154 passed.
- Helper coverage: the policy, packaging, Sonar and Gradle helpers have 95% combined coverage (111 focused tests, including the revision resolver tests). The revision resolver is loaded by file path under the alias `warmup_events_rev`; measuring that alias separately after transport/error regression additions gave 22 passed and 99% coverage. No live PyPI request was needed for those transport tests.
- Parent integration/guard checks — 538 passed; after review's gate-ownership and step-structure fixes, 258 passed across the implicated files.
- `ruff check .`, `ruff format --check .` — clean. Formatter-debt exclusions were honored; no unrelated whole-file formatting.
- Strict mypy with explicit namespace bases over all eight changed/new CI scripts — clean.
- SHA-pinned actionlint v1.7.7 over all ten changed workflow files — clean.
- No full architectural, e2e, performance/stress or repository-wide heavy suite was run locally. The CI subsystem and required fast baseline are not replacements for GitHub's module matrix.

Counts overlap: they are evidence for individual commands, not an additive total.

## Independent reviews and folds

All implementation/review delegates used the operator-specified DeepSeek V4.1 Flash 1017 model. The parent also reviewed the source and integrated the complete diff.

The first independent review found stale gate ownership assertions, advisory steps inside the strictly blocking docs-lint job, shallow commit-subject history, advisory timeout coupling, policy-cache trust misstatement and loss of hash-verified Ruff installation. The implementation now:

- keeps Ruff/TID251 and lock checks always-on under the required router gate;
- keeps docs-lint strictly blocking and moves bounded informational probes into the lock job with reserved budget and full history;
- uses hash-locked installation without installing the project/workspace;
- permits cross-run policy cache reads/writes only in the trusted default-branch namespace. A co-cached HMAC key is not an authentication boundary against a cache writer; PR and merge-queue events retain fresh local enforcement.

Final aggregate review found no blocking defect in the reviewed implementation and identified small follow-ups. Folded: disable rename collapsing in packaging diffs and test a shipping-input rename into docs; update enforcement/budget pointers; remove remaining implicit documentation environment syncs; document dynamic fixture opt-in; reject exit-one captures without a failed runtest report. Parent also added malformed projection/NaN tests, phase-error counting, restored-tool path containment, corrupt-root recovery and newest artifact-attempt selection.

Repository settings were inspected read-only: applied branch rules require exactly `Clean install verification`, `router gate` and `CI Modules gate`. All remain present. No settings were changed.

## Rollout boundaries

- The committed legacy timing arrays are not given invented node identities. Until real CI recapture publishes identity tables, legacy rows use visible count-based selection. Some rows already used that fallback because counts drifted; do not treat a historical-array skew model as a measured before/after CI regression or speedup.
- Review and land fresh identity captures through the existing bounded recapture proposal before claiming duration-weighted production balancing. Local full-module recapture would violate the project's heavy-suite boundary; none was fabricated.
- Full-mode job failures may reveal previously hidden pre-existing nightly reds. Classify those by test name and baseline; do not restore exit-zero wrappers.
- No unmeasured shard-count increase, debounce, cache purge, WIP gating change or legacy docsite rewrite was introduced.
- This Mission is submitted for PR review; it has not been accepted, consolidated into main or merged by the implementation agent.
