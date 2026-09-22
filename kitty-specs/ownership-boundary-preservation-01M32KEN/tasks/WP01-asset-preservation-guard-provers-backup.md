---
work_package_id: WP01
title: Asset-preservation guard, provers, and backup core
dependencies: []
requirement_refs:
- FR-001
- FR-002
- FR-003
- FR-007
- FR-008
- FR-009
- NFR-001
- NFR-003
- NFR-005
planning_base_branch: fix/ownership-boundary-preservation
merge_target_branch: fix/ownership-boundary-preservation
branch_strategy: Planning artifacts for this mission were generated on fix/ownership-boundary-preservation. During /spec-kitty.implement this WP may branch from a dependency-specific base, but completed changes must merge back into fix/ownership-boundary-preservation unless the human explicitly redirects the landing branch.
base_branch: kitty/mission-ownership-boundary-preservation-01M32KEN
base_commit: daad04b7bea4fe49274caeef6c4cc4af5ea3cbe5
created_at: '2026-09-22T05:34:32.442209+00:00'
subtasks:
- T001
- T002
- T003
- T004
- T005
- T006
- T007
phase: 'Phase 1 - Foundation: shared asset-preservation guard'
history:
- at: '{{TIMESTAMP}}'
  actor: system
  action: Prompt generated via /spec-kitty.tasks
