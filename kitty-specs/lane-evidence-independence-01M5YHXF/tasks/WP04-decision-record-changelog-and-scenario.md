---
work_package_id: WP04
title: Decision record, changelog and scenario
dependencies:
- WP03
requirement_refs:
- FR-008
- FR-009
- C-005
planning_base_branch: issue-6715-lane-evidence-independence
merge_target_branch: issue-6715-lane-evidence-independence
branch_strategy: Planning artifacts for this mission were generated on issue-6715-lane-evidence-independence. During /spec-kitty.implement this WP may branch from a dependency-specific base, but completed changes must merge back into issue-6715-lane-evidence-independence unless the human explicitly redirects the landing branch.
base_branch: kitty/mission-lane-evidence-independence-01M5YHXF
base_commit: b47211f25c9c6491f68e5222057dc81f94d66b8b
created_at: '2026-10-29T10:32:53.398914+00:00'
subtasks:
- T015
- T016
- T017
- T018
phase: Phase 4 - Record and prove
history:
- at: '2026-10-27T12:10:00Z'
  actor: system
  action: Prompt generated via /spec-kitty.tasks
agent_profile: implementer-ivan
authoritative_surface: docs/adr/4.x/
create_intent: []
execution_mode: code_change
model: ''
owned_files:
- docs/adr/4.x/2026-10-04-5-approval-stamp-bounds-the-approved-claim.md
- docs/changelog/CHANGELOG.md
- tests/scenarios/mission/review.feature
- CLAUDE.md
role: implementer
tags: []
task_type: implement
tracker_refs: []
---

# Work Package Prompt: WP04 – Decision record, changelog and scenario

## ⚡ Do This First: Load Agent Profile

Use the `/spk-charter-profile-load` skill to load the agent profile specified in the frontmatter (or any user-defined profile), and behave according to its guidance before parsing the rest of this prompt.

- **Profile**: `implementer-ivan`
- **Role**: `implementer`
- **Agent/tool**: `claude`

---

## ⚠️ IMPORTANT: Review Feedback

- Check `review_ref` via `spec-kitty agent tasks status`; address every item.

---

## Review Feedback

*[If this WP was returned from review, the reviewer feedback reference appears in the status event log.]*

---

## Objectives & Success Criteria

- ADR `2026-10-04-5` carries an "Amendment 2026-10-27" stating: owned-file evidence and review
  independence are a separate axis applied on every topology; the approval bound is unchanged;
  ruling 1 (independence = #5939 `tool:model:profile`, role not compared because it is
  lane-stamped) and ruling 2 (missing implementation refuses by default, an operator attestation
  lifts it, never independence) quoted; the `--force` decision; residuals.
- `docs/changelog/CHANGELOG.md` `[Unreleased]` entry (Fixed) in the file's existing style.
- A scenario in `tests/scenarios/mission/review.feature` that approves a work package with no
  committed work and expects the refusal; it fails on the pre-fix CLI and passes on the fixed one
  (Cucumber-JVM on JDK 25).
- CLAUDE.md: a short note in the Consolidation section, only if the charter's canonical-source
  rule allows (CLAUDE.md is a derived view; the ADR is canonical: keep the note a pointer, not a
  second statement of the rule). If AGENTS.md mirrors that section, mention it in the history note
  and leave AGENTS.md to the operator unless it is generated from CLAUDE.md.

## Context & Constraints

- Scenario steps: reuse those in `tests/scenarios/README.md` ("Available steps"); add a step only
  if none fits (step defs live under `acceptance-jvm/`; an addition there is an out-of-map edit
  to record). Run per `docs/development/testing/acceptance-scenarios.md` with
  `JAVA_HOME=/usr/lib/jvm/temurin-25` and the pinned Gradle on PATH
  (`source <scratchpad>/env.sh` or `scripts/dev/cloud-session-setup.sh`).
- Per-PR scenario contract: `tests/architectural/test_scenario_contract.py` must stay green.
- Docs carry an `updated:` date per the docs-freshness rule where the file has frontmatter.

## Branch Strategy

- **Planning base branch**: issue-6715-lane-evidence-independence
- **Merge target branch**: issue-6715-lane-evidence-independence

Run `spec-kitty agent action implement WP04 --agent claude --mission lane-evidence-independence-01M5YHXF`.

## Subtasks & Detailed Guidance

### Subtask T015 – ADR amendment

- Append the amendment section in the ADR's existing amendment style; link #6715 and #5939.

### Subtask T016 – Changelog

- One entry under `[Unreleased]` → Fixed: what an operator now sees (codes, flag), not internals.

### Subtask T017 – Scenario

- Write the scenario first and run it against the base CLI to see it fail (record in history),
  then on the lane to see it pass.

### Subtask T018 – CLAUDE.md note

- At most a few sentences pointing to the ADR amendment and naming the codes and the flag.

## Test Strategy

- `uv run --frozen pytest tests/architectural/test_scenario_contract.py tests/architectural/test_no_legacy_terminology.py -q`
- Cucumber-JVM run of the touched feature on JDK 25.

## Review Guidance

- The ADR amendment quotes both rulings; no second authority is created in CLAUDE.md.

## Progress & Status

- `spec-kitty agent tasks add-history WP04 --note "<what you did>"`
- `spec-kitty agent tasks move-task WP04 --to <status>`
