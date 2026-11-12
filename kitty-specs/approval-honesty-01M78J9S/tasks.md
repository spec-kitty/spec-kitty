# Tasks: Approval honesty: no fabricated reviewer or review cycle

**Mission**: `approval-honesty-01M78J9S` | **Spec**: [spec.md](spec.md) | **Plan**: [plan.md](plan.md)
**Planning base / merge target**: `fix/3044-approval-honesty` (the Mission topic branch lands there)

Four work packages run as **one linear chain** (WP01 → WP02 → WP03 → WP04). Every package edits
the `move-task` approval path, so a chain keeps a single code lane and avoids parallel edits to
`tasks_move_task.py`. Every work package opens with a **red-first ATDD commit**: a failing test
through `spec-kitty agent tasks move-task` in a real git repository, committed before any
implementation commit (charter C-011).

## Subtask Index

| ID | Description | WP | Parallel |
|----|-------------|----|----------|
| T001 | Red-first: honest identity end-to-end (distinctive git name absent; no minted token) | WP01 | |
| T002 | `latest_review_claim_identity` + `same_review_identity` in `status/review_roles.py` | WP01 | |
| T003 | Pure `resolve_reviewer_of_record` combiner + `ReviewerOfRecord` | WP01 | |
| T004 | Route the six identity sources through the combiner; `--reviewer` sets the actor | WP01 | |
| T005 | Delete `_detect_reviewer_name` and the token fallbacks; forced/carried/arbiter references; reference-only executor overwrite | WP01 | |
| T006 | Re-pin stale tests; `--reviewer` help text | WP01 | |
| T007 | WP01 validation (targeted tests, arch gates, ruff, mypy, complexity) | WP01 | |
| T008 | Red-first: claimant mismatch end-to-end + byte-identical refusal | WP02 | |
| T009 | `MoveTaskRequest.review_claimant` + population (one-line wiring in `tasks_move_task.py`) | WP02 | |
| T010 | Pure `_guard_review_claimant` + `APPROVER_NOT_CLAIMANT` code, message and diagnostic | WP02 | |
| T011 | Re-pin fixtures whose claimant differs from the approver | WP02 | |
| T012 | WP02 validation | WP02 | |
| T013 | Red-first: one review one cycle, #3451, citations, non-adoptable cycle, forced writes no cycle | WP03 | |
| T014 | Rename `create_rejected_review_cycle` → `create_review_cycle` (alias kept) | WP03 | |
| T015 | Adoption probe + citation parser/verifier in `review/cycle.py`; cycle refusal codes | WP03 | |
| T016 | Approval write: adopt, honest body, forced moves write no cycle | WP03 | |
| T017 | Wire the cycle refusals before any write (one-line call in `_mt_require_independent_approval`) | WP03 | |
| T018 | WP03 validation (incl. untrusted-path gate, NFR-001 timing) | WP03 | |
| T019 | Red-first: approval hint and skill teach `--agent` | WP04 | |
| T020 | Update `runtime_bridge_decision_mapping.py` hint and `spk-run-verdict-capture/SKILL.md` | WP04 | |
| T021 | ADR `2026-10-04-5` amendment: reviewer of record, three codes, residuals | WP04 | |
| T022 | Changelog fragment(s), including the `--reviewer` behaviour change | WP04 | |
| T023 | CLAUDE.md approval-stamp paragraph: one sentence pointing at the amendment | WP04 | |

## Phase 1 — Foundation

### WP01 — Reviewer of record: claimant fact, combiner, honest identity

- **Prompt**: [tasks/WP01-reviewer-of-record.md](tasks/WP01-reviewer-of-record.md)
- **Goal**: Every identity field of an approval names the reviewer of record (asserted identity, else the claimant). The git `user.name` and minted tokens are gone from the approval path. `approved -> done` and forced/arbiter moves carry honest values.
- **Priority**: P1 (#7569). **Independent test**: the approval flow in a repository whose git name is "Git User Fallback"; the name never appears in the event.
- **Subtasks**:
  T001 Red-first: honest identity end-to-end (WP01)
  T002 Claimant fact + identity equality in `status/review_roles.py` (WP01)
  T003 Pure combiner (WP01)
  T004 Route the six identity sources through the combiner (WP01)
  T005 Delete the fallbacks; forced/carried/arbiter references (WP01)
  T006 Re-pin stale tests; help text (WP01)
  T007 Validation (WP01)
- **Dependencies**: none
- **Risks**: the call-site counter in `test_verdict_attribution_4670.py:434-462`; `_do_move_task` at complexity 15; `DoneEvidence` requires a non-empty reference.

## Phase 2 — Refusals and cycles

### WP02 — Approver must be the review claimant

- **Prompt**: [tasks/WP02-approver-must-be-claimant.md](tasks/WP02-approver-must-be-claimant.md)
- **Goal**: An unforced `in_review -> approved/done` by any identity other than the claimant (tool, model and profile compared), or with a conflicting `--agent`/`--reviewer`, refuses with `APPROVER_NOT_CLAIMANT` and writes nothing.
- **Priority**: P1 (#7573). **Independent test**: claim as `claude:sonnet:reviewer-renata`, approve as `claude:sonnet:supervisor`; expect exit 1 and an unchanged log.
- **Subtasks**:
  T008 Red-first: claimant mismatch end-to-end (WP02)
  T009 Request field + population (WP02)
  T010 Pure guard + code (WP02)
  T011 Re-pin fixtures (WP02)
  T012 Validation (WP02)
- **Dependencies**: WP01
- **Risks**: six existing test files seed a claimant that differs from the approver; check each test's intent before re-pinning.

### WP03 — One review, one cycle; cited cycles exist

- **Prompt**: [tasks/WP03-one-review-one-cycle.md](tasks/WP03-one-review-one-cycle.md)
- **Goal**: An approval adopts the reviewer's post-claim cycle instead of writing another. Cited cycles must exist, be current and not be a rejection's cycle. A non-adoptable post-claim cycle refuses. Forced moves write no review cycle. #6709 is settled.
- **Priority**: P2 (#7571, #7570, #3451, #6709). **Independent test**: write a valid `review-cycle-1.md` after the claim, approve, and assert there is no `review-cycle-2.md`.
- **Subtasks**:
  T013 Red-first tests (WP03)
  T014 Rename with alias (WP03)
  T015 Adoption probe + citation verifier (WP03)
  T016 Honest approval write (WP03)
  T017 Wire refusals before any write (WP03)
  T018 Validation (WP03)
- **Dependencies**: WP02
- **Risks**: the existing patches of `create_rejected_review_cycle` must keep intercepting (callers stay on the alias); the untrusted-path containment gate.

## Phase 3 — Guidance and records

### WP04 — Shipped guidance, ADR amendment, changelog

- **Prompt**: [tasks/WP04-guidance-adr-changelog.md](tasks/WP04-guidance-adr-changelog.md)
- **Goal**: The shipped skill and the `spec-kitty next` hint teach `--agent`. ADR `2026-10-04-5` records the reviewer-of-record rule, the three codes and the residuals. The changelog announces the fix and the `--reviewer` behaviour change.
- **Priority**: P3. **Independent test**: the rendered hint contains `--agent`.
- **Subtasks**:
  T019 Red-first: hint and skill (WP04)
  T020 Hint + skill update (WP04)
  T021 ADR amendment (WP04)
  T022 Changelog (WP04)
  T023 CLAUDE.md sentence (WP04)
- **Dependencies**: WP03
- **Risks**: skill-manifest or packaging tests that hash `SKILL.md`.

## MVP

WP01 alone closes the core of #7569: no fabricated reviewer and no minted token.
