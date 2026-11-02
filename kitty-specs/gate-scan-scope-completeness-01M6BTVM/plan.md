# Implementation Plan: Architectural gate scan scopes — mechanical completeness check

**Mission**: `gate-scan-scope-completeness-01M6BTVM`
**Issue**: #7000 (follow-up to #6994 / #6996)
**Target branch**: `main`

## Summary

Add one static gate, `tests/architectural/test_gate_scan_scope_completeness.py`, backed by an
importable AST scanner `tests/architectural/_gate_read_scope.py`. The scanner extracts every
repository path a battery gate roots at the repository (`Path(__file__).resolve().parents[2]`,
names derived from it, `/` chains, `glob`/`rglob`/`iterdir`/`walk` calls) from the gate file and
from the `tests.architectural` helpers it imports transitively, and decides coverage against
(a) the gate's declared `scan_scopes` row and (b) the battery **code scope**, derived from the
router (every group the `architectural-heavy` job selects except `arch_scan_scope`) rather than
hardcoded. Uncovered reads fail with gate file, line, path prefix and owning gate. A narrow
exemption table admits the two reads that are not repository reads (a synthetic probe, an
untracked cache dir) and a stale exemption reds.

Landing the gate needs the declarations it finds missing to be fixed: 19 registry rows are
extended or added, the `arch_scan_scope` transcription in `ci-router.yml` is regenerated from
`gate_selection.battery_scope_router_globs()`, and a per-file timing budget is seeded for the new
gate. The existing routing property test (`test_battery_scan_scope_routing.py`) stays the pin for
the transcription.

## Technical Context

