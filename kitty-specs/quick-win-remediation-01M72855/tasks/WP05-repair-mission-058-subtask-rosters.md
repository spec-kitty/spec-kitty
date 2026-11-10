---
work_package_id: WP05
title: Repair Mission 058 subtask rosters
dependencies:
- WP02
requirement_refs:
- FR-012
- NFR-005
- C-005
- C-008
- SC-004
planning_base_branch: fix/quick-win-remediation
merge_target_branch: fix/quick-win-remediation
branch_strategy: Planning artifacts for this mission were generated on fix/quick-win-remediation. During /spec-kitty.implement this WP may branch from a dependency-specific base, but completed changes must merge back into fix/quick-win-remediation unless the human explicitly redirects the landing branch.
subtasks:
- T020
- T021
- T022
phase: Phase 2 - Data repair
history:
- at: '2026-11-10T08:19:33Z'
  actor: system
  action: Prompt generated via /spec-kitty.tasks
agent_profile: implementer-ivan
authoritative_surface: kitty-specs/058-hybrid-prompt-and-shim-agent-surface/tasks/
create_intent: []
execution_mode: planning_artifact
model: glm-5.3
owned_files:
- kitty-specs/058-hybrid-prompt-and-shim-agent-surface/tasks/WP01-restore-command-templates.md
- kitty-specs/058-hybrid-prompt-and-shim-agent-surface/tasks/WP02-registry-and-generator.md
- kitty-specs/058-hybrid-prompt-and-shim-agent-surface/tasks/WP03-init-hybrid-install.md
- kitty-specs/058-hybrid-prompt-and-shim-agent-surface/tasks/WP04-consumer-migration.md
- kitty-specs/058-hybrid-prompt-and-shim-agent-surface/tasks/WP05-deploy-to-consumers.md
- kitty-specs/058-hybrid-prompt-and-shim-agent-surface/tasks/WP06-tests-and-validation.md
role: implementer
tags: []
task_type: implement
tracker_refs: []
---

# Work Package Prompt: WP05 – Repair Mission 058 subtask rosters

## ⚡ Do This First: Load Agent Profile

Use the `/spk-charter-profile-load` skill to load the agent profile specified in the frontmatter (or any user-defined profile), and behave according to its guidance before parsing the rest of this prompt.

- **Profile**: `implementer-ivan`
- **Role**: `implementer`
- **Agent/tool**: `opencode`

If no profile is specified, run `spec-kitty agent profile list` and select the best match for this work package's `task_type` and `authoritative_surface`.

---

## ⚠️ IMPORTANT: Review Feedback

**Read this first if you are implementing this task!**

- **Has review feedback?**: Check the `review_ref` field in the event log (via `spec-kitty agent tasks status`).
- **You must address all feedback** before your work is complete. Feedback items are your implementation TODO list.
- **Report progress**: As you address each feedback item, record what you changed with `spec-kitty agent tasks add-history <WPID> --note "..."` (stored in the status event log).

---

## Review Feedback

*[If this WP was returned from review, the reviewer feedback reference appears in the status event log.]*

---

## Markdown Formatting

Wrap HTML/XML tags in backticks: `` `<div>` ``, `` `<script>` ``
Use language identifiers in code blocks: ````python`,````bash`

---

## Objectives & Success Criteria

**#7442 one-off data repair (operator decision 2026-11-10).** WP02 makes the subtask roster refuse any `subtasks:` entry that is not a task id. Mission 058 (`kitty-specs/058-hybrid-prompt-and-shim-agent-surface/`) is the only Mission in the repository whose WP files author `subtasks:` as maps; its six WP files hold 28 such entries. Rewrite each map entry as a plain task id, in the same order, changing **no other byte** of those files. (FR-012, NFR-005, C-005, C-008, SC-004)

