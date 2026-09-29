---
work_package_id: WP02
title: Ownership guard role allow-arms
dependencies:
- WP01
requirement_refs:
- FR-001
- FR-002
- FR-003
- FR-006
- FR-007
planning_base_branch: issue-5196-rework-is-not-an-override
merge_target_branch: issue-5196-rework-is-not-an-override
branch_strategy: Planning artifacts for this mission were generated on issue-5196-rework-is-not-an-override. During /spec-kitty.implement this WP may branch from a dependency-specific base, but completed changes must merge back into issue-5196-rework-is-not-an-override unless the human explicitly redirects the landing branch.
base_branch: kitty/mission-rework-is-not-an-override-01M3MQV6
base_commit: 59502db6825305687ecd04cc4262a05cdca0c52c
created_at: '2026-09-28T20:35:29.550410+00:00'
subtasks:
- T007
- T008
- T009
- T010
- T011
phase: Phase 2 - Unforced loop
history:
- at: '2026-09-28T20:30:00Z'
  actor: system
  action: Prompt generated via /spec-kitty.tasks
agent_profile: python-pedro
authoritative_surface: src/specify_cli/status/
create_intent:
- src/specify_cli/status/review_roles.py
- tests/unit/status/test_review_roles.py
- tests/specify_cli/cli/commands/agent/test_rework_unforced_loop.py
execution_mode: code_change
model: claude-sonnet-5-5
owned_files:
- src/specify_cli/status/review_roles.py
- src/specify_cli/status/__init__.py
- src/specify_cli/cli/commands/agent/tasks_transition_core.py
- src/specify_cli/cli/commands/agent/tasks_move_task.py
- tests/unit/status/test_review_roles.py
- tests/specify_cli/cli/commands/agent/test_tasks_transition_core.py
- tests/specify_cli/cli/commands/agent/test_rework_unforced_loop.py
role: implementer
tags: []
task_type: implement
tracker_refs: []
---

# Work Package Prompt: WP02 – Ownership guard role allow-arms

## ⚡ Do This First: Load Agent Profile

Use the `/ad-hoc-profile-load` skill to load the agent profile specified in the frontmatter, and behave according to its guidance before parsing the rest of this prompt.

- **Profile**: `python-pedro`
- **Role**: `implementer`
- **Agent/tool**: `claude`

---

## ⛔ HARD RULE — no heavy full suites during the mission

During implement and **every WP review** (by you AND every implementer/reviewer subagent you dispatch), NEVER run full or heavy suites:
- no whole `tests/architectural/`, no e2e or full-integration suites, no performance/stress/timing suites;
- no `make test-full`, no whole-repo pytest.

Per WP, run only:
- the test files covering the files the WP touches;
- the owning module's fast tier;
- the specific NAMED architectural gate files the change implicates.

Leave the broad sweeps to the END of the mission (closeout, and only the targeted set listed below) or to CI. This is the internal-pack directive NO_FULL_HEAVY_SUITES_IN_MISSION.

---

## ⚠️ IMPORTANT: Review Feedback

- **Has review feedback?** Check the `review_ref` field in the event log (via `spec-kitty agent tasks status`) or the Activity Log below.
- **You must address all feedback** before your work is complete.

---

## Objectives & Success Criteria

Make the ordinary review loop pass `move-task`'s agent-ownership guard **without `--force`**, while unrelated agents stay refused.

- **FR-001 / FR-002**: the WP's latest implementer resumes rework (`planned → claimed → in_progress`) and resubmits (`→ for_review`) unforced, after each of the three rejection routes.
- **FR-003**: a reviewer whose tool differs from the latest implementer's claims (`for_review → in_review`), approves (single hop `for_review → approved`, or from its own `in_review` claim), and rejects (`for_review → planned` with feedback), all unforced.
- **FR-006**: the WP01 ratchets stay green, so an unrelated agent is still refused on an occupied slot and on `in_review` verdicts.
- **SC-001**: 0 lane events with `force: true` strictly after the rejection, for each route.

Done when `test_rework_unforced_loop.py` was **RED on the planning base** (committed first, with the red run pasted into the Activity Log) and is GREEN now, the WP01 ratchets are green, and the named gates, ruff, format and mypy are clean.

## Context & Constraints

