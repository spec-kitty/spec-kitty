---
work_package_id: WP02
title: Document the documented default and record the change
dependencies:
- WP01
requirement_refs:
- FR-005
- FR-006
- SC-004
planning_base_branch: issue-6501-legacy-agent-list-no-widening
merge_target_branch: issue-6501-legacy-agent-list-no-widening
branch_strategy: Planning artifacts for this mission were generated on issue-6501-legacy-agent-list-no-widening. During /spec-kitty.implement this WP may branch from a dependency-specific base, but completed changes must merge back into issue-6501-legacy-agent-list-no-widening unless the human explicitly redirects the landing branch.
base_branch: kitty/mission-legacy-agent-list-no-widening-01M68J84
base_commit: a2c760f37b114fdf01f70c33d0f51e85e10066d6
created_at: '2026-10-31T09:27:47.790120+00:00'
subtasks:
- T005
- T006
- T007
history:
- at: '2026-10-31T08:55:00Z'
  actor: claude
  action: created by /spec-kitty.tasks
agent_profile: python-pedro
authoritative_surface: docs/
create_intent: []
execution_mode: code_change
owned_files:
- docs/api/configuration.md
- docs/changelog/CHANGELOG.md
- src/specify_cli/agent_utils/ignore_entries.py
role: implementer
tags: []
tracker_refs:
- '6501'
---

# WP02 — Document the documented default and record the change

## ⚡ Do This First: Load Agent Profile

Load **`python-pedro`** (implementer) with the `/spk-charter-profile-load` skill before reading
anything else. The review runs under `reviewer-renata`.

## Objective

The configuration reference currently promises the *old* behaviour ("default to the full
slash-command agent set"), which WP01 changes. Make the documentation state the rule the code now
follows, and record the user-facing change. Spec: FR-005, FR-006, SC-004.

## Branch Strategy

Planning base and merge target: `issue-6501-legacy-agent-list-no-widening`.

```bash
spec-kitty agent action implement WP02 --agent claude --mission legacy-agent-list-no-widening-01M68J84
```

## Subtasks

### T005 — Configuration reference

**File**: `docs/api/configuration.md` (the `> **Legacy behavior**:` blockquote under
"Config-Driven Agent Management", ~line 424, and the `agents.available` field rows).

State the documented default precisely:

- a config with no `agents.available` list is a legacy project; Spec Kitty treats the agents whose
  project command surface is already present (`.claude/commands`, `.github/prompts`, ...) as in use;
- it never widens to agents the project does not have, and it never creates a surface that was not
  there;
- the read warns once naming `.kittify/config.yaml` and `agents.available`, and the remedy is
  `spec-kitty agent config` (an explicit list is authoritative; `available: []` means none);
- a stated list — including `[]` — is used exactly as written (#6494).

Keep it short; no second description of the schema.

### T006 — The asymmetry note in code

**File**: `src/specify_cli/agent_utils/ignore_entries.py` — docstring of `ignored_agent_keys` only.

It currently says a config with no list "keeps every agent, the same fallback as
`get_agent_dirs_for_project` (#6501 owns that case)". After WP01 that is no longer the same fallback,
and the difference is deliberate: over-ignoring generated files is harmless (it only keeps untracked
files out of `git status`), while over-*acting* rewrites user files. Rewrite the sentence to say so
and keep the behaviour unchanged. No code change.

### T007 — Changelog

**File**: `docs/changelog/CHANGELOG.md`, `[Unreleased]` → `### Fixed` (find the existing heading; do
not add a second one). One entry, house style (bold impact-first lead, **Before:** / **After:**, then
`(#issue)`), under 1,200 characters, citing `(#6501)`:

- what a legacy project used to get (every agent folder rewritten or recreated by migrations and
  audited by `doctor`);
- what it gets now (only the agents whose command surface is already present, plus a warning naming
  the file and the key);
- what did not change (`available: []` still means none; a stated list is authoritative; a corrupt
  config still fails closed).

Then run the touched-docs checks: `uv run python -m scripts.docs.check_docs_freshness --ci` (expect
errors=0) and the legacy-terminology architectural test.
