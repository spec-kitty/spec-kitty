# Tasks: User-content preservation for mutating flows

**Mission**: `user-content-preservation-01M3549Q` | **Branch**: `fix/user-content-preservation` → merge target `fix/user-content-preservation` → PR to upstream `main`
**Spec**: [spec.md](./spec.md) · **Plan**: [plan.md](./plan.md) · **Contract**: [contracts/preservation-contract.md](./contracts/preservation-contract.md)

8 work packages. Model discipline: implement = sonnet (python-pedro, profile-loaded), review = opus (reviewer-renata). Every defect WP lands a RED-on-base `@pytest.mark.regression` repro (in `tests/regressions/test_issue_NNNN_*.py`) BEFORE the fix, then GREEN on the fix. Owned files are disjoint per WP so lanes do not collapse.

## Subtask Index

| ID | Description | WP | Parallel |
|----|-------------|----|----------|
| T001 | Add `backup_before_overwrite(path)->Path` to asset_preservation/backup.py | WP01 | |
| T002 | Symlink-aware capture (os.readlink, no silent deref) | WP01 | |
| T003 | Unit tests: byte-identity, mode/mtime, O_EXCL, symlink, broken link | WP01 | |
| T004 | [RED] repros: remove/sync preserve user file, mixed-dir preserve, manifest byte-identical, owned-delete anchors | WP02 | |
| T005 | Route `_remove_project_agent_surface` through guard (dir-level, ManifestProver); retire 3 literals | WP02 | |
| T006 | Verdict-driven return + messaging (no false "Removed" on preserve) | WP02 | |
| T007 | sync must not rewrite pinned command-skills-manifest.json; refresh behind explicit opt-in; --json enumerates mutations | WP02 | |
| T008 | AGENT_DIRS-table generality (not claude-special-cased) | WP02 | |
| T009 | [RED] repro: foreign hook backed up + surfaced; signed hook replaced; no-hook unchanged | WP03 | |
| T010 | Foreign-hook signature detection in hook_installer.install | WP03 | |
| T011 | backup_before_overwrite + surface path; stop swallowing in install_commit_guard | WP03 | |
| T012 | Caller wiring in implement_support surfaces the warning | WP03 | |
| T013 | [RED] repro: brief present + no sidecar → refuse w/o --force (explicit AND --auto), byte-identical | WP04 | [P] |
| T014 | Drop `and _source_path.exists()` at intake.py :296 and :156 | WP04 | [P] |
| T015 | Message + `--force` path preserved | WP04 | [P] |
| T016 | [RED] repro: mojibake, binary skip, CRLF preserve, honest "Fixed" | WP05 | [P] |
| T017 | Classify text vs binary by content sniff, not `.md` extension | WP05 | [P] |
| T018 | Scope fallback decode to offending bytes / refuse with offsets | WP05 | [P] |
| T019 | Preserve line endings; report "Fixed" only on faithful repair | WP05 | [P] |
| T020 | [RED] repro: frontmatter-only cycle/self-ref/unknown-WP → reject; valid acyclic succeeds | WP06 | [P] |
| T021 | Validate effective persisted graph (reuse mission_finalize validator) | WP06 | [P] |
| T022 | No status seeded on rejection; payload == persisted graph | WP06 | [P] |
| T023 | [RED] repro: partially-staged file → index+stash byte-identical across callers; upgrade propagates | WP07 | [P] |
| T024 | safe_commit via temp index / `commit --only` (never touch operator index) | WP07 | [P] |
| T025 | Narrow upgrade/autocommit except → propagate SafeCommitRecoveryFailed; render in upgrade.py | WP07 | [P] |
| T026 | Verify all callers commit exactly `paths` | WP07 | [P] |
| T027 | [RED] self-mutation: planted un-routed op fails gate; narrowed routed set fails | WP08 | |
| T028 | Widen census: config.py in `_module_set` + `_ROUTED_MODULES` (set-equality) + `:142` rmdir allowlist | WP08 | |

## Work Packages

### WP01 — Shared overwrite-backup helper (enabler)
**Goal**: One symlink-aware `backup_before_overwrite(path)->Path` in `asset_preservation/backup.py` (single backup-naming authority) for the hook flow to reuse.
**Priority**: P2 (enabler) · **Depends on**: none · **Subtasks**: T001–T003
**Independent test**: unit tests over the helper (byte-identity, mode/mtime, O_EXCL collision, symlink, broken link).
**Prompt**: [tasks/WP01-overwrite-backup-helper.md](./tasks/WP01-overwrite-backup-helper.md)

