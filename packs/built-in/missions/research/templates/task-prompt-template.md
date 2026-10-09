---
work_package_id: "WPxx"
subtasks:
  - "Txxx"
title: "Replace with work package title"
task_type: "implement"  # implement | review | plan | specify | research — drives agent_profile suggestion
phase: "Phase N - Replace with phase name"
execution_mode: "planning_artifact"  # code_change | planning_artifact — drives ownership consistency checks
owned_files:  # Repo-root-relative paths/globs this WP owns — never host-absolute or worktree-prefixed
  - "kitty-specs/replace-with-mission-slug/research.md"
  - "kitty-specs/replace-with-mission-slug/source-register.md"
authoritative_surface: "kitty-specs/replace-with-mission-slug/"  # Repo-root-relative prefix; must prefix at least one owned_files entry
create_intent:  # Repo-root-relative paths this WP will CREATE (suppresses literal-path zero-match at finalize)
  - "kitty-specs/replace-with-mission-slug/research.md"
agent_profile: ""  # Agent profile identifier (e.g., researcher-rita, architect-alphonso)
role: ""           # Role within the profile (e.g., "researcher", "reviewer")
agent: ""          # CLI agent/tool identifier (claude, codex, copilot, etc.)
model: ""          # Model identifier (e.g., claude-sonnet-4-6) — optional
assignee: ""       # Optional friendly name when claimed/in_progress
shell_pid: ""     # PID captured when the task was claimed
history:
  - at: "{{TIMESTAMP}}"
    actor: "system"
    action: "Prompt generated via /spec-kitty.tasks"
---

# Research Work Package: {{work_package_id}} – {{title}}

## ⚡ Do This First: Load Agent Profile

Use the `/spk-charter-profile-load` skill to load the agent profile specified in the frontmatter (or any user-defined profile), and behave according to its guidance before parsing the rest of this prompt.

- **Profile**: `{{agent_profile}}`
- **Role**: `{{role}}`
- **Agent/tool**: `{{agent}}`

If no profile is specified, run `spec-kitty agent profile list` and select the best match for this work package's `task_type` and `authoritative_surface`.

---

## Review Feedback

**Read this first if you are working on this research task!**

- **Has review feedback?**: Check the `review_ref` field in the event log (via `spec-kitty agent tasks status`).
- **You must address all feedback** before your work is complete. Feedback items are your research TODO list.
- **Report progress**: As you address each feedback item, record what you changed with `spec-kitty agent tasks add-history <WPID> --note "..."` (stored in the status event log).

---

## Review Feedback Details

*[If this WP was returned from review, the reviewer feedback reference appears in the status event log.]*

---

## Markdown Formatting

Wrap HTML/XML tags in backticks: `` `<div>` ``, `` `<script>` ``
Use language identifiers in code blocks: ````python`,````bash`

---

## Research Objectives & Success Criteria

- Summarize the exact outcomes that mark this research work package complete.
- Call out key acceptance criteria or quality metrics (e.g., minimum sources, confidence thresholds).

## Context & Methodology

- Reference prerequisite work and related documents.
- Link to supporting specs: `.kittify/charter/charter.md`, `kitty-specs/.../plan.md` (methodology), `kitty-specs/.../spec.md` (research question), `research.md`, `data-model.md`.
- Highlight methodological constraints or quality requirements.

## Evidence Tracking Requirements

- **Source Register**: All sources MUST be recorded in `research/source-register.csv`
- **Evidence Log**: All findings MUST be recorded in `research/evidence-log.csv`
- **Citations**: Every claim must link to evidence rows

## Branch Strategy

- **Strategy**: {{branch_strategy}}
- **Planning base branch**: {{planning_base_branch}}
- **Merge target branch**: {{merge_target_branch}}

> These fields are populated automatically by `spec-kitty agent mission finalize-tasks`.
> Do NOT change them manually unless you are certain the branch topology has changed.

## Subtasks & Detailed Guidance

### Subtask TXXX – Replace with summary

- **Purpose**: Explain why this research subtask exists.
- **Steps**: Detailed, actionable instructions for conducting research.
- **Sources**: Types of sources to search (academic, industry, gray literature).
- **Output**: What artifact to update (source-register.csv, evidence-log.csv, findings.md).
- **Parallel?**: Note if this can run alongside others (e.g., different databases).
- **Quality Criteria**: Minimum requirements for this subtask.

### Subtask TYYY – Replace with summary

- Repeat the structure above for every included `Txxx` entry.

## Quality & Validation

- Specify minimum source requirements.
- Define confidence level thresholds.
- Document methodology adherence checkpoints.

## Risks & Mitigations

- List known pitfalls (bias, incomplete coverage, contradictory findings).
- Provide mitigation strategies.

## Review Guidance

- Key acceptance checkpoints for `/spec-kitty.review`.
- Methodology adherence verification points.
- Any context reviewers should consider.

## Progress & Status

Progress, history, and status all live in the status event log
(`status.events.jsonl`) — never in this prompt file. Do **not** hand-edit a
history section here.

- **Record a progress note**: `spec-kitty agent tasks add-history <WPID> --note "<what you did>"`
- **Change WP status**: `spec-kitty agent tasks move-task <WPID> --to <status>`
- **View history and status**: `spec-kitty agent tasks status`

### File Structure

All WP files live in a flat `tasks/` directory.
