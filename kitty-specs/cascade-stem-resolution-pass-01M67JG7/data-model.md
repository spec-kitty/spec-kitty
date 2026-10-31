# Data model — the cascade's bounded activation batch (#6777)

The mission adds no persisted entity. It changes one value that flows through the cascade
activation path, and the batch it is resolved in.

## `ArtifactRef` (existing, unchanged)

One cascade target: the operator kind token (`ref.kind`), the config-stem id activation
lists store (`ref.id`), and the DRG URN the walk reported (`ref.urn`). The activation loop
now reads the kind token off the ref instead of carrying it beside it.

## The target batch (new, in-memory only)

```
activated: {kind_value: [bare DRG id, ...]}      # the DRG walk's output, unchanged
        │
        ▼  _cascade_target_refs(activated, ids)     # ONE ResolutionPass, all reads
refs: [ArtifactRef(kind, config_stem, urn), ...]    # same order: sorted kind, then walk order
        │
        ▼  for ref in refs: manager.activate(...)    # the only writes
entries: [CascadeEntry(CASCADED|FAILED, ref, message?), ...]
```

Invariants the guards pin (`contracts/cascade-stem-resolution.md`):

1. Every `config_id` lookup of one cascade run receives the **same** `ResolutionPass`
   instance.
2. Every lookup completes **before** the first `manager.activate()` call.
3. The entry order (and therefore the render order) is unchanged: `sorted(activated)`, then
   each kind's walk order.

## `ResolutionPass` (existing, unchanged)

The per-pass memo of layer scans (`scans`) and artifact id reads (`ids`) in
`charter.activation.kind_vocabulary`. Its documented lifetime rule — a pass never spans a
write to the files it reads — is why the batch is resolved before the first activation
write rather than threaded through the loop.

## Ledger and config surfaces (unchanged)

`.kittify/config.yaml`, the activation ledger and the deny lists receive exactly the writes
they received before; the only difference is that the identity lookups feeding them are
deduplicated. Nothing new is persisted, so no migration or schema change is involved.
