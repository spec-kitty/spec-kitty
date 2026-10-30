# Data Model — events tail multi-log selector

Entities for `events-tail-multi-log-and-json-01M66F8A`. The mission adds one
value object; everything else is an existing, unchanged core entity it feeds.

## LogKind (new)

The `--log` selector's closed vocabulary — a frozen mapping from kind name to
path-resolution rule. There is exactly one registry (single canonical
authority); it lives in `src/specify_cli/cli/commands/_events_tail_logs.py`.

| Kind | Resolution rule | Scope |
|------|-----------------|-------|
| `status` (default) | `<resolved status surface dir>/status.events.jsonl` | mission (surface-resolved, topology-aware) |
| `decisions` | `<resolved status surface dir>/decisions.events.jsonl` | mission (same resolved surface as `status`) |
| `mission` | `<resolved feature_dir>/mission-events.jsonl` | mission (primary partition) |
| `run` | latest `run.events.jsonl` under `<repo_root>/.kittify/runtime/runs/*/` whose sibling `state.json` names this mission | run |
| `glossary` | `<repo_root>/.kittify/events/glossary/<mission_id>.events.jsonl` | mission (project-root keyed) |
| `ops` | `<repo_root>/kitty-ops/lifecycle.jsonl` | project |
| `canonical` | `<repo_root>/.kittify/canonical-events.jsonl` | project |

**Invariants**

- The kind set is closed (C-001): exactly these seven; anything else is a
  Typer choice usage error before any file access.
- Every rule is a join over an existing resolution seam (`ResolvedMission`,
  `resolve_surface_dir_or_typed_error`, `locate_project_root`) — the registry
  never re-derives a surface (C-002).
- `run` selection never returns a journal belonging to another mission: a
  run dir matches only if its `state.json` carries this mission's
  `mission_id` (or, for legacy rows without one, its `mission_slug`); no
  match is a typed `run_log_unavailable` refusal, not a fallback.
- Legacy tolerance: a run dir with a missing or unreadable `state.json` is
  skipped, never fatal to the scan.

**Relationships**: LogKind → `Path` (resolution output) → the unchanged core
reader entities below. LogKind is the subscriber-facing subset of the #6603
writes gate's `LOG_FAMILIES` census (a test-side writer taxonomy), not a
second census.

## Unchanged core entities (fed, not modified)

- **TailCursor** (`offset`, `content_invariant`) — resumable byte position in
  whichever log the kind resolved to. Caller-owned; unchanged.
- **PollResult** (`cursor`, `events`, `file_present`) — one poll's outcome;
  unchanged (missing project-level logs report `file_present=False`).
- **ResumeRefused** (`negative` | `out_of_range` | `misaligned` |
  `content_mismatch`) — unchanged; validated against the selected log's path.

## Output shapes (presentation, not persisted)

- **JSON mode** (`--json`): one `json.dumps(event)` line per event, including
  the reader-injected `tail_offset`/`tail_invariant` cursor keys — byte-stable
  contract for scripted subscribers.
- **Human mode** (default): one plain-`print` line per event —
  `<timestamp|at|-> <event_type|type|-> <compact sorted payload>` — with the
  cursor keys omitted and `log_truncated` signals rendered as a visible
  warning line. Deterministic (sorted keys, fixed field order).
