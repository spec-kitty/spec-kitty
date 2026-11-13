---
work_package_id: WP04
title: Shipped guidance, ADR amendment, changelog
dependencies:
- WP03
requirement_refs:
- FR-011
- C-005
- C-008
- SC-005
planning_base_branch: fix/3044-approval-honesty
merge_target_branch: fix/3044-approval-honesty
branch_strategy: Planning artifacts for this mission were generated on fix/3044-approval-honesty. During /spec-kitty.implement this WP may branch from a dependency-specific base, but completed changes must merge back into fix/3044-approval-honesty unless the human explicitly redirects the landing branch.
base_branch: kitty/mission-approval-honesty-01M78J9S
base_commit: 9f223981182e71a3312c29ad0ae0641dc256fff7
created_at: '2026-11-13T09:10:40.829829+00:00'
subtasks:
- T019
- T020
- T021
- T022
- T023
phase: Phase 3 - Guidance and records
history:
- at: '2026-11-12T20:00:00Z'
  actor: system
  action: Prompt generated via /spec-kitty.tasks
agent_profile: python-pedro
authoritative_surface: src/runtime/next/runtime_bridge_decision_mapping.py
create_intent:
- tests/runtime/next/test_approval_hint_identity.py
- docs/changelog/unreleased/7569-approval-honesty.fixed.md
- docs/changelog/unreleased/7569-approval-honesty.upgrade-notes.md
execution_mode: code_change
model: ''
owned_files:
- src/runtime/next/runtime_bridge_decision_mapping.py
- src/charter/offering/skills/spk-run-verdict-capture/SKILL.md
- tests/runtime/next/test_approval_hint_identity.py
- tests/runtime/next/test_merged_mission_terminal.py
- docs/adr/4.x/2026-10-04-5-approval-stamp-bounds-the-approved-claim.md
- docs/changelog/unreleased/7569-approval-honesty.fixed.md
- docs/changelog/unreleased/7569-approval-honesty.upgrade-notes.md
- CLAUDE.md
role: implementer
tags: []
task_type: implement
tracker_refs: []
---

# Work Package Prompt: WP04 – Shipped guidance, ADR amendment, changelog

## ⚡ Do This First: Load Agent Profile

Use the `/spk-charter-profile-load` skill to load the agent profile specified in the frontmatter, and behave according to its guidance before parsing the rest of this prompt.

- **Profile**: `python-pedro`
- **Role**: `implementer`
- **Agent/tool**: `claude`

If no profile is specified, run `spec-kitty agent profile list` and select the best match for this work package's `task_type` and `authoritative_surface`.

---

## ⚠️ IMPORTANT: Review Feedback

**Read this first if you are implementing this task!**

- **Has review feedback?**: Check `review_ref` in the event log (`spec-kitty agent tasks status --mission approval-honesty-01M78J9S`).
- **You must address all feedback** before your work is complete.
- **Report progress** with `spec-kitty agent tasks add-history WP04 --note "..." --mission approval-honesty-01M78J9S`.

---

## Review Feedback

*[If this WP was returned from review, the reviewer feedback reference appears in the status event log.]*

---

## Objectives & Success Criteria

After WP01-WP03, approvals record only real identities, and three new refusals exist. This
package teaches the honest command, records the rule, and announces the change.

**Done when:**
- The `spec-kitty next` merged-Mission hint (`runtime_bridge_decision_mapping.py:318`) prints the
  approve command with `--agent <your identity>`.
- `src/charter/offering/skills/spk-run-verdict-capture/SKILL.md`:
  - the approve line carries `--agent <your identity>`;
  - it states that the reviewer is the identity that claimed the review, and that it is never
    auto-detected;
  - it names the three refusal codes in one sentence.
- ADR `docs/adr/4.x/2026-10-04-5-approval-stamp-bounds-the-approved-claim.md` gains an
  **Amendment 2026-11-12** recording:
  - the reviewer-of-record rule (one identity in every recorded field; never the git user; no
    minted tokens);
  - the claimant definition (newest unforced, non-migration, non-placeholder `-> in_review`,
    shared with consolidation);
  - the three codes and their remedies;
  - review-cycle adoption;
  - the residuals listed in `plan.md` (`--force` route, which is #5721 route (a); auto-walk;
    impersonation; override-persist ordering; the `agent status emit` and `orchestrator-api` doors;
    done bookkeeping).
- Changelog fragments:
  - `7569-approval-honesty.fixed.md`: one entry covering #7569, #7571, #7570, #7573, #6709 and
    #3451, in Before/After style;
  - `7569-approval-honesty.upgrade-notes.md`: the `--reviewer` behaviour change (it is now an
    identity that must match `--agent` and the claimant; a free-text name such as `"Jane Doe"` now
    refuses), and the new refusals that scripts may hit.
- CLAUDE.md: one sentence in the "Approved claim is bounded by the approval stamp (#5668)"
  paragraph area, pointing at the amendment, so the paragraph does not drift from the ADR (charter
  vs CLAUDE.md drift rule).
- Requirements: FR-011, C-005, C-008; SC-005 (records).

## Context & Constraints

