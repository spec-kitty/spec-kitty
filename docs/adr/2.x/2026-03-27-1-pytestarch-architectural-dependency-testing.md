---
title: 'ADR: Architectural Dependency Testing & Graph Infrastructure'
description: Adopts PyTestArch so the kernel, doctrine, charter, and specify_cli dependency direction is executable, and a violating import fails a test instead of lingering.
status: Accepted
doc_status: active
kind: ADR
date: '2026-03-27'
---

## Context

The 2.x architecture defines four peer containers with a strict dependency direction:

```
kernel          (zero outgoing dependencies — the true root)
  ^
doctrine        (depends on kernel only)
  ^
charter    (depends on doctrine + kernel, may import specify_cli.runtime)
  ^
specify_cli     (depends on all three)
```

These invariants are documented in `architecture/2.x/00_landscape/` and enforced by convention. However, violations can be introduced silently:

- **Lazy imports** inside method bodies (e.g., `from specify_cli.runtime.resolver import resolve` inside a `doctrine` class method) pass mypy, pass import-time checks, but violate the boundary at runtime. This was discovered during the mission 058 architectural review (AR-1).
- **Accidental imports** during refactoring — a developer moving code between packages may inadvertently introduce a backward dependency.
- **Transitive violations** — module A imports module B which imports module C, creating an indirect dependency chain that's hard to spot in code review.

There is no automated CI gate that catches these violations today.

## Decision

