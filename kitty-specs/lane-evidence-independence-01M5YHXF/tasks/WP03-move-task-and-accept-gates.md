---
work_package_id: WP03
title: Move-task and accept gates
dependencies:
- WP01
- WP02
requirement_refs:
- FR-001
- FR-002
- FR-003
- C-004
- SC-001
- SC-002
planning_base_branch: issue-6715-lane-evidence-independence
merge_target_branch: issue-6715-lane-evidence-independence
branch_strategy: Planning artifacts for this mission were generated on issue-6715-lane-evidence-independence. During /spec-kitty.implement this WP may branch from a dependency-specific base, but completed changes must merge back into issue-6715-lane-evidence-independence unless the human explicitly redirects the landing branch.
base_branch: kitty/mission-lane-evidence-independence-01M5YHXF
base_commit: bdbe79b9141f1eef353642062b8b06f7cecf08b6
created_at: '2026-10-27T22:17:58.141585+00:00'
subtasks:
- T010
- T011
- T012
- T013
- T014
phase: Phase 3 - Early refusals
history:
- at: '2026-10-27T12:10:00Z'
  actor: system
  action: Prompt generated via /spec-kitty.tasks
agent_profile: implementer-ivan
authoritative_surface: src/specify_cli/cli/commands/accept.py
create_intent:
- tests/integration/test_6715_lane_autowalk_guards.py
- tests/specify_cli/cli/commands/test_accept_evidence_preflight.py
- tests/specify_cli/cli/commands/agent/test_move_task_evidence_gate.py
execution_mode: code_change
model: ''
owned_files:
- src/specify_cli/cli/commands/accept.py
- src/specify_cli/cli/commands/agent/tasks_move_task.py
- tests/integration/test_6715_lane_autowalk_guards.py
- tests/specify_cli/cli/commands/test_accept_evidence_preflight.py
- tests/specify_cli/cli/commands/agent/test_move_task_evidence_gate.py
role: implementer
tags: []
task_type: implement
tracker_refs: []
---

# Work Package Prompt: WP03 – Move-task and accept gates

## ⚡ Do This First: Load Agent Profile

Use the `/spk-charter-profile-load` skill to load the agent profile specified in the frontmatter (or any user-defined profile), and behave according to its guidance before parsing the rest of this prompt.

- **Profile**: `implementer-ivan`
- **Role**: `implementer`
- **Agent/tool**: `claude`

---

## ⚠️ IMPORTANT: Review Feedback

- Check `review_ref` via `spec-kitty agent tasks status`; address every item; report with
  `spec-kitty agent tasks add-history WP03 --note "..."`.

---

## Review Feedback

*[If this WP was returned from review, the reviewer feedback reference appears in the status event log.]*

---

## Objectives & Success Criteria

- The issue's exact scenario (coord, WP claimed by `claude`, no owned commit, subtask ticked,
  `move-task --to approved --agent claude --note lgtm`) refuses at the move with
  `IMPLEMENTATION_MISSING`; nothing reaches `approved`.
- An unforced approval by the implementer's own `tool:model:profile` identity (with a real
  commit) refuses with `REVIEW_NOT_INDEPENDENT` on every topology.
- `--force` keeps bypassing both at the move (ruling 3 / C-004).
- `accept` refuses (exit 1; `--json` envelope `error_code` + `error_codes`) before writing
  anything, regardless of `--lenient` and of how the WP was approved, with the same codes; and
  `accept --attest-no-implementation <WP> --attest-reason "<why>"` records the WP02 attestation
  first and then passes that WP's `IMPLEMENTATION_MISSING`.
- Positive control on lanes, coord, single_branch: real owned commit + independent review moves
  and accepts at rc 0.

## Context & Constraints

- Move-task: `_mt_require_single_branch_implementation` (`tasks_move_task.py` ~L926) is the
  single_branch gate; it runs at ~L1695 in the pipeline. Generalise it into one gate that, for
  an unforced move crossing into review territory, (a) resolves the WP's evidence window through
  `consolidation.wp_evidence` (code lane, planning lane, single_branch) and refuses
  `IMPLEMENTATION_MISSING` / `IMPLEMENTATION_UNREADABLE` / `EVIDENCE_WINDOW_UNCOMPUTABLE`; keep
  the single_branch codes and wording (existing tests:
  `tests/specify_cli/cli/commands/agent/test_single_branch_refusal_wording.py`); (b) for a move
  INTO `approved`/`done`, refuses `REVIEW_NOT_INDEPENDENT` when the approving actor's
  `actor_full_identity` (built from `--agent` plus `--profile`/`--model` or the resolved binding,
  the way the move will record it) equals the latest implementer's (`preflight._latest_implementer_identity`).
  Unknown implementer ⇒ do not refuse at the move (accept/consolidate are strict).