agent_profile: python-pedro
authoritative_surface: src/specify_cli/asset_preservation/
create_intent:
- src/specify_cli/asset_preservation/__init__.py
- src/specify_cli/asset_preservation/guard.py
- src/specify_cli/asset_preservation/provers.py
- src/specify_cli/asset_preservation/backup.py
- tests/specify_cli/asset_preservation/test_guard.py
- tests/specify_cli/asset_preservation/test_provers.py
execution_mode: code_change
model: ''
owned_files:
- src/specify_cli/asset_preservation/**
- src/specify_cli/skills/installer.py
- tests/specify_cli/asset_preservation/**
role: implementer
tags: []
task_type: implement
tracker_refs: []
---

# Work Package Prompt: WP01 – Asset-preservation guard, provers, and backup core

## ⚡ Do This First: Load Agent Profile

Use the `/ad-hoc-profile-load` skill to load the agent profile specified in the frontmatter (or any user-defined profile), and behave according to its guidance before parsing the rest of this prompt.

- **Profile**: `python-pedro`
- **Role**: `implementer`
- **Agent/tool**: `claude`

If no profile is specified, run `spec-kitty agent profile list` and select the best match for this work package's `task_type` and `authoritative_surface`.

---

## ⚠️ Binding post-tasks corrections (supersede any conflicting text below)

The **guard performs the removal itself** on `owned=True` (`shutil.rmtree` when `is_tree`, else
`unlink`); it does NOT return and let the caller delete. The raw destructive literal lives ONLY
inside the guard (the chokepoint). See [contract](../contracts/ownership-guard-contract.md) C1
invariant 0 + [data-model](../data-model.md) "Decision surface + backup". This is load-bearing for
WP09's non-vacuity, so build the guard this way from the start. `CanonicalContentProver` scans for
the single `<!-- spec-kitty-command-version:` marker (no `# …` syntax).

## Objectives & Success Criteria

Build the single shared decision surface `src/specify_cli/asset_preservation/` that every routing
WP (WP02–WP08) imports and that the gate (WP09) asserts is called. This is the **foundation** —
it blocks all downstream lanes.

- A new package `src/specify_cli/asset_preservation/` with `__init__.py`, `guard.py`,
  `provers.py`, `backup.py`, declaring `__all__` (C-007).
- Public API exactly:
  `guard_destructive_removal(path, project_path, *, prover, is_tree=False, backup_parent=None, dry_run=False) -> OwnershipVerdict`
  plus `OwnershipVerdict`, `OwnershipProver`, `ManifestProver`, `ManagedPathProver`,
  `CanonicalContentProver`, `AnyProver`.
- Four provers, each provable in BOTH directions (owned + unprovable).
- Copy-only backup core extracted from `skills.installer._archive_existing_path`; the skills
  wrapper delegates to it (single authority — no duplicate).
- **Success**: `pytest tests/specify_cli/asset_preservation -q` green; `mypy --strict`, `ruff
  check`, `ruff format --check` clean over the new package with zero new suppressions (NFR-005).
- **Layering (NFR-003)**: imports down to `kernel.atomic`; reuses `template`/`skills`/
  `manifest_store`/`tool_surface` peers; nothing in `kernel`/`charter` imports this package.
  `tests/architectural/test_layer_rules.py` stays green.

## Context & Constraints

- **Charter**: `.kittify/charter/charter.md` L463–479 (Ownership Boundaries for Mutating Flows) —
  name heuristics are never proof (L470); unprovable ⇒ preserve + warn (L472); document the
  ownership proof in code (L479). Load doctrine via `spec-kitty charter context --action implement`.
- **Design**: [plan.md](../plan.md) · [data-model.md](../data-model.md) ·
  [contracts/ownership-guard-contract.md](../contracts/ownership-guard-contract.md) (C1 invariants) ·
  [research.md](../research.md) (Decisions 1–3, 6) · [quickstart.md](../quickstart.md).
- **Requirement refs**: FR-001, FR-002, FR-003, FR-007, FR-008, FR-009, NFR-001, NFR-003, NFR-005.
- **Constraints**: C-002 (reuse canonical primitives, honestly scoped — do NOT force skills-manifest
  machinery onto manifest-less sites); C-003 (distinct name `asset_preservation`, never
  `specify_cli/ownership/`); C-004 (no `--feature`; no code in `specify_cli/__init__.py`).
- **Reuse anchors** (verified on base): `OwnershipProof` at
  `src/specify_cli/tool_surface/operations.py:93` (kinds `manifest`/`managed_path`/
  `canonical_content`, fields `kind`/`reference`); `_replacement_is_owned` at
  `src/specify_cli/skills/installer.py:187` (`ManagedSkillManifest`-typed;
  `content_hash == "sha256:"+sha256`, `delivery_mode == DELIVERY_COPY`); `_archive_existing_path`
  at `installer.py:148`; `manifest_store.fingerprint_file` at
  `src/specify_cli/skills/manifest_store.py:409` (bare 64-hex) + `ManifestEntry`
  (`path`/`content_hash`/`agents`, no `delivery_mode`); `back_up_operator_subtrees` +
  `_allocate_backup_dir` in `src/specify_cli/template/manager.py`; `kernel.atomic.atomic_write`.
- **Complexity ceiling ≤15** — split guard/provers/backup into small functions (C901/S3776).

## Branch Strategy

- **Strategy**: shared-lane
- **Planning base branch**: fix/ownership-boundary-preservation
- **Merge target branch**: fix/ownership-boundary-preservation

> These fields are populated automatically by `spec-kitty agent mission tasks`.
> Do NOT change them manually unless you are certain the branch topology has changed.

## Subtasks & Detailed Guidance

### Subtask T001 – `OwnershipVerdict` + `OwnershipProver` protocol + package skeleton

- **Purpose**: Establish the value types and the package public surface every other subtask and WP
  builds on.
- **Steps**:
  1. Create `src/specify_cli/asset_preservation/__init__.py` re-exporting the public API and
     declaring `__all__` (C-007): `guard_destructive_removal`, `OwnershipVerdict`,
     `OwnershipProver`, `ManifestProver`, `ManagedPathProver`, `CanonicalContentProver`,
     `AnyProver`.
  2. In `provers.py`, define `OwnershipProver` as a `typing.Protocol`:
     `def prove(self, path: Path, project_path: Path) -> OwnershipProof | None: ...`.
  3. Define `OwnershipVerdict` as a frozen dataclass: `owned: bool`, `proof: OwnershipProof | None`,
     `preserved_path: Path | None`, `backup_path: Path | None`, `reason: str`, `diagnostic: str`.
  4. REUSE `OwnershipProof` from `tool_surface.operations` — do NOT re-declare it.
- **Files**: `asset_preservation/__init__.py`, `asset_preservation/provers.py` (type stubs first).
- **Notes**: `mypy --strict` clean; no import cycle (`asset_preservation` imports from
  `tool_surface`, not the reverse).

### Subtask T002 – `ManifestProver` (two predicates)

- **Purpose**: Prove ownership for manifest-tracked skills/commands. The two manifest shapes are
  structurally different, so two internal predicates.
- **Steps**:
  1. **Managed-skills predicate**: reuse `skills.installer._replacement_is_owned`
     (`ManagedSkillManifest`; `content_hash == "sha256:"+sha256(bytes)`, `delivery_mode == "copy"`,
     installed-path derivation). Return an `OwnershipProof(kind="manifest", reference=<entry ref>)`
     on a match, else `None`.
  2. **Command-skills predicate**: mirror `manifest_store.fingerprint_file(path) ==
     entry.content_hash` (bare 64-hex; `ManifestEntry` has `path`/`content_hash`/`agents`, no
     `delivery_mode`/`installed_path`). Return a `manifest` proof on match.
  3. **Directory rule**: a directory is owned ONLY if every tracked member matches its manifest
     entry AND there are no untracked members. Any untracked member ⇒ `None` (preserve).
  4. Accept which manifest(s) to check via constructor data so a site can check managed, command,
     or both.
- **Files**: `asset_preservation/provers.py`.
- **Edge cases**: missing/corrupt manifest ⇒ `None` (fail closed); symlink ⇒ `None`; mixed dir ⇒
  `None`.

### Subtask T003 – `ManagedPathProver`

- **Purpose**: Prove ownership for manifest-less locations that are package-managed or regenerable
  this run (e.g. `.kittify/templates/`, `.scratch`, `.resolved-*`, `.merged-*`).
- **Steps**:
  1. Construct with an explicit contract: a path list (package-managed regenerable locations) plus
     a run-scope set (paths this run created).
  2. `prove` returns a `managed_path` proof iff the path is a package-managed regenerable location
     OR was created by this run; else `None`.
  3. The LEGACY tier `.kittify/command-templates/` is operator-authorable ⇒ **never owned-by-name**
     ⇒ always `None` (this is what preserves the #4861 user template in WP03).
- **Files**: `asset_preservation/provers.py`.
- **Notes**: name/basename equality alone never yields owned (contract C1.2).

### Subtask T004 – `CanonicalContentProver` (data-injected, one code path)

- **Purpose**: Prove ownership by content — a version marker or a byte-match against shipped
  canonical bytes — with NO per-format branching in `prove()`.
- **Steps**:
  1. Constructor DATA: `marker_syntaxes` (the comment forms wrapping
     `spec-kitty-command-version:` — both `<!-- … -->` for `.md` and `# …` for `.toml`);
     `canonical_bytes` (optional shipped-canonical bytes/digest to byte-match); a head-window line
     count (default 15).
  2. `prove` (ONE path): owned iff the file carries the version marker in ANY configured syntax
     within the head window, OR byte-matches a supplied canonical. No marker + no canonical ⇒
     `None` (unprovable ⇒ preserve).
  3. Model on `m_3_1_2_globalize_commands._is_generated_file` (marker) and
     `m_2_0_7._matches_package_default` (byte-match) — the already-correct exemplars.
- **Files**: `asset_preservation/provers.py`.
- **Edge cases**: marker past the head window ⇒ not found (documented; command-toml sites use
  `AnyProver` with a manifest predicate first — WP06); binary/unreadable ⇒ `None`.

### Subtask T005 – `AnyProver` ordered composite

- **Purpose**: Express dual-signal sites as guard-owned data, not call-site branching.
- **Steps**:
  1. `AnyProver([p1, p2, …])`: `prove` returns the FIRST non-`None` proof; `None` if all abstain.
  2. Used by #4 (`manifest`→`canonical_content`, WP06) and #9 (`canonical_content`→`managed_path`,
     WP04).
- **Files**: `asset_preservation/provers.py`.
- **Notes**: preserve prover order (short-circuit on first proof).

### Subtask T006 – `guard.py` decision surface + `backup.py` copy-only core

- **Purpose**: The prove-or-preserve/archive decision, and the single-authority verbatim writer.
- **Steps**:
  1. `guard_destructive_removal(path, project_path, *, prover, backup_parent=None, dry_run=False)`:
     run `prover.prove`. **owned** ⇒ `OwnershipVerdict(owned=True, proof=…)`; the CALLER performs
     its own delete/prune (the guard does not change each migration's delete mechanics).
     **unprovable** ⇒ preserve in place when the parent survives; else archive verbatim via
     `backup_parent`; return `owned=False` + a diagnostic (path + reason + backup location).
     **Never deletes.** `dry_run` computes the verdict without writing.
  2. `backup_parent` is MANDATORY for archive-when-parent-removed sites; it must resolve OUTSIDE the
     doomed tree so the backup survives the caller's `rmtree` (contract C1.4).
  3. `backup.py`: extract a **copy-only** verbatim writer (~13 lines: symlink-or-`O_EXCL` write +
     `chmod_fd` + `os.utime`, depending only on `FileState`/`chmod_fd`/stdlib) out of
     `skills.installer._archive_existing_path`. **EXCLUDE the trailing `_safe_unlink(dest)`** (it is
     redundant when the parent is removed and wrong for in-place preserve). Make
     `skills.installer._archive_existing_path` DELEGATE to this extracted core (single authority —
     no duplicated copy logic). Dir-granular archiving reuses
     `template.manager.back_up_operator_subtrees` + `_allocate_backup_dir`.
- **Files**: `asset_preservation/guard.py`, `asset_preservation/backup.py`; edit
  `src/specify_cli/skills/installer.py` ONLY to delegate `_archive_existing_path` to the new core.
- **Notes**: keep each function ≤15 complexity; `atomic_write` for any rewrite.

### Subtask T007 – Unit tests (both directions, fail-closed, idempotent)

- **Purpose**: Prove the guard and every prover behave in BOTH directions and fail closed.
- **Steps** — cover:
  1. Each prover: an owned case (proof returned) AND an unprovable case (`None`).
     `ManifestProver`: managed + command shapes, drifted hash ⇒ `None`, mixed dir ⇒ `None`.
     `ManagedPathProver`: regenerable ⇒ owned, `command-templates` ⇒ `None`.
     `CanonicalContentProver`: marker present (both syntaxes) ⇒ owned, byte-match ⇒ owned, neither
     ⇒ `None`. `AnyProver`: first-proof short-circuit; all-abstain ⇒ `None`.
  2. `guard_destructive_removal`: preserve-in-place (parent survives), archive (parent removed, via
     `backup_parent`, byte-identical + mode/mtime where the platform allows), owned verdict.
  3. Fail-closed: prover exception, corrupt/unreadable manifest, symlink target, mixed dir ⇒
     `owned=False`.
  4. Idempotent: a second run over an already-preserved/already-owned tree ⇒ same verdict, no extra
     mutation.
  5. Diagnostic completeness: preserving verdict names path + reason + backup location when archived.
- **Files**: `tests/specify_cli/asset_preservation/test_provers.py`,
  `tests/specify_cli/asset_preservation/test_guard.py`.

## Test Strategy

- New unit tests live under `tests/specify_cli/asset_preservation/` (single home; avoids overlap
  with WP03 skills tests).
- Commands:
  ```bash
  PWHEADLESS=1 .venv/bin/python -m pytest tests/specify_cli/asset_preservation -q
  uv run --frozen ruff check src/specify_cli/asset_preservation tests/specify_cli/asset_preservation
  uv run --frozen ruff format --check src/specify_cli/asset_preservation tests/specify_cli/asset_preservation
  uv run --frozen mypy --strict src/specify_cli/asset_preservation
  ```
- This WP owns typed sources — the `mypy --strict` run is mandatory and gates the WP in addition to
  the test runner.
- Also run the skills suite to confirm the `_archive_existing_path` delegation did not regress:
  `pytest tests/skills -q` (or the module's mirror).

## Risks & Mitigations

- **Prover re-fragmentation / boundary leak** (forcing skills machinery onto manifest-less sites) —
  mitigated by the per-signal prover split + data-injected `CanonicalContentProver` + `AnyProver`.
- **Duplicated backup authority** — mitigated by extracting the copy-only core and delegating the
  skills wrapper to it (contract C1.5).
- **Import cycle** — `provers.ManifestProver` imports `skills.installer._replacement_is_owned`, and
  `skills.installer` must delegate to `asset_preservation.backup`. To avoid a package-init cycle,
  have `skills.installer` import the copy-only core with a **function-local import** (inside
  `_archive_existing_path`), not a module-level one; keep `asset_preservation/__init__` light.
  `ManifestProver`'s import of `_replacement_is_owned` may likewise be function-local. Verify
  `python -c "import specify_cli.skills.installer, specify_cli.asset_preservation"` both orders.
- **Layer violation** — keep judgement in `specify_cli`; only mechanical write/backup touches
  `kernel.atomic`.
- **Complexity >15** — split lookup/build/emit phases into helpers.

## Review Guidance

- Confirm the public API signature matches the contract exactly and `__all__` is declared.
- Confirm `_archive_existing_path` now delegates to the extracted copy-only core (no duplicate
  copy logic) and that the trailing unlink was NOT carried into the core.
- Confirm each prover has BOTH-direction tests and fail-closed cases; confirm idempotency.
- Confirm `mypy --strict` + ruff + ruff format all clean with zero new suppressions.
- Confirm `tests/architectural/test_layer_rules.py` stays green (no new `kernel`/`charter` import
  of this package).

## Activity Log

> **CRITICAL**: Activity log entries MUST be in chronological order (oldest first, newest last).

- {{TIMESTAMP}} – system – Prompt created.
