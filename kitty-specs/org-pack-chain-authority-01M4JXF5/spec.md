# Mission Specification: One org-pack chain authority

**Mission Branch**: `org-pack-chain-authority-01M4JXF5`
**Created**: 2026-10-10
**Status**: Draft
**Input**: Issue #6006 (stacked on PR #6005), with the #5956 loader seam included per operator ruling.

## Context & Problem

A project may declare more than one organization charter pack under
`charter_packs.org.packs`. When it does, the charter surfaces disagree about
which packs they read: several read **pack #1 only**, so an artifact, template,
or mission declaration that lives in a later pack is invisible, or a colliding
id renders the wrong pack's body. The chain is computed in at least five
different spellings today (`resolve_org_roots`, `resolve_existing_org_roots`,
`resolve_org_dirs`, `require_declared_org_roots`, `resolve_org_root_chain`),
and the pack-1-only readers each re-decide the rule locally — a parallel-authority
defect. PR #6005 (stacked beneath this mission) fixed `charter context --include`
and `charter activate` by extending a per-pack **retry loop**
(`_activate_cascade_target`); this mission generalizes the fix into **one chain
authority** that every surface reads, retires the retry loop, and makes a
declared-but-missing pack fail loudly instead of silently vanishing.

This is the foundation the #6005 landing review calls for, and the seam that
#4984 (missing-pack fails open) and #5956 (Mission-type requirement-kind
declarations resolved through charter) build on.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - A later org pack is a first-class citizen everywhere (Priority: P1)

An operator layers two organization charter packs (a base `acme-base`, then a
team overlay `acme-web`). An artifact — a directive, a template, or a mission —
that exists only in the second pack must behave identically to one in the first
pack: it appears in listings, it activates, its body renders, and a colliding id
resolves to the later pack (last-declared-wins).

**Why this priority**: This is the whole point of the mission and the user-visible
defect in #6006/#5779. Without it, multi-pack org governance is a trap.

**Independent Test**: In a repo with two org packs, run `charter list --all` and
confirm a pack-2-only artifact is listed; `charter activate` it and confirm
success; confirm a colliding id renders pack-2's body. Each is observable through
the CLI over a two-pack fixture.

**Acceptance Scenarios**:

1. **Given** two org packs where `c-directive` exists only in pack 2, **When** the operator runs `charter list --all`, **Then** `c-directive` appears in the org tier (it did not before this mission).
2. **Given** the same two packs, **When** the operator runs `charter activate directive c-directive`, **Then** it succeeds via a single chain-aware availability scan (no per-pack retry).
3. **Given** a same-layout directive id declared in both packs, **When** a simple-override surface resolves it, **Then** the later pack's body wins (last-declared-wins). This verdict is pinned by a collision fixture on list, `--include`, context (body rendering), and the loader; activate/deactivate resolve availability across the full chain (presence, not body), so a pack-2-only id is activatable. The mixed-layout kind-vocabulary tiebreak is governed by NFR-005, not this scenario.

---

### User Story 2 - One authority, enforced (Priority: P1)

A maintainer must be able to trust that exactly one function decides the org-pack
chain, so the next surface added cannot quietly reintroduce the pack-1-only bug.

**Why this priority**: The parallel-authority defect is the root cause; a single
canonical authority plus an enforcing gate is what prevents the next recurrence
(charter Governing Principle: single canonical authority).

**Independent Test**: An architectural gate scans the source tree; a planted
chain-assembly call outside the authority turns it red, and removing the plant
turns it green. The allowlist is empty.

**Acceptance Scenarios**:

