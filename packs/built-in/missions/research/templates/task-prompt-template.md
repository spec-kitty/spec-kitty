---
work_package_id: "WPxx"
subtasks:
  - "Txxx"
title: "Replace with work package title"
task_type: "implement"  # implement | review | plan | specify | research — drives agent_profile suggestion
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

## Review Feedback

**Read this first if you are working on this research task!**

- **Has review feedback?**: Check the `review_ref` field in the event log (via `spec-kitty agent tasks status` or the Activity Log below).
- **You must address all feedback** before your work is complete. Feedback items are your research TODO list.
- **Report progress**: As you address each feedback item, update the Activity Log explaining what you changed.

---

## Review Feedback Details

*[If this WP was returned from review, the reviewer feedback reference appears in the Activity Log below or in the status event log.]*

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

## Activity Log

> **CRITICAL**: Activity log entries MUST be in chronological order (oldest first, newest last).

### How to Add Activity Log Entries

**When adding an entry**:

1. Scroll to the bottom of this Activity Log section
2. **APPEND the new entry at the END** (do NOT prepend or insert in middle)
3. Use exact format: `- YYYY-MM-DDTHH:MM:SSZ – agent_id – <action>`
4. Timestamp MUST be current time in UTC (check with `date -u "+%Y-%m-%dT%H:%M:%SZ"`)
5. Agent ID should identify who made the change (claude-sonnet-4-5, codex, etc.)

**Format**:

```
- YYYY-MM-DDTHH:MM:SSZ – <agent_id> – <brief action description>
```

**Example (correct chronological order)**:

```
- 2026-01-12T10:00:00Z – system – Prompt created
- 2026-01-12T10:30:00Z – claude – Started literature search
- 2026-01-12T11:00:00Z – claude – Research complete, ready for review
- 2026-01-12T11:30:00Z – codex – Review passed, findings validated  <- LATEST (at bottom)
```

**Common mistakes (DO NOT DO THIS)**:

- Adding new entry at the top (breaks chronological order)
- Using future timestamps (causes acceptance validation to fail)
- Inserting in middle instead of appending to end

**Why this matters**: The acceptance system reads the LAST activity log entry as the current state. If entries are out of order, acceptance will fail even when the work is complete.

**Initial entry**:

- {{TIMESTAMP}} – system – Prompt created.

---

### Updating Status

Status is managed via `status.events.jsonl`. Use `spec-kitty agent tasks move-task <WPID> --to <status>` to change WP status.

### File Structure

All WP files live in a flat `tasks/` directory.
