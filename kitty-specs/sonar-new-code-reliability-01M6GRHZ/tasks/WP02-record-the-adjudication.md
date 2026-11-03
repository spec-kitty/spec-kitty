---
work_package_id: WP02
title: Record the adjudication and the changelog
dependencies:
- WP01
requirement_refs:
- FR-004
- NFR-001
- C-002
- C-003
- SC-002
- SC-004
planning_base_branch: main
merge_target_branch: main
branch_strategy: Planning artifacts for this mission were generated on main. During /spec-kitty.implement this WP may branch from a dependency-specific base, but completed changes must merge back into main unless the human explicitly redirects the landing branch.
base_branch: kitty/mission-sonar-new-code-reliability-01M6GRHZ
base_commit: 5b193449971ab049113e0b18b1d652abfaaa8307
created_at: '2026-11-03T13:15:00+00:00'
subtasks:
- T007
- T008
- T009
- T010
phase: Phase 2 - The adjudication record handed to the maintainer
history:
- at: '2026-11-03T13:15:00Z'
  actor: system
  action: Prompt generated via /spec-kitty.tasks
agent_profile: python-pedro
authoritative_surface: docs/changelog/unreleased/
create_intent:
- docs/changelog/unreleased/7113.internal.md
execution_mode: code_change
model: ''
owned_files:
- docs/changelog/unreleased/7113.internal.md
role: implementer
tags: []
task_type: document
tracker_refs:
- '#7113'
---

# Work Package Prompt: WP02 – Record the adjudication and the changelog

## ⚡ Do This First: Load Agent Profile

Use the `/spk-charter-profile-load` skill to load the agent profile specified in the frontmatter, and behave according to its guidance before parsing the rest of this prompt.

- **Profile**: `python-pedro`
- **Role**: `implementer`

---

## ⚠️ IMPORTANT: Review Feedback

Check `review_ref` in the event log (`spec-kitty agent tasks status --mission sonar-new-code-reliability-01M6GRHZ`) and address every item before handing back.

## Objectives & Success Criteria

- `kitty-specs/sonar-new-code-reliability-01M6GRHZ/evidence/README.md` states the new-code window, the 4-vs-19 split, the per-finding disposition, and the one-command reproduction — with the raw API responses committed beside it.
- The evidence is updated with the post-change state (what is left on new code, and why `A` is not reachable from inside this repository).
- `docs/changelog/unreleased/7113.internal.md` exists in the shape `docs/changelog/unreleased/README.md` requires, names what changes and what does not, and passes `check_changelog_style`.
- The PR body will carry the same split under `## Change` and `## Deferred`; no claim in it is stronger than the evidence supports.

## Context

The issue's work list implies 23 findings are in scope and asks for the two BLOCKERs to be marked as false positives in the SonarCloud UI. Neither is available to an agent: the UI is a web action (no token in this environment, C-001), and only 4 of the 23 findings are on new code at all. `inNewCodePeriod=true` is silently ignored by the project's API; `sinceLeakPeriod=true` is the parameter that reflects the leak period, and it returns 4.

That makes the durable artefact here a **record**, not an edit: the classification a maintainer needs to act on, with the query that reproduces it, so `#7113` can be closed or re-scoped on facts. The mission ships it in-repo (the mission's `evidence/` directory plus the PR body) because the issue is a tracker for exactly this information.

## Subtasks

- **T007** Re-read `evidence/README.md` against the raw JSON beside it and correct anything the post-change tree falsifies. Add a short "After this change" section naming the remaining new-code finding (`java:S5960` at `acceptance-jvm/.../CharterSteps.java:134`, MAJOR) and the reason it stays: `sonar.yml`'s documented decision to analyse that tree as MAIN code so the full Java rule set applies. State plainly that the rating therefore moves E → C, not E → A, and that A needs either a maintainer decision on that scope or a SonarCloud UI adjudication.
- **T008** Write `docs/changelog/unreleased/7113.internal.md`. Read `docs/changelog/unreleased/README.md` first: the file holds the entry exactly as it reads in the changelog, no heading, US spelling. `internal` is the right section — the change is not user-visible (the default kind, the compiler's import order and a dead branch are all invisible to operators). One or two entries at most, impact-first, with the `(#7113)` reference, and honest that the pre-existing findings are untouched.
- **T009** Validate both surfaces: `uv run --frozen python -m scripts.docs.check_changelog_style` and `uv run --frozen python -m scripts.docs.check_spelling --pass unreleased` exit 0. If the fragment's id must change to the PR number, do that in a follow-up edit once the PR exists — the README allows the issue-number-plus-slug placeholder until then.
- **T010** Draft the PR body's `## Change` and `## Deferred` text from the evidence (the PR itself is opened by the mission, from `.github/PULL_REQUEST_TEMPLATE.md`, and validated with `python packs/internal/assets/validate-pr-body.py`). Deferred must name, with reasons: the Java `S5960` (maintainer decision on scan scope), the 19 pre-existing findings (deliberate determinism controls; stale `test_live_frame.py` entry), and the fact that the new-code window re-anchors at `4.0.0rc8` so the classification is dated evidence, not a permanent claim.

## Constraints

- Never claim the rating is A, or will be A, or that the gate is green: the honest terminal state is E → C with the remaining item named.
- Never describe the two BLOCKERs as "fixed defects"; they are intentional constructs whose analyzer reading was removed. The S2583 is a true positive (dead branch) with no runtime effect. Keep that distinction in both surfaces.
- Do not edit `docs/changelog/CHANGELOG.md` (`check_changelog_style` rejects the pre-#6988 shape) and do not touch the 19 pre-existing findings' sites.
- Do not add a docs page: fragments are skipped by the docs index, so no `docs_index` regeneration is required for this WP. If you do add a page, you own the index regeneration.
- No personal data or machine-local paths in either surface.

## Definition of Done

- `uv run --frozen python -m scripts.docs.check_changelog_style` exits 0.
- `uv run --frozen python -m scripts.docs.check_spelling --pass unreleased` exits 0.
- The evidence README's claims re-checked against the committed JSON in the same directory.
- Both surfaces quote the same numbers: `new_bugs` 4 before, 1 after; window anchor `previous_version` `4.0.0rc7` / 2026-10-15.
