# Data Model: Charter Activation Catalog Coherence (#4785)

No new persisted schema is introduced. This documents the existing charter-store entities
the mission operates on and the derived/authored boundary that the single-authority
recompile must preserve.

## Entities

### Charter store (`.kittify/charter/`)
The governance store owned by the repository-root checkout. Written only through the
charter write commands. "Established" = a compiled `charter.yaml` exists; "fresh" = no
compiled catalog yet.

### `charter.yaml`
A single YAML document with two classes of section:

| Section | Class | Owner | Recompile behavior |
|---------|-------|-------|--------------------|
| `catalog.references` | **derived** | `compile_charter` (sole authority) | fully recomputed each compile; canonical order; the mission's coherence target |
| `catalog.languages`, other `catalog.*` | derived | `compile_charter` | recomputed |
| `metadata.generated_at` | derived (timestamp) | `compile_charter` | stamped only when the catalog content changed (NFR-002) |
| `governance` | **authored** | operator | byte-identical across recompiles |
| `directives` | authored | operator | byte-identical |
| `activated_directives` (+ other `activated_*`) | authored (activation lists) | `activate`/`deactivate` config write | byte-identical during a pure recompile |
| `overrides` | authored | operator | byte-identical |

### `catalog.references[]` entry
The derived reference row. Shape (illustrative, not a new schema):

- `id` — canonical kind-qualified id, e.g. `DIRECTIVE:DIRECTIVE_001`.
- `title` — human title.
- `summary` — the directive's `intent` from the typed doctrine repository, OR the placeholder
  `"Definition unavailable in bundled doctrine."` when the id does not resolve (the F4b defect).

### Directive resolution graph
- **DRG transitive closure** (`_resolve_transitive_reference_graph` → `load_validated_graph`):
  yields the set of directive ids reachable via `requires`/`suggests` edges (built-in + project
  + org layers). This is authority α — *what ids enter the closure*.
- **Typed doctrine repository** (`build_activation_aware_doctrine_service().directives`,
  keyed by canonical `DIRECTIVE_NNN`): authority β — *what ids can produce a real summary*.
- **F4b invariant to restore**: every id α emits that has a bundled definition must resolve in
  β (via the canonical-id bridge). An id that resolves in neither is a genuine unresolved
  reference → diagnostic, not a silent placeholder row.

## Checkout topology (F3)

| Concept | Meaning | Charter-write policy |
|---------|---------|----------------------|
| Repository-root checkout / dedicated clone | The non-worktree checkout that owns the charter store | charter writes allowed |
| Linked git worktree | A `.worktrees/...` checkout whose `.git` is a pointer file | charter writes **fail closed** (non-zero + "use a repository-root checkout or dedicated clone") |

Detection: kernel `git_topology` (git-dir vs git-common-dir), cross-platform, git-absent safe.

## State transitions (activation → catalog)

```
activate <directive>
  → append id to activated_directives            (authored activation list write)
  → recompile catalog.references (DEFAULT)        (derived; via compile_charter, from_interview=False)
  → coherence guard passes

activate <directive> --no-compile
  → append id to activated_directives
  → (catalog NOT recompiled; command reports the deferral explicitly)

deactivate <directive>
  → remove id from activated_directives
  → recompile catalog.references (DEFAULT)
  → coherence guard passes
```
