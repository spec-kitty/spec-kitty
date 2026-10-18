# Mission Specification: Built-in re-vendor — pin lockfile + vendor command + drift gate

**Mission Branch**: `feat/builtin-revendor-pin-gate`
**Created**: 2026-10-17
**Status**: Draft
**Input**: Implement ADR `2026-08-16-2` (amended 2026-10-11) Option B for issue #3504 — pin the open-packs built-in source, add a vendor command, and a CI drift gate that keeps the committed `packs/built-in/` tree provably equal to the pin.

## Intent Summary *(confirmed)*

- **Primary actor**: a Spec Kitty maintainer bumping or verifying built-in doctrine provenance; and CI acting on every contributor PR.
- **Trigger**: built-in content is authored in `spec-kitty-open-packs` and vendored into core's committed `packs/built-in/`; today nothing ties the two, so core silently drifts from its provenance source (it just did — 8 files moved past the recorded pin).
- **Desired outcome**: core carries a committed pin (open-packs repo URL + commit **SHA** + tree digest + `requires_core`); a `spec-kitty charter pack vendor` command re-copies and verifies the pinned tree; a drift gate fails any PR whose `packs/built-in/` ≠ pin; the release re-verifies before building.
- **Load-bearing invariant**: the committed tree stays in place and byte-identical — it becomes a **verified build cache** (like a committed `uv.lock`), never a second authority. Consumer installs and `resolve_pack_root("built-in")` are unchanged.
- **Canonical terms**: *vendor* = release/pin-time copy of the pinned tree into the committed `packs/built-in/` (this mission); *materialize* = optional local on-demand populate (NOT built here); *fetch* = runtime pull from a data dependency (Option C / #3022, out of scope). *Pin* = a commit SHA + digest, never a tag.
- **Scope ruling (operator, 2026-10-17)**: run #3504 exactly as ADR `2026-08-16-2` (amended 2026-10-11) defines it — **Shape A, tree stays committed**. Removing the committed tree / build-time materialization, `packs/internal/`, and the authoring flip are explicit non-goals (ADR decisions 1, 5, 6).

## User Scenarios & Testing *(mandatory)*

### User Story 1 - A committed pin anchors built-in provenance (Priority: P1)

A maintainer can read, in core, exactly which open-packs commit the vendored `packs/built-in/` came from and verify the tree against it, without consulting the open-packs repo.

**Why this priority**: the pin is the single provenance anchor every other piece (vendor, drift gate, release re-verify) depends on. Nothing else can be built without it.

**Independent Test**: a committed lockfile resolves to a real open-packs commit SHA + a tree digest; a digest helper recomputes the committed `packs/built-in/` digest and it equals the recorded value.

**Acceptance Scenarios**:

1. **Given** a fresh checkout at HEAD, **When** the pin lockfile is read, **Then** it names the open-packs repository URL, a commit SHA (not a tag), a tree digest computed with `charter.offering.packs` hashing, and a `requires_core` range.
2. **Given** the committed `packs/built-in/` tree, **When** its clean-tree digest is computed, **Then** it equals the digest recorded in the lockfile.

---

### User Story 2 - `charter pack vendor` re-copies and verifies the pinned tree (Priority: P1)

A maintainer runs one command to resolve the pinned open-packs ref, copy its built-in subtree into `packs/built-in/`, and have the command refuse unless the result matches the pin and is core-compatible.

**Why this priority**: this is the sanctioned, verified way to change `packs/built-in/` (a pin bump). Hand edits are what the drift gate forbids; the command is their replacement.

**Independent Test**: running `vendor` against the recorded pin on a clean tree is a no-op that exits 0; running it against a deliberately stale pin rewrites the tree to match the new pin and refreshes the lockfile digest.

**Acceptance Scenarios**:

1. **Given** the recorded pin, **When** `spec-kitty charter pack vendor` runs, **Then** it resolves the open-packs ref by SHA, copies the built-in subtree into `packs/built-in/`, and asserts the recomputed digest equals the lockfile digest.
2. **Given** a pinned tree whose `pack.yaml` `requires_core` is incompatible with the running core version, **When** `vendor` runs, **Then** it refuses with a clear, non-zero error naming the incompatibility and leaves `packs/built-in/` unchanged.
3. **Given** an unreachable or unverifiable open-packs ref, **When** `vendor` runs, **Then** it fails closed (non-zero, tree unchanged) and never writes a partial or empty tree.
4. **Given** a **tag** supplied as the vendor ref, **When** the pin is written/bumped, **Then** the stored pin is the resolved commit **SHA** and the tag is never persisted (FR-002). *(Positive control for the refuse/no-mutation scenarios 2 & 3: this scenario and FR-004's stale-pin case prove the vendor path **does** rewrite `packs/built-in/` + the lockfile on the same harness, so the "tree unchanged" assertions are non-vacuous.)*
5. **Given** an open-packs ref carrying changes **outside** the `built-in` subtree (another pack, or repo-root files), **When** the pin digest is computed, **Then** the digest is unaffected — only `built-in` subtree content moves it (C-006).

---

### User Story 3 - A drift gate forbids silent divergence (Priority: P1)

Every PR is checked: if `packs/built-in/` no longer matches the pin, CI fails with a message telling the author to bump the pin (via `vendor`) rather than hand-edit the tree.

**Why this priority**: this is the defect #3504 exists to close — built-in drifting from its provenance source with nothing to catch it. It is the mission's regression guard.

**Independent Test**: a verify-only `vendor --check` exits 0 on the in-sync tree and non-zero on a one-byte edit to any `packs/built-in/` file; wiring it into CI makes a drifting PR red.

**Acceptance Scenarios**:

1. **Given** `packs/built-in/` equal to the pin, **When** `spec-kitty charter pack vendor --check` runs, **Then** it exits 0 and mutates nothing.
2. **Given** a single edited file under `packs/built-in/` with no matching pin bump, **When** the drift gate runs **the same `spec-kitty charter pack vendor --check` command CI invokes** (not a test over the workflow file's text), **Then** it exits non-zero and prints a message naming the drift and the `vendor` remedy (FR-010).

---

### User Story 4 - The release ships provably-pinned bytes (Priority: P2)

The release build re-verifies `packs/built-in/` against the pin before producing the distribution, so the shipped wheel is provably the pinned content.

**Why this priority**: closes the loop at the point that matters to consumers; lower than P1 because the per-PR gate already keeps `main` honest, and the wheel force-include is unchanged.

**Independent Test**: the release workflow and the `RELEASE_CHECKLIST.md` manual pre-tag build both run the verify step before `python -m build`; a post-build assertion confirms the wheel's `packs/built-in/` digest equals the pin.

**Acceptance Scenarios**:

1. **Given** the release pipeline, **When** it runs, **Then** `vendor --check` (or equivalent) verifies the pin before the distribution build and a post-build check asserts the wheel's built-in tree matches the pin.

### Edge Cases

- A pin whose `requires_core` range is satisfied by the coarse version string yet whose content needs a newer core (open-packs#39): the pin must be verified by **SHA + digest**, not by trusting `requires_core` alone.
- A stray git-ignored artifact under `packs/built-in/` (e.g. `assets/__pycache__/*.pyc`): the digest must be the **clean-tree** digest that ignores such artifacts (reuse `pack_clean_digest`), so local pollution never reds the gate.
- open-packs layout is `packs/<name>/` per-pack; the pin/digest must target only the `built-in` subtree of the open-packs ref, not the repo root.
- Offline / air-gapped PR CI: the per-PR drift gate must verify against the **committed** tree + lockfile with no network (digest comparison only); only an actual pin bump (`vendor`) needs to reach open-packs.

## Requirements *(mandatory)*

### Functional Requirements

| ID | Title | User Story | Priority | Status | Delivery | No-op passable? |
|----|-------|------------|----------|--------|----------|-----------------|
| FR-001 | Committed pin lockfile | As a maintainer, I want a committed core lockfile recording the open-packs repo URL, commit SHA, tree digest, and `requires_core` so built-in provenance is anchored in-repo. | High | Open | [build] | no — a round-trip test recomputes the digest from the real tree |
| FR-002 | Pin by SHA, not tag | As a maintainer, I want the pin stored as a commit SHA (a tag only resolved to a SHA, never stored) so the pin is immutable. | High | Open | [build] | no — asserted against a tag-vs-SHA fixture |
| FR-003 | `charter pack vendor` resolves + copies | As a maintainer, I want a command that resolves the pinned open-packs ref and copies its `built-in` subtree into `packs/built-in/`. | High | Open | [build] | no — exercised against a real pinned ref |
| FR-004 | Vendor verifies digest | As a maintainer, I want `vendor` to assert the recomputed clean-tree digest equals the lockfile digest and refuse on mismatch. | High | Open | [build] | no — paired stale-pin (rewrites) vs in-sync (no-op) controls |
| FR-005 | Vendor verifies `requires_core` | As a maintainer, I want `vendor` to assert core-compatibility via `core_compat.check_requires_core` and refuse on incompatibility, tree unchanged. | High | Open | [build] | no — incompatible refuses (tree unchanged), paired with the FR-004 stale-pin-rewrites control proving the vendor path mutates on the same harness |
| FR-006 | Fail-closed on unresolvable ref | As a maintainer, I want `vendor` to fail closed (tree unchanged, non-zero) when the open-packs ref is unreachable or unverifiable, never writing a partial tree. | High | Open | [build] | no — unreachable-ref asserts no mutation, paired with the FR-004 stale-pin-rewrites control proving the vendor path can mutate on the same harness |
| FR-007 | `vendor --check` verify-only | As CI, I want a verify-only mode that compares `packs/built-in/` to the pin without mutating and exits non-zero on drift. | High | Open | [build] | no — in-sync (0) vs edited-byte (non-0) controls |
| FR-008 | Per-PR drift gate | As a contributor, I want CI to run the drift check on every PR touching built-in so divergence from the pin fails the PR with a clear remedy. | High | Open | [build] | no — a drifting-tree fixture must red the gate through the same `vendor --check` command CI invokes |
| FR-009 | Release re-verification | As the release process, I want the pin re-verified before the distribution build and the built wheel's tree asserted equal to the pin. | Medium | Open | [build] | no — asserted in the packaging/parity test |
| FR-010 | Drift message names the remedy | As a contributor who hand-edited built-in, I want the gate failure to tell me to bump the pin via `vendor`, not hand-edit. | Medium | Open | [build] | no — message asserted in the gate test |

### Non-Functional Requirements

| ID | Title | Requirement | Category | Priority | Status |
|----|-------|-------------|----------|----------|--------|
| NFR-001 | Deterministic, reproducible digest | The drift verdict is deterministic: the clean-tree digest is identical across a git-archive export, a worktree (even with `__pycache__` pollution), and an installed copy (reuse `pack_clean_digest`'s guarantee). | Reliability | High | Open |
| NFR-002 | Integrity by content, not version string | Verification is by SHA + content digest, never by trusting the coarse `requires_core` range (open-packs#39); it runs at vendor time and release, never at consumer runtime. | Security | High | Open |
| NFR-003 | Consumer install unchanged | The released wheel still force-includes byte-identical `packs/built-in/`; `resolve_pack_root("built-in")` and the sibling ancestor-walk resolve the same tree; no new runtime network dependency. | Compatibility | High | Open |
| NFR-004 | Per-PR gate is offline | The per-PR drift gate compares the committed tree to the committed lockfile with no network access. | Reliability | Medium | Open |

### Constraints

| ID | Title | Constraint | Category | Priority | Status |
|----|-------|------------|----------|----------|--------|
| C-001 | Tree stays committed | `packs/built-in/` stays git-tracked and present in-tree; no removal, no build-time materialization (ADR `2026-08-16-2` amended decision 1). | Technical | High | Open |
| C-002 | `packs/internal/` untouched | The internal tier stays authored in core and never ships; `tests/cross_cutting/packaging/test_packaging_safety.py` is unchanged (ADR decision 5; ADR `2026-08-16-3`). | Technical | High | Open |
| C-003 | Authoring flip out of scope | Moving authorship to open-packs and rewriting CLAUDE.md / the charter source-home guidance is a separate later slice (ADR decision 6) and is NOT done here. | Technical | High | Open |
| C-004 | Reuse landed primitives | Build on the primitives #6046/#6048 (c3fc8aa349) landed — `core_compat.check_requires_core`, `pack_clean_digest.clean_tree_digest`, `charter pack regenerate-graph --pack-root` — do not re-author digest/compat logic. | Technical | High | Open |
| C-005 | Option B only | This is Option B (filesystem sibling, force-included in the wheel). No runtime resolution and no second published package — that is Option C / #3022, the deferred north star. | Technical | High | Open |
| C-006 | Pin targets the built-in subtree | The pin/digest targets only the `built-in` subtree of the open-packs ref, respecting its per-pack `packs/<name>/` layout; content elsewhere in the open-packs ref must not move the digest (US1-S5). | Technical | High | Open |

### Key Entities

- **Pin lockfile**: the committed core record of built-in provenance — open-packs repo URL, commit SHA, clean-tree digest (and optionally the `snapshot_sha256`), and the `requires_core` range. The only built-in-related file *authored* in core.
- **Vendored tree** (`packs/built-in/`): a verified build cache — read-only in core, changed only through a pin bump, provably equal to the pin.
- **Drift gate**: the per-PR + release verification that the vendored tree equals the pin.

## Issue Matrix *(references)*

- **#3504** — primary issue this mission delivers (Option B re-vendor pipeline).
- Context / not folded (cite as parent, follow-up, or soft dependency — no work owed here): parent epic #2466; deferred north-star #3022 (Option C, runtime fetch); GA-gating charter-extraction epic #6099 (different axis); pack-trust soft deps #2467, #2539, #2543, #2471 (a plain SHA + digest pin is enough to start).
- Cross-repo references (open-packs): open-packs#31 (seed content + first tag — now materially cleared; tagged `v0.1.0`); open-packs#39 (`requires_core` too coarse — folded as the constraint behind NFR-002).
- Governing ADRs (cite; no new amendment needed — this implements the 2026-10-11 amendment): `2026-08-16-2` (ratifying + amended decisions 1–6), `2026-08-16-3` (internal is a public org pack, not force-shipped), `2026-10-11-2` (a pack declares its level), `2026-08-16-1` (pack manifest unification — digest source).

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: A PR that edits any file under `packs/built-in/` without a matching pin bump fails CI with a drift message naming the `vendor` remedy. — [build] · no-op passable: no
- **SC-002**: `charter pack vendor` from the recorded pin reproduces `packs/built-in/` byte-identical to the committed tree (clean round-trip). — [build] · no-op passable: no
- **SC-003**: The released wheel's `packs/built-in/` tree digest equals the committed pin. — [build] · no-op passable: no
- **SC-004**: `resolve_pack_root("built-in")` resolves to a tree whose clean-tree digest **equals the committed pin** (so consumer-observable resolution is provably the pinned bytes, and a drifted/no-op tree would fail this). — [ratchet] · no-op passable: yes — positive control: a fixture pointing the resolver at a deliberately mutated tree makes this probe go red
