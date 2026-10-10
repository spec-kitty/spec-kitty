# Research — One org-pack chain authority (#6006)

Grounded by two profile-loaded opus lenses (paula-patterns inventory,
architect-alphonso architecture) and two post-spec lenses (analyst-annie,
reviewer-renata). Every file:line below verified on the stacked base
`kitty/org-pack-chain-authority-stack`.

## Decision 1 — Authority shape and home

- **Decision**: `resolve_pack_chain(repo_root, *, strict: bool)` in `src/charter/activation/layer_roots.py`. `strict=True` raises on a declared-but-missing pack (today's `require_declared_org_roots` logic + remedy); `strict=False` returns the existing-filtered chain (today's `resolve_existing_org_roots`). Last-declared-wins ordering.
- **Rationale**: `layer_roots.py` is already the charter-tier layer-root seam and already hosts `resolve_org_root_chain`; collapsing the five spellings behind one posture flag satisfies both "one authority" (FR-001) and "fail-closed missing pack" (FR-007) over one registry read.
- **Alternatives considered**: two separate functions (strict/lenient) — rejected, duplicates the registry read and splits the authority; keeping `resolve_org_root_chain` as a second entry — rejected (parallel authority; reviewer-renata BLOCKER 2). `resolve_org_root_chain` is **absorbed** into `resolve_pack_chain`, zero callers remain outside the authority module.

## Decision 2 — Do NOT widen `resolve_layer_roots`'s dict

- **Decision**: `resolve_layer_roots` keeps returning `dict[str, Path]` with a single `roots["org"]` (pack 1). The chain travels as a separate `list[Path]`.
- **Rationale**: `pack_manager._scan_layer_dirs` and `kind_vocabulary._layer_scan_dirs` unconditionally do `root / ...` on each dict value; a `list[Path]` there TypeErrors or silently resolves a non-existent dir (NFR-002 silent-success). The separate-`list[Path]` convention already exists (`_org_scan_dirs`, `preset_application`, `effective_set`). This deliberately does not take the issue's literal "widen `layer_roots`" wording — the architect ruling.
- **Alternatives considered**: `dict[str, list[Path]]` parallel map — rejected (only the org layer is ever multi-valued; over-general; still rewrites every `root / ...` site).

## Decision 3 — Retire `_activate_cascade_target` by widening `ActiveCharterManager`

- **Decision**: Add `org_root_chain: list[Path] | None = None` to `activate`/`list_available`/`list_available_detailed`/`_scan_layer_dirs`; emit one ORG pair per chain root last-declared-first; fall back to the single slot when None. Collapse `_activate_cascade_target` to one `manager.activate(...)`.
- **Rationale**: the retry loop exists only because the availability scan saw pack 1; pushing the chain into the scan removes the reason for the loop. `ActiveCharterManager` is stateless, so the chain enters via method params, not a constructor.
- **Alternatives considered**: keep the loop (independent-scope option) — rejected by operator (stack ruling: retire it on top of #6005).

## Decision 4 — Fail-closed split (strict vs lenient)

- **Decision**: strict posture on decision surfaces — `charter activate`/`deactivate` availability scan, `load_requirement_kinds`, `effective_set._declared_org_roots`. Lenient posture (silent degrade) on `charter list` display, `effective_set._readable_roots`/`_fallback_ids`, and the runtime hot path `resolve_org_dirs`.
- **Rationale**: a missing pack on a governance decision must be loud (#4984); forcing the hot path/display closed would regress NFR-002/NFR-004 silent-degrade behavior. "Declared-but-missing" means declared-and-absent, never "none declared" (edge case: zero packs → no raise in either posture).
- **Lenient surfaces are re-pointed onto `resolve_pack_chain(strict=False)`** (not left calling primitives), so the empty allowlist stays honest (reviewer-renata BLOCKER 1).

## Decision 5 — Empty-allowlist gate discriminator (module-ownership)

- **Decision**: AST census mirroring `tests/architectural/test_remote_contact_owner.py`. Outside `layer_roots.py` (authority) and `org_pack_config.py` (primitives' own module), forbid calling `resolve_org_roots`/`resolve_existing_org_roots`/`require_declared_org_roots`/`resolve_org_root_chain` or iterating `load_pack_registry().packs` to assemble roots. Empty allowlist; file-count floor + planted-violation + owner-bypass controls.
- **Rationale**: a symbol-name blanket would false-positive on the legitimate single-root `resolve_layer_roots` (which lives in the authority module, so module-ownership exempts it); a too-narrow name-only gate misses `effective_set`/`preset_application` assembly (analyst-annie, reviewer-renata). Module-ownership is AST-checkable and matches the charter's empty-allowlist invariant.
- **Note**: FR-002/FR-005 carry their OWN behavioural/structural controls — the gate proves "no foreign assembly", not "this caller reads the full chain" or "no `[0]` index survives".

## Decision 6 — Loader seam mirrors `load_manifest`, with two documented divergences

- **Decision**: `requirement_kinds.py` (frozen models, `extra="forbid"`) + `load_requirement_kinds` beside `load_manifest`, mirroring `resolve_org_expected_artifacts` (last-matching-file-wins, whole-file, `MalformedManifestError`/schema → `ManifestSchemaError`-shaped).
- **Divergence A**: `load_manifest` has **no project tier**; the loader adds `.kittify/charter-packs/missions/<type>/requirement-kinds.yaml`, project wins over org/built-in (#5956 design). (Corrected from the pre-cutover `.kittify/doctrine/` path in #5956's design: that directory is retired and refused by the `LEGACY_CHARTER_STATE` gate, FR-011.)
- **Divergence B**: `load_manifest` resolves the org chain through the lenient `resolve_existing_org_roots`; the loader resolves through the **strict** `resolve_pack_chain` so a declared-but-missing pack refuses (FR-007/FR-011).
- **Rationale**: honors #5956's whole-file-override + fail-closed design and point (5)'s fail-closed intent; divergences are deliberate and recorded so an implementer does not "fix" them back to the `load_manifest` precedent.
- **Alternatives considered**: field-merge override — rejected (D2 of #5956: whole-file). Lenient org chain — rejected (fails the #4984 seam for the loader).

## Decision 7 — `_org_scan_dirs` flat-wins precedence is preserved

- **Decision**: `resolve_pack_chain` owns root SELECTION and ORDER only. `kind_vocabulary._org_scan_dirs`'s flat-layout-wins-regardless-of-root-order precedence (pinned by `tests/charter/test_kind_vocabulary_scan_roots.py`) is unchanged (NFR-005).
- **Rationale**: the two rules are orthogonal (pack ordinal vs flat-vs-legacy layout). On a mixed-layout cross-pack collision the flat file still wins; last-declared-wins governs same-layout collisions and the simple-override surfaces (list, `--include`/context body, loader). Flagged by analyst-annie as a latent contradiction; resolved by scoping.

## Supply-chain security

N/A — this mission adds/upgrades/removes no dependency. No adversarial supply-chain evidence pass required (advisory posture, DIRECTIVE_051).

## Contracts

No external HTTP/GraphQL/webhook interface. The new public surfaces are an
internal Python function API (`resolve_pack_chain`, `load_requirement_kinds`) and
a YAML file schema (`requirement-kinds.yaml`), both captured in
[data-model.md](./data-model.md). `meta.json` sets `contracts: "none"` with a
rationale so strict `accept` waives the `contracts/` requirement.