- Read: `spec.md`, `plan.md` (Design), `research.md` R-01..R-03 and R-07, and **`contracts/ownership-role-allowance.md`**. That contract is normative; implement it exactly.
- Root cause (code-truth): `_guard_agent_ownership` (`src/specify_cli/cli/commands/agent/tasks_transition_core.py:439-504`) compares only the **tool** of the slot occupant (`req.current_agent`) with the requester (`req.agent`), via `_actor_key`. The three rejection routes and the resubmit leave the slot holding the *other* role.
- **Do not change slot mutation.** The #4673 re-plant semantics and `test_move_task_rollback_clears_claim.py::…replants_claim` stay as they are (research R-01).
- **C-008**: the refusal `error` string is pinned byte-exact (`test_move_task_durability.py:~2325`, `test_tasks_transition_core.py:~268`), and the `ownership_refusal` diagnostic stays. Any new hint goes into `console_warning` only.
- `in_review → *` stays claim-holder-only, so the reviewer-vs-reviewer race classification (`tests/integration/test_review_durability_matrix.py:2647-2777`, read-only) is unchanged.
- C-001: no edits under `src/specify_cli/consolidation/**` or `tests/integration/**`.
- NFR-002: every touched or added function has cc ≤ 15 (`_mt_gather_review_facts` is ~6 today; the guard is 4).
- Don't add a new top-level `_mt_*` function in `tasks_move_task.py`: `test_tasks_compat_surface.py` would then demand a registry row and a `tasks.py` re-export.

## Branch Strategy

- **Strategy**: lanes (populated by finalize-tasks)
- **Planning base branch**: `issue-5196-rework-is-not-an-override`
- **Merge target branch**: `issue-5196-rework-is-not-an-override`

Worktrees are allocated per computed lane from `lanes.json`. Start with `spec-kitty agent action implement WP02 --agent <you>`. Use the WP01 harness from the lane base.

## Subtasks & Detailed Guidance

### Subtask T007 – RED: unforced two-cycle loop across 3 rejection routes (commit FIRST)

- **File**: `tests/specify_cli/cli/commands/agent/test_rework_unforced_loop.py` (new). Import from `_rework_loop_harness` (WP01).
- **Tests**:
  - `@pytest.mark.regression` plus the directory's normal markers. Add a docstring citing #5196.
  - Parametrize over `route ∈ {for_review_to_planned, in_review_to_planned, in_review_to_in_progress}`:
    1. `drive_to_for_review` (IMPLEMENTER).
    2. `reject(route, REVIEWER)`. For `for_review_to_planned` the rejection must be **unforced** as well (FR-003 covers reviewer rejection from `for_review`).
    3. The IMPLEMENTER resumes (`→ claimed` → `in_progress`, or just `→ for_review` from `in_progress` for the in_progress route) and resubmits `→ for_review`, with no `--force`.
    4. The REVIEWER claims `→ in_review`, then `→ approved`, with no `--force`.
    5. Assert every exit is 0, `forced_after(rejection_idx) == 0`, all five `override_probes` are False, and `review_cycle_files == ["review-cycle-1.md", "review-cycle-2.md"]`.
       - That last assertion observes #5194. If it fails for a reason unrelated to this WP, do not fix it. Scope the assertion down and add a note in the Activity Log for the orchestrator to post on #5194.
  - A single-hop variant: after the resubmit, the REVIEWER runs `for_review → approved` unforced.
- **Run it on the base** and paste the failing summary into the Activity Log. Expected red: `Agent mismatch: WP01 is assigned to …`.
- **Commit** this file alone as the first lane commit: `test(rework): red-first unforced review loop (#5196)`.

### Subtask T008 – Pure role projection

- **File**: `src/specify_cli/status/review_roles.py` (new, pure leaf, no I/O). Follow the precedent of `src/specify_cli/status/review_claim_predicate.py`.
- **API**: `latest_implementer_actor(events: Sequence[StatusEvent], wp_id: str) -> str | None`. Declare `__all__`.
- **Rule** (from the contract): scan the WP's events newest-first and return the actor of the first event with `to_lane ∈ {claimed, in_progress}` that is **neither**:
  - a reviewer rework verdict: `from_lane ∈ {for_review, in_review, approved}` **and** `review_ref` set; nor
  - an event whose actor projects (`_actor_key`) into `GENERIC_IMPLEMENTATION_ACTORS`.
