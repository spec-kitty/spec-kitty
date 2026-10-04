---
work_package_id: WP06
title: Decision records and operator docs
dependencies:
- WP02
- WP04
- WP05
requirement_refs:
- FR-010
- C-003
- C-007
- NFR-003
planning_base_branch: issue-5457-upgrade-project-global-state
merge_target_branch: issue-5457-upgrade-project-global-state
branch_strategy: Planning artifacts for this mission were generated on issue-5457-upgrade-project-global-state. During /spec-kitty.implement this WP may branch from a dependency-specific base, but completed changes must merge back into issue-5457-upgrade-project-global-state unless the human explicitly redirects the landing branch.
subtasks:
- T022
- T023
- T024
- T025
phase: Phase 4 - Docs
history:
- at: '2026-10-04T19:40:00Z'
  actor: system
  action: Prompt generated via /spec-kitty.tasks
agent_profile: scribe-sally
authoritative_surface: docs/
create_intent:
- docs/adr/4.x/2026-10-04-2-upgrade-writes-project-global-state-once.md
- docs/operations/upgrade-with-live-lanes-recovery.md
execution_mode: planning_artifact
model: ''
owned_files:
- docs/adr/4.x/2026-10-04-2-upgrade-writes-project-global-state-once.md
- docs/adr/4.x/index.md
- docs/adr/3.x/2026-07-07-1-ignored-surface-backfill-migration-pattern.md
- docs/adr/3.x/2026-05-14-1-stale-lane-auto-rebase-classifier-policy.md
- docs/architecture/branch-target-routing.md
- docs/operations/upgrade-with-live-lanes-recovery.md
- docs/changelog/CHANGELOG.md
- docs/operations/toc.yml
- docs/operations/index.md
role: implementer
tags: []
task_type: implement
tracker_refs: []
---

# Work Package Prompt: WP06 – Decision records and operator docs

## ⚡ Do This First: Load Agent Profile

Use the `/ad-hoc-profile-load` skill (canonical: `spk-doctrine-profile-load`):
`spec-kitty agent profile show scribe-sally` and `spec-kitty charter context --action implement --json`. The writing doctrine applies: audience-first (`DIRECTIVE_047`), one Divio quadrant per page, `updated:` freshness frontmatter, and docs that mirror shipped behaviour.

- **Profile**: `scribe-sally` · **Role**: `implementer` · **Agent/tool**: `claude`

---

## ⚠️ IMPORTANT: Review Feedback

Check `review_ref` in the event log. Every feedback item is a TODO.

---

## Objectives & Success Criteria

Record the decision and its residuals, and give operators the recovery path. Describe **shipped** behaviour only: read the merged WP02, WP04 and WP05 code before writing.

Spec refs: FR-010; Assumptions (residuals); C-003 (no destructive remedies); Out of Scope (the deferred stale-remedy follow-up). Read `spec.md`, `plan.md` (IC-05), `research.md`, and `research/code-grounding.md`.

## Context & Constraints

- **The ADR directory convention**: new ADRs go in `docs/adr/4.x/` (see its `index.md`). The `2026-10-04-1` slot is taken, so use `-2`. Check `ls docs/adr/4.x/ | grep 2026-10-04` and bump the number if needed; then update `owned_files` intent in the Activity Log. Mirror the frontmatter of an existing 4.x ADR exactly (`title`, `description`, `status`, `date`, plus anything `test_adr_content_invariance` requires).
- **The inventory refresh**: `python -m scripts.docs.freshen_adr_inventory docs/adr/4.x/<file>`, if that script exists. Also regenerate the docs retrieval index if the repo convention requires it after adding a doc (`scripts/docs/docs_index.py --write`). Check what the gates expect before running anything that writes outside `owned_files`, and report any extra file it touches.
- **Amendments are in place** (precedent: `docs/adr/3.x/2026-09-03-1-…`): add a dated `## Amendment 2026-10-04 (#5457)` section. Never rewrite the original decision text.
- **Terminology**:
  - write "repository root checkout", never "main repository" / "main repo";
  - name the sense of "primary";
  - use Mission, not feature;
  - say "status commit", never "ceremony".
- **The how-to's location**: `docs/operations/` (operator recovery runbooks live there, e.g. `coord-worktree-missing.md`); mirror their frontmatter.

## Branch Strategy

- **Strategy**: lanes · **Planning base branch**: `issue-5457-upgrade-project-global-state` · **Merge target branch**: `issue-5457-upgrade-project-global-state`.

## Subtasks & Detailed Guidance

### Subtask T022 – The new ADR

`docs/adr/4.x/2026-10-04-2-upgrade-writes-project-global-state-once.md`, status Accepted.

- **Context**:
  - #5457, paths A, B and C;
  - the per-branch commits of `.kittify/metadata.yaml` and `.gitattributes`;
  - why the #2385/#2392/#4972 per-worktree design could never converge (per-record `applied_at`).
