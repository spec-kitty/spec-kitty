# Glossary Field Guide

Reference for glossary data structures, scope mechanics, and event-sourcing behaviour.

## Seed File Schema

Each scope has a YAML seed file at `.kittify/glossaries/<scope>.yaml`.

```yaml
terms:
  - surface: <lowercase trimmed string>
    definition: <non-empty string>
    confidence: <float 0.0-1.0>    # default 1.0
    status: <active|deprecated|draft>  # default draft
```

**Validation rules:**

- `surface` is mandatory and must equal `surface.lower().strip()` (the store
  rejects non-normalized values at load time)
- `definition` is mandatory and must not be blank
- `confidence` is optional; defaults to 1.0 if omitted
- `status` is optional; defaults to `draft` if omitted or unrecognised

## Scope Hierarchy

Scopes are resolved in precedence order. When a term appears in more than one
scope, the narrowest scope wins.

| Precedence | Scope | Typical Content |
|:----------:|-------|-----------------|
| 0 (highest) | `mission_local` | Terms coined for a specific mission |
| 1 | `team_domain` | Shared vocabulary across the engineering team |
| 2 | `audience_domain` | Terms as the end user understands them |
| 3 (lowest) | `spec_kitty_core` | Spec Kitty's own canonical terminology |

**Example:** If `workspace` is defined in both `team_domain` (as "shared office")
and `spec_kitty_core` (as "git worktree directory"), the `team_domain` definition
wins during resolution because it has higher precedence.

## Status Lifecycle

```
draft  ──promote──>  active  ──retire──>  deprecated
  ^                                           │
  └───────────── re-draft ────────────────────┘
```

| Status | Included in Resolution | Appears in Event History |
|--------|:---------------------:|:------------------------:|
| `draft` | Yes (low priority) | Yes |
| `active` | Yes | Yes |
| `deprecated` | No | Yes |

- **draft**: Auto-extracted or newly created senses. They participate in
  resolution but with lower weight.
- **active**: Promoted by a human or by high-confidence extraction. These are
  the authoritative definitions.
- **deprecated**: Removed from active resolution but kept in history so that
  old event references remain valid.

## Event-Sourcing Mechanics

The glossary is event-sourced. The seed files provide the initial state, and
the event log records every mutation.

**State reconstruction flow:**

1. Load all seed files (one per scope) into an in-memory `GlossaryStore`
2. Replay events from `.kittify/events/glossary/*.events.jsonl` in file-sort
   order
3. Apply `GlossarySenseUpdated` events (add or overwrite senses)
4. Apply `GlossaryClarificationResolved` events (promote selected senses)
5. The resulting store is the current glossary state

**Key event types:**

| Event Type | Trigger | Effect |
|-----------|---------|--------|
| `GlossaryScopeActivated` | Scope loaded at runtime | Informational only |
| `GlossarySenseUpdated` | Term added or definition changed | Adds/overwrites sense in store |
| `GlossaryClarificationRequested` | Ambiguity detected during runtime | Creates a pending conflict |
| `GlossaryClarificationResolved` | Human resolves a conflict | Promotes selected sense to active |
| `SemanticCheckEvaluated` | Strictness gate runs | Records findings, may block step |

**Event log location:** `.kittify/events/glossary/<mission-id>.events.jsonl`

Each line is a self-contained JSON object with an `event_type` field. Events
are append-only; the log is never rewritten.

## Store Lookup Behaviour

`GlossaryStore.lookup(surface, scopes)` returns all matching senses across the
requested scopes, ordered by scope precedence. Callers receive a list because
a term may have multiple active senses (which constitutes an AMBIGUOUS
conflict if the usage is unqualified).

The store uses an LRU cache (up to 10,000 entries) for repeated lookups.
The cache is invalidated whenever `add_sense()` is called.

## Strictness Precedence Chain

Effective strictness is determined by a four-tier chain. The most specific
override wins:

```
global config (.kittify/config.yaml)
  └── mission override (mission.yaml)
       └── step override (step metadata)
            └── runtime override (CLI --strictness flag)
```

If no override is set at any level, the global default (`medium`) applies.

## Conflict Resolution Flow

```
Term detected in LLM output
  │
  ├─ Found in store with 1 active sense ──> No conflict
  │
  ├─ Found with 2+ active senses ──> AMBIGUOUS conflict
  │     └─ Strictness gate evaluates severity
  │           ├─ Blocked? ──> GlossaryClarificationRequested event
  │           └─ Warned? ──> SemanticCheckEvaluated event (non-blocking)
  │
  ├─ Not found ──> UNKNOWN conflict
  │     └─ Severity scored by confidence + step criticality
  │
  └─ Found but contradicted by output ──> INCONSISTENT conflict
        └─ Always LOW severity (informational)
```

## CLI Quick Reference

```bash
# List terms (human-readable table)
spec-kitty glossary list

# List terms filtered by scope and status
spec-kitty glossary list --scope team_domain --status active

# List terms as JSON
spec-kitty glossary list --json

# Show conflict history
spec-kitty glossary conflicts

# Show only unresolved conflicts
spec-kitty glossary conflicts --unresolved

# Filter conflicts by strictness and mission
spec-kitty glossary conflicts --strictness max --mission 012-docs

# Resolve a conflict interactively
spec-kitty glossary resolve <conflict-uuid>

# Resolve within a specific mission context
spec-kitty glossary resolve <conflict-uuid> --mission 012-docs
```
