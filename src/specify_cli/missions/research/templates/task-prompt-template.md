---
work_package_id: "WPxx"
title: "Replace with work package title"
dependencies: []
planning_base_branch: "{{planning_base_branch}}"  # Planning branch active when this WP prompt was generated
merge_target_branch: "{{merge_target_branch}}"    # Final landing branch for completed changes
branch_strategy: "{{branch_strategy}}"            # Repeat this branch contract before coding; never guess
subtasks:
  - "Txxx"
phase: "Phase N - Replace with phase name"
assignee: ""      # Optional friendly name when claimed/in_progress
agent: ""         # CLI agent identifier (claude, codex, etc.)
shell_pid: ""     # PID captured when the task was claimed
history:
  - at: "{{TIMESTAMP}}"
    actor: "system"
    action: "Prompt generated via /spec-kitty.tasks"
---

# Research Work Package: {{work_package_id}} – {{title}}

## Branch Strategy

- **Planning/base branch at prompt creation**: `{{planning_base_branch}}`
- **Final merge target for completed work**: `{{merge_target_branch}}`
- **Actual execution workspace is resolved later**: `/spec-kitty.implement` decides the lane workspace path and records the lane branch in `base_branch`. Sequential WPs in the same lane reuse the same worktree.
- **If the resolved workspace differs from your expectation**: trust the path printed by `spec-kitty agent action implement/review`; do not manually create a different worktree.
- **If human instructions contradict these fields**: stop and resolve the intended landing branch before working.

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
Use language identifiers in code blocks: ````python`, ````bash`

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
