---
work_package_id: WP01
title: Command-skill regeneration follow-ups
dependencies: []
requirement_refs:
- FR-001
- FR-002
- FR-003
- FR-004
- NFR-001
- NFR-002
- NFR-003
- NFR-004
- C-001
- C-002
- C-003
- SC-001
- SC-002
- SC-003
- SC-004
- SC-005
planning_base_branch: issue-6155-command-skill-regeneration-followups
merge_target_branch: issue-6155-command-skill-regeneration-followups
branch_strategy: Planning artifacts for this mission were generated on issue-6155-command-skill-regeneration-followups. During /spec-kitty.implement this WP may branch from a dependency-specific base, but completed changes must merge back into issue-6155-command-skill-regeneration-followups unless the human explicitly redirects the landing branch.
subtasks:
- T001
- T002
- T003
- T004
- T005
- T006
- T007
- T008
phase: Phase 1 - Follow-ups
history: []
agent_profile: implementer-ivan
authoritative_surface: src/specify_cli/skills/command_installer.py
create_intent:
- tests/specify_cli/skills/test_command_installer_derived_regeneration_702.py
execution_mode: code_change
model: ''
owned_files:
- src/specify_cli/skills/command_installer.py
- src/specify_cli/tool_surface/providers/command_skills.py
- src/specify_cli/tool_surface/repair.py
- src/specify_cli/cli/commands/upgrade.py
- src/specify_cli/cli/commands/init.py
- src/specify_cli/cli/commands/agent/config.py
- tests/specify_cli/skills/test_command_installer.py
- tests/specify_cli/skills/test_command_installer_derived_regeneration_702.py
- tests/specify_cli/tool_surface/providers/test_command_skills.py
- tests/specify_cli/cli/commands/test_upgrade_command_skill_drift.py
- tests/specify_cli/cli/commands/test_doctor_skills.py
- docs/changelog/CHANGELOG.md
role: implementer
tags: []
task_type: implement
tracker_refs:
- spec-kitty/spec-kitty#6155
---

# WP01 — Command-skill regeneration follow-ups

## HOLD

Implementation is held until PR **#6113** (closes #702) merges to `main`. #6113's
`_CommandBatch.preserve()` change is this WP's base. When #6113 has merged: `git fetch origin main`,
confirm it is present, rebase `issue-6155-command-skill-regeneration-followups` onto the updated
`main`, re-verify the EDIT line numbers, then begin.

## Goal

Deliver #6155's three follow-ups on the DERIVED/git-IGNORED command-skill projection
(`.agents/skills/spec-kitty.<command>/SKILL.md`):

1. **Item 1 (report)** — name each regenerated projection path once in human output and under
   `--json` `surface_repair`; silent for an in-sync projection or one equal to the recorded
   manifest hash; exit code and `UpgradeOutcome` kind unchanged.
2. **Item 2 (runtime gate)** — gate `preserve()`'s regenerate on the live DERIVED/IGNORED read
   of `shared_skills_projection` from `STATE_SURFACES`, else fall through to the existing consent
   branch (`overwrite_paths` → `consent_required`); revive `overwrite_paths` on the non-adopt
   path; reconcile the inline + provider comments.
3. **Item 3 (prune)** — `remove_entry()` prunes a retired command's drifted manifest-owned
   projection and its manifest entry on the same gate, still refusing a directory and never
   touching an unowned path.

Non-manifest / third-party paths under `.agents/skills/` stay untouched throughout (installer
NFR-002).

## Context / grounding

See `research/code-grounding.md` and `plan.md`. The change locus is two methods of
`src/specify_cli/skills/command_installer.py` (`preserve()`, `remove_entry()`) plus reporting
threaded through `InstallReport` (init/agent-config legs) and a new `DriftPolicySummary`
bucket (upgrade leg). `install_command()` only ever manages the DERIVED surface, so the gate is
safe there. `command_installer.py` does not yet import `specify_cli.state.contract` — item 2
adds that intra-layer import.

## Subtasks

- **T001** [P] — Red-first (item 2): non-DERIVED fall-through keeps `consent_required`; REAL
  class still regenerates; `overwrite_paths` consent overwrites on the fall-through. RED on base; commit first.
- **T002** [P] — Red-first (item 3): retired command's drifted manifest-owned projection pruned
  + manifest entry dropped; unowned file kept; directory refused. RED on base; commit first.
- **T003** — Reporting tests (item 1): each regenerated path named exactly once (human +
  `--json surface_repair["regenerated"]`); in-sync and recorded-hash-equal silent; exit/outcome unchanged.
- **T004** — Fix (item 2): runtime DERIVED/IGNORED gate in `preserve()` + fall-through + revive
  `overwrite_paths` + reconcile inline/provider comments. Commit GREEN.
- **T005** — Fix (item 3): split `remove_entry()` guard; prune on the gate; keep refusing
  directory; manifest-entry-only. Commit GREEN.
- **T006** — Fix (item 1): record the regenerated `rel`; `InstallReport.regenerated` +
  `DriftPolicySummary.regenerated`; thread the notice through upgrade/init/agent-config via the
  owned `surface_repair` summary (not a presentation `print`). Commit GREEN.
- **T007** [P] — Docs: `[Unreleased]` CHANGELOG entry; verify `upgrade-lifecycle.md`.
- **T008** — Gates: targeted suites + `make test-fast`; `test_no_legacy_terminology.py` +
  `test_upgrade_outcome_single_rendering.py` (named individually); ruff/format/mypy; complexity
  ≤ 15; non-vacuity revert proof. Record commands + counts.

## Acceptance

- **FR-001 / NFR-003 / SC-001**: `spec-kitty upgrade --yes` on a drifted-projection fixture
  names the path once in human output and once under `--json` `surface_repair`; an in-sync or
  recorded-hash-equal projection emits no line.
- **NFR-001**: the process exit code and `outcome` kind are identical to the pre-change run on
  the same fixture; `test_upgrade_outcome_single_rendering.py` stays green.
- **FR-002 / FR-003 / C-002 / SC-002**: a monkeypatched non-ignored/non-derived class keeps the
  drifted projection as `consent_required`; the real class regenerates; `overwrite_paths` consent
  overwrites on the fall-through; the premise guard stays green and agrees with the runtime read.
- **FR-004 / NFR-002 / SC-003**: a retired command's drifted manifest-owned projection and its
  manifest entry are removed; an unowned file at a `spec-kitty.*` path is kept; a directory is
  refused; `spec-kitty doctor skills --json` is green afterwards.
- **C-003 / SC-004**: the item-2 and item-3 fixes are RED before and GREEN after (revert → RED)
  through the real reconcile/provider/prune entry points.
- **NFR-004 / C-001 / SC-005**: scope held to the command-skill surface; ruff/format/mypy clean;
  complexity ≤ 15; no suppressions; targeted suites + named arch gates green (modulo honest
  baseline reds).

## Out of scope

`.claude/skills/**` managed-file installer, `.claude/agents/*.md` profiles, slash-command files,
plugin-bundle components (ADR 2026-10-04-3 Decision 5 unchanged), the `.agents/` gitignore
policy, the manifest schema, and the unresolved-drift exit code (#5745). Adjacent #5710 (stale
manifest / unsafe symlink healing) and #5677 (`doctor --fix` overwrite visibility) are
file-and-link, not this WP.