Done means:
- `authored_subtask_roster(Path("kitty-specs/058-hybrid-prompt-and-shim-agent-surface"), "WP0N")` returns the expected ids for N = 1…6 (table below) instead of refusing.
- `git diff` of the six files shows only the 28 entry rewrites (each `- id: TNNN` line becomes `- TNNN`; each entry's `title:` and `status:` lines are removed). Nothing else changes.
- `tests/architectural/test_archive_root_byte_identical.py` passes (WP02's sanctioned-correction entry covers exactly these six paths).

## Context & Constraints

- Spec: `kitty-specs/quick-win-remediation-01M72855/spec.md` (User Story 5 scenario 6, FR-012, NFR-005, C-005, C-008). Plan: `plan.md` IC-06. Decision `01M7286ZAMNZ9S1E0CA4MZNG27`.
- **Dependency**: WP02 must be approved first — it adds the roster rule and the `_OPERATOR_SANCTIONED_CORRECTIONS` entry in `tests/architectural/test_archive_root_byte_identical.py`. Without that entry the archive gate refuses any edit to these archived files. Do **not** edit the gate file here (WP02 owns it).
- **Nothing is lost**: every title is also in Mission 058's own `tasks.md`, and the per-entry `status: planned` is stale (all six 058 WPs are `approved` in its `status.json`; subtask completion is event-sourced). The backfill seed reads subtask runtime from `tasks.md`, not frontmatter (`src/specify_cli/migration/backfill_runtime_state.py:541,604`).
- **Edit line-wise** (C-008): a text editor or a careful line-based edit. Do **not** load and re-dump the files through `FrontmatterManager`, `ruamel.yaml` or any YAML writer — they may reorder keys, re-quote strings or reflow lines.
- Leave `kitty-specs/058-hybrid-prompt-and-shim-agent-surface/tasks.md`, `README.md`, `meta.json`, `status.*` and every other file untouched. Note: `kitty-specs/058-mission-template-repository-refactor/` is a different Mission and is not affected.
- No `make test-fast`, no `make test-full`, no bare directories.

### Entries to rewrite (verify against the files before editing)

| File (`tasks/`) | Entries (in order) | Count |
|---|---|---|
| `WP01-restore-command-templates.md` | T001 T002 T003 T004 T005 T006 T007 | 7 |
| `WP02-registry-and-generator.md` | T008 T009 T010 T011 | 4 |
| `WP03-init-hybrid-install.md` | T012 T013 T014 T015 | 4 |
| `WP04-consumer-migration.md` | T016 T017 T018 | 3 |
| `WP05-deploy-to-consumers.md` | T019 T020 T021 T022 T023 | 5 |
| `WP06-tests-and-validation.md` | T024 T025 T026 T027 T028 | 5 |

Each entry today is three lines, e.g. (`WP03-init-hybrid-install.md:18-20`):

```yaml
- id: T012
  title: Update init.py to call generate_agent_assets() for prompt-driven commands
  status: planned
```

and becomes:

```yaml
- T012
```

Watch for: a single-quoted title (`WP03` T015: `title: 'Integration test: …'`); a title that wraps onto a continuation line (if any entry spans more than three lines, remove the whole entry body — every line indented under the `- id:` line — and nothing else); the `subtasks:` key itself and its indentation stay exactly as they are.

## Branch Strategy

- **Strategy**: populated by finalize-tasks
- **Planning base branch**: populated by finalize-tasks
- **Merge target branch**: populated by finalize-tasks

> These fields are populated automatically by `spec-kitty agent mission finalize-tasks`.
> Do NOT change them manually unless you are certain the branch topology has changed.
> Execution worktrees are allocated per computed lane from `lanes.json`. Start with:
> `spec-kitty agent action implement WP05 --agent opencode --mission quick-win-remediation-01M72855`

## Subtasks & Detailed Guidance

### Subtask T020 – Baseline evidence (the red check for FR-012)

- **Purpose**: prove, on the tree that includes WP02, that the 058 rosters refuse before the repair.
- **Steps**:
  1. Confirm WP02 is approved/done: `spec-kitty agent tasks status --mission quick-win-remediation-01M72855`.
  2. In your workspace (which includes WP02's changes), run a one-off read (no file written to the repo):
     ```bash
     .venv/bin/python -c "
     from pathlib import Path
     from specify_cli.core.subtask_rows import authored_subtask_roster, SubtaskRosterResolutionError
     d = Path('kitty-specs/058-hybrid-prompt-and-shim-agent-surface')
     for n in range(1, 7):
         try:
             print(f'WP0{n}', authored_subtask_roster(d, f'WP0{n}'))
         except SubtaskRosterResolutionError as e:
             print(f'WP0{n} REFUSED:', e)
     "
     ```
     Expect six `REFUSED` lines naming each file and the list form. Record the output in `spec-kitty agent tasks add-history WP05 --note "T020 baseline: 6/6 refused"`.
  3. Also count the entries to repair: `grep -c "^- id: T" kitty-specs/058-hybrid-prompt-and-shim-agent-surface/tasks/WP0*.md` → 7, 4, 4, 3, 5, 5 (total 28). If the counts differ, stop and record it — the table above would be stale.

### Subtask T021 – Line-wise rewrite of the 28 entries

- **Steps**:
  1. For each of the six files, inside the `subtasks:` block only: replace `- id: TNNN` with `- TNNN` and delete the entry's indented continuation lines (`  title: …`, `  status: …`). Keep ids in their existing order.
  2. Do not touch any other line: other frontmatter keys, the body, trailing newline, line endings.
  3. Commit the six files together with a message such as `fix(kitty-specs): author Mission 058 subtask rosters as task-id lists (#7442)` and a body naming the operator decision (2026-11-10) and the sanctioned-correction entry added by WP02.
- **Files**: the six WP files listed in `owned_files`.

### Subtask T022 – Verification

- **Steps**:
  1. Re-run the T020 one-off read → each WP prints its ids exactly as in the table (WP01 `['T001', …, 'T007']`, …, WP06 `['T024', …, 'T028']`).
  2. Byte-minimality (NFR-005): `git diff --stat <WP02 approved tip or the lane base>.. -- kitty-specs/058-hybrid-prompt-and-shim-agent-surface/` shows only the six files; `git diff` shows only `- id: TNNN` → `- TNNN` changes and removed `title:` / `status:` lines (28 entries). `git diff --check` is clean.
  3. Run:
     ```bash
     git fetch origin main   # the archive gate resolves merge-base(HEAD, main)
     .venv/bin/python -m pytest -q tests/architectural/test_archive_root_byte_identical.py \
       tests/specify_cli/migration/test_dogfood_corpus_backfilled.py tests/architectural/test_bare_prose_corpus_ratchet.py
     ```
     Record commands and counts with `add-history`.
  4. Tracer: one `tooling-friction` or `approach` entry about the archived-data repair (e.g. the sanctioned-correction route and its follow-up removal) via `spec-kitty agent tracer-append --mission quick-win-remediation-01M72855 --category approach --actor "<agent:model:profile>" --entry "**[YYYY-MM-DD][implement] ...**"`.

## Test Strategy

Verification is the roster read (T020/T022) plus the three named test files above. No unit test is added: this WP owns only data files, and WP02's tests own the roster rule.

## Risks & Mitigations

- **Archive gate red** → the sanctioned entry from WP02 must be present on your base; if the gate still reports these paths, check that WP02's entry names exactly the same six paths (case and spelling) and tell the reviewer — do not edit the gate here.
- **YAML writer reformatting** → forbidden; line-wise edit only.
- **Wrapped titles** → remove every indented line belonging to the entry, nothing beyond it.

## Review Guidance

- Diff is exactly 28 entry rewrites across six files, ids in order, no other byte changed.
- The T020 baseline (6/6 refused) and the T022 read (6/6 resolved) are both recorded in the WP history.
- Archive gate, corpus reader and prose ratchet green.

## Progress & Status

Progress, history, and status all live in the status event log
(`status.events.jsonl`) — never in this prompt file. Do **not** hand-edit a
history section here.

- **Record a progress note**: `spec-kitty agent tasks add-history <WPID> --note "<what you did>"`
- **Change WP status**: `spec-kitty agent tasks move-task <WPID> --to <status>`
- **View history and status**: `spec-kitty agent tasks status`
