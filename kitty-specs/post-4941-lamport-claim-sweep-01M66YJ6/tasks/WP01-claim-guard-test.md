---
work_package_id: WP01
title: Guard test for retired status-path ordering claims
dependencies: []
requirement_refs:
- FR-007
- SC-002
planning_base_branch: main
merge_target_branch: main
branch_strategy: Planning artifacts for this mission were generated on main. During /spec-kitty.implement this WP may branch from a dependency-specific base, but completed changes must merge back into main unless the human explicitly redirects the landing branch.
subtasks:
- T001
- T002
- T003
phase: Phase 1 - Red-first guard
history:
- at: '2026-10-30T17:50:00Z'
  actor: system
  action: Prompt generated via /spec-kitty.tasks
agent_profile: python-pedro
authoritative_surface: tests/architectural/
create_intent:
- tests/architectural/test_status_path_ordering_claims.py
execution_mode: code_change
model: ''
owned_files:
- tests/architectural/test_status_path_ordering_claims.py
role: implementer
tags: []
task_type: implement
tracker_refs:
- '#6604'
---

# Work Package Prompt: WP01 – Guard test for retired status-path ordering claims

## ⚡ Do This First: Load Agent Profile

Use the `/spk-charter-profile-load` skill to load the agent profile in the frontmatter
**before parsing the rest of this prompt**, and behave according to its guidance.

- **Profile**: `python-pedro`
- **Role**: `implementer`
- **Agent/tool**: your harness

If the profile cannot be loaded, run `spec-kitty agent profile list` and select the best
match for `task_type: implement` on `authoritative_surface: tests/architectural/`.

## Objective

Write `tests/architectural/test_status_path_ordering_claims.py`: the durable guard that
fails when the retired "the CLI status path is Lamport-ordered" wording returns to a living
page, the agent guidelines, or the one corrected code docstring — and that fails if the ADR
amendment this mission records is removed.

This is the **red-first** WP. The test is written against the tree *before* WP02/WP03
correct anything, so it must fail on the files they will fix (and pass on the negated
mentions the repo already contains). Record that failing output in this WP's history.

## Context & Constraints

Ground truth to read before writing the test:

- [spec.md](../spec.md) FR-007, SC-002, and the "Edge Cases" list.
- [plan.md](../plan.md) "Guard test design (reference for tasks)" — the design is fixed
  there; do not invent a different shape.
- [research.md](../research.md) "What the code does now" — the facts the failure message
  must restate.

Facts the guard enforces (do not re-derive them from prose; they come from the code):

- `src/specify_cli/status/reducer.py:205` `reduce()` calls
  `spec_kitty_events.diary.reduce_parsed` directly; `:401` `materialize_snapshot()` calls
  `reduce_shared_state`, which is `spec_kitty_events.status.reduce`, a re-export of
  `diary.reduce`. One fold, two parsers.
- `diary._order_transitions` sorts by `(at, event_id)` with the approved-departure lift
  (`_approved_departure_sort_at`, `_carry_lifted_sort_at`), naming spec-kitty-events#101 /
  spec-kitty#4941.
- CLI lane rows carry no Lamport clock; the residual is a **non-approval** transition
  minted on a clock behind the event it follows.

Constraints:

- Pure filesystem/text test: no `git` subprocess, no network, no `spec-kitty` subprocess.
- Marks: `pytest.mark.architectural` **and** `pytest.mark.docs_scoped` — it reads `docs/`,
  so it must run on the docs-only CI trim (NFR-001). Do not add `git_repo`.
- Bounded corpus (NFR-002), about ten paths, each asserted to exist. A missing covered path
  is a failure, never a skip.
- Runtime under 5 seconds.
- The test must not ban the word `Lamport`: retrospective lifecycle code
  (`src/specify_cli/retrospective/lifecycle_events.py`), `kernel/clock.py`'s "distinct from
  a Lamport logical clock" and the decision-point line-count proxy are all legitimate and
  are not in the corpus anyway.

## Branch Strategy

Planning artifacts were generated on `kitty/mission-post-4941-lamport-claim-sweep-01M66YJ6`.
Execution worktrees are allocated per computed lane from `lanes.json`; completed changes
merge back into `kitty/mission-post-4941-lamport-claim-sweep-01M66YJ6` unless the human
redirects the landing branch.

## Subtasks

### T001 — Write the guard module

