# CLI Boundary Robustness — final-gates regression fixes (implementer handoff)

Mission: `cli-boundary-robustness-01M2NQCB` / issue #4600 / PR #4674.
Frozen-core final-gates evidence: `final-gates-ea5fc3678ebb-20260916T231123Z/`.

Three genuine (non-baseline) regressions were fixed, each as its own commit,
mirrored into both checkouts (core mission source-of-truth `spec-kitty` on
`fix/cli-boundary-robustness`, and the GitHub-PR-backing `review-pr` on
`issue-4600-cli-boundary-robustness`). All commits are local only — nothing
pushed to `origin`, nothing merged.

## Commits

| # | Checkout | Branch | Commit | Subject |
|---|----------|--------|--------|---------|
| 1a | review-pr | issue-4600-cli-boundary-robustness | `264f566d7` | test(dashboard): update stale project-root mocks for json_output keyword |
| 1b | spec-kitty (core) | fix/cli-boundary-robustness | `21a5aabec` | test(cli): mirror stale project-root mock fix from review-pr |
| 2a | spec-kitty (core) | fix/cli-boundary-robustness | `08f83da3b` | fix(arch-gate): refresh stale register() hashes, allowlist uncaught exception |
| 2b | review-pr | issue-4600-cli-boundary-robustness | `ccd787071` | fix(arch-gate): refresh stale register() hashes, allowlist uncaught exception |
| 3a | spec-kitty (core) | fix/cli-boundary-robustness | `d8e05ee7d` | test(charter): close 5-line diff-coverage gap on consistency_check.py |
| 3b | review-pr | issue-4600-cli-boundary-robustness | `2d0864eb8` | test(charter): close 5-line diff-coverage gap on consistency_check.py |

