# Implementation Plan: Tree-wide org-pack chain authority

**Branch**: `feat/org-pack-chain-tree-wide-authority` | **Date**: 2026-10-10 | **Spec**: [spec.md](./spec.md)
**Input**: Mission specification from `kitty-specs/org-pack-chain-tree-wide-authority-01M4KGZG/spec.md`

## Summary

Route every remaining non-charter org-pack chain-deriving caller through the single `resolve_pack_chain()` authority (`src/charter/activation/layer_roots.py`, landed in #6006), preserving each caller's posture except on the governed decision surfaces, where #4984 requires a fail-closed (`strict=True`) posture. Then widen the FR-006 empty-allowlist census (`tests/architectural/test_org_pack_chain_single_authority.py`) from its charter-surface path scope to the whole `src/` tree, expressing the two legitimate exemptions (`src/charter/offering/**` tier; name-paired registry enumeration) as scan rules — the allowlist stays empty.

The brownfield scout (see [research.md](./research.md)) corrected the issue's caller list: `discovery.py:82` is a docstring (no migration), the three `resolve_org_dirs` sites are out of scope (not a forbidden primitive), and `_retired_activation.py:353` is an additional in-scope caller.

## Technical Context

**Language/Version**: Python 3.11+
**Primary Dependencies**: internal only — `charter.activation.layer_roots.resolve_pack_chain`; no new third-party dependency (no supply-chain review needed)
**Storage**: N/A (filesystem org-pack roots)
**Testing**: pytest; the FR-006 architectural census gate (`tests/architectural/test_org_pack_chain_single_authority.py`); focused per-caller unit tests; red-first regression for the #4984 fail-closed behaviour change
**Target Platform**: Linux/macOS dev + CI
**Project Type**: single (library/CLI)
**Performance Goals**: no regression — the lenient hot paths keep `quiet`/best-effort semantics; `resolve_pack_chain(strict=False)` is the same `resolve_existing_org_roots` body
**Constraints**: `resolve_pack_chain` is Path-only (name-paired enumeration NOT migrated, C-001); census allowlist stays empty (C-003); `src/charter/offering/**` cannot import the activation authority (C-001); complexity ≤15, new branches tested in-commit (NFR-003)
**Scale/Scope**: 13 call sites across 11 modules + 1 architectural gate widen; 3 of the call sites are behaviour-changing (#4984 fail-closed)

## Charter Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

- **Single canonical authority (DIRECTIVE_044)**: this mission *is* the application of this principle — one authority (`resolve_pack_chain`) for the ordered org-pack chain. ✅ aligned.
- **Architectural alignment / layering (DIRECTIVE_001)**: migrated callers import `resolve_pack_chain` directly from `charter.activation.layer_roots` (consistent with all 16 existing importers); the scout verified no `offering→activation` import inversion is introduced and `src/charter/offering/**` stays excluded. ✅
- **Test-first / quality gate (DIRECTIVE_030, DIRECTIVE_034)**: the #4984 fail-closed change lands red-first with an issue-pinned regression; new branches get focused tests in-commit. ✅
- **Terminology canon**: Mission, not Feature. ✅
- No charter violations → Complexity Tracking empty.

## Project Structure

### Documentation (this mission)

```
kitty-specs/org-pack-chain-tree-wide-authority-01M4KGZG/
├── plan.md              # This file
├── research.md          # Phase 0 — brownfield scout map + decisions
├── spec.md              # Mission spec
└── tasks/               # Phase 2 output (/spec-kitty.tasks)
```

No `data-model.md`/`contracts/` — this is an internal refactor with no new interfaces; `meta.json` will carry `"contracts": "none"` + rationale for strict `accept`.

### Source Code (repository root)

```
src/charter/activation/layer_roots.py        # the authority (resolve_pack_chain) — unchanged, the migration target
src/runtime/next/runtime_bridge_io.py        # :465  strict=False   (hot path)
src/runtime/next/_internal_runtime/discovery.py  # :82 docstring only — optional refresh, NOT a call
src/specify_cli/runtime/resolver.py          # :356, :818  strict=False (hot path)
src/specify_cli/mission_loader/command.py    # :235  strict=False   (hot path; :275 resolve_org_dirs OUT OF SCOPE)
src/specify_cli/skills/catalog.py            # :154  strict=False   (hot path prefilter)
src/specify_cli/invocation/org_profiles.py   # :67   strict=False   (hot path short-circuit)
src/specify_cli/cli/commands/profiles_cmd.py # :109  strict=False   (read-only view)
src/specify_cli/cli/commands/_charter_pack_collect.py  # :258,:365,:609,:1213  strict=False (diagnostics)
src/specify_cli/upgrade/migrations/_retired_activation.py  # :353  strict=False (keep retired-key splice)
src/specify_cli/review/gate_bindings.py      # :286  strict=True  [#4984 BEHAVIOUR CHANGE]
src/specify_cli/mission_step_contracts/executor.py  # :194  strict=True [#4984 BEHAVIOUR CHANGE]  (:173 resolve_org_dirs OUT OF SCOPE)
src/specify_cli/tool_surface/providers/agent_profiles.py  # :574  strict=True [#4984 — already manual-raises]
src/charter/drg.py                           # frozen compat re-exports — leave primitive re-exports; callers import resolve_pack_chain direct
tests/architectural/test_org_pack_chain_single_authority.py  # WP05: widen _SCOPE_DIRS to src/, offering exclusion rule, raise floor, allowlist stays empty
```

**Structure Decision**: single-project library/CLI; edits are in-place caller migrations plus one architectural-gate widen. No new modules.

## Decision record (resolved at plan time)

- **#4984 crash-vs-degrade (DEC-6012-1)**: the three decision surfaces (`gate_bindings:286`, `executor:194`, `agent_profiles:574`) move existing-filtered → `strict=True`, i.e. a declared-but-unfetched org pack **raises** (naming the pack + `spec-kitty charter fetch` remedy) instead of silently proceeding. This is the explicit intent of issue #6012 / #4984 ("fails closed where it should on the decision surfaces"); the operator-visible impact (refuse vs silent-degrade) is recorded here and gets a CHANGELOG entry + a red-first regression test. `agent_profiles:574` already manual-raises, so strict=True only swaps its ad-hoc message for the canonical remedy message.
- **drg.py (DEC-6012-2)**: leave `charter.drg`'s primitive re-exports frozen (compat surface for `resolve_org_dirs` users + primitive unit tests); migrated callers import `resolve_pack_chain` **directly** from `charter.activation.layer_roots`, consistent with the 16 existing importers. No offering→activation cycle (scout-verified).

## Implementation Concern Map

> Concerns, not WPs. `/spec-kitty.tasks` translates these into executable work packages.

### IC-01 — Runtime-tier lenient hot-path migration

- **Purpose**: route the runtime/next template-discovery and resolution hot paths onto `resolve_pack_chain(strict=False)` without behaviour change.
- **Relevant requirements**: FR-001, FR-002, FR-006, NFR-001.
- **Affected surfaces**: `runtime_bridge_io.py:465`, `runtime/resolver.py:356/:818`, `mission_loader/command.py:235`; refresh `discovery.py:82` docstring + the DEC-004/005 comment blocks.
- **Sequencing/depends-on**: none.
- **Risks**: lazy-import ordering (keep imports lazy); comment blocks still name the old primitive; raw→`strict=False` adds an existence filter (harmless in template search — note, no behaviour-change test).

### IC-02 — specify_cli lenient callers

- **Purpose**: migrate the best-effort / diagnostic / read-only specify_cli callers to `strict=False`.
- **Relevant requirements**: FR-001, FR-002, FR-006, NFR-001.
- **Affected surfaces**: `skills/catalog.py:154`, `invocation/org_profiles.py:67`, `cli/commands/profiles_cmd.py:109`, `cli/commands/_charter_pack_collect.py:258/:365/:609/:1213`.
- **Sequencing/depends-on**: none.
- **Risks**: verify `CharterOfferingService` treats absent roots as no-ops before the raw→filtered swap on `_charter_pack_collect` (else an unfetched pack could be hidden from `doctor`); diagnostic completeness comes from the separate `registry.packs` name-capturing loops (not census hits), so those stay.

### IC-03 — #4984 fail-closed decision surfaces

- **Purpose**: move the governed decision surfaces to `strict=True` so a declared-but-missing pack fails closed (completes #4984).
- **Relevant requirements**: FR-005, FR-002, NFR-002, NFR-003.
- **Affected surfaces**: `review/gate_bindings.py:286`, `mission_step_contracts/executor.py:194`, `tool_surface/providers/agent_profiles.py:574`.
- **Sequencing/depends-on**: none (independent of IC-01/02).
- **Risks**: real behaviour change (refuse vs degrade) — red-first regression per surface (unfetched pack ⇒ raises naming pack + remedy), CHANGELOG entry; update any test monkeypatching the old primitive on these modules / asserting the old `agent_profiles` message string.

### IC-04 — migration-tier caller + drg.py decision

- **Purpose**: migrate `_retired_activation.py:353` (keep the retired-key splice) and settle the `charter.drg` re-export decision (DEC-6012-2: leave frozen).
- **Relevant requirements**: FR-001, FR-002.
- **Affected surfaces**: `src/specify_cli/upgrade/migrations/_retired_activation.py:353`, `src/charter/drg.py` (no change beyond confirming the decision).
- **Sequencing/depends-on**: shares the import-path decision with IC-01.
- **Risks**: `_retired_activation` is a frozen migration — keep behaviour byte-identical; its `_retired_key_org_roots` helper is not a census hit (iterates retired-key entries, not `registry.packs`).

### IC-05 — widen the census gate tree-wide (lands last)

- **Purpose**: widen `test_org_pack_chain_single_authority.py` to scan all of `src/`, allowlist empty, with rule-based exemptions.
- **Relevant requirements**: FR-003, FR-004, SC-002.
- **Affected surfaces**: `tests/architectural/test_org_pack_chain_single_authority.py` (`_SCOPE_DIRS`→`src/`; add `src/charter/offering/**` scan-exclusion rule; raise `_SCANNED_FILE_FLOOR`; extend docstring noting name-paired readers rely on existing rule semantics; `_ALLOWED` stays empty).
- **Sequencing/depends-on**: **MUST follow IC-01..IC-04** — widening before the callers migrate turns the gate red.
- **Risks**: file-floor must track the (much larger) tree-wide scanned count; the offering exclusion must be a documented rule, not an allowlist entry (C-003, ADR 2026-09-30-1).
