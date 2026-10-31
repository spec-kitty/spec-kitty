# Research: Opaque declared-command failure identity (#6751)

## Grounding on current `main`

`main@512567eee7`. The issue's own snippet is reproduced verbatim (a throwaway script, no repo change):

```text
baseline: (BaselineFailure(test='<declared-command>', error='error: no build.zig file found, in the current directory or any parent directories', file='unknown'),)
candidate: (BaselineFailure(test='<declared-command>', error="src/example.zig:1:1: error: expected type 'u64', found '[]const u8'", file='unknown'),)
outcome: no_new_failures new: 0 pre: 1
```

Not superseded: `git log -S "<declared-command>"` shows only the three commits that introduced and last touched the ScopeSource (`dd6083d5a7`, `c844a0df22`, `584a5c2c11`); no open or merged PR references #6751; the changelog has no entry for it.

## The three cited symbols, read at `512567eee7`

| Symbol | File:line | Behaviour |
|---|---|---|
| `_whole_run_failure` | `review/scope_source.py:246` | `parse_results` calls it when the text strategy found no `FAIL ` line and `returncode != 0`. Returns `BaselineFailure(test="<declared-command>", error=<last line, 200 chars>, file="unknown")`. |
| `diff_baseline` | `review/baseline.py:699` | Builds `{f.test}` sets; a current failure is pre-existing iff its name is in the baseline name set. `error`, `file` and the run's exit status are ignored. |
| `_classify_current_failures` | `review/pre_review_gate.py:676` | Calls `diff_baseline`; no new failures → `NO_NEW_FAILURES`. |

So the collision is exactly as filed: the placeholder name *is* the identity, and two unrelated opaque failures share it.

## Who calls what (blast radius)

- `diff_baseline` has exactly one product caller (`pre_review_gate._classify_current_failures`) and one test module (`tests/review/test_baseline.py`); its two lists are consumed by the verdict and by `_mt_pre_review_gate_metadata` (`new_failure_count`, `new_failure_nodeids`, `pre_existing_failure_count`).
- `_classify_current_failures` has two callers: `_evaluate_via_scope_source` (the injected port, where the declared command runs as a subprocess and a real `returncode` is in hand) and `evaluate_with_scope`'s legacy pytest/JUnit branch (no opaque identity is ever produced there — JUnit parsing yields real test names).
- `BaselineFailure`/`BaselineTestResult` are persisted in `tasks/WPxx/baseline-tests.json` via `to_dict`/`from_dict`; `from_dict` reads fixed keys, so an added key must default rather than raise (NFR-003).
- `source_identity` (e.g. `DeclaredCommandScopeSource/text`) already gates comparability across the two runs; the opaque rule is a second, finer axis inside the same identity.

## Constraint discovered: the parity oracle pins the verdict metadata exactly

`tests/review/test_transition_gate_parity.py` rebuilds `GateVerdict`s from `tests/review/fixtures/parity/*.json`, runs them through `_mt_pre_review_gate_metadata` + `_mt_pre_review_gate_console_warning`, and asserts **`actual["metadata"] == expected["metadata"]`** and the **exact console string**. Those fixtures are an oracle captured from the base commit and are explicitly never regenerated from HEAD. Consequences for the design:

1. The candidate exit status must **not** become a new metadata key — the whole fixture set would fail.
2. It must ride on the existing `reason` field (already in the metadata payload) and, for humans, on the existing `no_new_failures` dim console line, appended only when a reason exists. A fixture verdict (no exit status, `reason: null`) keeps rendering `Pre-review regression gate: no new failures` byte-identically.
3. `GateVerdict` may gain a defaulted field; the fixtures reconstruct it without that field.

## Options considered

| Option | Verdict |
|---|---|
| Classify any opaque mismatch as `UNVERIFIED_BASELINE` | Rejected: warn-and-pass by construction, so a genuine regression still lands green-ish; the issue explicitly wants unverified *or* a bounded identity, and the bound identity is available. |
| Fold exit status + summary into the failure *name* (`<declared-command>:exit 2:...`) | Rejected: it keeps one string doing two jobs, truncates the summary at the 200-char cap inside a name, and makes the human-facing `nodeids` list unreadable. An explicit `opaque` marker + `exit_code` field says what it means. |
| Bind identity to `(exit status, digest of the FULL output tail)`, match opaque only against opaque | Chosen. Exact-equality binding is the tightest honest identity available without a per-test parser; a differing opaque candidate failure is a new failure (fail-closed), and an identical one stays pre-existing. The last-line summary alone was rejected during review: `make` ends every recipe failure with the same tail, so exit status + summary still collapsed unrelated failures (see the WP01 review fold). |

## Known limitation (documented, not hidden)

An opaque summary that embeds a nondeterministic token (a temp-directory path, a PID, a runtime) will not match the baseline and will be reported as a new failure. That is the fail-closed direction the gate should err in: the alternative is the collision this issue reports. The verdict reason names the mismatch so an operator can see it is an identity problem, not a silently-equal failure.

## Related, out of scope

- #6746 (bounded project budgets) — already landed as `129527bfa4`; no timeout default is touched here.
- #6798, #6801 (red on `main`, unrelated modules) — cited in the PR if they surface in CI.
- #6816 (router gate false red) — CI infrastructure, cited if it surfaces.

## Decisions reached (discovery summary)

- The opaque placeholder name is not an identity; the bound identity is (exit
  status, full-output digest), and only an exact match is pre-existing. A
  differing opaque candidate failure is a `new_failures` verdict — fail-closed,
  never a silent pass.
- Named identities (`FAIL <name>`, JUnit test names) keep name-based matching, so
  the incumbent pre-existing-failure behaviour is unchanged.
- The candidate's observed exit status is carried on the verdict and stated in
  the `no_new_failures` reason; it rides on the existing `reason` field because
  the transition-gate parity oracle asserts exact metadata equality.

## Open questions

None outstanding. The two design choices that could have needed an operator call
(new-failure vs. unverified for a differing opaque pair; digest vs. last-line
summary) are settled above and pinned by tests; neither changes a gate default,
a timeout or the opt-in block predicate.