Note on ordering: `review-pr` already had commit `0e9068060` ("test(cli):
update resolver mocks for JSON mode keyword") applied *before* this session
started, from an earlier post-merge remediation pass — it fixed the 3
identical stale-lambda sites in `tests/agent/test_commands.py`. That commit
was **not** in core. So for item 1, review-pr only needed the 2 remaining
sites in `test_duplicate_prefix_rendering.py`, while core needed all 5 sites
(3 from `test_commands.py` + 2 from `test_duplicate_prefix_rendering.py`) —
commit 1b mirrors 0e9068060's exact diff for the 3 `test_commands.py` sites
plus the 2 `test_duplicate_prefix_rendering.py` sites, into core.

## Item 1 — Dashboard stale-mock regression (test-only)

**Root cause:** `get_project_root_or_exit(start: Path | None = None, *,
json_output: bool = False)` in `src/specify_cli/cli/helpers.py`. Several
tests monkeypatched it with a zero-arg (or positional-only) lambda that
breaks once the boundary refactor added the `json_output` keyword.

**Files fixed (both checkouts):**
- `tests/dashboard/test_duplicate_prefix_rendering.py` —
  `test_dashboard_json_cli_renders_three_distinct_rows`,
  `test_rendered_json_contains_every_mid8` (2 sites, zero-arg lambdas).
- `tests/agent/test_commands.py` (core only — review-pr already had this) —
  `test_verify_setup_command_runs`, `test_dashboard_kill_stops_instance`,
  `test_verify_setup_json_output` (3 sites), applying the exact diff from
  `0e906806015e4260d7846b29d1d956bd905d3fbc`.

**Red (review-pr, before fix):**
```
$ .venv/bin/pytest tests/dashboard/test_duplicate_prefix_rendering.py::test_dashboard_json_cli_renders_three_distinct_rows tests/dashboard/test_duplicate_prefix_rendering.py::test_rendered_json_contains_every_mid8 -q
FAILED ...renders_three_distinct_rows - TypeError: <lambda>() got an unexpected keyword argument 'json_output'
FAILED ...contains_every_mid8
2 failed in ~1s
```

**Red (core, before fix, all 5 sites):**
```
$ .venv/bin/pytest tests/agent/test_commands.py::test_verify_setup_command_runs tests/agent/test_commands.py::test_dashboard_kill_stops_instance tests/agent/test_commands.py::test_verify_setup_json_output tests/dashboard/test_duplicate_prefix_rendering.py::test_dashboard_json_cli_renders_three_distinct_rows tests/dashboard/test_duplicate_prefix_rendering.py::test_rendered_json_contains_every_mid8 -q
5 failed in 41.77s
```

**Green:**
```
$ .venv/bin/pytest tests/dashboard/test_duplicate_prefix_rendering.py -q   # review-pr: 8 passed in 29.54s
$ .venv/bin/pytest tests/agent/test_commands.py tests/dashboard/test_duplicate_prefix_rendering.py -q   # core: 26 passed in 190.71s
```

Fix pattern (per test): replace the stale lambda with a small function
accepting `*, json_output: bool = False`, e.g.:
```python
def fake_project_root(*, json_output: bool = False) -> Path:
    return colliding_080_repo

monkeypatch.setattr(
    "specify_cli.cli.commands.dashboard.get_project_root_or_exit",
    fake_project_root,
)
```

## Item 2 — Three dead-code-gate symbols

Gate: `tests/architectural/test_no_dead_symbols.py::test_no_public_symbol_in_all_is_unimported`.

Investigation verdicts:

1. **`specify_cli.cli.commands._env_file_doctor::register`** — NOT dead.
   Already allowlisted under `_CATEGORY_C_DOCTOR_AUTO_DISCOVERY_SEAM`
   (reached only via `doctor.py`'s `_auto_discover_doctor_siblings()`'s
   dynamic `getattr(module, "register")` call — invisible to the gate's
   static-import scan). The CLI-boundary refactor changed the `register`
   shell's nested `env_file` command body, which changed its content-tier
   `SymbolKey.body_hash`, orphaning the old allowlist entry. **Fix:**
   recomputed the hash with the gate's own `_symbol_key.definition_span` /
   `body_hash` helpers and refreshed the allowlist entry (old
   `f4c52c62e8b8...`, new `d2dde051e8ad...`).

2. **`specify_cli.cli.commands._provenance_doctor::register`** — same
   root cause and same fix (old `dd9512fa1755...`, new `5e4f0244801f...`).

3. **`charter.activation.mission_type_profiles::MissionTypeEmptyActionSequenceError`**
   — NOT dead, and not a wire-up gap either. It's raised twice intra-module
   (`resolve_mission_type_context` / the layered-roster resolver, WP06,
   FR-004) but **deliberately never caught by name** at any `src/` call
   site: `charter/activation/charter_activate.py`'s `except
   UnknownMissionTypeError:` narrows to that *sibling* exception only, so
   this one propagates uncaught to the CLI boundary (see
   `charter/activate.py`'s handler comment quoting spec.md Edge Cases: "must
   surface that resolution failure rather than silently treating 'cannot
   resolve' as 'no steps were removed'"). The gate's import-based caller
   detector cannot see a deliberately-uncaught `raise` as a reference — same
   fail-loud shape as the pre-existing `OperatorEnvFileUnreadableError`
   allowlist entry in `_CATEGORY_C_OPERATOR_CONFIG_PUBLIC_API`. **Fix:**
   added a new allowlist category
   `_CATEGORY_C_MISSION_TYPE_UNCAUGHT_PROPAGATION_SURFACE` with a rationale
   comment and a `#4600 (FR-303)` tracker reference, per the gate's own
   fix-instructions (option 4).

All three fixes are allowlist-only edits to
`tests/architectural/test_no_dead_symbols.py` — no `src/` changes.

**Red:**
```
$ .venv/bin/pytest tests/architectural/test_no_dead_symbols.py::test_no_public_symbol_in_all_is_unimported -q
(pre-existing failure captured in final-gates-ea5fc3678ebb-20260916T231123Z/architecture.log:)
FAILED tests/architectural/test_no_dead_symbols.py::test_no_public_symbol_in_all_is_unimported
  - charter.activation.mission_type_profiles::MissionTypeEmptyActionSequenceError
  - specify_cli.cli.commands._env_file_doctor::register
  - specify_cli.cli.commands._provenance_doctor::register
```

**Green (both checkouts, identical):**
```
$ .venv/bin/pytest tests/architectural/test_no_dead_symbols.py::test_no_public_symbol_in_all_is_unimported -q
1 passed in ~70s
$ .venv/bin/pytest tests/architectural/test_no_dead_symbols.py -q
34 passed in ~122s
```

Also ran the directly-affected functional test files to confirm nothing
depended on old behavior: `tests/charter/test_mission_type_profiles.py`,
`tests/specify_cli/cli/commands/test_env_file_doctor.py`,
`tests/specify_cli/cli/commands/test_provenance_doctor.py` — 55 passed.

## Item 3 — Coverage gap on `consistency_check.py`

Final-gates `critical-diff-cover` gate (fail-under 90) scored
`src/charter/activation/consistency_check.py` at 89.6% (missing lines 628,
632, 636, 1363, 1504), pulling the overall critical score to 89%.

All 5 missing lines are fail-closed error branches with no existing test:

- **628 / 632 / 636** — `_load_reference_ids_by_kind`'s three post-parse
  `isinstance` shape guards, each raising `CharterYamlCorruptError`:
  document root not a mapping (628), `catalog` not a mapping (632),
  `catalog.references` not a list (636). The sibling YAML-*parse*-failure
  case was already tested
  (`tests/doctrine/test_activation_parity_guard.py::test_corrupt_references_yaml_fails_closed`),
  and that same file's own module docstring already *named* the missing
  test — `test_references_yaml_malformed_schema_fails_closed` — but the
  function itself was never written. Added it, parametrized over the three
  shapes, asserting `coherent=False` and the exact `CharterYamlCorruptError`
  message fragment lands in `verification_errors`.

- **1363** (`scan_enforcement_lattice_violations`) / **1504**
  (`scan_decision_documentation_scoped_on_implement`) — each raises a
  `RuntimeError` when the DRG reports an edge/URN as active but the
  directive repository cannot resolve it (a genuine DRG↔doctrine-repository
  disagreement, not a legitimate "nothing to check" skip). Added one test
  per gate in `tests/charter/test_enforcement_lattice.py` and
  `tests/charter/test_decision_documentation_on_implement.py`, each forcing
  the disagreement by monkeypatching `consistency_check._resolve_directives`
  to return an empty repository while the DRG fixture graph still marks the
  edge's endpoints active — asserting `pytest.raises(RuntimeError,
  match="cannot resolve")`.

No `src/` changes — test-only, in the three files that already own
coverage for `consistency_check.py`'s respective functions.

**Green (new tests):**
```
$ .venv/bin/pytest tests/doctrine/test_activation_parity_guard.py -q -k malformed_schema   # 3 passed
$ .venv/bin/pytest tests/charter/test_enforcement_lattice.py -q                             # 8 passed
$ .venv/bin/pytest tests/charter/test_decision_documentation_on_implement.py -q             # 6 passed
```

**Scoped diff-cover before/after** (both checkouts, identical numbers —
fresh `--cov=src` XML from the 5 owning test files, scored against the
frozen-core run's already-generated `critical.statements.diff`; source file
`consistency_check.py` is unchanged so the diff itself is still valid):

| | Before (frozen-core run) | After (this session) |
|---|---|---|
| `consistency_check.py` | 89.6%, missing 628,632,636,1363,1504 | 93.8%, missing 307-308,558 |
| Total (critical diff) | 89% (43/48) | 93% (45/48) |

The remaining scoped-run gap (lines 307-308, 558) is covered by other
`tests/charter/*` files not included in this targeted 5-file rerun (e.g.
`test_kind_cascade_exhaustive.py` / `test_check_graph_kind_parity.py`); the
original frozen-core run's `owner-callers-coverage` pass, which runs the
full suite together, already had those two covered (they were absent from
the original missing-lines list) — only 628/632/636/1363/1504 were the
regression.

**Reproduce (from either checkout root, `.venv` already synced):**
```bash
COVERAGE_FILE=/tmp/scoped.coverage .venv/bin/python -m pytest \
  tests/charter/test_consistency_check.py \
  tests/charter/test_enforcement_lattice.py \
  tests/charter/test_decision_documentation_on_implement.py \
  tests/doctrine/test_activation_parity_guard.py \
  tests/charter/test_tension_unreconciled.py \
  -m "not timing and not stress" \
  --cov=src --cov-report=xml:/tmp/scoped-coverage.xml -q

.venv/bin/diff-cover /tmp/scoped-coverage.xml \
  --diff-file <final-gates-dir>/critical.statements.diff --fail-under=90
```

## Reproduce item 1 and item 2

```bash
# Item 1
.venv/bin/pytest tests/agent/test_commands.py tests/dashboard/test_duplicate_prefix_rendering.py -q

# Item 2
.venv/bin/pytest tests/architectural/test_no_dead_symbols.py -q
```

## What was NOT touched

- No `src/` production code changed anywhere in this session — all three
  fixes are test-only or allowlist-only.
- `SPEC_KITTY_ENABLE_SAAS_SYNC` was never read, set, or unset.
- No merges, no pushes, no history rewrites, no worktree/branch changes
  beyond the 6 commits above (3 in core, 3 in review-pr).
- The full `tests/` suite and `make test-full` were never run — only the
  targeted node IDs/files listed above, plus the two scoped `--cov=src`
  reruns for item 3's coverage confirmation.

## Outstanding for the independent reviewer

- Confirm the `MissionTypeEmptyActionSequenceError` allowlist rationale
  reads correctly against `charter/activate.py`'s actual except-clause
  wording (it was quoted/paraphrased from that file's own comment).
- The `#4600 (FR-303)` tracker reference in the new allowlist category is a
  reference to this mission's own GitHub issue, following the existing
  convention of citing a real issue number alongside `(FR-303)`; there is
  no separate new ticket filed for the wire-or-prune follow-up.
- Full (non-scoped) final-gates re-run is the authoritative confirmation
  for item 3's coverage number — the scoped rerun here is evidence the gap
  is closed, not a replacement for the real gate.