- Do **not** edit `runtime/next/prompt_builder.py` (#7596). Its APPROVE line already carries the caller's `--agent` suffix.
- Do **not** edit anything under `packs/`. The open-packs review prompt (`--actor <name>`) is a follow-up issue in spec-kitty-open-packs, which the orchestrator files.
- Docs rules (charter "Writing, Communication & Diagramming Doctrine"):
  - the ADR keeps its own format; read the earlier amendments in the file and mirror their shape;
  - fragments follow `docs/changelog/unreleased/README.md`, and must pass
    `uv run --frozen python -m scripts.docs.check_changelog_style` and
    `uv run --frozen python -m scripts.docs.check_spelling --pass unreleased`.
- Terminology: Mission, never "feature". "Review claimant" as defined in the spec.

## Branch Strategy

- **Planning base branch**: `fix/3044-approval-honesty` (via the Mission topic branch)
- **Merge target branch**: `fix/3044-approval-honesty`

Workspace: `spec-kitty agent action implement WP04 --agent <name> --mission approval-honesty-01M78J9S`.

## Subtasks & Detailed Guidance

### Subtask T019 – Red-first: hint and skill

- New file `tests/runtime/next/test_approval_hint_identity.py`.
  - Build the merged-Mission straggler decision the way `tests/runtime/next/test_merged_mission_terminal.py:430-475` does, and assert that `decision.reason` contains `--to approved --mission <slug> --agent`.
  - Read `SKILL.md` and assert that its approve command line contains `--agent`.
- Keep `test_merged_mission_terminal.py:444/473`, which asserts the prefix substring `spec-kitty agent tasks move-task <wp> --to approved`; it should stay green. If it does not, re-pin it in the same commit.
- **Commit**: `test(review): pin approve guidance carries --agent (red, FR-011)`.

### Subtask T020 – Hint and skill text

- `runtime_bridge_decision_mapping.py:318`: `f"'spec-kitty agent tasks move-task <wp> --to approved --mission {mission_slug} --agent <your identity>'."`
- `SKILL.md`:
  - approve line: `spec-kitty agent tasks move-task <WP> --to approved --mission <slug> --agent <your identity> --note "<why>"`;
  - add the sentence: "The approval records the identity that claimed the review (`spec-kitty agent action review <WP> --agent <id>`); it is never taken from git. `APPROVER_NOT_CLAIMANT`, `REVIEW_CYCLE_CITATION_MISSING` and `REVIEW_CYCLE_NOT_ADOPTABLE` explain a refused approval."
  - The `agent status emit --to done --actor <name>` example: keep it, but say that `--actor` must be a real identity. Do not change that command's behaviour (out of scope).
- Run `tests/charter_offering/test_spk_skill_pack.py` and any skill-manifest or packaging test that hashes skills (`grep -rln "SKILL.md" tests/charter_offering tests/cross_cutting | head`). If a recorded digest must be refreshed, use the repository's canonical regeneration command (look for it in the failing test's message), never a hand edit.

### Subtask T021 – ADR amendment

Append `## Amendment 2026-11-12: approvals record the review claimant, never a fabricated reviewer (#7569, #7573, #7571, #7570)` after the last amendment. The sections, in the style of the earlier amendments:
- **Context**, with the evidence: 931 of 1,390 approvals since 2026-09-18 carry a non-actor reviewer, and one review is recorded as two cycles.
- **Decision**: the reviewer-of-record rule, the claimant definition, the three codes and their remedies, and adoption. Cite the decision IDs from `kitty-specs/approval-honesty-01M78J9S/decisions/`.
- **Consequences**: `--reviewer` semantics and the residuals.
- **Not changed**: consolidation verdicts (C-004), the event schema (C-001) and history (C-002).

### Subtask T022 – Changelog fragments

- `.fixed.md`, for example: `- **An approval records the reviewer who claimed the review** (#7569, #7573, #7571, #7570, #6709, #3451). **Before:** \`move-task --to approved\` recorded \`git config user.name\` and an \`auto-approval:\` token, accepted any \`--agent\`, wrote a second review cycle when the reviewer had written one, and accepted citations of missing cycles. **After:** every field names the review claimant or the asserted \`--agent\`; another identity is refused with \`APPROVER_NOT_CLAIMANT\`; the reviewer's cycle is adopted; a cited cycle must exist (\`REVIEW_CYCLE_CITATION_MISSING\`).`
- `.upgrade-notes.md`: the `--reviewer` change and the new refusals; scripts that approved as an identity other than the claimant must pass the claimant or use `--force`.
- Run both style checks.

### Subtask T023 – CLAUDE.md sentence

In the section "Approved claim is bounded by the approval stamp (#5668)", or right after the
"Owned-file evidence and review independence (#6715)" paragraph, add exactly one sentence:
"Since #7569 an approval records one reviewer of record (the asserted `--agent`, else the review
claimant, never the git user) and refuses a non-claimant with `APPROVER_NOT_CLAIMANT`; see ADR
`2026-10-04-5` Amendment 2026-11-12." Do not restructure anything else.

## Test Strategy

```bash
.venv/bin/python -m pytest -q tests/runtime/next/test_approval_hint_identity.py tests/runtime/next/test_merged_mission_terminal.py tests/charter_offering/test_spk_skill_pack.py
.venv/bin/python -m pytest -q tests/architectural/test_no_legacy_terminology.py
uv run --frozen python -m scripts.docs.check_changelog_style
uv run --frozen python -m scripts.docs.check_spelling --pass unreleased
make test-fast
.venv/bin/ruff check <changed py>; .venv/bin/ruff format --check --force-exclude <changed py>; .venv/bin/mypy src/runtime/next/runtime_bridge_decision_mapping.py
```

Record the counts in `add-history`.

## Risks & Mitigations

- **Skill digests or manifests.** Regenerate them with the canonical command only.
- **ADR drift with CLAUDE.md.** Add one sentence only. If they still conflict, flag it in `add-history`; do not pick silently.

## Review Guidance

- The hint and the skill both show `--agent`; `prompt_builder.py` is untouched.
- The amendment names every residual and cites the decision IDs.
- The fragments pass both style checks.

## Progress & Status

`spec-kitty agent tasks add-history WP04 --note "<what you did>" --mission approval-honesty-01M78J9S`.

Implementation command:

```bash
spec-kitty agent action implement WP04 --agent <name> --mission approval-honesty-01M78J9S
```