- **Decision**:
  1. Upgrade writes project-global state once, in the repository root checkout, and skips integrating worktrees: `kitty/mission-…` branches, or an unreadable branch.
  2. The state contract declares primary-owned bookkeeping (`StateSurface.primary_owned`; currently `.kittify/metadata.yaml`).
  3. Each integration merge site has a fixed resolution side. Copy the table from `data-model.md` and verify it against the code.
  4. The stale check ignores content-identical overlaps.
- **Consequences and residuals**:
  - lanes keep their pre-upgrade `.gitignore` / `.gitattributes` until they integrate;
  - ignored per-checkout surfaces are no longer refreshed in lanes;
  - pre-`kitty/` legacy branches are not recognised;
  - `--strategy rebase` is not covered;
  - the general stale-remedy follow-up (link the issue number if it has been filed by then; otherwise "follow-up issue").
- **Alternatives considered**: per-worktree alignment; refusing upgrade while lanes are live; a merge driver; per-hunk classifier rules.

### Subtask T023 – Amendments [P]

- **`2026-07-07-1`**: Decision item 3 ("inherits `runs_on_worktrees=True` so lane worktrees receive the same gitignore protection") no longer reaches integrating worktrees. Lanes receive the protection through integration. Document the residual window.
- **`2026-05-14-1`**:
  - add `R-PRIMARY-OWNED-BOOKKEEPING` as a **managed-artifact (whole-file) rule**, stating the distinction from the per-hunk `RULES` list;
  - its resolution is stage 3, the incoming coordination or mission side;
  - `R-DEFAULT-MANUAL` is still the fail-safe default for everything else.

### Subtask T024 – Recovery how-to and the architecture note [P]

- **The how-to** (Divio how-to; audience: an operator who upgraded mid-mission on 4.0.0rc5 and is stuck):
  - the symptoms: the three refusal texts, verbatim from the issue;
  - the fix: install the fixed CLI, re-run `spec-kitty consolidate --mission <slug>` (or the review or implement that refused);
  - what happens under the hood, in one paragraph;
  - what **not** to do: no `git reset --hard`, no history rewrite, no hand-editing of `metadata.yaml`;
  - when to still expect a refusal: genuine overlaps on operator-editable files.
  - Add the `updated: 2026-10-04` frontmatter.
- **`docs/architecture/branch-target-routing.md`**: a short paragraph stating that upgrade writes only on the repository root checkout's branch, and that integrating branches receive project-global state by integration. Bump `updated:`.

### Subtask T025 – CHANGELOG and gates

- **The `docs/changelog/CHANGELOG.md` `[Unreleased]` entry** (the root `CHANGELOG.md` is a symlink):
  - a bold, impact-first lead with `(#5457)`;
  - then before → after: "upgrading while a mission had live lanes made `consolidate`, review and implement refuse on `.kittify/metadata.yaml`" → "upgrade writes project-global state once; missions already affected recover on the next `consolidate`/review with no manual edits".
  - Follow the neighbouring entries' format exactly.
- **Gates**:
  - `uv run --frozen python scripts/docs/check_docs_freshness.py --ci` (errors=0, if the script exists);
  - `uv run --frozen pytest tests/architectural/test_no_legacy_terminology.py -q`;
  - `uv run --frozen pytest tests/architectural/test_adr_content_invariance.py -q`, if present;
  - any docs index test the repo has (`grep -rl "docs_index\|freshness" tests/architectural | head`). Run only the specific files.

## Post-tasks squad folds (binding)

- **Runbook navigation**: add the new runbook to `docs/operations/toc.yml`, and to `docs/operations/index.md` if that file lists runbooks.
- **Issue-matrix closeout**: the orchestrator records issue verdicts with `spec-kitty agent mission issue-verdict` at accept time. In the docs, write context-only references explicitly ("see #4933", "Follow-up: #…") rather than as bare citations.
- **The CHANGELOG will conflict** with open PRs that also edit `[Unreleased]`. Keep the entry self-contained, as one bullet block.
- **Gate-file rights**: if a named architectural gate goes red because of a *legitimate* change, you may edit **only** that gate's own pin or allowlist entry. Name the file in the commit body with a one-line justification, and the reviewer re-checks it. Never add a new allowlist (C-007).

## Risks & Mitigations

- **Docs that describe intended rather than shipped behaviour**: read the merged code; quote function names exactly.
- **An inventory script touching extra files**: report it, and keep the change if a gate requires it.

## Review Guidance

- Every behavioural claim matches the code on the WP base.
- There is no destructive recipe anywhere.
- The freshness and terminology gates are green.

## Activity Log

- 2026-10-04T19:40:00Z – system – Prompt generated via /spec-kitty.tasks
