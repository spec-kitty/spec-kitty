# Tasks: Architectural gate scan scopes — mechanical completeness check

**Mission**: `gate-scan-scope-completeness-01M6BTVM` | **Branch**: `issue-7000-gate-scan-scope-completeness`
**Issue**: #7000

Two work packages. WP02 adds the adversarial controls to the scanner WP01 builds, so it lands
after WP01; both are static, dependency-free Python.

## Subtask Index
| ID | Description | WP | Parallel |
| --- | --- | --- | --- |
| T001 | Scanner: repo-root read extraction + coverage + exemptions (`_gate_read_scope.py`) | WP01 | [P] |
| T002 | The gate: every uncovered read reds, naming gate/line/prefix (`test_gate_scan_scope_completeness.py`) | WP01 | [P] |
| T003 | Fix the 19 incomplete declarations in the registry + regenerate the router transcription + budget entry | WP01 | [P] |
| T004 | Control tests: planted undeclared read, dropped declaration, stale exemption, dynamic read, parse failure (`test_gate_read_scope_controls.py`) | WP02 | [P] |
| T005 | Docs: ci-gate-mechanics paragraph, registry comment line, changelog fragment | WP02 | [P] |

## WP01 — The completeness gate and the declarations it proves missing — P1
Goal: a static gate that reds on every repository-root read a gate makes outside its declared scan
scope or the battery code scope, and a registry whose declarations satisfy it today.
FR-001, FR-002, FR-003, FR-004, FR-005, FR-006, NFR-001, NFR-002, NFR-003.
- [ ] T001 `tests/architectural/_gate_read_scope.py`: resolve repo-root names
  (`Path(__file__).resolve().parents[2]`, `_THIS.parents[2]`, derived names), extract maximal `/`
  chains and `glob`/`rglob`/`iterdir`/`walk` calls, attribute a helper module's reads to every gate
  that imports it transitively, derive code scope from the router, and expose a pure
  `uncovered_reads(...)` plus `EXEMPT_READS` / `validate_exemptions(...)` (WP01)
- [ ] T002 `tests/architectural/test_gate_scan_scope_completeness.py`: the live property (one
  failure line per uncovered read, naming gate file, line, prefix, owning gate), a non-vacuity
  floor, exemption rules, and loud failure on an unparseable gate (WP01)
- [ ] T003 Fix the 19 incomplete declarations the gate names (`uv.lock`, `.gitignore`,
  `.github/CODEOWNERS`, `contracts/tools/**`, `tests/scenarios/**`,
  `acceptance-jvm/src/test/java/**`, `kitty-specs/**`, `tests/**`, `docs/api/**`, `ruff.toml`,
  `packs/built-in/**`; exempt the synthetic `.nonexistent-home` probe and the untracked
  `.pytest_cache/home-isolation-probes`), regenerate the `arch_scan_scope` block from
  `gate_selection.battery_scope_router_globs()`, add the new gate's timing budget, and update the
  registry comment block (WP01)
**Independent test**: plant `_REPO_ROOT / "planted-undeclared-dir"` in a gate → the gate reds
naming it; declare it → green. `test_battery_scan_scope_routing.py` and
`tests/ci/test_battery_roster_budgets.py` stay green.

## WP02 — Adversarial controls and the operator-facing docs — P2
Goal: prove the check can fail for the right reason and document it where the CI mechanics are
explained. FR-007, NFR-001.
- [ ] T004 `tests/architectural/test_gate_read_scope_controls.py`: scan a synthetic tree with an
  undeclared read (fails, names the prefix), the same read declared (passes), a partially dynamic
  read whose parent is undeclared (fails with `prefix/**`), a registry copy with one row dropped
  (the live scan reds naming that gate), a stale exemption and a reasonless/`**` exemption (each
  reds), and an unparseable gate file (raises with its path) (WP02)
- [ ] T005 `docs/development/reference/ci-gate-mechanics.md` gains the completeness paragraph next
  to the #6994 scan-scope bullet; the registry comment block names the new gate; the changelog
  fragment lands under `docs/changelog/unreleased/` (WP02)
**Independent test**: every control reds on its mutation with a message naming the mutated gate,
glob or exemption; removing the mutation greens it.

**MVP**: WP01 (the gate and a green registry). **Dependencies**: WP01 → WP02 (the controls test the
scanner WP01 creates; no file overlap).
