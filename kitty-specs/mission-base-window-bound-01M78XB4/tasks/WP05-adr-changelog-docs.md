---
work_package_id: WP05
title: ADR amendment, changelog, CLAUDE.md
dependencies:
- WP04
requirement_refs:
- FR-008
- C-004
- FR-009
planning_base_branch: fix/7560-dependency-ref-spine-base
merge_target_branch: fix/7560-dependency-ref-spine-base
branch_strategy: Planning artifacts for this mission were generated on fix/7560-dependency-ref-spine-base. During /spec-kitty.implement this WP may branch from a dependency-specific base, but completed changes must merge back into fix/7560-dependency-ref-spine-base unless the human explicitly redirects the landing branch.
base_branch: kitty/mission-mission-base-window-bound-01M78XB4
base_commit: 55d9dbcf5154fbc820cf163ef76e30214dc025d1
created_at: '2026-11-13T01:44:55.040251+00:00'
subtasks:
- T020
- T021
- T022
- T023
phase: Phase 4 - Governance
history:
- at: '2026-11-12T22:40:00Z'
  actor: system
  action: Prompt generated via /spec-kitty.tasks
agent_profile: scribe-sally
authoritative_surface: docs/adr/3.x/
create_intent:
- docs/changelog/unreleased/7560.fixed.md
- tests/architectural/test_consolidation_stamp_reads.py
execution_mode: code_change
owned_files:
- docs/adr/3.x/2026-09-29-1-closed-world-refuse-on-mixed-lanes.md
- docs/changelog/unreleased/7560.fixed.md
- CLAUDE.md
- tests/architectural/test_consolidation_stamp_reads.py
role: documentarian
tags: []
task_type: implement
tracker_refs: []
---

# Work Package Prompt: WP05 – ADR amendment, changelog, CLAUDE.md

## ⚡ Do This First: Load Agent Profile

Use the `/spk-charter-profile-load` skill to load the agent profile specified in the frontmatter, and behave according to its guidance before parsing the rest of this prompt.

- **Profile**: `scribe-sally`
- **Role**: `documentarian`
- **Agent/tool**: `claude`

---

## ⚠️ IMPORTANT: Review Feedback

Check `spec-kitty agent tasks status` for a `review_ref`, and address every item. Record progress with `spec-kitty agent tasks add-history WP05 --note "..."`.

---

## Objectives & Success Criteria

FR-008: record the verdict change where it is governed, and describe shipped behaviour only (code is the source of truth).

- ADR `docs/adr/3.x/2026-09-29-1-closed-world-refuse-on-mixed-lanes.md` gains an **Amendment 2026-11-12 (#7560)** in the style of its existing amendments (read them first; the 2026-10-31 amendment introduced `--dependency-ref`).
- One changelog fragment in `docs/changelog/unreleased/`, following its `README.md` (id `7560`, section `fixed`; check the README for the exact naming). Never edit `CHANGELOG.md`.
- CLAUDE.md, section "Mixed lanes are attributed per WP", bullet **"Declared dependency ref (#6771)"**: add one or two sentences about the Mission base. Keep it short; CLAUDE.md is dense.

## Context & Constraints

- The behaviour to describe (verify it against WP02–WP04's code before writing):
  - The **Mission base** is the commit the Mission branch was cut from. It is recorded as `meta.json` `mission_base_sha` at create/mint. Missions without the key derive it as the first parent of the earliest first-parent commit on the Mission branch that adds `kitty-specs/<slug>/`. A candidate that is not an ancestor of the Mission branch is not used. If neither source yields a base, it is unavailable, and today's bound (the target's pre-run tip) applies.
  - **Pre-Mission history** = `window_base..mission_base`, which is empty whenever the target reaches the base. On the closed-world scan, the squash blob/deletion axes and the patch-id window, it has the standing of content already on the target, and its commits are not Mission spine commits for the #6771 guard. The declared ref's own window is unchanged.
  - The approved-bound and canceled-content axes are unchanged.
  - A derived base reads history the operator can edit; editing it is a recorded operator act.
  - The note line on consolidate and dry-run.
  - Rulings: DM `01M78XBQS8NE8PPMSTZHMDJ610`, `01M78XBWYTWJ6TZJVF4GWQMCQF`, `01M78XC2CJVH9ZXR0WB92NWYG5`.
- Writing doctrine: plain language, audience = maintainers/reviewers of consolidation; the ADR gets an `updated:` freshness bump if its frontmatter has one.
- Run the terminology guard: `pytest tests/architectural/test_no_legacy_terminology.py`. Use Mission, never feature.

## Branch Strategy

- **Planning base branch**: `fix/7560-dependency-ref-spine-base`
- **Merge target branch**: `fix/7560-dependency-ref-spine-base`
- Run `spec-kitty agent action implement WP05 --agent claude --mission mission-base-window-bound-01M78XB4`.

## Subtasks & Detailed Guidance

### Subtask T020 – ADR amendment

Sections: Context (#7560: fork shape, both reports), Decision (the bullets above), Consequences (a fork's pre-Mission content lands without a WP attributing it, by operator ruling; it is fail-closed when the base cannot be established; there is no new refusal code), Residuals (a rebased Mission branch with no scaffold on its first-parent spine falls back to today's bound).

### Subtask T021 – Changelog fragment

One user-facing sentence or two: "`consolidate` no longer treats history from before a Mission was created as Mission work on a fork whose target lacks the Mission's base commit (#7560)…"

### Subtask T022 – CLAUDE.md

Append to the "Declared dependency ref (#6771)" bullet. Example: "Pre-Mission history (`target..mission_base`, the Mission base being `meta.json` `mission_base_sha` or the scaffold commit's parent) is outside every window and never Mission spine work (#7560, ADR `2026-09-29-1` Amendment 2026-11-12)."

### Subtask T023 – #7593 fold (conditional, FR-009)

- Check `gh api repos/spec-kitty/spec-kitty/pulls/7596 --jq .merged` (gh for read-only checks only) and whether `src/specify_cli/consolidation/consolidation_events.py` exists on this branch after a rebase onto `origin/main`.
- **Not merged** (expected): change nothing. Record `add-history WP05 --note "FR-009 blocked: PR #7596 unmerged"`. The orchestrator reports #7593 as blocked and keeps it `Refs`.
- **Merged**: read #7593 in full and add `tests/architectural/test_consolidation_stamp_reads.py` as it specifies: an AST gate saying consolidation reads commit-to-target stamps only through `consolidation_events`, with an empty allowlist, a concrete floor and a self-mutation test (Charter Standing Order 5, `architectural-gate-non-vacuity`). Escalate before adding it if it cannot start empty.

## Test Strategy

```bash
.venv/bin/python -m pytest tests/architectural/test_no_legacy_terminology.py -q
# if a changelog-fragment or docs gate exists, run it:
ls tests/ | grep -i changelog; grep -rl "changelog/unreleased" tests/ | head
```

## Review Guidance

- Docs match the merged code.
- The changelog is a fragment, not a `CHANGELOG.md` edit.
- No version numbers in scope text.
