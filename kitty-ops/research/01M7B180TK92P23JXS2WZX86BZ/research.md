# Grounding note: #7622 + #7623 (nightly red, `SimpleNamespace` stands in for `Decision`)

Op `01M7B180TK92P23JXS2WZX86BZ` (profile `python-pedro`). Base: `origin/main` at `1fb3b55f`.
Kind: test-quality, red-first. Shape: Op (two test files, one surface).

## Triager finding, verified

- `8d911981` ("refactor(landing): read decision.suppress_step_pairing directly", 2026-11-12)
  changed one line of `src/specify_cli/cli/commands/next_cmd.py`. Verified on GitHub; the local
  clone carries the line through grafted history (`git blame` points at `a822df1a`, #7601).
- `next_cmd._decide_and_pair` (`next_cmd.py:477`) now reads `decision.suppress_step_pairing`.
  `runtime.next.decision.Decision` declares it (`decision.py:240`, internal, default `False`).
- Two test files stub `decide_next` with a `SimpleNamespace` that lacks the field:
  - `tests/specify_cli/cli/commands/test_next_owned_lock_timeout.py:66-67` (`_stub_decision`),
    4 tests.
  - `tests/specify_cli/cli/commands/test_next_commits_coordination_row_5938.py:246`, 1 test.
- Red reproduced on `origin/main`, py3.11, `-n0`: `5 failed, 18 passed`, each
  `AttributeError: 'types.SimpleNamespace' object has no attribute 'suppress_step_pairing'`.
  The product behaviour is correct; the stubs are stale. Not a regression.

## Fix shape

Both stubs return a real `Decision`. A `kind="step"` `Decision` must carry a `prompt_file` that
resolves on disk (`Decision.__post_init__`), so each test writes a one-line prompt file under
`tmp_path`. No assertion changes. No `getattr` fallback restored in `next_cmd.py`.

## Similar-surfaces squad

Sweep: `grep -rn "SimpleNamespace(kind" tests`, plus every `SimpleNamespace` file that names
`decide_next` / `Decision` / `_print_decision`.

| Site | What it stands in for | Disposition |
|---|---|---|
| `test_next_owned_lock_timeout.py:66` | `decide_next` return | in scope, fixed |
| `test_next_commits_coordination_row_5938.py:246` | `decide_next` return | in scope, fixed |
| `tests/runtime/next/test_next_invoked_row_asks_the_door_7539.py:104` | decision passed to `emit_mission_next_invoked` (typed `decision: object`) | latent, green today; operator asked |
| `tests/specify_cli/next/test_next_invocation_lifecycle_seam.py:648`, `:791` | same helper | latent; operator asked |
| `tests/integration/test_next_lifecycle_records.py:44` (`_FakeDecision`) | same helpers | latent; operator asked |
| `tests/specify_cli/cli/commands/test_next_owned_fact.py:378` | `query_current_state` return (`_print_decision` is stubbed) | latent; operator asked |
| `tests/runtime/test_bridge_decision_log_flush.py:271` | the engine's `plan_advance` result (a different type) | out of shape |

No other `decide_next` stub uses a `SimpleNamespace`. A guard against `SimpleNamespace` standing
in for `Decision` would be a new gate: not added without an operator ruling.

## Tracked-issues squad

- #7622, #7623: the nightly escalations for this red. Closes both.
- #7341 (closed), #7586 (closed, PR #7613): the earlier occurrences of the same class (a
  `SimpleNamespace` stand-in drifts when production reads a new field). Refs.
- #5345 (open): mock-heavy harnesses that stub out new gates. Related class (over-mocking);
  not folded.
- #5106 (open): parent epic of #7622/#7623. Refs.
- No duplicate of #7622/#7623 found.

## Out-of-matrix note

`tests/specify_cli/cli/commands` is an `out_of_matrix_test_dirs` entry
(`.github/ci-module-registry.yml`): it runs only in the nightly, so the per-PR CI does not run
these two files. The PR records the local runs.
