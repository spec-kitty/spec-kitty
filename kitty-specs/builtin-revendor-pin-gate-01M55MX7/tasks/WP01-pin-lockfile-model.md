---
work_package_id: WP01
title: Pin lockfile model
dependencies: []
requirement_refs:
- FR-001
- FR-002
- NFR-001
- NFR-002
- C-006
- SC-002
- SC-004
planning_base_branch: feat/builtin-revendor-pin-gate
merge_target_branch: feat/builtin-revendor-pin-gate
branch_strategy: Planning artifacts for this mission were generated on feat/builtin-revendor-pin-gate. During /spec-kitty.implement this WP may branch from a dependency-specific base, but completed changes must merge back into feat/builtin-revendor-pin-gate unless the human explicitly redirects the landing branch.
subtasks:
- T001
- T002
- T003
- T004
- T015
phase: Phase 1 - Implementation
history:
- at: '2026-10-17T20:00:00Z'
  actor: system
  action: Prompt generated via /spec-kitty.tasks
agent_profile: python-pedro
authoritative_surface: src/charter/offering/packs/
create_intent:
- src/charter/offering/packs/built_in_pin.py
- packs/built-in.source.yaml
- tests/charter_offering/test_built_in_pin.py
execution_mode: code_change
model: sonnet
owned_files:
- src/charter/offering/packs/built_in_pin.py
- packs/built-in.source.yaml
- tests/charter_offering/test_built_in_pin.py
role: implementer
tags: []
task_type: implement
tracker_refs:
- '3504'
---

# Work Package Prompt: WP01 – Pin lockfile model

## ⚡ Do This First: Load Agent Profile

Use the `/spk-charter-profile-load` skill to load the agent profile named in the frontmatter
(or any user-defined profile), and behave according to its guidance before parsing the rest of
this prompt.

- **Profile**: `python-pedro`
- **Role**: `implementer`
- **Agent/tool**: `claude`

---

## Objectives & Success Criteria

Deliver the single in-core authority for "which open-packs commit `packs/built-in/` was vendored
from", plus a pure verify function. Concretely:

1. A committed YAML lockfile `packs/built-in.source.yaml` (sibling of `packs/built-in/`, so it is
   **outside** the digested tree) recording:
   - `repository` — the open-packs repo URL (`git@github.com:spec-kitty/spec-kitty-open-packs.git`),
   - `commit` — the open-packs **SHA** (never a tag),
   - `tree_digest` — `{algorithm, value}` where `value` is `clean_tree_digest(packs/built-in, level=BUILT_IN)`,
   - `requires_core` — the PEP 440 range the vendored built-in pack declares (expected `>=4.0.0rc7,<5`).
   - MAY also carry `snapshot_sha256` as a secondary cross-check, but it is NOT the gate authority.
2. A thin, pure `src/charter/offering/packs/built_in_pin.py` that loads, verifies, and writes that
   lockfile.
3. The lockfile seeded with the REAL current pin (T003): open-packs tag `v0.1.0`, which dereferences
   to commit `1c09592df5f55b5b2dd51bdd172d9e7349d2a159` (= open-packs `main` HEAD at authoring time),
   and the `tree_digest` computed by `clean_tree_digest` over the committed `packs/built-in/` tree.

Success = FR-001, FR-002, NFR-001, NFR-002, C-006, SC-002, **SC-004** (the resolver-observable
pinned-bytes guarantee — T015) in [spec.md](../spec.md) hold.

## Context & Constraints

- **Plan**: [plan.md](../plan.md) IC-01. **Research**: [research.md](../research.md) D1, D2. **Charter**: `.kittify/charter/charter.md`.
- **Reuse the landed digest primitive — do NOT re-author it (C-004)**:
  `from charter.offering.packs.pack_clean_digest import clean_tree_digest` and
  `from kernel.pack_tiers import BUILT_IN`. Call `clean_tree_digest(pack_root, level=BUILT_IN)`.
  It is a declared-file-set, LF-normalized digest (never `rglob`), so it is immune to a stray
  `assets/__pycache__/*.pyc` in a polluted worktree — this is exactly why it, not `snapshot_sha256`,
  is the gate authority (D2: the live re-seed saw `snapshot_sha256` = `9c96178e` over a polluted
  worktree while the clean tree is `99e5e97c`).
