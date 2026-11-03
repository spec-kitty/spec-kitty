---
title: 'Engineering notes: code shape and architecture survey (2026-11-03)'
description: 'Measured code-shape and architecture-alignment debt on main: the C901 baseline gap, duplicate authorities, god modules, stale hosted docs, and the remediation scope.'
doc_status: active
updated: '2026-11-03'
audience:
- profile: internal/maintainer
  guidance_text: Written for the Maintainer reader.
type: reference
related:
- development/reference/ci-gate-mechanics
- architecture/00_landscape
---
# Engineering notes: code shape and architecture survey (2026-11-03)

Tracking ticket: [#7155](https://github.com/spec-kitty/spec-kitty/issues/7155).
Base: `main@dcdacbd2e5`. Three independent lenses (architecture, code shape, tests/gates)
surveyed `src/**`, `tests/**`, `.github/**` and `docs/architecture/**`; every finding below was
re-verified against the tree by the maintainer. Two proposed findings were wrong and are recorded
under [Rejected](#rejected) so they are not re-raised.

## CI cost, measured

From `.github/ci-shard-timings.json` (module durations, the basis the shard budgets use):

| Module | Measured cost |
| --- | --- |
| consolidation | 1870 s |
| charter | 1401 s |
| upgrade | 1089 s |
| core_misc | 954 s |
| execution_context | 556 s |
| ci | 305 s |
| cli | 254 s |
| lanes | 175 s |

The file also records an xdist worker crash (INTERNALERROR) on
`tests/retrospective/test_writer_atomicity.py::test_dir_fsync_failure_is_non_fatal`; that is a
harness event to watch, not a per-PR failure.

## HIGH

### 1. The "complexity ceiling is 15" is hollowed out by an unguarded baseline

`ruff.toml` carries **25 whole-file `C901` exemptions** for `src/**` files, so every function in
those files may exceed the ceiling. Measured with ruff's own mccabe (threshold 1, inline `noqa`s
respected):

| mccabe | function | where |
| --- | --- | --- |
| 69 | `run_enhanced_verify` | `src/specify_cli/verify_enhanced.py:56` |
| 39 | `build_summary` | `src/specify_cli/retrospective/summary.py:380` |
| 39 | `_display_status_board` | `src/specify_cli/agent_utils/status.py:389` |
| 35 | `compute_lanes` | `src/specify_cli/lanes/compute.py:835` |
| 35 | `synthesize_cmd` | `src/specify_cli/cli/commands/agent_retrospect.py:589` |

The formatter-exclude and PT-pair baselines are shrink-only ratcheted; **the C901 list is not**, and
it has moved both ways historically (309 entries at creation, 353 at its peak, 338 now). A baseline
that grows by goodwill is not a ratchet.

### 2. `init()` is a 769-line, ~121-decision-point command

`src/specify_cli/cli/commands/init.py:877` (inline `# noqa: C901`). It performs at least six
distinct jobs: dependency asserts, argument/path validation, `--ai` parsing, the
already-initialized resume/repair path, the operator-content backup decision, and the scaffold.
The resume/repair block (~944–977) and the `--ai` parsing (~924–942) are self-contained clusters
that belong in helpers.

### 3. The "living" C4 context diagram presents removed hosted surfaces as current

`docs/architecture/diagrams/01_context/README.md` (`doc_status: active`, updated 2026-11-01) still
draws `Team Kitty SaaS`, the `Zeitgeist relay`, and the "one moment per lane transition, when drain
is on" edge; the table describes the relay publish path in the present tense.
`docs/architecture/index.md:186` calls `context/team-kitty.md` "the live hosted model". The client
code (`auth`, `zeitgeist_client/`, `saas_client/`) was removed in #6164 — only gitignored
`__pycache__` debris remains — and `docs/architecture/zeitgeist-session-identity.md` is still
`doc_status: active` while its env var has zero `src/` references.

## MEDIUM

### 4. Two canonical-repo-root resolvers

`core/paths.py:413 resolve_canonical_root` (plus `get_main_repo_root:482`, ~114 callers; pure path
walk, honours `GIT_CEILING_DIRECTORIES`, raises `WorkspaceRootNotFound`) versus
`charter/resolution.py:79 resolve_canonical_repo_root` (~39 callers; kernel git probe, LRU-cached,
resolves `core.worktree` for submodules). The code concedes the duality in a comment ("the two root
authorities must agree on the submodule case (FR-007)") and no gate covers it.

### 5. The layer chain is gated only against the top layer

`tests/architectural/test_layer_rules.py` forbids kernel→{charter, specify_cli},
charter→specify_cli and glossary→specify_cli. Nothing forbids kernel→{glossary, runtime,
mission_runtime}, charter→{glossary, runtime, mission_runtime}, or sibling edges. Zero such imports
exist today, so this is a latent gate gap rather than live rot.

### 6. Ledgers ratchet breadth, not import-site mass

The `runtime` inversion ledger is capped at 22 subpackages and `mission_runtime` at 10; measured
live mass is ~105 and ~88 import lines respectively. A new import site inside an already-ledgered
subpackage passes green.

### 7. The activation facade reacharound ledger is 231 rows

`tests/architectural/_baselines.yaml` (`boundary_baseline: 231`) drains roughly one row a week
against a 4.0.0 GA target (epic #6099); `runtime/next` alone holds ~14 rows. Bulk-draining by
consumer cluster is the only realistic path.

### 8. `mission_runtime/resolution.py` is a god-module

3,307 lines and 62 functions: more than half of its layer. It mixes topology, owned-checkout
context, status-surface resolution, WP resolution, placement assembly, branch naming and
issue-matrix probing, and carries most of the ledgered upward imports. The package root surface is
pinned by `test_mission_runtime_surface.py`, so an internal split is mechanically contained.

### 9. `acceptance/__init__.py` is a 2,117-line residual

A partial decomposition left the executor, dirty-gate, encoding recovery and WP iteration in the
package `__init__` (plus a `__getattr__` lazy surface). Package inits are interfaces, not logic
homes.

### 10. Duplicated canonical constants

`_CONSOLIDATED_CONTENT_ABSENT_CODE` is defined three times (`mission_runtime/resolution.py:244`,
`coordination/write_seam.py:177`, `cli/commands/safe_commit_cmd.py:93`) and both mirrors match on
the literal, so a rename silently breaks the cross-layer match. `status.events.jsonl` is redefined
13 times beside the canonical `EVENTS_FILENAME` in `status/store.py:50`.

### 11. Alias shims and broad catches

34 pure forwarding shims, including four local wrappers around one `coord_mission_dir_name` seam.
832 broad `except Exception` handlers, of which the actionable subset is the read-path
catch-and-return-default shape (for example `task_metadata_validation.py`), where the failure reason
is discarded while the caller branches on the flattened result.

### 12. No module-length gate

`consolidation/reconciliation.py` (3,875 lines) is cohesive but oversized;
`cli/commands/agent/workflow.py` + `workflow_executor.py` is a 5,255-line command pair. The existing
`test_module_length_agreement.py` is about CI shard-timing lists, not code size.

## Rejected

- **Make `sonar-pr` blocking.** Contradicts the documented "reported, not required" decision; the
  `needs:` set-equality assertion in `ci-aggregate.yml` exists precisely to stop silent widening
  onto the merge path.
- **"CI timeouts are hardcoded rather than derived."** The 58-minute module budget is not the
  constraint: the worst module measures 31 minutes in total, and shards have run 23 minutes.
- **Per-test durations said to come from `ci-shard-timings.json`.** That file stores an unnamed
  duration list per module, not per-test names; the attributions were unverifiable and are omitted.

## Remediation scope, ordered

1. **Shrink-only ratchet for the `ruff.toml` C901 exemptions**, then convert whole-file exemptions
   to per-function `# noqa: C901` with an inline rationale as each file is fixed.
2. **Close the layer-chain direction gaps** (four missing `LayerRule` pairs; they land green today).
3. **Hosted-surface docs cutover**: correct the context diagram, deprecate
   `zeitgeist-session-identity.md`, fix the three `index.md` rows.
4. **Single repo-root authority**: delegate one resolver to the other behind a thin adapter that
   preserves the legacy error surface.
5. **Unify the duplicated constants**, then add ledger *mass* caps, then split
   `mission_runtime/resolution.py` and thin `acceptance/__init__.py` as WP-sized slices.

Items deliberately not proposed: splitting `consolidation/reconciliation.py` (cohesive,
safety-critical, owned by its mission) and touching migration files that carry content-hash
immutability.