**Language/Version**: Python 3.12 (the repository's `.python-version`; the battery runs on 3.12 in CI)

**Primary Dependencies**: `pytest`, the standard library (`ast`, `pathlib`, `fnmatch`, `collections`), `pyyaml` (already used by the existing gates), and the in-repo `scripts.ci.gate_selection` seam. No new dependency, no network, no subprocess.
- **Existing seams reused, not duplicated**:
  - `scripts.ci.gate_selection`: `load_router()` (`Router.filters`, `Router.job_gates`),
    `battery_scan_scopes()`, `always_on_battery_files()`, `scope_trigger_globs()`,
    `battery_code_helpers()`, `HEAVY_BATTERY_JOB`, `BATTERY_SCOPE_GROUP`.
  - `tests/architectural/test_battery_scan_scope_routing.py`: the routing property and the
    router-transcription pin (unchanged).
  - `tests/ci/test_battery_roster_budgets.py`: the roster/budget rule (a new *heavy* file needs
    no roster slot; a timing entry avoids drift warnings).
- **Read extraction** (FR-001):
  1. Repo-root names: `X = Path(__file__).resolve().parents[2]`, `X = _THIS.parents[2]` where
     `_THIS = Path(__file__)`, and any name assigned a chain already rooted at such a name
     (`_SRC = _REPO_ROOT / "src"`).
  2. Reads: `BinOp(Div)` chains rooted at those names (constant, f-string and attribute parts kept
     literal where they are constant; any other right operand becomes a wildcard component), and
     `Call(func=Attribute(attr in {glob, rglob, iterdir, walk}))` on those names.
  3. Only the maximal chain per source line is kept, so `_REPO_ROOT / "a" / "b"` is one read
     (`a/b`), not three.
- **Coverage** (FR-002): a read prefix `p` is covered when `p` (or `p/__probe__`) matches any glob
  of the owning gate's declared row or of the code scope. A dynamic reader's literal parent
  (`p/**`) must be covered; a read rooted at the repository root needs `**`. Code scope = union
  of `Router.filters[g]` for `g` in `Router.job_gates[HEAVY_BATTERY_JOB] - {BATTERY_SCOPE_GROUP}`
  plus `src/**` and `tests/architectural/**` (the two globs the registry comment names as code
  scope; the rest is the router's own statement of what runs the whole battery).
- **Ownership** (FR-001): a helper module's reads belong to every gate that reaches it through
  `tests.architectural` imports — the same attribution `gate_selection.battery_code_helpers()`
  already uses for "battery code". Gate set = `tests/architectural/test_*.py`.
- **Exemptions** (FR-005): `EXEMPT_READS: Mapping[str, Mapping[str, str]]` in the scanner: gate →
  exact path prefix → reason. Rules pinned by tests: non-empty reason, no `**` prefix, entry must
  currently be needed (stale entry reds), and every exemption is reported in the gate's docstring
  count so a reviewer sees the whole list in one place.
- **Failure mode** (NFR-003): an unreadable/unparseable file raises with its path; a scan that
  finds fewer than the non-vacuity floor fails.

## Charter Check

- **Single canonical authority**: reads come from source, declarations from the registry, code
  scope from the router. The only new authority (the exemption table) is small, exact-prefix and
  test-pinned.
- **Locality of change / smallest viable diff**: no production code changes; no routing semantics
  change; no gate weakened. `gate_selection.py` is consumed, not modified.
- **ATDD-first / red-first**: the gate is authored first and its red is recorded (34 undeclared
  reads across 19 gates) before any declaration is touched; each declaration commit turns a named
  failure green.
- **Terminology**: "scan scope", "code scope", "battery", "gate" — the registry's own vocabulary;
  no `feature*` language.
- **Boy scout rule**: the registry comment block that documents `scan_scopes` gains the one line
  naming the completeness gate, in the same block that already names the routing property test.

## Implementation Concerns

### IC-01 — The scanner and the gate (FR-001, FR-002, FR-003, FR-004, NFR-003)

`_gate_read_scope.py` exposes: `repo_root_names(tree)`, `repo_root_reads(path) -> tuple[Read, ...]`,
`imported_battery_modules(path)`, `code_scope(router)`, `covers(glob, prefix)`,
`uncovered_reads(...) -> tuple[Finding, ...]` (pure over its inputs so controls can mutate them),
`EXEMPT_READS`, `validate_exemptions(...)`.

`test_gate_scan_scope_completeness.py` (fast, static, `architectural` + `fast` markers):
- `test_every_repo_root_read_is_declared` — the live property, one failure line per uncovered read.
- `test_the_scan_is_not_vacuous` — floor on gates and reads seen, and every declared gate file
  exists.
- `test_every_exemption_is_narrow_justified_and_needed`.
- `test_the_scan_errors_loudly_on_an_unparseable_gate`.

### IC-02 — The declarations the gate proves are missing (FR-006, NFR-002)

For each of the 19 gates: extend its `scan_scopes` row (or add one) with the minimal globs the
scan reports (`uv.lock`, `.gitignore`, `.github/CODEOWNERS`, `contracts/tools/**`,
`tests/scenarios/**`, `acceptance-jvm/src/test/java/**`, `kitty-specs/**`, `tests/**`,
`docs/api/**`, `ruff.toml`, `packs/built-in/**`, `.pytest_cache/...` exempt instead). Regenerate
the `arch_scan_scope` block in `ci-router.yml` from `battery_scope_router_globs()` (only new
union members land: `.github/CODEOWNERS`, `uv.lock`, `contracts/tools/**`,
`acceptance-jvm/src/test/java/**`; anything already covered by a wider union member is filtked
out by the derivation). Seed `battery_file_durations.architectural` with a measured entry for the
new gate file. Update the registry comment block and
`docs/development/reference/ci-gate-mechanics.md`; add the changelog fragment.

### IC-03 — Controls that prove the check can fail (FR-007)

Synthetic-tree controls in the gate: a tmp gate file with an undeclared `_REPO_ROOT / "planted"`,
the same read declared, a dynamic read whose parent is undeclared, a registry copy with a row
removed (the live scan reds naming that gate), a stale exemption, and an unparseable file.

## Project Structure

```
tests/architectural/_gate_read_scope.py                    # new: scanner (AST, coverage, exemptions)
tests/architectural/test_gate_scan_scope_completeness.py   # new: the gate + controls
.github/ci-module-registry.yml                             # scan_scopes rows + budget entry + comment
.github/workflows/ci-router.yml                            # arch_scan_scope transcription (derived)
docs/development/reference/ci-gate-mechanics.md            # the one paragraph naming the new check
docs/changelog/unreleased/<pr>.internal.md                 # changelog fragment
kitty-specs/gate-scan-scope-completeness-01M6BTVM/**       # mission artifacts
```

## Key Decisions

1. **Static AST over runtime tracing.** A tracer would need every gate to run (heavy, and the
   battery is not run in full); AST is deterministic, fast, and covers the #6994 class (a literal
   new root). Dynamic reads are handled by requiring their literal parent, not by pretending the
   scan can resolve them.
2. **Code scope derived from the router, not from a second list.** A hardcoded `src/**` +
   `tests/architectural/**` would drift from `ci_config` and the module groups; reading
   `Router.job_gates[architectural-heavy]` means the check follows the router that actually
   decides "whole battery".
3. **Helper reads attributed per importing gate.** Matches the existing battery-code model and is
   conservative: a gate that imports a helper which reads `docs/**` declares `docs/**`.
4. **Exact prefixes, reasons, and staleness for exemptions.** A `**` exemption or a reasonless
   entry would be a silent hole; a stale entry keeps a dead allowance alive.
5. **Fix declarations instead of exempting them.** 32 of the 34 findings are real reads of tracked
   paths; only the synthetic `.nonexistent-home` probe and the untracked
   `.pytest_cache/home-isolation-probes` are exempted.
6. **No change to `gate_selection.py` or the routing property test.** The routing behaviour changes
   only through the registry rows, which is the declared single source.
