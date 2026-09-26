# Data Model

This is a correctness/preservation mission; the "data model" is the small set of domain concepts the
fixed sites reason about, not a persistence schema.

## Entities

### ProjectAsset (`.kittify/**`)
- **Represents**: an operator-visible file under a project's `.kittify/` tree.
- **Ownership states**: `identical-default` (byte-equal to shipped package default), `customised`
  (shipped counterpart exists but bytes differ — includes both team edits and *outdated* defaults),
  `user-created` (no package counterpart).
- **Rule**: only `identical-default` is safely removable. `customised` and `user-created` are preserved
  or archived. Ownership is decided by content provers (`ManifestProver`, `CanonicalContentProver`),
  never by name/path/basename.
- **Disposition (post-fix)**: `identical` → remove; `customised`/`unprovable` → preserve/archive
  (reported); `user-created` → move to `overrides/` (existing behaviour).

### OrgPack (git-sourced `local_path`)
- **Represents**: a doctrine/charter pack directory materialised from a git remote, possibly outside
  the repository, possibly hand-authored, possibly with local commits ahead of upstream.
- **States**: `absent` (no dir), `foreign` (non-empty, not a clone of `url`), `clone-of-url` (a valid
  clone), `clone-dirty` (valid clone with uncommitted/committed local edits).
- **Rules**:
  - `absent` → first-install may create it.
  - `foreign` → refuse (never rmtree); operator content preserved.
  - `clone-of-url` → update path; reset resolves `origin/<ref>`.
  - `clone-dirty` → back up (reported) before any reset; never silent discard.

### OwnershipVerdict (existing, `asset_preservation`)
- Returned by `guard_destructive_removal`; carries proven/unproven + a `diagnostic` naming any
  preserved/backed-up path. The command surfaces this instead of a raw filesystem outcome.

## State transitions (OrgPack, `charter fetch`)

```
absent ──clone ok──▶ clone-of-url
absent ──clone fail──▶ absent            (temp removed; nothing user-authored existed)
foreign ──fetch──▶ foreign (REFUSED, preserved)      [FR-003]
clone-of-url ──fetch ok, ref origin/<ref>──▶ advanced clone-of-url   [FR-004 sub-bug B]
clone-dirty ──fetch──▶ backed-up then advanced        [FR-004 sub-bug A]
```

## Non-entities (explicitly out of scope)
- `.kittify/missions/**` counterpart resolution (deferred).
- Text/encoding repair of asset contents (encoding cluster, deferred).