- **Direction (document plainly — NFR/clarity, avoids the IC-01 risk)**: core's
  `packs/built-in.source.yaml` records **open-packs → core** ("which open-packs SHA core vendored
  from"). open-packs' *own* `built-in.source.yaml` records the OPPOSITE anchor (**core → open-packs**).
  Same schema shape, opposite provenance direction. The module docstring and the lockfile's own
  header comment MUST state this, so a future reader never conflates the two files.
- **Lockfile sits OUTSIDE the digested tree (C-006)**: it is at `packs/built-in.source.yaml`, a
  sibling of `packs/built-in/`. `clean_tree_digest` enumerates only files *under* `packs/built-in/`,
  so the lockfile is never part of what it hashes. Do NOT place it inside `packs/built-in/`.
- **Pin by SHA, never a tag (FR-002)**: the stored `commit` is a 40-hex SHA. A tag is only ever a
  resolution input; the model never persists a tag string in `commit`.
- **`requires_core` mirrors the vendored pack's `pack.yaml`**: it is a declared PEP 440 specifier
  (validated as a specifier at pack-descriptor load time). Core is currently `4.0.0rc8`, which
  satisfies `>=4.0.0rc7,<5`.
- **I/O style**: use `ruamel.yaml` (the repo's YAML dependency) for load/write, matching sibling
  pack YAML readers. Keep the model a thin, side-effect-free-where-possible dataclass/pydantic shape
  plus explicit `load`/`write` functions; cyclomatic complexity ≤15; declare `__all__` (this is
  under `src/charter/`, so the `__all__` + dead-symbol gate applies — every exported name needs a
  caller, so WP02 will import the loader/verifier).

## Branch Strategy

- **Strategy**: single_branch (direct in the write checkout; no lane worktree)
- **Planning base branch**: feat/builtin-revendor-pin-gate
- **Merge target branch**: feat/builtin-revendor-pin-gate (PR → main)

> These fields are populated/normalized by `spec-kitty agent mission finalize-tasks`.

## Subtasks & Detailed Guidance

### Subtask T001 – Round-trip digest test (RED before the model/lockfile)

- **Purpose**: ADR `2026-07-17-1` red-first. Prove the provenance round-trip through the real
  primitive before the model exists (FR-001, SC-002 foundation).
- **Steps**:
  1. In `tests/charter_offering/test_built_in_pin.py`, write a test that loads
     `packs/built-in.source.yaml` via the new `built_in_pin` loader, recomputes
     `clean_tree_digest(<repo>/packs/built-in, level=BUILT_IN)`, and asserts it equals
     `pin.tree_digest.value`.
  2. Run it and CONFIRM IT IS RED on current code (no lockfile, no module yet). Record the red
     output (ImportError / FileNotFoundError is an acceptable first red; tighten it once T002/T003
     land so it reds on a *digest mismatch*, not just absence).
- **Files**: `tests/charter_offering/test_built_in_pin.py`
- **Parallel?**: No (precedes the model).
- **Notes**: Resolve the repo root from the test file location (mirror `test_packaging_parity.py`'s
  `REPO_ROOT = _THIS.parents[2]`). Do not hardcode an absolute path.

### Subtask T002 – `BuiltInPin` load/verify/write model

- **Purpose**: the pure lockfile model (FR-001, FR-002, NFR-002).
- **Steps**:
  1. Create `src/charter/offering/packs/built_in_pin.py` with a frozen model carrying
     `repository: str`, `commit: str`, `tree_digest: {algorithm: str, value: str}`,
     `requires_core: str | None`, optional `snapshot_sha256: str | None`.
  2. `load_built_in_pin(path) -> BuiltInPin` (ruamel.yaml read, schema-validate; fail closed with a
     clear error on a missing/malformed field).
  3. `verify_built_in_pin(pin, pack_root) -> bool` (or a result object): recompute
     `clean_tree_digest(pack_root, level=BUILT_IN)` and compare to `pin.tree_digest.value`. Reject
     a `commit` that is not 40-hex (FR-002 guard — a tag string must never be accepted as `commit`).
  4. `write_built_in_pin(pin, path)` (ruamel.yaml write, stable key order, with the direction header
     comment).
  5. Module docstring states the open-packs→core direction and that `clean_tree_digest` (not
     `snapshot_sha256`) is the integrity authority. Declare `__all__`.
- **Files**: `src/charter/offering/packs/built_in_pin.py`
- **Parallel?**: No.

### Subtask T003 – Seed the real pin

- **Purpose**: the committed lockfile anchors real provenance (FR-001, US1-S1/S2).
- **Steps**:
  1. Write `packs/built-in.source.yaml` with:
     - `repository: git@github.com:spec-kitty/spec-kitty-open-packs.git`
     - `commit: 1c09592df5f55b5b2dd51bdd172d9e7349d2a159` (confirm it still equals `v0.1.0`
       dereferenced — `git ls-remote <url> 'refs/tags/v0.1.0^{}'`).
     - `tree_digest: {algorithm: sha256, value: <clean_tree_digest(packs/built-in, level=BUILT_IN)>}`
       — compute this against the *committed* tree in a clean checkout (run a sweep of stray
       `__pycache__` first to be safe, though the clean digest is pollution-immune by construction).
     - `requires_core:` the value the vendored built-in `pack.yaml` declares (expected
       `>=4.0.0rc7,<5`; read it from `packs/built-in/pack.yaml` rather than hardcoding blind).
     - A header comment stating the open-packs→core direction.
  2. Make T001 GREEN.
- **Files**: `packs/built-in.source.yaml`
- **Parallel?**: No (depends on T002).
- **Notes**: Compute the digest with the branch's own venv from a non-worktree dir (memory:
  "Corpus audit: use branch's own code"). Do not invent the digest value — compute it.

### Subtask T004 – Subtree-scoping, tag-vs-SHA, and direction coverage

- **Purpose**: FR-002, C-006, NFR-001.
- **Steps**:
  1. Add a test asserting the committed `commit` is a 40-hex SHA (FR-002), and that
     `load_built_in_pin` / `verify_built_in_pin` reject a lockfile whose `commit` is a tag-like
     string.
  2. Add a C-006 unit proof that `clean_tree_digest` is a function of `packs/built-in/` content only:
     construct a tmp pack-root fixture, compute the digest, add a file *outside* the built-in
     subtree (a sibling dir), recompute, and assert the digest is unchanged; then change a file
     *inside* and assert it moves. (This pins "only built-in subtree content moves the digest" at the
     primitive this mission relies on — US1-S5.)
  3. Add an NFR-001 determinism proof: compute the digest twice over the same tree (optionally once
     with a stray `__pycache__/*.pyc` present) and assert equality.
- **Files**: `tests/charter_offering/test_built_in_pin.py`
- **Parallel?**: No.

### Subtask T015 – SC-004 resolver-observable pinned-bytes probe (+ positive control)

- **Purpose**: SC-004 — the consumer-observable guarantee that `resolve_pack_root("built-in")`
  resolves to the pinned bytes. This is distinct from T001's SC-002 round-trip (which digests the
  **direct** `<repo>/packs/built-in` path): T015 goes **through the resolver**, the surface a
  consumer actually sees.
