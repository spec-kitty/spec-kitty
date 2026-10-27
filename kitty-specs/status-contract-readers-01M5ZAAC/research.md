# Research: Status contract readers

Phase 0 grounding for #6448 and #6400, taken on `origin/main` `581b5c46` (2026-10-27).

## 1. Code grounding (cited lines re-verified)

### #6448: hand-copied lane tuple

- `src/specify_cli/status_lanes.py:8-18`: `CANONICAL_LANES` is a literal 9-tuple
  (`planned` .. `canceled`).
- `spec_kitty_events.status.Lane` (installed 11.0.0, pin `>=11.0.0,<12`) has 10 members in
  this order: `genesis, planned, claimed, in_progress, for_review, in_review, approved, done,
  blocked, canceled`. Removing `genesis` gives exactly today's tuple, in the same order.
- Consumers that must not see `genesis` (triage comment, re-verified):
  - `task_metadata_validation.py:269-278`: frontmatter `lane` validation (authorable lanes + `doing`).
  - `status/validate.py:116-126`: `genesis` allowed only as a `from_lane`.
  - `status/event_log_merge.py:18-33`: forward rank from the *declared* order of
    `CANONICAL_LANES` minus `blocked`/`canceled`; enum order happens to match but the code
    must keep the explicit order.
  - Also `task_utils/support.py:28` (`LANES`), `m_2_0_6_consistency_sweep.py:230,354`,
    `status/transitions.py:19`, `status/__init__.py:99`.
- A second local copy exists: `status/models.py:29` `Lane(StrEnum)` = package lanes plus the
  read sentinel `uninitialized`. #6185 (which owned the "3x lane-list duplication") is closed
  not-planned, so the duplication sits with this mission. Replacing the `StrEnum` itself is out
  of scope (hundreds of call sites); a parity guard is in scope.
- Red-first: no test fails today because the tuple happens to match. The red test is the
  missing derivation: an `AUTHORABLE`/derivation contract test that imports the new names
  (ImportError on base) and a parity test against the package enum.

### #6400: two actor shapes, profile always null

- `cli/commands/agent/tasks_mark_status.py:506`: `actor="user"` on the subtask annotation.
- `cli/commands/agent/tasks_move_task_executor.py:236-250`: a transition gets the structured
  actor only when `_binding_role_for_lane(target)` is not `None` **and** a resolved binding
  exists; `for_review`, `in_progress`, `planned` (rejection) hops and every hop without
  `--profile`/`--invocation-id` write the bare `_mt_hop_actor` string
  (`tasks_move_task_hops.py:139-162`, falls back to `"user"`).
- `tasks_move_task_executor.py:542`: paired note annotation actor is the bare string
  `st.final_hop_actor or st.actor`.
- `tasks_verdict_persistence.py:734` → `tasks_materialization.py:70-106` `_persist_review_artifact_override`: the review-override (verdict) annotation is written with `actor=st.agent or "operator"`.
- `agent issue-verdict` (`issue_verdict.py`) writes issue-matrix rows only, never a status event, so it has no status actor to fix; the #6400 acceptance item "review verdict path" is the review-override annotation above.
- `tasks.py:1217` (`agent tasks add-history`): note annotation with the bare `agent_name`.
- `workflow_executor.py:680,921,1067,1212,1237,1970`: implement/review annotations pass the
  bare `agent` string; the transitions at `:903`/`:1925` use `build_self_asserting_actor`.
- `status/emit.py:1366-1450`: `build_resolved_actor` / `build_self_asserting_actor` are the
  existing structured builders. They never consult WP frontmatter and record no provenance.
- `status/models.py:161-195`: `decode_actor` requires **exactly** the four keys
  `{role, profile, tool, model}`; a fifth key raises. Must widen to accept the new key while
  still reading legacy 4-key dicts and strings.
- `status/models.py:255` `actor_full_identity` (#5340/#5939 independence) compares
  `tool:model:profile`.
- `status/work_package_lifecycle.py:116` `_actor_key` is tool-only; claim matching and
  `review_roles` (`:53-99`) are unaffected by a profile change.
- `contracts/mission-status/schemas/Actor.yaml`: the Read API projection is `{tool, role,
  profile}`, `additionalProperties: false`; it copies field by field, so an extra stored key
  is dropped by the projection, not forwarded. Adding `profile_source` to the read contract is
  #6409's call, not this mission's.
- Red-first: a `move-task --to for_review` and a `mark-status` run on a fixture mission whose
  WP declares `agent_profile` write a bare-string actor with no profile today. The ATDD test of
  the first implementation WP pins that through the real CLI entry points.

- Performance: every CLI invocation already imports `spec_kitty_events` (checked with `-X importtime`: `--version`, `--help`, `agent tasks status --help`, `next --help` all load it), so deriving lanes at import costs the CLI nothing.

## 2. Architectural alignment

- ADR 2026-10-22-1 (Java write service is the canonical writer): the CLI keeps the domain
  decision and sends a command carrying "Mission identity, work package, intended transition,
  **actor**, evidence" (ADR line 113). Building the actor is CLI-side request construction and
  survives the cut-over; reader changes (`decode_actor`, identity projection) survive too.
  Nothing here adds a Python append path or changes the two persistence doors.
- Epic #6608/#6117: the actor shape is part of the payload the Java core will validate.
  Proposed to spec-kitty-events #92 (comment drafted; posting needs repository access).
- Ordering stays wall-clock (#4941); Lamport is post-GA (#6609). Not touched.
- `spec_kitty_events.StatusTransitionPayload.actor` accepts `Union[str, Dict[str, Any]]`, so
  the extra key needs no package change.

## 3. Related issues and surfaces

| Item | Relation | Action |
|---|---|---|
| #6715 (branch `issue-6715-lane-evidence-independence`, mission `lane-evidence-independence-01M5YHXF`, planning only) | Edits `tasks_move_task.py`; independence reuses `tool:model:profile` with "no new event field" (its C-002) | Frontmatter-filled profiles are excluded from `actor_full_identity` (operator decision), so identities stay byte-identical to today; rebase after it if it merges first |
| #6675 / #6716 (PR, Java lock spike) | Protocol and Java only | No file overlap |
| #6185 | Closed not-planned | Lane duplication falls to this mission (parity guard) |
| #6411, #6447/#6449 | Parked for events #92 | Not touched |
| #6409 | Queued behind this mission | Read API may expose `profile_source` later |
| #3532, #3859, #2861 | Distinct (event model, flag naming, closed leak) | Not touched |

## 4. Tidy-first candidates

- Lift the profile-resolution inputs (binding, compact `--agent`, WP frontmatter) into one
  pure helper before changing behaviour, so every write path calls one seam.
- `tasks_move_task_executor._mt_emit_transitions` is long; the actor branch extracts cleanly.

## Decisions (operator, 2026-10-27; Decision Moments recorded)

- `profile_source` in {`invocation`, `flag`, `agent_string`, `wp_frontmatter`}, `null` exactly
  when `profile` is `null`.
- `actor_full_identity` ignores a `wp_frontmatter` profile.
- Scope: agent/operator write paths; system writers keep string actors (follow-up issue).
- `mark-status` gains an optional `--agent`; default tool `user`, role `implementer`.