- Owned checkouts keep `_mt_require_owned_implementation`; don't double-gate them.
- Matching helpers `_mt_owned_file_patterns` / `_mt_matches_owned_file` must delegate to
  `wp_evidence` (one matcher).
- The move gate's window must agree with consolidate's (same module) so a move that passes is
  not refused at consolidate for evidence.
- Accept: add a preflight step in `accept()` after `_check_origin_freshness` and before
  `_collect_summary_or_exit`; use `wp_evidence`'s general refusal (WP01 public entry) on the
  status surface (`_coord_status_feature_dir` / mission_dir as accept reads it). Refuse with
  `_fail`/`_refusal_envelope` style. `--no-commit` / `--diagnose` report the refusal too (they are
  read-only; an attestation flag with them refuses as "would record" like consolidate's dry run).

## Branch Strategy

- **Planning base branch**: issue-6715-lane-evidence-independence
- **Merge target branch**: issue-6715-lane-evidence-independence

Run `spec-kitty agent action implement WP03 --agent claude --mission lane-evidence-independence-01M5YHXF`.

## Subtasks & Detailed Guidance

### Subtask T010 – Red-first fixtures

- `tests/integration/test_6715_lane_autowalk_guards.py`: the issue's exact flow on coord
  (3 WPs optional; 2 suffice: WP01 real, WP02 owns `tools/check.sh`), parametrised over coord and
  lanes; plus single_branch for the independence move gate.
  - hollow self-approval refused at the move (rc != 0, `IMPLEMENTATION_MISSING`, lane not approved);
  - coord bookkeeping commits (the "Start WPxx implementation" chore + planning merge) do not
    count;
  - real commit + self-approval (unforced) ⇒ `REVIEW_NOT_INDEPENDENT` at the move;
  - same agent name, different `--profile` ⇒ allowed;
  - hollow WP forced to approved by a different reviewer ⇒ move rc 0, `accept` refuses
    `IMPLEMENTATION_MISSING`, nothing `done`;
  - `accept --attest-no-implementation WP02 --attest-reason "docs-only"` ⇒ accept rc 0 and
    consolidate rc 0 naming WP02;
  - positive control rc 0 end to end.
- Unit-level: `tests/specify_cli/cli/commands/agent/test_move_task_evidence_gate.py`,
  `tests/specify_cli/cli/commands/test_accept_evidence_preflight.py` for branches (force bypass,
  owned checkout skip, unknown implementer, JSON envelope).
- Commit tests first; capture the red run.

### Subtask T011 – Move-task evidence gate

- Generalise `_mt_require_single_branch_implementation` (rename to a neutral name; keep the
  call site). Topology dispatch via `is_single_branch_mission` and the lane of the WP from
  `lanes.json`. Missing/corrupt `lanes.json` keeps today's behaviour (return).

### Subtask T012 – Move-task independence gate

- Only for unforced moves into `approved`/`done`; compare full identities; message:
  `REVIEW_NOT_INDEPENDENT: <WP> cannot be approved by its implementer (<identity>). Have a reviewer with a different agent, model or profile approve it.`

### Subtask T013 – Accept preflight + attestation flag

- New options `--attest-no-implementation` (repeatable) and `--attest-reason`; record through
  WP02's recorder before the preflight; refusal of the request records nothing.
- Envelope: `{"error": ..., "error_code": codes[0], "error_codes": codes}` (match
  `_refusal_envelope`).

### Subtask T014 – Re-pin fixtures

- Run move-task and accept suites; judge each newly red test (DIRECTIVE_041); re-pin with a real
  owned commit / distinct reviewer when the test's intent is elsewhere. Out-of-map edits allowed
  with a one-line rationale.

## Test Strategy

- `uv run --frozen pytest tests/specify_cli/cli/commands/agent tests/specify_cli/cli/commands/test_accept*.py tests/cli -k "accept or move" tests/integration/test_6715_lane_autowalk_guards.py tests/integration/test_5939_single_branch_autowalk_guards.py -q`
- `make test-fast`
- ruff, ruff format `--force-exclude`, mypy on touched files.

## Risks & Mitigations

- Move-task is a large pipeline with many fixtures that approve under one agent; the
  independence gate only fires on a positively-same full identity, unforced.
- Open PRs #6714 and #6705 touch move-task: expect textual merge friction only.

## Review Guidance

- The move gate and consolidate use the same window and matcher (one module).
- `--force` bypass at the move is deliberate (ruling 3).

## Progress & Status

- `spec-kitty agent tasks add-history WP03 --note "<what you did>"`
- `spec-kitty agent tasks move-task WP03 --to <status>`