Structure (names are the plan's; keep them):

```python
COVERED_PATHS: tuple[str, ...] = (
    "AGENTS.md",
    "docs/architecture/diagrams/01_context/README.md",
    "docs/architecture/diagrams/02_containers/README.md",
    "docs/architecture/event-ledger-writers-and-readers.md",
    "docs/architecture/status-model.md",
    "docs/plans/domains/api-dashboard-domain-plan.md",
    "src/specify_cli/consolidation/preflight.py",
)

RETIRED_PHRASES: tuple[tuple[str, str], ...] = (  # (phrase, why it is wrong)
    ...
)

AFFIRMATIVE_RE = re.compile(r"Lamport[\s_-]+(reducer|reduction|wrapper)", re.IGNORECASE)
NEGATION_MARKERS = ("not ", "never", "no ", "NOT ", "n't")
```

- `_covering_files()` resolves each path under the repo root and asserts it exists.
- `_violations(text)` returns `[(lineno, line)]` for every line that matches
  `AFFIRMATIVE_RE` and carries no negation marker on the same line.
- Tests:
  - `test_covered_paths_exist` (fails, not skips, when one is missing).
  - `test_no_affirmative_lamport_status_path_claims` — every covered file is clean.
  - `test_retired_phrases_are_gone` — the exact strings this mission removed are absent
    corpus-wide.
  - `test_adr_amendment_records_wall_clock` — ADR `docs/adr/4.x/2026-10-01-2-…md` still
    contains the historical D-5 sentence `moves them onto the Lamport reducer` **and**
    contains a `## Amendment 2026-10-30 (Accepted)` section whose body names
    `(at, event_id)`, `lift` and `#6609`.
  - `test_residual_is_stated` — `AGENTS.md` still names the non-approval clock-skew
    residual (so the guard cannot be satisfied by deleting the caveat), and the gap table
    row G-3 records the closure.
  - `test_detector_is_not_vacuous` — `_violations` reports exactly one hit for a synthetic
    stale line (`"core owns event ledger + Lamport reducer"`) and zero for a synthetic
    negated line (`"CLI lane rows carry no Lamport clock"`).

Each failure message names the file, the line number, the offending text and the correct
statement ("the status path is ordered by wall clock (at, event_id) with the
approved-departure lift; see ADR 2026-02-09-3 Amendment 2026-10-22").

### T002 — Non-vacuity

Prove the detector can see the phrase: the synthetic stale line must produce exactly one
violation, the negated line zero. Also assert `len(COVERED_PATHS) >= 5` so a future edit
cannot shrink the corpus to nothing, and that `_covering_files()` raises when a path is
missing (feed it a bogus path).

### T003 — Show it red

Run the test on the unmodified tree and capture the failure:

```bash
uv run pytest tests/architectural/test_status_path_ordering_claims.py -x -q
```

Expect failures naming the C4 pages, the domain plan, `AGENTS.md`, the preflight docstring
and the missing ADR amendment. Save a short excerpt into this WP's history (and the PR's
`## Tests run`), then leave the test in place: WP02 and WP03 turn it green. Do **not**
weaken an assertion to make it pass and do **not** edit files outside `owned_files`.

## Test strategy

- `uv run pytest tests/architectural/test_status_path_ordering_claims.py -q` — red here,
  green at the end of WP03.
- `uv run ruff check tests/architectural/test_status_path_ordering_claims.py` and
  `uv run mypy tests/architectural/test_status_path_ordering_claims.py` if the repo's
  config covers tests.

## Definition of Done

- [ ] The module exists at the exact path, with both pytest marks.
- [ ] All six tests are present; the detector has the non-vacuity test.
- [ ] The test fails on today's tree and the failure output is recorded (T003).
- [ ] No file outside `owned_files` is modified.
- [ ] `ruff` is clean on the new file.

## Risks

- **Over-broad regex** → red on a legitimate mention. Mitigation: bounded corpus plus the
  negation allowance; do not scan `src/**` wholesale.
- **Vacuous pass** when a covered path is deleted or renamed → the existence test fails.
- **Assertion drift**: pinning exact sentences makes the guard brittle. Pin only the
  retired phrases (which can never legitimately return) and assert *concepts* for the
  replacement text.

## Reviewer guidance

Check that the guard can fail for the right reason (read T003's red output), that it does
not simply grep `Lamport`, and that the ADR assertions preserve history rather than
requiring a rewrite. Reject a version that skips missing paths or that drops the
non-vacuity test.
