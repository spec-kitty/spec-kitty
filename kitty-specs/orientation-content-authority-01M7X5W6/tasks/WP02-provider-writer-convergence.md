---
work_package_id: WP02
title: Provider and writer consume the authority; S1/S3/S4 repaired
dependencies:
- WP01
requirement_refs:
- FR-004
- FR-005
- FR-006
- FR-008
- FR-009
- NFR-001
- NFR-002
- C-003
- C-004
- SC-001
- SC-002
planning_base_branch: fix/5215-orientation-content-authority
merge_target_branch: fix/5215-orientation-content-authority
branch_strategy: Planning artifacts for this mission were generated on fix/5215-orientation-content-authority. During /spec-kitty.implement this WP may branch from a dependency-specific base, but completed changes must merge back into fix/5215-orientation-content-authority unless the human explicitly redirects the landing branch.
subtasks:
- T006
- T007
- T008
- T009
- T010
phase: Phase 2 - Repair surfaces
history:
- at: '2026-11-20T19:30:00Z'
  actor: system
  action: Prompt generated via /spec-kitty.tasks
agent_profile: python-pedro
authoritative_surface: src/specify_cli/tool_surface/providers/
create_intent:
- tests/specify_cli/tool_surface/providers/test_session_presence_orientation_5215.py
execution_mode: code_change
owned_files:
- src/specify_cli/tool_surface/providers/session_presence.py
- src/specify_cli/session_presence/writers/markdown_rules.py
- tests/specify_cli/tool_surface/providers/test_session_presence.py
- tests/specify_cli/tool_surface/providers/test_session_presence_orientation_5215.py
- tests/specify_cli/session_presence/test_markdown_rules_writer.py
- tests/architectural/dead_symbol_allowlist.yaml
role: implementer
tags: []
task_type: implement
tracker_refs: []
---

# Work Package Prompt: WP02 – Provider and writer consume the authority; S1/S3/S4 repaired

## ⚡ Do This First: Load Agent Profile

Use the `/spk-charter-profile-load` skill to load the agent profile specified in the frontmatter, and behave according to its guidance before parsing the rest of this prompt.

- **Profile**: `python-pedro`
- **Role**: `implementer`
- **Agent/tool**: `claude`

---

## ⚠️ IMPORTANT: Review Feedback

Check the `review_ref` field in the event log (`spec-kitty agent tasks status`). Address all feedback before re-submitting.

## Objectives & Success Criteria

- A block whose content differs from the expected rendering is reported stale (FR-004) and repaired (FR-005).
- Upgrade surface repair and `doctor tool-surfaces --fix` write byte-identical blocks; a second pass changes nothing (FR-006, NFR-001).
- Hand-edited blocks are still preserved (FR-009).
- One applicability predicate (FR-008).

## Context & Constraints

- Depends on WP01 (`projection.py`).
- The #2265 rule "do not churn on health" is now met by deterministic content, not by version-only comparison. Keep #4706/#4707/#4782/#5757/#4893 tests green.
- No migration; rc39 untouched.

## Branch Strategy

- **Strategy**: single_branch on `fix/5215-orientation-content-authority`.
- **Planning base branch**: fix/5215-orientation-content-authority
- **Merge target branch**: fix/5215-orientation-content-authority
- Command: `spec-kitty agent action implement WP02 --agent claude --mission orientation-content-authority-01M7X5W6`

## Subtasks

### T006 — Red-first acceptance tests

New `tests/specify_cli/tool_surface/providers/test_session_presence_orientation_5215.py`. Fixture: tmp project dir `dirname-differs`, `.kittify/config.yaml` with `agents.available: [claude]` and `project.slug: local-agent-bus`, `.claude/` present. Write a block via `SessionPresenceContent(<installed>, "dirname-differs", "healthy", None).render()` into `.claude/CLAUDE.md`.

- **S1**: `provider.probe(instance)` for the context-file instance → `STATE_STALE`; positive control: a block rendered with `local-agent-bus` → `STATE_PRESENT`.
- **S3**: block stamped `4.0.0rc8` with the right slug; run `prepare_upgrade_repairs` + its apply path (`upgrade/assessment.py`), or `provider.assess(AssessmentInputs(root, consent=...))` + `apply` with no projected content → the file names `local-agent-bus`.
- **S4**: `provider.repair(root, statuses)` → names `local-agent-bus`.
- **Convergence**: bytes after the upgrade path == bytes after the `--fix` path (separate fixtures); a second `repair` reports nothing actionable and changes no bytes.
- **Live health converges once**: a block with `(upgrade-available)` + upgrade line at the current version is stale and is rewritten to `(healthy)`; then present.
- **Hand-edited**: a non-canonical block at the current version stays present and is not rewritten.

Confirm each fails on the WP01 tip before T007–T009.

### T007 — `orientation_drift`

Add `orientation_drift(root, rules_path) -> bool` to `projection.py` (out-of-map edit of a WP01 file, justified: it is the authority's drift test). Rule: read the managed block (`SECTION_OPEN`..`SECTION_CLOSE`); absent → False; stamped version ≠ installed → True; canonical block (reuse `markdown_rules._canonical_section` via a small public helper) and normalised bytes ≠ `expected_orientation(root).render()` → True; otherwise False. In the provider, `probe` calls it instead of `_orientation_version_is_stale`; delete `_orientation_version_is_stale`, `_on_disk_orientation_version` and the version constants if unused.

### T008 — Provider content and applicability

- `_orientation_content(root)` → `expected_orientation(root)`.
- `_prepare`: replace the inline `isinstance(...) and (configured is None or tool in configured)` + `can_write` checks with `orientation_writer`, keeping the observation order (observe the check dir before `can_write`) and the `kinds` filter.

### T009 — Writer equality

`MarkdownRulesWriter.prepare`: replace the version+invocation shortcut with "normalised block == rendered (without trailing newline)" → unchanged. Canonical-but-different blocks are rewritten; non-canonical blocks keep `preserve`.

### T010 — Cleanup and re-pins

- Delete `local_presence_content` from `manager.py` (out-of-map, justified: last caller removed here).
- Re-pin stale tests in `test_session_presence.py` / `test_markdown_rules_writer.py` that assert version-only staleness or the shortcut (judge each: stale → re-pin to the new rule; valid → keep).
- Run `tests/architectural/test_dead_symbols*.py` (or the gate that reads `dead_symbol_allowlist.yaml`); remove allowlist entries for deleted symbols, add none.

## Test commands

```bash
.venv/bin/python -m pytest tests/specify_cli/tool_surface tests/specify_cli/session_presence tests/specify_cli/upgrade/migrations -k "session_presence or orientation or rc39" tests/upgrade/test_upgrade_assessment_boundary.py -q
```

## Definition of Done

- S1/S3/S4/convergence tests red on WP01 tip, green after.
- Blast-radius files from research.md green; ruff/format/mypy clean.

## Reviewer guidance

Check that a correct block is never rewritten (no churn), that hand-edited blocks stay preserved, and that the upgrade and `--fix` paths share one content source.
