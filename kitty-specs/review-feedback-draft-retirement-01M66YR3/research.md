# Research — review-feedback-draft-retirement-01M66YR3

Discovery findings for spec-kitty/spec-kitty#6632. Every claim below was checked against the code in
this clone at planning time, and the reproduction was run end-to-end.

## D-1 — The issue still reproduces on current `main` (grounding)

Reproduced through the real CLI on a lanes-shaped fixture mission (git repo, one WP, event log seeded
genesis → planned → claimed → in_progress → for_review → in_review, `auto_commit: true`,
`protected_branches: []`, a lane implementation commit and a recorded `planning_commit_sha` so the
evidence-window gate passes):

```text
move-task WP01 --to planned --review-feedback-file .../tasks/WP01-core/review-feedback-1.md
  exit 0
  git status --porcelain kitty-specs/ →
    ?? kitty-specs/001-repro-6632/status.events.jsonl
    ?? kitty-specs/001-repro-6632/status.json
    ?? kitty-specs/001-repro-6632/tasks/WP01-core/review-feedback-1.md
move-task WP01 --to for_review
  exit 1
  Error: Cannot move WP01 to for_review
  Blocking: 1 uncommitted file(s):
    ?? kitty-specs/001-repro-6632/tasks/WP01-core/review-feedback-1.md (owned by WP01)
```

The two `status.*` entries are benign under `classify_dirty_paths` (`is_toolchain_generated_churn`);
the feedback draft is the only blocking entry, and it is blocking **because** it is the moving WP's
own residue (`review/dirty_classifier.py::owning_wp_for_path`).

Not superseded: `git log -S` over `review/cycle.py`, `tasks_verdict_persistence.py`,
`workflow_executor.py` and `dirty_classifier.py` shows no change that retires or commits the source
file; `docs/changelog/CHANGELOG.md` has no #6632 entry; the only merged PR that mentions the issue
(#6740) touches local event-log retention. #2939 (closed) made the *record* durable — its regression
test asks for a clean tree after the rejection, which is exactly what is still false for the source
file. #3430 (closed) introduced the advertised sibling filename; its changelog entry claims the file
is "still committed in the WP's own in-repo directory", which no code does.

## D-2 — Where the leftovers come from

- `review/cycle.py::review_feedback_source_path` owns the advertised name
  `review-feedback-<N>.md`; `next_review_feedback_source_path` numbers it through the same
  `max(parsed) + 1` authority the record allocator uses.
- `cli/commands/agent/workflow.py` prints that path in the review prompt; `workflow_executor.py`
  labels it "in-repo, committed with the project" and adds "The Python script handles all file
  updates automatically" — the two claims that make the leftover look acceptable.
- `cli/commands/agent/tasks_move_task.py::_mt_resolve_feedback` resolves and reads the file;
  `tasks_verdict_persistence.py::persist_rejected_review_cycle_for_rollback` calls
  `create_rejected_review_cycle(feedback_source=...)`, which writes `review-cycle-N.md` and commits
  **only** that artifact (`_commit_review_cycle_artifact` → `commit_router.commit_artifact((artifact_path,))`).
- `dirty_classifier.py` then classifies the leftover as blocking, and `acceptance/__init__.py`'s
  `git_dirty` check reports it too (the issue's `--diagnose` observation).

## D-3 — Decision: retire the consumed draft after a durable record

Two candidate repairs, both named in #6632. Rejected the first:

- **Commit the source** (issue's option 1): the first issue comment documents that this does not
  survive the coordination topology — the draft lands on the coordination branch, re-claiming the WP
  merges it onto the lane branch, `move-task` refuses a `kitty-specs/` file committed on a lane, the
  printed remedy deletes it there, and `consolidate`'s squash carries the deletion to the target
  branch. The reviewer's text is lost (#3044's shape). It also adds a second copy of bytes the
  record already holds.
- **Retire the source** (issue's option 2, with "remove once the record's commit is verified
  durable"): chosen. The record holds the body verbatim (`_resolve_review_body` returns the file
  text, optionally with a `body_header` prefix that only *prepends*), so no information is lost, and
  there is nothing left to commit onto a lane or delete later.

Implementation seam: `create_rejected_review_cycle` (the single place that both knows the
`feedback_source` and holds the `VerdictPersistenceOutcome`) — one owner (NFR-003), covering the
rejection leg, the #6652 approval-with-feedback leg and `_persist_review_feedback`. The retirement is
gated on `persistence.verdict_durably_persisted` — the same proof `_commit_review_cycle_artifact`
already establishes by reading the bytes back from the destination ref.

## D-4 — Safety predicates for the removal

Every one of these is a way the "fix" could destroy a reviewer's only copy, so each is a requirement
and a test:

1. **Durable record only** — `local_only` (`--no-auto-commit`), `persistence_failed` and the
   protected-target-branch path keep the draft.
2. **Inside `kitty-specs/<mission>/` only** — a `--review-feedback-file` elsewhere (a `/tmp` scratch
   note, a path in another mission) is not this seam's to delete. Checked against the mission
   directory in the checkout that owns it, and against the coordination worktree's copy of the same
   mission directory, using resolved paths.
3. **Untracked only** — a draft the reviewer already committed is left alone: unlinking it would
   create a deletion, i.e. trade one dirty tree for another. Queried with
   `kernel.git.listing.is_tracked`, whose `GitCommandError` path means "leave it".
4. **Bytes still equal what the record holds** — re-read before unlinking; a draft edited between
   the read and the removal is kept and reported. (TOCTOU on the reviewer's own file.)
5. **Never fail a recorded rejection** — an unlink error is reported on stderr and the exit code
   stays 0, because the durable record is the outcome that matters (NFR-002).

## D-5 — Prompt text and docs

The review prompt's rejection block must stop claiming the draft is "committed with the project" and
must say what happens: the record keeps the text and the command removes the draft once it is
committed. The #3430 changelog entry is historical and stays as written; the `[Unreleased]` entry for
this mission states the correct contract.

## Evidence

- Reproduction transcript: `research/repro-6632.txt` (this directory's sibling `research/` folder).
- `tests/specify_cli/cli/commands/agent/test_move_task_reject_fix_approve_cycle.py` — the closest
  existing harness: real `move-task` app, lane manifest, `commit_lane_implementation`. It stubs
  `_validate_ready_for_review`, which is precisely the gate under test here, so the new regression
  test must not.
- `tests/integration/test_review_cycle_rejection_only.py` — `_persist_review_feedback` harness and
  the review-cycle artifact assertions.

## Open questions (resolved during plan)

- Does the retirement belong in `move-task` or in the writer? → Writer (one owner; covers the
  approval leg #6652 created, which has the same leftover shape).
- Should the prompt advertise a path outside the repository instead? → No: the record keeps the body,
  the draft is a staging file, and moving it out of the repository would hide the reviewer's own draft
  from their `git status` while still promising in-repo. Retiring it keeps the prompt's "write it
  next to the record" ergonomics and removes the dirt.