- Normalize lanes with `resolve_lane_alias` / `Lane`. Return the actor **as recorded** (string form); the guard compares via `_actor_key`. If a dict-shaped actor exists, use `actor_identity_str` or whatever `_actor_key` accepts.
- **Facade**: re-export `latest_implementer_actor` from `src/specify_cli/status/__init__.py` and add it to `__all__`. The SR-2 boundary gate forbids `tasks_move_task.py` importing the submodule directly.
- **Tests**: `tests/unit/status/test_review_roles.py` (`pytestmark = pytest.mark.unit`), one test per truth-table row:
  1. The plain implementer claim is counted.
  2. `in_review → in_progress` by the reviewer with a `review_ref` is skipped, and the earlier implementer is returned.
  3. The legacy review claim `for_review → in_progress` with `review_ref="action-review-claim"` is skipped.
  4. The `action implement` rework `in_review → in_progress` by a new actor with **no** `review_ref` is counted, so a takeover is honoured.
  5. A forced `planned → claimed` carrying a copied rejection `review_ref` (the legacy log) is counted.
  6. Generic actors (`user`, `implement-command`, `unknown`) are skipped.
  7. No qualifying event returns `None`.
  8. Other WPs' events are ignored.
  9. A dict-shaped actor claim (`{"tool": "codex", ...}`, which move-task writes) is returned, and projects correctly through `_actor_key`.

  Use realistic ULID-shaped event ids and full `tool:model:profile:role` actors.

### Subtask T009 – Request field + guard allow-arms