1. **Given** the chain authority `resolve_pack_chain()`, **When** any module other than the authority assembles a chain (iterates the pack registry, or calls a registry primitive to build a chain), **Then** the architectural gate fails and names the offending site.
2. **Given** the gate, **When** the mission ships, **Then** its allowlist has zero entries and no shrink-only ratchet (Standing Order #5 / ADR 2026-09-30-1).

---

### User Story 3 - A declared-but-missing pack fails loudly where it matters (Priority: P2)

An operator declares an org pack that was never fetched (a stale `local_path`).
On the surfaces that make governance decisions (activate/deactivate, the
requirement-kinds loader), that must be a loud, actionable refusal — not a silent
drop that makes the artifact look "Unknown". On best-effort display and the
runtime resolution hot path, it must still degrade silently as it does today.

**Why this priority**: This is the #4984 seam; fail-open on a missing pack is a
reliability defect, but over-strictness on the lenient hot paths would regress
runtime behavior (NFR-002 silent-degrade contract).

**Independent Test**: Over a fixture with one declared-but-absent pack, the strict
authority posture raises a message naming the pack and the `spec-kitty charter
fetch` remedy; the lenient posture returns the existing roots with no raise. Both
are exercised from one shared fixture.

**Acceptance Scenarios**:

1. **Given** a declared pack whose `local_path` does not exist, **When** `charter activate` or the requirement-kinds loader resolves the chain (strict posture), **Then** it refuses, naming the unfetched pack and the fetch remedy.
2. **Given** the same fixture, **When** `charter list` display, a best-effort scan, or runtime template resolution resolves the chain (lenient posture), **Then** it drops the missing pack silently (byte-identical to today).

### Edge Cases

- **No org packs configured**: the chain is empty; every surface behaves exactly as with zero packs today (no raise in either posture — "declared-but-missing" means declared-and-absent, not "none declared").
- **Colliding id across three packs (same layout)**: last-declared-wins resolves to the highest-ordinal pack that declares it, on the simple-override surfaces (list, `--include`/context body, loader).
- **Colliding id across packs with mixed layout (flat vs legacy)**: on the kind-vocabulary resolution path (`_org_scan_dirs`), the existing flat-layout-wins-regardless-of-root-order rule still governs (NFR-005); `resolve_pack_chain` decides only root order, not the flat-vs-legacy tiebreak. This mission does not change that rule.
- **`resolve_layer_roots["org"]` single-Path consumers** (`_scan_layer_dirs`, `kind_vocabulary._layer_scan_dirs`): the dict contract is deliberately **not** widened; the chain travels as a separate `list[Path]`, so these call sites stay byte-identical.
- **Requirement-kinds file present but unparseable / schema-invalid**: the loader refuses (fail-closed), never silently falls through to the built-in default.
- **Requirement-kinds file absent at every tier**: the loader returns the built-in default kind set for the mission type (absence is not a refusal).
- **Project-tier override present**: the project `requirement-kinds.yaml` wins over org and built-in (whole-file, not field-merge).

## Requirements *(mandatory)*

### Functional Requirements

| ID | Title | User Story | Priority | Status | Delivery | No-op passable? |
|----|-------|------------|----------|--------|----------|-----------------|
| FR-001 | Single chain authority | As a maintainer, I want one `resolve_pack_chain(repo_root, *, strict)` in `charter/activation/layer_roots.py` to be the sole producer of the ordered, existing org-pack chain (last-declared-wins), exposing a strict and a lenient posture, so every surface reads the same chain. | High | Open | [build] | no — new function; test asserts a two-pack fixture yields both roots in declaration order under lenient, and a raise under strict for a missing pack (positive+negative on one fixture) |
| FR-002 | Chain-assembly callers migrated (charter surfaces) | As a maintainer, I want every chain-deriving caller **within the charter surfaces** (`src/charter/**` and `src/specify_cli/cli/commands/charter/**`) routed through `resolve_pack_chain()`, so no charter-surface module re-derives the chain. This covers the named bug readers plus the other charter-surface primitive callers (`effective_set`, `preset_application`, `org_charter`, `active_charter_service_builder`, `_drg_helpers`, `language_vocabulary`, `profile_resolution`, `project_registration`, `skill_preparation`, `offering/resolver`, `manifest_loader`'s `load_manifest` path, and the `cli/commands/charter/*` consumers incl. `interview`, `deactivate`, `_resynthesis_preflight`, `pack_asset`, `context`). The already-correct `context.py` `--include` reader (fixed by #6005) is re-pointed only. Non-charter callers (runtime/tool_surface/review/skills/…) are a named follow-up (see Out of Scope). | High | Open | [build] | no — a same-fixture **behavioural** positive control on the posture-bearing surfaces (`effective_set`, `preset_application`): a pack-2-only artifact is observable through them; the swap-only re-points are guarded by the charter-surface regression suites (the gate alone cannot see a regression to the NFR-001-legal single-`Path` read) |
| FR-003 | `charter list --all` reads the full chain | As an operator, I want `charter list --all` to list org missions, templates, and artifacts from every configured existing pack, not pack #1 only. | High | Open | [build] | no — a pack-2-only artifact (`c-directive`) is absent before, present after. Explicit `TestListAllLayersBackCompat` disposition: **KEEP** `test_resolve_layer_roots_org_key_stays_single_path_over_a_chain` and `test_list_all_does_not_crash_over_a_two_pack_chain`; **SUPERSEDE** `test_list_all_shows_pack_one_but_not_pack_two_unchanged` (it now asserts `c-directive` IS shown) |
| FR-004 | Retry loop retired | As a maintainer, I want `_activate_cascade_target` removed and `ActiveCharterManager.activate`/`list_available`/`list_available_detailed`/`_scan_layer_dirs` widened with an `org_root_chain: list[Path] \| None` so the availability scan validates against the whole chain in one pass. | High | Open | [build] | no — positive control: a pack-2-only artifact activates through the single widened scan; assert `_activate_cascade_target` no longer exists |
| FR-005 | Dead pack-1 single-root reads removed | As a maintainer, I want the write-only `ProjectContext.org_root` single-root field (`invocation_context.py`) removed, and the `action_governance_bundle` legacy `org_root` representative param dropped (its chain resolution stays **lenient** — a governance bundle over existing packs), so no surface carries a pack-1-only org root. | Medium | Open | [build] | no — own structural assertions: `ProjectContext.org_root` is gone (attribute absent) and the `action_governance_bundle` `org_root` param is gone; plus a behavioural control that bundle resolution over a two-pack fixture reflects pack-2 content (not FR-006, which does not see a single-element `[0]` index) |
| FR-006 | Empty-allowlist architectural gate (charter-surface scope) | As a maintainer, I want an architectural test (mirroring `test_remote_contact_owner.py`) that enforces one authority, shipping with an empty allowlist and non-vacuity controls (file-count floor, planted-violation positive control, owner-bypass control). Discriminator (module-ownership): within the census **scope** (`src/charter/**` and `src/specify_cli/cli/commands/charter/**`, this mission), outside the authority module (`layer_roots.py`) and the primitives' own module (`org_pack_config.py`), no code may call a chain primitive (`resolve_org_roots`/`resolve_existing_org_roots`/`require_declared_org_roots`/`resolve_org_root_chain`) or iterate `load_pack_registry().packs` to assemble roots. The allowlist is literally empty (no ratchet); the scope — not an allowlist — is what bounds the mission. Widening the census to the whole tree is the named follow-up. | High | Open | [build] | no — planted violation turns the gate red; removing it turns it green; owner-bypass control proves the census sees the authority |
| FR-007 | Declared-but-missing pack fails closed (strict) | As an operator, I want the strict authority posture to raise on a declared-but-absent pack, naming the pack and the `spec-kitty charter fetch` remedy, consumed by activate/deactivate and the requirement-kinds loader (the #4984 seam). | High | Open | [build] | no — same-fixture pair: strict raises naming the pack; lenient drops it silently |
| FR-008 | Lenient surfaces re-pointed onto the authority | As a maintainer, I want `charter list` display, best-effort scans (`effective_set._readable_roots`/`_fallback_ids`), and the runtime resolution hot path (`resolve_org_dirs`) **re-implemented over `resolve_pack_chain(strict=False)`** (behavior byte-identical per NFR-004), so they no longer call the chain primitives directly and the empty allowlist stays honest, while still degrading silently on a missing pack. | High | Open | [ratchet] | no — non-vacuity is FR-007's shared missing-pack fixture (strict-raise vs lenient-drop on one fixture); plus the gate (FR-006) proves no direct primitive call survives on these paths |
| FR-009 | Requirement-kinds loader (model) | As a #5956 consumer, I want a frozen `RequirementKind` / `RequirementKindDeclaration` Pydantic model (`extra="forbid"`) in `charter/offering/missions/requirement_kinds.py`, mirroring the `ExpectedArtifactManifest` precedent. | Medium | Open | [build] | no — model validates a well-formed declaration and rejects an unknown field |
| FR-010 | Requirement-kinds loader (chain + tiers) | As a #5956 consumer, I want `load_requirement_kinds(mission_type, repo_root)` (beside `load_manifest`) to resolve `requirement-kinds.yaml` through built-in → org full-chain (last-declared-wins) → project tier (`.kittify/charter-packs/missions/<type>/requirement-kinds.yaml`, project wins), whole-file override, so a declaration in any configured pack is honored. | Medium | Open | [build] | no — fixture: pack-2 declaration overrides pack-1; project declaration overrides both (whole-file, verified field-by-field distinct) |
| FR-011 | Requirement-kinds loader (fail-closed) | As a #5956 consumer, I want the loader to refuse on a present-but-invalid declaration (schema/unparseable → a `ManifestSchemaError`-shaped error) and on a declared-but-missing pack (via the strict chain), never silently falling through to the default. | Medium | Open | [build] | no — same-fixture pair: a valid file loads; a one-field-corrupted copy refuses |

### Non-Functional Requirements

| ID | Title | Requirement | Category | Priority | Status |
|----|-------|-------------|----------|----------|--------|
| NFR-001 | `resolve_layer_roots` contract preserved | `resolve_layer_roots(repo_root)` returns `dict[str, Path]` byte-identical; `roots["org"]` stays a single `Path` (pack 1); `_scan_layer_dirs` / `kind_vocabulary._layer_scan_dirs` single-Path call sites are unchanged. (The issue's literal "widen `layer_roots` to take the chain" is deliberately **not** taken; the chain travels as a separate `list[Path]`, per the architect ruling — see Edge Cases.) Verified: `isinstance(resolve_layer_roots(...)["org"], Path)` and the two KEEP assertions in `TestListAllLayersBackCompat` (`test_resolve_layer_roots_org_key_stays_single_path_over_a_chain`, `test_list_all_does_not_crash_over_a_two_pack_chain`) stay green. | Compatibility | High | Open |
| NFR-002 | Empty allowlist, no ratchet | The architectural gate (FR-006) ships with exactly zero allowlist entries and no shrink-only ratchet. Verified: allowlist length == 0; non-vacuity controls present. | Maintainability | High | Open |
| NFR-003 | Quality gates clean | New/changed code passes `ruff check`, `ruff format --check`, and `mypy` with zero issues; cyclomatic complexity ≤ 15; no new blanket `# noqa` / `# type: ignore` / per-file ignores. | Quality | High | Open |
| NFR-004 | Lenient-path behavior byte-identical | Runtime template/mission/FSM resolution (`resolve_org_dirs`) and best-effort scans degrade on a missing pack byte-identically to today (same return, same single WARNING per drop, no new refusal), even after being re-pointed onto `resolve_pack_chain(strict=False)` (FR-008). Verified by the existing org_pack_config / resolver tests staying green. | Reliability | High | Open |
| NFR-005 | `_org_scan_dirs` flat-wins precedence preserved | `resolve_pack_chain()` owns only root SELECTION and ORDER (last-declared-wins by pack ordinal). It does **not** override `kind_vocabulary._org_scan_dirs`'s existing flat-layout-wins-regardless-of-root-order precedence (pinned by `tests/charter/test_kind_vocabulary_scan_roots.py`). On a mixed-layout cross-pack id collision the flat-layout file still wins. Verified: that test stays green unchanged. | Compatibility | High | Open |

### Constraints

| ID | Title | Constraint | Category | Priority | Status |
|----|-------|------------|----------|----------|--------|
| C-001 | Architectural layering | The authority lives in the `charter` tier (`charter/activation/layer_roots.py`); the chain is handed down as `list[Path]` data. The enforced chain `kernel <- charter <- {glossary, runtime, mission_runtime} <- specify_cli` is preserved (`tests/architectural/test_layer_rules.py`). | Technical | High | Open |
| C-002 | Stacked on PR #6005 | This mission builds on PR #6005 and modifies its `_activate_cascade_target` and `TestListAllLayersBackCompat`. The PR sequences after #6005: it rebases onto `main` once #6005 lands, keeping #6005's commits beneath until then. | Process | High | Open |
| C-003 | Scope fence (#5956) | Only the #5956 **loader seam** (model + `load_requirement_kinds`) ships. The #5956 gate handlers, glossary terms, grammar integration, and the #3546 gate behavior are out of scope. No hosted / Team-Kitty surface is touched. | Business | High | Open |
| C-004 | Single canonical authority | Chain resolution has one owning source, `resolve_pack_chain()`. `resolve_org_root_chain` is **absorbed into / replaced by** it (zero remaining callers outside the authority module — it is itself a chain assembler, not a primitive). The three genuine DRG registry readers in `org_pack_config.py` (`resolve_org_roots`, `resolve_existing_org_roots`, `require_declared_org_roots`) survive as primitives but are callable only from the authority module and their own module (FR-006) — reconcile, never add a parallel authority. | Technical | High | Open |

### Key Entities

- **Org-pack chain**: the ordered list of existing organization pack roots a project declares, with last-declared-wins precedence on any collision.
- **Pack chain authority** (`resolve_pack_chain`): the single function that produces the chain, in a strict (fail-closed on a declared-but-missing pack) or lenient (existing-filtered) posture.
- **Requirement-kind declaration** (`requirement-kinds.yaml`): the full requirement-kind set a mission type declares, resolved through built-in → org (last-wins) → project; the loader seam for #5956.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: With two org packs declared, every charter surface (list, activate, `--include`, context, invocation, action bundle, requirement-kinds loader) resolves the same ordered existing chain; a pack-2-only artifact is visible/activatable/renderable everywhere it was pack-1-only before. — [build] · no-op passable: no (pack-2-only fixture: absent/failing before, present/succeeding after)
- **SC-002**: Exactly one function computes the org-pack chain; the empty-allowlist architectural gate has zero entries and goes red when any other module assembles a chain. — [build] · no-op passable: no (planted-violation control proves non-vacuity)
- **SC-003**: A declared-but-missing org pack produces a loud refusal naming the pack and the `spec-kitty charter fetch` remedy on the gated surfaces (activate/deactivate/loader), while list display, best-effort scans, and the runtime hot path still degrade silently. — [build] · no-op passable: no (same-fixture strict-raise vs lenient-drop)
- **SC-004**: The Mission-type requirement-kinds loader resolves `requirement-kinds.yaml` across built-in → org (last-wins) → project (project wins) with whole-file override and refuses an invalid or declared-but-missing pack, ready for #5956 to consume. — [build] · no-op passable: no (override fixture + corrupted-file refusal)

## Assumptions

- **#6005 lands first.** This mission's PR is authored on the stacked base and rebases onto `main` once #6005 merges. If #6005's shape changes materially in review, the stacked base is refreshed before this mission's PR goes ready.
- **`action_governance_bundle[0]` is benign today.** The grounding confirmed the full chain is already threaded and used downstream; dropping the legacy single-root param is a no-behavior-change cleanup, chosen over an allowlist-with-reason entry to keep the gate's allowlist empty.
- **`ProjectContext.org_root` has no production reader.** Only a test asserts it is `None`; removing the field is safe and that test is updated.
- **Loader project-tier path** is `.kittify/charter-packs/missions/<type>/requirement-kinds.yaml`, (canonical project pack root); (Corrected from the pre-cutover `.kittify/doctrine/` path in #5956's design: that directory is retired and refused by the `LEGACY_CHARTER_STATE` gate, FR-011.) `load_manifest` itself has no project tier, so the loader adds one (a deliberate, documented divergence from the `load_manifest` precedent, as is resolving its org chain through the strict authority rather than the lenient `resolve_existing_org_roots`).

## Out of Scope

- The #5956 gate handlers (`MissionStep.gates` / `on_step_exit`), glossary entries for kinds, requirement-mapping grammar integration, and the #3546 research-kind gate behavior.
- Widening `resolve_layer_roots`'s `dict[str, Path]` contract or the `_scan_layer_dirs` single-Path call sites.
- Any hosted / Team-Kitty surface.
- Pack `depends_on` DAG (#5228) and resolvable parent references (#3358) — these build on this authority but are separate missions.
- **Tree-wide chain-authority migration (named follow-up).** The ~12 non-charter-surface chain-deriving callers (`src/runtime/**`, `src/specify_cli/tool_surface/**`, `src/specify_cli/review/**`, `src/specify_cli/skills/**`, `src/specify_cli/invocation/**`, `src/specify_cli/mission_loader/**`, `src/specify_cli/mission_step_contracts/**`, `src/specify_cli/cli/commands/_charter_pack_collect.py`, `src/specify_cli/cli/commands/profiles_cmd.py`, `src/specify_cli/runtime/resolver.py`, and the retired-migration `_retired_activation.py`) already read the full chain correctly and are not bugs; migrating them onto `resolve_pack_chain()` and widening the FR-006 census to the whole tree is a follow-up issue filed by this mission (operator ruling: path-scoped gate + follow-up). The `charter/drg.py` re-export of the primitives is tightened there too.

## Traceability

- **Closes**: #6006.
- **Seam toward**: #4984 (declared-but-missing fails closed at the authority — strict posture), #5956 (requirement-kinds loader seam).
- **Built on**: #5962 (merged) — the charter-pack vocabulary rename is the vocabulary basis for this work, per the #6006 extra-scope note.
- **Context**: #5779 is closed by the stacked PR #6005; #5228 and #3358 build on this authority later.