Adopt **PyTestArch** (v4.0.1, Apache 2.0, [github.com/zyskarch/pytestarch](https://github.com/zyskarch/pytestarch)) as a dev dependency for architectural dependency testing.

### Why PyTestArch

| Criterion | Assessment |
|-----------|-----------|
| **API fit** | `LayeredArchitecture` + `LayerRule` maps 1:1 to our C4 containers |
| **Detection method** | AST parsing — sees ALL import statements including lazy/conditional imports inside method bodies |
| **Granularity** | Sub-module rules express "charter may import `specify_cli.runtime` but not `specify_cli.cli`" |
| **pytest native** | Session-scoped fixture, `assert_applies()`, standard pytest assertions |
| **Performance** | One-time AST parse per session; graph traversal per rule. ~500 source files is well within bounds |
| **Maintenance** | Active (255 commits, 27 releases, 153 stars). Python 3.9-3.13 supported |
| **License** | Apache 2.0 — compatible with our MIT license |

### What it catches

- Direct imports across package boundaries (both module-level and lazy)
- Transitive dependency violations via graph traversal
- Regressions introduced by refactoring

### What it does not catch

- `importlib.import_module()` dynamic imports (rare in our codebase)
- Non-Python dependency references (YAML cross-references, etc.)
- Circular dependency cycles (no built-in API; addressed by networkx — see Decision 2 below)

### Alternatives considered

| Alternative | Why not |
|-------------|---------|
| Manual `grep` in CI | Fragile, misses transitive violations, no graph semantics |
| `import-linter` | Less expressive rule API, no layer abstraction, less active maintenance |
| Custom AST walker | Maintenance burden, reinvents what PyTestArch already provides |
| mypy plugin | mypy checks types not architectural boundaries; wrong tool for the job |

## Implementation

### Test structure

```
tests/
  architectural/
    conftest.py          # session fixtures: evaluable, landscape
    test_layer_rules.py  # invariant tests
```

### Core invariants encoded

1. **kernel imports nothing** from doctrine, charter, or specify_cli
2. **doctrine imports only kernel** — never specify_cli or charter
3. **charter does not import specify_cli** (except `specify_cli.runtime`, which is permitted)
4. **No reverse dependencies** — specify_cli does not import from itself through doctrine or charter

### CI placement

Tests are marked `@pytest.mark.architectural` and run at the same priority as kernel tests: fast, every PR, fail-fast. A single violation blocks the PR.

## Decision 2: networkx for Graph Infrastructure Consolidation

### Context

The codebase contains **4 independent graph implementations**, each hand-rolling the same fundamental algorithms:

| Domain | Location | Algorithms | Lines |
|--------|----------|------------|-------|
| WP dependencies | `specify_cli/core/dependency_graph.py` | DFS 3-color cycle detection, Kahn's topo sort | ~170 |
| Doctrine references | `charter/reference_resolver.py` | DFS path-tracking cycle detection | ~90 |
| Event causation | `specify_cli/spec_kitty_events/topology.py` | Kahn's topo sort + cycle detection | ~60 |
| Worktree stacking | `specify_cli/core/worktree_topology.py` | Delegates to WP dependency graph | ~80 |

All four domains model directed acyclic graphs. All four need cycle detection. Three need topological ordering. None share code.

Additionally, PyTestArch (Decision 1) explicitly lacks cycle detection — a gap networkx fills.

### Decision

Adopt **networkx** (BSD license, [github.com/networkx/networkx](https://github.com/networkx/networkx)) as a runtime dependency at the **kernel** level (zero domain-specific dependencies).

### Why networkx

| Criterion | Assessment |
|-----------|-----------|
| **API fit** | `DiGraph` maps directly to all 4 existing adjacency-list graphs |
| **Algorithm coverage** | `topological_sort`, `topological_generations`, `simple_cycles`, `descendants`, `ancestors`, `dag_longest_path` — all currently hand-rolled or missing |
| **Parallel wave scheduling** | `topological_generations()` yields groups of independent nodes — directly models WP parallel execution waves |
| **Impact analysis** | `ancestors()` / `descendants()` enable "what depends on this?" queries for doctrine artifacts and glossary terms |
| **Visualization** | `nx.drawing.nx_pydot.write_dot()` exports to Graphviz for debugging doctrine DAGs and dependency trees |
| **Maturity** | 11k+ GitHub stars, NumFOCUS sponsored, Python 3.10-3.13, BSD license |
| **Size** | ~4MB installed, pure Python (no C extensions required) |

### What it consolidates

The 4 existing implementations (~400 lines total) reduce to domain-specific wrappers around `nx.DiGraph`:

```python
# Before: 170 lines of Kahn's + DFS in dependency_graph.py
# After:
G = nx.DiGraph(adjacency)
order = list(nx.topological_sort(G))
cycles = list(nx.simple_cycles(G))
waves = list(nx.topological_generations(G))  # NEW: parallel scheduling
```

Each domain retains its own error types (`MergeOrderError`, `DoctrineResolutionCycleError`, `CyclicDependencyError`) wrapping networkx exceptions.

### What it enables (not currently possible)

- **WP parallel wave scheduling**: `topological_generations()` computes independent groups directly — currently inferred manually from the dependency summary
- **Doctrine blast radius**: "If I change this tactic, which directives are affected?" — `nx.ancestors(G, tactic_id)`
- **Glossary orphan detection**: Terms with in-degree 0 (referenced by nothing)
- **Critical path analysis**: `nx.dag_longest_path(G)` for WP dependency chains — identifies the bottleneck sequence
- **Subgraph extraction**: Isolate a feature's dependency neighborhood for focused analysis

### Alternatives considered

| Alternative | Why not |
|-------------|---------|
| Keep hand-rolled implementations | 4 independent copies of the same algorithms; no path to wave scheduling or impact analysis |
| `igraph` | C extension dependency, harder to install, overkill for our graph sizes |
| `graphlib` (stdlib) | Python 3.9+ `TopologicalSorter` only — no cycle detection, no descendants/ancestors, no visualization |

### Rollout

1. **Phase 1**: Add `networkx` as a runtime dependency. Refactor `dependency_graph.py` to use `nx.DiGraph`. This is the lowest-risk entry point — WP dependency graphs are small and well-tested.
2. **Phase 2**: Migrate doctrine `reference_resolver.py` and event `topology.py`. Add visualization export for debugging.
3. **Phase 3**: Expose `topological_generations()` in the implement workflow for automated parallel wave scheduling.

Phase 1 can be scoped as a WP within mission 058 or as a standalone follow-up mission.

## Consequences

### Decision 1 (PyTestArch)

**Positive**:
- Package boundary violations are caught before merge, not during architectural review
- New contributors get immediate feedback on dependency direction
- The invariants are executable documentation, not just prose in `00_landscape/`
- Session-scoped fixture means near-zero overhead added to test suite

**Negative**:
- One new dev dependency (`pytestarch`)
- AST parsing treats lazy imports the same as module-level imports — this is intentional for our use case but means a legitimate lazy import pattern (if one were ever needed) would require an explicit exclusion in the test

**Neutral**:
- The evaluable architecture is rebuilt per test session. If the codebase grows significantly (>5000 files), the session fixture may need `level_limit` tuning.

### Decision 2 (networkx)

**Positive**:
- Eliminates ~400 lines of duplicated graph algorithms across 4 modules
- Unlocks parallel wave scheduling, impact analysis, and visualization — none currently possible
- Battle-tested algorithms replace hand-rolled implementations
- kernel-level placement means all containers can use it without violating dependency direction

**Negative**:
- One new runtime dependency (~4MB)
- Developers must learn networkx API (well-documented, widely known)

**Neutral**:
- Existing domain error types and public APIs remain unchanged — only internal implementations change
- Graph sizes in spec-kitty are small (typically <50 nodes) — networkx performance characteristics are irrelevant at this scale
