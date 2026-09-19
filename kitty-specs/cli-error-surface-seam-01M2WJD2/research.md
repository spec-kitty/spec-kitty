# Research — Canonical guarded-read + CLI error-presentation seam

**Mission**: cli-error-surface-seam-01M2WJD2 · **Umbrella**: #2899

## Decisions

### D1 — Format-agnostic kernel primitive (not read+decode+validate)
- **Decision**: `kernel.read_guarded(path, parse, *, errors=(...))` wraps a
  caller-supplied `parse` callable and a caller-declared exception tuple, always
  adds `OSError`/`UnicodeDecodeError`, and raises one `GuardedReadError` base.
- **Rationale**: the in-scope readers span 5 decode formats (JSON, YAML+pydantic,
  TOML, raw utf-8). A kernel primitive that schema-validated would need to import
  `runtime`'s pydantic `WorkflowFile` model → violates the enforced direction
  `kernel <- charter <- {glossary, runtime, mission_runtime} <- specify_cli`
  (`tests/architectural/test_layer_rules.py`). Keeping decode/schema in the caller
  layer keeps kernel dependency-free.
- **Alternatives rejected**: (a) a JSON-only primitive (doesn't help #4738/#4637);
  (b) a primitive per format (multiplies authorities, fails C-002); (c) pydantic in
  kernel (deepens the zero-dep root with a heavy validation lib — architecturally
  wrong even though the layer *package* test wouldn't catch an external lib).

### D2 — Global Typer error hook (not an opt-in decorator)
- **Decision**: register one top-level Typer error handler that catches the
  `GuardedReadError` base (+ subclasses) and any explicit CLI domain error, renders
  human text or a JSON envelope at exit 1, and **re-raises** all other exceptions.
- **Rationale**: an opt-in `@handle_domain_errors` decorator is forgettable — the
  exact omission that produced #4642 — and its only gate (decorator-presence) is
  gameable. A global hook cannot be forgotten, is trivially gate-checkable (assert
  registered), and closes every command boundary at once, which is why #4724's 14
  resolver call sites and the live `accept` crash are fixed for free. Over-catch is
  neutralised by scoping to a single base and re-raising the rest.
- **Alternatives rejected**: per-command decorator; keeping per-site bespoke emitters
  (`_emit_meta_read_error`, `_emit_unsafe_mission_slug_error`, merge's) — those ARE
  the C-002 "two authorities" smell and fold into the hook.

### D3 — Subclass compatibility, never flat type replacement
- **Decision**: the 7 legacy typed errors become subclasses of `GuardedReadError`
  (re-parented in place). No raised type is flat-replaced.
- **Rationale**: caller census (below) found ~85 `except` sites, many tuple-catches
  and coupled pairs; a flat type change silently breaks them and re-opens the class
  off the 6 in-scope commands. Subclassing keeps every `except LegacyError` matching
  while also making the hook catch them via the base.

### D4 — Exit codes
- **Decision**: handled domain errors → exit **1** (matches shipped #4600/#4642);
  Typer *usage* errors keep exit **2** and are never swallowed by the hook. `specify`
  name validation stops raising `typer.BadParameter` (bypasses the hook, forces exit
  2/stderr) and raises a domain error → exit 1 + JSON on stdout. Crashing boundaries
  (`mission close`, `accept`) go to exit 1 via the hook; the already-clean `next`
  (exit 2) is left untouched to avoid churning a working command (charter
  locality/smallest-diff). Residual `next`(2)/others(1) inconsistency noted in the PR
  as an optional future consistency follow-up.

### D5 — Missing-vs-corrupt contract preserved
- **Decision**: hardening a reader keeps its current `None`/empty return for *absent*
  input; only decode/parse/schema failure routes to the typed error. The masking
  broad `except Exception` around `load_wps_manifest` in `runtime_bridge.py` (call
  ~:1024, catch ~:1034) is replaced by the typed seam WITH a companion assertion that
  the other operations in that block keep their behavior.
- **Rationale**: callers branch on the `None` return (e.g. `runtime_bridge`'s
  fallback to prose `tasks.md` parsing). Collapsing missing→error would silently
  kill those fallbacks.

## `except`-site caller census (from the boundary lens — verify + extend in WP01)

| Legacy error | def / raise | `except` catch sites (src) | Notes |
|--------------|-------------|----------------------------|-------|
| `MissionMetaReadError` (`core/paths.py`) | 1 / 1 | ~48 across ~30 modules | many tuple-catches (`status/store.py`, `coordination/status_transition.py`, `mission_runtime/resolution.py`, `merge/forecast.py`, …) |
| `DecisionIndexReadError` (`decisions/store.py`) | 1 / 2 | 12 | 6 in `cli/commands/decision.py`, 5 in `orchestrator_api/commands.py` |
| `CorruptLanesError` (`lanes/persistence.py`) | 1 / 1 | 12 (+10 coupled with `MissingLanesError`) | treat the pair as ONE unit |
| `AgentConfigError` (`core/agent_config.py`) | 1 / 6 | 13 | shipped #4600 guard |
| `UnsafePathSegmentError` (`core/paths.py`, `ValueError` subclass) | — | resolver called from 14 CLI files; `next`/`merge` catch, `accept` does NOT | hook covers all |

**Action for WP01**: reproduce this census (src **and** tests — `pytest.raises(...)`
sites ripple too), record final counts, and add the NFR-006 back-compat regression
that asserts each legacy type is still caught (incl. the `MissingLanes`/`CorruptLanes`
pair) after re-parenting.

## Adversarial evidence (post-spec squad, per contracts/adversarial-evidence-contract)

| Finding (lens) | Disposition |
|----------------|-------------|
| FR-001 impossible as read+decode+validate in kernel (architecture) | **changed** → D1 format-agnostic |
| FR-011 gate under-specified / vacuity risk (architecture) | **changed** → FR-011 names invariant + self-mutation (WP08) |
| Presentation: decorator vs hook (architecture) | **changed** → D2 global hook |
| #4739 root cause is the text-stream `stream.read()`, not the bytes branch (architecture) | **accepted** → FR-008 guards `stream.read()` |
| #4720 `typer.BadParameter` bypasses the hook (architecture) | **accepted** → FR-009 raises a domain error |
| #4724 resolver called from 14 sites; `accept` unguarded (architecture) | **accepted** → single hook covers all; `accept` added |
| `-f`=`--mission` on 4 sites, not only close (architecture) | **accepted** → FR-006 sweep |
| FR-013 flat type change breaks ~85 catch sites (boundary) | **changed** → D3 subclassing + census + NFR-006 |
| `runtime_bridge` broad-except unmask ripple (boundary/completeness) | **accepted** → D5 companion assertion |
| Missing-vs-corrupt return contract (boundary) | **accepted** → D5 |
| #4637 has 3 failure modes (completeness) | **accepted** → FR-007 |
| audit-tail tests must run through command entry point (completeness) | **accepted** → US3 scenarios 2–3 |
| mission-close exit-code contradiction (completeness) | **changed** → D4 |
| NFR-003 5 ms wall-clock flaky (completeness) | **changed** → NFR-003 structural |
| NFR-005 `.isascii()` vacuous under reject (completeness) | **changed** → NFR-005 negative no-write assertion |
| FR-004 export unverifiable / no scenario (completeness) | **accepted** → US1 scenario 3 |
| mixed `auth日本` silent-drop not scenario'd (completeness) | **accepted** → US2 scenario 3 |

No contested finding was silently dropped.

## Supply-chain (DIRECTIVE_051)
- **N/A** — the mission adds, upgrades, and removes **no** dependency. `PyYAML`,
  `pydantic`, `tomllib` (stdlib), `typer`, `rich`, `ruamel.yaml` all already ship.
  No lifecycle-script, registry-authenticity, or freshness decision arises. Recorded
  explicitly per the advisory posture (silence ≠ compliance).
