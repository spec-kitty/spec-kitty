# Tasks: Plugin bundle directory conformance

**Mission**: `plugin-bundle-directory-conformance-01M68ZVP`
**Issue**: spec-kitty/spec-kitty#6479
**Spec**: [spec.md](./spec.md) · **Plan**: [plan.md](./plan.md)
**Baseline**: `main` @ `dfe9efb0e8`

Work packages are reference lists, not checkboxes. Progress is recorded with
`spec-kitty agent tasks mark-status`, and the red test lands before its fix
(charter, ATDD-First Discipline).

---

## Phase 1 — Version projection and the shared Agent Plugins manifest

### WP01 — SemVer projection and the Agent Plugins 1.0.0 manifest

- **Prompt**: `tasks/WP01-version-projection-and-agent-plugins-manifest.md`
- **Summary**: Add the single PEP 440 → SemVer projection and rebuild the shared
  manifest payload as an Agent Plugins 1.0.0 document, so the Copilot and VS Code
  projections stop emitting `0.0.0`, `distribution_target` and no `$schema`.
- **Priority**: P1 · **Independent test**: project a Copilot and a VS Code bundle
  and assert the pinned `$schema` const, the closed key set and the SemVer version.
- **Subtasks**: T001 red test for the shared payload; T002 `to_semver` + unit
  tests; T003 `plugin_manifest_payload` rewrite and its call sites; T004 update
  the existing projection tests.
- **Requirements**: FR-003, FR-006, FR-007, SC-001
- **Depends on**: none
- **Risks**: the version is read from installed metadata; the test must not
  assume a specific package version, only SemVer shape plus a known mapping case.

---

## Phase 2 — Claude and Codex bundles

### WP02 — Claude bundle reduction and Codex directory conformance

- **Prompt**: `tasks/WP02-claude-and-codex-directory-conformance.md`
- **Summary**: Remove the Claude top-level `bin/` and the redundant hooks
  pointer, add the shared links/license fields to the Claude manifest, and fill
  the Codex manifest to its pinned limits — shipping the square brand asset the
  manifest declares.
- **Priority**: P1 · **Independent test**: build both targets and assert the tree
  shape, every field limit and that each declared image resolves inside the bundle.
- **Subtasks**: T005 red tests through both build entry points; T006 delete the
  wrapper staging and the module; T007 Claude manifest links + hooks pointer;
  T008 Codex manifest fields, guard and asset; T009 update existing expectations
  and the packaging artifact glob.
- **Requirements**: FR-001, FR-002, FR-003, FR-004, FR-005, FR-008, SC-002, SC-003, SC-004
- **Depends on**: WP01 (uses the SemVer projection)
- **Risks**: existing tests assert the wrapper's presence; each changed assertion
  is replaced with one that pins the new required shape, never deleted for
  convenience.

---

## Phase 3 — Documentation and changelog

### WP03 — Changelog and the Claude install guide

- **Prompt**: `tasks/WP03-changelog-and-install-guide.md`
- **Summary**: Record the user-facing change under `[Unreleased]` and remove the
  install guide's claims about a bundled runtime wrapper.
- **Priority**: P2 · **Independent test**: the changelog entry names `(#6479)`
  with before/after under 1,200 characters, and the guide no longer documents a
  `bin/` wrapper.
- **Subtasks**: T010 changelog entry; T011 install-guide rewrite; T012 docs
  freshness check.
- **Requirements**: SC-001
- **Depends on**: WP01, WP02
- **Risks**: `CHANGELOG.md` is a symlink to `docs/changelog/CHANGELOG.md`; edit the
  target file and never replace the symlink.

---

## Dependency graph

```
WP01 ──▶ WP02 ──▶ WP03
```

All three work packages are independently reviewable; WP02 and WP03 build on the
projection and manifest work WP01 lands.