- **File**: `tasks_transition_core.py`.
  - Add `latest_implementer: str | None = None` to the frozen `MoveTaskRequest` dataclass, after `mission_slug`, with a default so `_base_request` test constructors stay valid.
  - Add pure helpers:
    - `_reviewer_arm(req) -> bool`: `old == FOR_REVIEW`, `target ∈ {IN_REVIEW, APPROVED, PLANNED}`, and `_actor_key(req.agent) != _actor_key(req.latest_implementer)`.
    - `_implementer_arm(req) -> bool`: `old ∈ {PLANNED, CLAIMED, IN_PROGRESS}`, `target ∈ {CLAIMED, IN_PROGRESS, FOR_REVIEW}`, and the keys are equal.
    - `_ownership_role_allowance(req) -> bool`: returns False when `latest_implementer` is empty, or when its key is generic or `None`. Otherwise it returns `_reviewer_arm(req) or _implementer_arm(req)`.
    - Normalize lanes with `resolve_lane_alias`.
  - In `_guard_agent_ownership`, after the existing early return, add `if _ownership_role_allowance(req): return None`. Leave the `error` string and the diagnostic untouched.
  - **Mandatory (FR-007's refusal-text surface)**: append one line to `console_warning`: "   After a review rejection, the implementer resumes with its own --agent and a reviewer distinct from the implementer can review; neither needs --force." The `error` string is unchanged. Add a unit assertion on the new `console_warning` line. If some test pins the warning tuple byte-exact, re-pin it with a #5196 rationale.
- **Tests**: `test_tasks_transition_core.py`. Add rows via `_base_request(**overrides)`:
  - Reviewer arm allowed for `for_review → in_review / approved / planned` (feedback provided).
  - Reviewer arm refused when the requester's tool == the latest implementer's tool.
  - Reviewer arm does not apply to `done` or to `in_review → approved`.
  - Implementer arm allowed for `planned → claimed`, `claimed → in_progress`, `in_progress → for_review`.
  - Implementer arm refused for a THIRD tool.
  - `latest_implementer=None` and a generic latest implementer: refused as today.
  - `--force` path unchanged.
  - The existing byte-exact refusal assertions still pass.

### Subtask T010 – Resolve the fact in pass 1 (fail-closed)

- **File**: `tasks_move_task.py`, **inline** in `_mt_gather_review_facts` (~line 947), with no new top-level `_mt_*` function.
  - Read events once with `_tasks.read_events_transactional(feature_dir=st.feature_dir, mission_slug=st.mission_slug, repo_root=st.main_repo_root, **({"effective_root": st.owned.root} if st.owned else {}))`. Use the same keywords as `_mt_current_event_lane` (~2518).
  - Compute `latest_implementer_actor(events, st.task_id)`.
  - Wrap the read in `except Exception:  # noqa: BLE001 — fail closed toward today's behaviour (R-03)` (the house pattern; unit tests call pass-1 helpers with bare state), and set `None` on failure.
  - Pass it into `_mt_build_request(..., latest_implementer=...)` as a new keyword. Update `_mt_build_request`'s signature and its `MoveTaskRequest(...)` construction.
- **NFR-001**: this is exactly one additional event read per `move-task`.
- Add **no new top-level callable** to `tasks_move_task.py`: `test_tasks_compat_surface.py::_native_module_defs` pins every callable defined there. If extraction is needed, put the helper in `tasks_transition_core.py` or `status/review_roles.py`.

### Subtask T011 – Green-up, un-mark, gates

- Remove `@pytest.mark.regression` from `test_rework_unforced_loop.py` once it is green (ADR `docs/adr/3.x/2026-07-17-1-*`: red-first repros are converted to focused tests and never left regression-marked). Keep the focused tests.
- Run (targeted only):

```bash
uv run --frozen pytest tests/specify_cli/cli/commands/agent/test_rework_unforced_loop.py tests/specify_cli/cli/commands/agent/test_rework_guard_ratchets.py tests/unit/status/ tests/specify_cli/cli/commands/agent/test_tasks_transition_core.py tests/specify_cli/cli/commands/agent/test_move_task_rollback_clears_claim.py tests/specify_cli/cli/commands/agent/test_tasks_move_task_seam.py tests/specify_cli/cli/commands/agent/test_move_task_durability.py tests/specify_cli/cli/commands/agent/test_tasks_compat_surface.py tests/specify_cli/cli/commands/agent/test_move_task_reject_fix_approve_cycle.py tests/specify_cli/cli/commands/agent/test_fixmode_ownership_4673.py tests/specify_cli/cli/commands/agent/test_move_task_agent_persistence_3029.py tests/specify_cli/cli/commands/agent/test_move_task_orchestration.py tests/status/test_work_package_lifecycle.py -q
uv run --frozen pytest tests/architectural/test_status_module_boundary.py tests/architectural/test_no_dead_symbols.py tests/architectural/test_no_dead_modules.py tests/architectural/test_layer_rules.py tests/architectural/test_cold_import_status_boundary.py tests/architectural/test_fast_tier_marker_completeness.py tests/architectural/test_src_reachability_guard.py tests/architectural/test_status_events_writes_gate.py tests/architectural/test_2093_authority_invariant.py tests/architectural/test_verdict_vocab_single_source.py -q
uv run --frozen ruff check <touched files> && uv run --frozen ruff format --check <touched files>
uv run --frozen mypy src/specify_cli/status/review_roles.py src/specify_cli/cli/commands/agent/tasks_transition_core.py src/specify_cli/cli/commands/agent/tasks_move_task.py
uv run --frozen ruff check --select C901 src/specify_cli/cli/commands/agent/tasks_transition_core.py src/specify_cli/cli/commands/agent/tasks_move_task.py src/specify_cli/status/review_roles.py
```

- If a named gate file does not exist, note it and skip it. If a gate reds, classify it against the base per the baseline-red gotcha in `CLAUDE.md` before acting.

## Risks & Mitigations

- **Generic actor vacuity** (post-plan D2): a generic `latest_implementer` must never grant an arm (T008 row 6, T009 generic row).
- **Hop expansion** (D3): a reviewer who walks a WP forward from `planned` becomes the "latest implementer". Tests must not route a reviewer through `planned → in_review`.
- **Pre-existing residual** (research R-07): once a same-tool implementer holds the slot, the existing same-key check lets it approve its own work from `for_review`. That behaviour is unchanged. Do not claim to fix it.

## Review Guidance

- Verify the RED commit precedes the implementation commits, and the red output is in the Activity Log.
- Verify the contract rules exactly: the exclusions, `done` absent from the reviewer arm, `in_review → *` untouched.
- Verify the refusal `error` string is unchanged and the diagnostic keys are intact.
- Verify the WP01 ratchets are still green (FR-006).
- Reviewer ≠ implementer. Respect the HARD RULE.

## Hardening (post-tasks squad — binding)

- T007 calls `reject(..., allow_force=False)` for **all** routes, and passes `--agent` on every hop (the harness asserts this).
- **RED proof**: in the Activity Log, show that the base failure output contains `Agent mismatch` at the expected first refused hop:
  - `for_review_to_planned`: the reject itself;
  - `in_review_*`: the cycle-1 review claim `for_review → in_review` (then the rework hops).

  A red for any other reason (fixture, import) is not a valid RED.
- Assert via the harness `argv_log` that `"--force"` appears in no argv after `drive_to_for_review`.
- `CLAUDE.md`'s "`__init__.py` change ⇒ version bump + CHANGELOG" rule applies to the package root `src/specify_cli/__init__.py`, not `status/__init__.py`. The CHANGELOG entry is written at mission closeout. Do not bump the version.

## Activity Log

- 2026-09-28T20:30:00Z – system – Prompt created.