### WP02 — Ownership-gate agent command-surface removal + manifest pins (#4907 P0, #2691)
**Goal**: Route `_remove_project_agent_surface` through the existing guard (dir-level) for both `remove` and `sync` orphan sweep; verdict-driven messaging; stop `sync` rewriting repository-pinned manifests.
**Priority**: P1 (release-blocker) · **Depends on**: none · **Subtasks**: T004–T008
**Independent test**: `remove`/`sync` preserve a user command file + report it; mixed-dir preserved whole; pinned manifest byte-identical; owned-delete still occurs.
**Prompt**: [tasks/WP02-config-removal-ownership-gate.md](./tasks/WP02-config-removal-ownership-gate.md)

### WP03 — Preserve a foreign `.git/hooks/pre-commit` before install (#4895 P0)
**Goal**: `implement` backs up a foreign hook (signature check) via the WP01 helper, installs, and surfaces the backup path; a signed hook is replaced as today.
**Priority**: P1 (release-blocker) · **Depends on**: WP01 · **Subtasks**: T009–T012
**Independent test**: foreign hook backed up + path printed; user hook restorable; signed hook replaced.
**Prompt**: [tasks/WP03-pre-commit-hook-preservation.md](./tasks/WP03-pre-commit-hook-preservation.md)

### WP04 — intake brief overwrite gate keys on existence (#4910)
**Goal**: Both `intake` entry points refuse to overwrite an existing brief without `--force`; no backup.
**Priority**: P2 · **Depends on**: none · **Subtasks**: T013–T015
**Independent test**: brief present + no sidecar → refuse (explicit + `--auto`), byte-identical.
**Prompt**: [tasks/WP04-intake-brief-overwrite-gate.md](./tasks/WP04-intake-brief-overwrite-gate.md)

### WP05 — validate-encoding `--fix` repairs faithfully (#4896)
**Goal**: Content-sniff binaries, byte-scoped decode, line-ending preservation, honest "Fixed".
**Priority**: P2 · **Depends on**: none · **Subtasks**: T016–T019
**Independent test**: mojibake avoided, binary skipped, CRLF preserved, "Fixed" only on faithful repair.
**Prompt**: [tasks/WP05-validate-encoding-faithful-fix.md](./tasks/WP05-validate-encoding-faithful-fix.md)

### WP06 — Legacy finalize validates the persisted graph (#4890)
**Goal**: `agent tasks finalize-tasks` validates the effective persisted dependency graph (cycles/self-refs/unknown-WP), reusing the canonical validator; no status seeded on rejection.
**Priority**: P2 · **Depends on**: none · **Subtasks**: T020–T022
**Independent test**: frontmatter-only cycle/self-ref/unknown-WP rejected; valid acyclic succeeds and payload == persisted graph.
**Prompt**: [tasks/WP06-legacy-finalize-effective-graph.md](./tasks/WP06-legacy-finalize-effective-graph.md)

### WP07 — safe_commit never wipes the operator's index (#4888)
**Goal**: `safe_commit` commits via a temporary index so the operator's index/worktree is untouched; `upgrade` propagates `SafeCommitRecoveryFailed` instead of a misleading exit-0 skip.
**Priority**: P2 (highest regression risk — hot shared helper) · **Depends on**: none · **Subtasks**: T023–T026
**Independent test**: with an unrelated file partially staged, index + stash byte-identical across all callers; forced-failure path surfaces stash ref + SHA.
**Prompt**: [tasks/WP07-safe-commit-index-preservation.md](./tasks/WP07-safe-commit-index-preservation.md)

### WP08 — Census closure: widen the routing gate to config.py (FR-013)
**Goal**: Widen `test_mutation_ownership_routing.py` to cover `cli/commands/agent/config.py` (3 synchronized edits) so the removal preservation cannot silently regress.
**Priority**: P3 (by-construction backstop) · **Depends on**: WP02 · **Subtasks**: T027–T028
**Independent test**: planted un-routed op fails the gate; narrowed routed set fails (self-mutation both directions).
**Prompt**: [tasks/WP08-census-widen-config.md](./tasks/WP08-census-widen-config.md)

## Dependency graph

```
WP01 ──► WP03
WP02 ──► WP08
WP04  WP05  WP06  WP07   (independent, parallel)
```

## MVP / ordering

The two P0 release-blockers — **WP02** (#4907) and **WP03** (#4895, after the tiny WP01) — land first. The P1 lanes (WP04–WP07) run in parallel. **WP08** (census closure) lands last, after WP02 is routed and literal-free.
