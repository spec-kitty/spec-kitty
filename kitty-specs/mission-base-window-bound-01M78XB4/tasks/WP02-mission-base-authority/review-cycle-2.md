---
affected_files: []
cycle_number: 2
mission_slug: mission-base-window-bound-01M78XB4
reproduction_command:
reviewed_at: '2026-11-12T23:20:47Z'
reviewer_agent: claude::reviewer-renata
wp_id: WP02
---

# WP02 review cycle 2 (reviewer-renata) -- changes requested

Cycle-1 items: (2) layering FIXED (no module under `src/specify_cli/core/` imports `specify_cli.consolidation`; `record_mission_base_sha` lives in `specify_cli.mission_metadata`); (3) `--no-patch` FIXED; (4) docstring FIXED. (1) the rename case is now fail-closed and tested, but the fix over-reaches and breaks the derivation on every real Mission. Blocking.

Passing: 237 targeted (test_mission_base, test_mission_base_recording, test_mission_creation_family, test_layer_rules, test_mission_metadata); fast tier 3017 passed / 7 skipped; ruff, format, mypy clean on the 7 changed files.

**Issue 1 (blocking): `-C --find-copies-harder` pairs every real scaffold with another Mission's files, so the derived base is always UNAVAILABLE.**
`--find-copies-harder` makes every unchanged file in the tree a copy source. A Mission scaffold always looks like a copy of an older Mission: `tasks/.gitkeep` is empty, so it pairs `C100` with any other empty `.gitkeep`, and `tasks/README.md`, `checklists/requirements.md` and `issue-matrix.json` pair at 55-83%. Run on this repository, with no `meta.json`:
```
resolve_mission_base(repo, None, mission_branch="kitty/mission-mission-base-window-bound-01M78XB4", mission_slug="mission-base-window-bound-01M78XB4")
  -> UNAVAILABLE "... by a rename or copy from kitty-specs/008-unified-python-cli/tasks/.gitkeep"
resolve_mission_base(repo, None, mission_branch="HEAD", mission_slug="next-lifecycle-integrity-01M77BWP")
  -> UNAVAILABLE "... copy from kitty-specs/typed-context-diagnostics-01M5ZA6Q/checklists/requirements.md"
resolve_mission_base(repo, None, mission_branch="HEAD", mission_slug="lane-code-verification-01M76AC0")
  -> UNAVAILABLE "... copy from kitty-specs/doctrine-built-in-seam-consolidation-01KYW3TX/acceptance-matrix.json"
```
All three are plain `agent mission create` scaffolds, so the derived step (the only one that covers Missions created before this WP) never yields a base. The unit tests miss this because their repositories hold no other Mission.
It is also slow: the full-tree copy search took 0.6 s, 3.9 s and 3.7 s per commit here (about 40k tracked files), and the three calls above took 9 s together. That is not acceptable on a consolidation path.

Fix: detect renames only. A rename needs the source to be deleted in the same commit, which is exactly the cycle-1 case:
`git diff --no-ext-diff --name-status -z -M -l0 --diff-filter=R <parent> <commit>`
On the three real scaffolds above it reports 0 renames in about 6 ms each. On the cycle-1 probe (`git mv kitty-specs/old kitty-specs/new`) it reports `R100 kitty-specs/old/spec.md -> kitty-specs/new/spec.md`. The `drafts/` -> `kitty-specs/<slug>/` test still holds.
- Add a regression test whose repository already holds another Mission (an empty `tasks/.gitkeep` plus a `tasks/README.md` like the new one), and assert the new Mission still DERIVES.
- Drop `test_mission_dir_arrived_by_copy_is_unavailable`, or rework it: a copy that leaves the source in place (`cp -r old <slug>`) cannot be told apart from an ordinary scaffold that resembles an older Mission. Record it, together with a move under the 50% similarity threshold, as a named residual in the module docstring ("the derivation follows git's rename detection; a copy, or a move edited past the similarity threshold, is not detected").
- Update the NFR-002 cost note to say the derived case uses a rename-only diff.

Anti-pattern checklist: synthetic fixture FAIL (the copy fixture holds no other Mission, so it hid the false positive); silent empty return PASS; production fragility FAIL (issue 1); frozen surface, locked decision, shared-file ownership PASS.
