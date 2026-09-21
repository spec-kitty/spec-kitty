# Contract: registration path-update (#4834) — independent correctness fix

> **Scope change (post-plan squad):** the filename **migration/self-heal was dropped** (go-forward only). Existing SCREAMING-filename repos validate green via the hybrid manifest-driven validator (see `bundle-validate-contract.md`), with authored files **untouched** — so `_registration_records` performs **no rename**, and the registration module's "never mutate authored source" invariant (C-004) is preserved. This contract therefore covers only the #4834 path-update fix, retained as a standalone latent-bug fix.

## Path-update on drift (#4834 / FR-007)
- `_registration_records` (`src/charter/activation/project_registration.py:195`) early-`continue`s when `previous and previous.content_hash == content_hash and (root/previous.provenance_path).is_file()`, skipping the manifest-entry rebuild at ~L216 entirely.
- **New rule**: even when the content hash is unchanged, the manifest entry is re-written when `previous.path != resolved_path` OR `previous.provenance_path != resolved_provenance_path`.
- **Behavior**: if an artifact's resolved path or provenance path drifts on unchanged content, the manifest is corrected in a single registration pass — no sidecar deletion, no half-stale entry that would make `verify_manifest` raise forever.
- **`slug` reuse caveat** (squad MEDIUM→HIGH): where the code reuses `previous.slug` for an existing entry, it must reconcile against `slug_for(kind, id)` and not perpetuate a legacy non-canonical slug. Under today's data this is benign (the engine has always kebab'd directive slugs), but the reconciliation is stated so a future non-canonical manifest slug cannot silently survive.

## Test (red-first)
- Seed a manifest entry whose `path`/`provenance_path` differs from the current resolved values on an artifact with unchanged content; run one registration pass; assert the manifest entry is updated (not skipped by the early-`continue`).
- Confirm `verify_manifest` / `charter bundle validate` is green afterward, and no sidecar was deleted.

## Explicitly out of scope (dropped)
- No rename of authored artifact files. No clobber/dirty-tree/crash-atomicity migration machinery. No `activated_directives` config-stem rewrite. These were the migration's risks; dropping the migration removes them.
