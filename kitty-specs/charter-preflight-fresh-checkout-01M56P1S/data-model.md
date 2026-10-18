# Data Model: Fix charter preflight blocking `next` on a fresh checkout

This is a behaviour fix over existing data structures; no new persisted entities are introduced.
The relevant entities and the one new in-memory decision are:

## Entities (existing)

### SynthesisManifest (`.kittify/charter/synthesis-manifest.yaml`)
- `bundle_content_hash: str | None` — the stamped content-identity hash the freshness reader compares against. **This is the field that drifts.**
- `built_in_only: bool` — when `true`, short-circuits the hash comparison (PASS). The drift case has `false`.
- `artifacts: list[ManifestArtifactEntry]` — each with `kind`, `slug`, `path`, `provenance_path`, `content_hash` (SHA-256 of the on-disk artifact bytes).
- `manifest_hash: str` — self-hash recomputed by `finalize_manifest`.
- **Invariant (target state)**: after any `charter.yaml` write, `bundle_content_hash == compute_bundle_content_hash(repo)`.

### Charter bundle (`.kittify/charter/charter.yaml`)
- The single file hashed by `charter.bundle.compute_bundle_content_hash` (`BUNDLE_CONTENT_HASH_FILES = ("charter.yaml",)`). Authored + derived charter content.

### FreshnessSubState `synthesized_drg` (`freshness/computer.py`)
- `state ∈ {fresh, built_in_only, stale, missing, invalid}`. PASS states: `{fresh, skipped, built_in_only}`.
- Produced by `_synthesized_drg_graph_state`: `stale` iff `stored_hash is None or current_hash is None or stored_hash != current_hash` (when graph exists and `built_in_only` is false).

## New in-memory decision: the safe-heal verdict (IC-01)

A pure predicate computed in the preflight layer (no new persisted field):

```
heal_is_safe(repo, manifest) :=
    synthesized_drg.state == "stale"
    AND manifest is not None
    AND manifest.bundle_content_hash is not None          # not a missing-file None
    AND compute_bundle_content_hash(repo) is not None      # charter.yaml present & readable
    AND manifest.bundle_content_hash != compute_bundle_content_hash(repo)   # stamp lags
    AND manifest.verify(repo) succeeds                      # derived artifacts consistent (no ManifestIntegrityError)
```

- **True** ⇒ re-stamp `bundle_content_hash` to the recompute via `finalize_manifest`, persist atomically, treat `synthesized_drg` as `fresh` for this run → preflight passes.
- **False** (including `verify()` raising, a missing-file `None`, or `built_in_only`/`missing`/`invalid`
  states) ⇒ **no heal**; existing behaviour stands (actionable `blocked_reason`, never greenwashed).

### State transition

```
stale (stamp lags, verify OK) --[heal, allow_heal=True]--> fresh (re-stamped)
stale (verify raises)         --[no heal]---------------->  stale (actionable block)
stale (allow_heal=False, query)--[no heal, warn-only]---->  stale (continue, read-only)
```

## Validation rules

- The re-stamp changes **only** `bundle_content_hash` (and the derived `manifest_hash`); authored
  content and every `ManifestArtifactEntry` are byte-preserved (NFR-002).
- The recompute uses the single `compute_bundle_content_hash` authority (C-002) — no second recipe.
- Idempotent: re-running the heal on an already-stamped manifest is a no-op (NFR-003).
