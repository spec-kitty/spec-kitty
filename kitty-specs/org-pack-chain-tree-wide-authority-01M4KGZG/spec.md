# Mission Specification: Tree-wide org-pack chain authority

**Mission Branch**: `feat/org-pack-chain-tree-wide-authority`
**Created**: 2026-10-10
**Status**: Draft
**Input**: Follow-up to #6006 — complete the single-authority migration of org-pack chain derivation across the non-charter surfaces, widen the empty-allowlist gate tree-wide, and complete #4984 fail-closed behaviour on governed decision surfaces.

## Intent Summary

- **Primary actor**: a Spec Kitty maintainer (and every governed consumer surface that must read the ordered org-pack chain).
- **Trigger**: #6006 landed `resolve_pack_chain()` (`src/charter/activation/layer_roots.py`) as the single ordered org-pack-chain authority and migrated the charter surfaces behind a **path-scoped** empty-allowlist gate; the remaining non-charter callers still derive the chain directly.
- **Desired outcome**: every non-charter chain-deriving caller reads the chain through `resolve_pack_chain()` (preserving its current posture), the FR-006 census is widened tree-wide with the allowlist still empty, and declared-but-missing-pack fails closed on the governed decision surfaces (#4984) while lenient hot paths keep their by-design silent-degrade.
- **Rule that must always hold**: there is exactly one authority for the ordered, existing org-pack chain. A correctly-configured chain resolves **byte-for-byte identically** before and after migration; this is consistency, not a behavioural change to the happy path.
- **Canonical boundary**: `resolve_pack_chain` is **Path-only**. Name-paired registry enumeration and the `src/charter/offering/**` tier are explicitly out of scope and stay on their own primitives.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Single chain authority across the tree (Priority: P1)

Every non-charter surface that needs the ordered org-pack chain obtains it from `resolve_pack_chain()`, so the ordering and existence/strict semantics live in one place.

**Why this priority**: scattered chain derivation is the parallel-authority risk #6006 set out to close; leaving ~12 callers on the old primitives keeps two authorities alive.

**Independent Test**: for a two-pack project, every migrated caller resolves the same ordered `[Path, …]` chain (declaration order, last-declared-wins) as a direct `resolve_pack_chain()` call, and a grep/AST census finds no direct `resolve_existing_org_roots` / `require_declared_org_roots` outside the documented exemptions.

**Acceptance Scenarios**:

1. **Given** a project with two configured org packs, **When** any migrated caller derives the chain, **Then** it returns the identical ordered Path list `resolve_pack_chain(repo_root, strict=<that caller's posture>)` returns.
2. **Given** the migrated tree, **When** the widened census runs with an empty allowlist, **Then** it passes.
3. **Given** a developer reintroduces a direct `resolve_existing_org_roots` call on a non-exempt surface, **When** the census runs, **Then** it fails and names the offending file.

### User Story 2 - Declared-but-missing pack fails closed on decision surfaces (Priority: P2)

On a governed **decision** surface, a declared org pack whose root is absent on disk is refused with a clear diagnostic, rather than silently dropped.

**Why this priority**: #4984 — a decision made against a silently-shortened chain is an integrity hole; the lenient hot paths intentionally keep degrading silently so they never block.

**Independent Test**: with a declared-but-unfetched pack, a decision-surface caller raises/refuses naming the pack and the `spec-kitty charter fetch` remedy; a lenient hot-path caller still returns the existing-filtered chain without raising.

**Acceptance Scenarios**:

1. **Given** a declared pack with no root on disk, **When** a governed decision surface resolves the chain, **Then** it fails closed (strict posture) naming the pack + remedy.
2. **Given** the same state, **When** a lenient hot path resolves the chain, **Then** it silently drops the missing pack and continues (unchanged by design).

### Edge Cases

- Zero declared org packs → `resolve_pack_chain` returns `[]` in either posture, never raises; every migrated caller behaves exactly as before.
- Name-paired enumeration (`_enumerate_org_pack_paths[_strict]`, `pack_context._read_org_packs`) still needs pack **names** + the unfiltered missing-pack diagnostic → NOT migrated; the census exempts it.
- `src/charter/offering/**` cannot import the activation-tier authority → stays excluded; the census does not flag it.
- `_retired_activation.py` (retired migration) is frozen → exempt.

## Requirements

### Functional Requirements

| ID | Requirement | Status | Delivery | No-op passable? |
|----|-------------|--------|----------|-----------------|
| FR-001 | Each listed non-charter chain-deriving caller (`src/runtime/next/_internal_runtime/discovery.py`, `src/runtime/next/runtime_bridge_io.py`, `src/specify_cli/runtime/resolver.py`, `src/specify_cli/tool_surface/providers/agent_profiles.py`, `src/specify_cli/review/gate_bindings.py`, `src/specify_cli/skills/catalog.py`, `src/specify_cli/invocation/org_profiles.py`, `src/specify_cli/mission_loader/command.py`, `src/specify_cli/mission_step_contracts/executor.py`, `src/specify_cli/cli/commands/_charter_pack_collect.py`, `src/specify_cli/cli/commands/profiles_cmd.py`, and the `src/charter/drg.py` re-export) resolves the ordered org-pack chain via `resolve_pack_chain()` instead of calling the lower-level primitives directly. | Draft | [ratchet] | no |
| FR-002 | Each migrated caller preserves its pre-migration posture: a caller that used the existing-filtered primitive calls `resolve_pack_chain(..., strict=False)`; one that used the fail-closed primitive calls `strict=True`. | Draft | [ratchet] | no |
| FR-003 | The FR-006 empty-allowlist architectural census (`tests/architectural/test_org_pack_chain_single_authority.py`) is widened to cover the whole source tree (charter-surface path scope dropped), with the allowlist kept empty. | Draft | [build] | no |
| FR-004 | The widened census exempts the legitimate non-migration surfaces by rule, not by allowlist entry: `src/charter/offering/**` (tier cannot import the authority) and the name-paired registry enumeration that reads `load_pack_registry()` for names + the unfiltered missing-pack diagnostic. | Draft | [build] | no |
| FR-005 | On the governed non-charter **decision** surfaces, a declared-but-missing org pack fails closed (strict posture) with a diagnostic naming the pack and the `spec-kitty charter fetch` remedy, completing #4984; the lenient hot paths keep their by-design silent-degrade (existing-filtered) behaviour. | Draft | [build] | no |
| FR-006 | A correctly-configured chain resolves to the identical ordered Path list through every migrated caller after migration as before it (consistency, not a happy-path behaviour change). | Draft | [ratchet] | no |

### Non-Functional Requirements

| ID | Requirement | Threshold | Status |
|----|-------------|-----------|--------|
| NFR-001 | No happy-path regression: the existing test suites for every migrated caller pass unchanged; the resolved chain order is byte-identical pre/post. | 100% of touched-caller tests green; 0 chain-order diffs | Draft |
| NFR-002 | Each per-caller posture decision (strict vs existing-filtered) is justified against whether the caller is a decision surface or a lenient hot path, and recorded in the plan. | Every migrated caller classified; 0 unexplained posture changes | Draft |
| NFR-003 | New/changed branches and helpers carry focused tests in the same commit; cyclomatic complexity of touched functions stays ≤ 15. | Sonar new-code gate green; complexity ≤ 15 | Draft |

### Constraints

| ID | Constraint | Status |
|----|-----------|--------|
| C-001 | `resolve_pack_chain` is Path-only. Name-paired enumeration is NOT a migration target; if a `(name, root)` authority is ever wanted, add a variant rather than forcing those callers through the Path-only authority. | Draft |
| C-002 | Depends on #6006 (landed): `resolve_pack_chain()` is the authority this mission routes callers onto. | Draft |
| C-003 | The census allowlist stays **empty**. Legitimate exemptions are expressed in the gate's scoping rules (offering tier, name-paired enumeration), never by adding an allowlist entry to make the gate pass. | Draft |
| C-004 | The charter is binding; terminology canon holds (Mission, never Feature). | Draft |

### Success Criteria

- **SC-001**: 100% of the listed non-charter callers resolve the chain via `resolve_pack_chain()`; a tree-wide census finds 0 direct `resolve_existing_org_roots` / `require_declared_org_roots` derivations outside the documented exemptions. — [ratchet] · no-op passable: no
- **SC-002**: The widened census passes with an empty allowlist and fails (naming the file) when a direct chain-derivation is reintroduced on a non-exempt surface. — [build] · no-op passable: no
- **SC-003**: A declared-but-missing pack on a governed decision surface fails closed with a diagnostic naming the pack and the `spec-kitty charter fetch` remedy; a lenient hot path continues silently. — [build] · no-op passable: no

## Key Entities

- **Org-pack chain**: the ordered list of existing org-pack roots (`[Path, …]`), declaration order, last-declared-wins for consumers.
- **`resolve_pack_chain(repo_root, *, strict)`**: the single authority (`src/charter/activation/layer_roots.py`); `strict=False` existing-filtered (drops absent), `strict=True` fail-closed (raises naming the pack + remedy).
- **Posture**: a caller's existence stance — existing-filtered (lenient hot path) vs fail-closed (governed decision surface).
- **FR-006 census gate**: `tests/architectural/test_org_pack_chain_single_authority.py` — the empty-allowlist architectural test enforcing the single authority.

## Dependencies & Assumptions

- Assumes #6006 is merged (it is) and `resolve_pack_chain` is stable.
- Assumes the per-caller posture is derivable from each caller's current primitive + its role; the plan's brownfield scout confirms the decision-surface vs hot-path classification per caller.
- Name-paired enumeration and `src/charter/offering/**` are confirmed out of scope by the source issue.