- **Steps**:
  1. Add a test asserting
     `clean_tree_digest(resolve_pack_root("built-in"), level=BUILT_IN) == load_built_in_pin(...).tree_digest.value`
     (import `resolve_pack_root` from `charter.offering.pack_paths`, `BUILT_IN` from
     `kernel.pack_tiers`; `clean_tree_digest`'s `level` is keyword-only).
  2. **Positive control (SC-004 is `no-op passable: yes`, so this is mandatory):** point the resolver
     at a deliberately mutated tree (monkeypatch `SPEC_KITTY_PACKS_ROOT`, or `resolve_pack_root`, to a
     tmp `packs/built-in` with one edited file) and assert the probe goes **red** — proving the probe
     can *see* a changed resolution and is not vacuous.
- **Files**: `tests/charter_offering/test_built_in_pin.py`
- **Parallel?**: No.

## Test Strategy

- Round-trip digest test RED before model/lockfile, GREEN after T003 (ATDD).
- FR-002 SHA-not-tag guard; C-006 subtree-scoping proof; NFR-001 determinism proof.
- Targeted surface: `tests/charter_offering/test_built_in_pin.py` plus the owning subsystem tree
  `tests/charter_offering/` and `tests/charter/` (both own `src/charter/offering/**` per charter
  Testing Requirements). Record commands + pass/fail counts in the PR. NO full `tests/architectural/`
  sweep (`NO_FULL_HEAVY_SUITES_IN_MISSION`).

## Risks & Mitigations

- **Direction confusion with open-packs' own file (IC-01 risk)**: document the open-packs→core
  direction in the module docstring and the lockfile header.
- **Lockfile inside the digested tree**: keep it at `packs/built-in.source.yaml`, a sibling — never
  under `packs/built-in/`.
- **Invented digest**: compute `clean_tree_digest` for real against the committed tree; a wrong seed
  value reds T001 (deliberately).
- **Dead-symbol gate**: `src/charter/` modules need `__all__` with real callers; WP02 imports the
  loader/verifier, so keep the public surface minimal and consumed.

## Review Guidance

- Confirm `packs/built-in.source.yaml` is a sibling of (not inside) `packs/built-in/`.
- Confirm `commit` is a 40-hex SHA equal to `v0.1.0` dereferenced; no tag persisted.
- Confirm the digest was computed with `clean_tree_digest(..., level=BUILT_IN)`, not `snapshot_sha256`.
- Confirm the module reuses the landed primitive and does not re-author digest logic.
- Confirm the direction note is present.

## Progress & Status

Progress/history/status live in the status event log — do not hand-edit here.
- Record a note: `spec-kitty agent tasks add-history WP01 --note "<what you did>"`
- Change status: `spec-kitty agent tasks move-task WP01 --to <status>`
- View: `spec-kitty agent tasks status`
