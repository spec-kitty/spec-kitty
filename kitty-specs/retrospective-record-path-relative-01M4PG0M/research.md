# Research: Repo-relative retrospective record_path (#5868)

## Decision: emit `canonical_path.relative_to(repo_root).as_posix()`

- **Decision**: In `emit_captured._build`, persist `record_path` as the
  repository-relative POSIX path of `canonical_path` relative to `repo_root`,
  rather than `str(canonical_path)` (absolute).
- **Rationale**: `canonical_path = resolve_retrospective_home(repo_root, slug) /
  RETROSPECTIVE_FILENAME`. `resolve_retrospective_home` composes the durable home
  via the module-private leaf `_compose_primary_feature_dir(repo_root, slug)`,
  which joins `KITTY_SPECS_DIR` directly onto `repo_root` (no `resolve()`, no
  symlink normalization). Therefore `canonical_path` is *always* a descendant of
  the same `repo_root` object, and `Path.relative_to(repo_root)` is total and
  cannot raise for this input. `.as_posix()` gives git-style `/` separators so
  the committed value is identical across OSes.
- **Alternatives considered**:
  - `os.path.relpath` — tolerates non-descendant paths by emitting `../`
    segments, which would *reintroduce* leakage risk and mask a real bug if the
    home resolver ever changed; rejected in favour of the stricter `relative_to`
    that fails loudly on a genuine invariant break.
  - Kernel `GitPath` abstraction — a repo-relative path type, but it parses from
    an already-relative string; it adds no value when we are converting a known
    descendant `Path`, and would pull a kernel dependency into this leaf for no
    behavioural gain. Rejected (keep the change minimal).
  - Backfilling existing committed absolute paths — out of scope (Decision
    `specify.scope.migration`, forward-only); append-only logs are immutable
    history and the sole known occurrence was hand-scrubbed on #5856.

## Grounding: no consumer depends on an absolute `record_path`

- `tests/retrospective/test_gate_decision.py` already exercises relative
  `record_path` values (`.kittify/missions/test/retrospective.yaml`).
- `tests/retrospective/test_events.py::test_retrospective_captured_to_dict`
  already constructs the dataclass with a *relative* path — but no test asserts
  the value `emit_captured` itself computes, which is why the absolute-path bug
  went uncaught. This mission adds exactly that assertion, red-first.
- The gate/reducer read paths resolve `record_path` for display/existence; none
  require it to be absolute.

## Contract alignment

- The retrospective-events contract types `record_path` as a `string`
  ("Absolute (or repo-relative) path"); emitting the repo-relative form is
  contract-conformant.
- The separate Mission-Status Read-API contract (`mission-status-contract-v1`)
  forbids the property on *its* surface (a leak-pattern guard). That is a
  different surface (the read API output, not the event log) and is untouched;
  no change needed there.
