# Work Packages: Op Records Stop Naming A Model, And Carry The Operator's Attribution

**Inputs**: Design documents from `kitty-specs/op-record-model-and-coauthor-01M6EJV5/`
**Prerequisites**: plan.md (required), spec.md (user stories), research.md, contracts/op-record-attribution.md
**Issue**: #7013

**Organization**: Fine-grained subtasks (`Txxx`) roll up into work packages (`WPxx`).
Subtasks are reference rows; completion is recorded with
`spec-kitty agent tasks mark-status <Txxx> --status done`.

## Subtask Index

| Txxx | Description | WP | Parallel |
| ---- | ----------- | -- | -------- |
| T001 | Red test: a written Op record carries no model identifier; a legacy line with `model_id` still parses and is not re-serialised | WP01 | |
| T002 | Drop `model_id` from `OpStartedEvent`; stop filling it in `invoke()`; refresh the optional-field comments | WP01 | |
| T003 | Red test: a `--model` assertion with `--invocation-id` is refused and the claim records `RESOLVED_MODEL_ABSENT` | WP01 | |
| T004 | `_resolve_dispatch_binding`: correlate profile/mission/WP/action only; refuse a model it cannot prove | WP01 | |
| T005 | Red tests: configured trailer on both commit paths, the unconfigured ratchet, explicit override precedence, malformed config refusal, blank override rejected | WP01 | |
| T006 | New `git/commit_attribution.py`: resolve, normalise and validate the operator trailer | WP01 | |
| T007 | Append the trailer in `_commit_op_record`; thread `complete_invocation(co_author=...)` and `profile-invocation complete --co-author` | WP01 | |
| T008 | Targeted suites plus `make test-fast`; prove each half goes red when reverted | WP01 | |
| T009 | `docs/architecture/trail-model.md`: the field list, the immutable-history ruling, the trailer | WP02 | |
| T010 | `docs/api/configuration.md` (`commit.co_author`) and `docs/api/profile-invocation.md` (`--co-author`) | WP02 | |
| T011 | Regenerate `docs/api/cli-commands.md`; add the per-PR changelog fragment | WP02 | |
| T012 | Docs freshness (`check_docs_freshness --ci`) and `tests/architectural/test_no_legacy_terminology.py` | WP02 | |

---

## Work Package WP01: The record names no model, and the commit is attributed (Priority: P0)

**Goal**: A newly written Op record contains no AI model identifier, the claim
seam refuses a model it can no longer prove, and the Op auto-commit carries the
operator's `Co-Authored-By` trailer (configured or explicit).
**Independent Test**: Open and close an Op through the production paths on a git
fixture that tracks Op records: the written record has no `model_id`, and
`git log -1 --format=%B` ends with the configured trailer.
**Prompt**: `tasks/WP01-record-and-trailer.md`
**Requirement Refs**: FR-001, FR-002, FR-003, FR-004, FR-005, FR-006, FR-007, FR-008, NFR-001, NFR-002, NFR-003, C-001, C-002, C-003

### Included Subtasks

T001 Red test: a written Op record carries no model identifier; a legacy line with `model_id` still parses and is not re-serialised
T002 Drop `model_id` from `OpStartedEvent`; stop filling it in `invoke()`; refresh the optional-field comments
T003 Red test: a `--model` assertion with `--invocation-id` is refused and the claim records `RESOLVED_MODEL_ABSENT`
T004 `_resolve_dispatch_binding`: correlate profile/mission/WP/action only; refuse a model it cannot prove
T005 Red tests: configured trailer on both commit paths, the unconfigured ratchet, explicit override precedence, malformed config refusal, blank override rejected
T006 New `git/commit_attribution.py`: resolve, normalise and validate the operator trailer
T007 Append the trailer in `_commit_op_record`; thread `complete_invocation(co_author=...)` and `profile-invocation complete --co-author`
T008 Targeted suites plus `make test-fast`; prove each half goes red when reverted

### Implementation Notes

- Order: record schema first (T001–T002), then the claim seam it breaks
  (T003–T004), then the fully independent attribution half (T005–T007).
- The auto-commit is best-effort: the completed event is durable before the
  commit is attempted, so an attribution problem must surface as
  `OpCommitOutcome.refusal`, never as a failed close.
- Historical `kitty-ops/<ULID>.jsonl` files are never touched (the
  archive-preservation gate), so "unchanged" is asserted, not "migrated".

### Parallel Opportunities

- T005–T007 (attribution) touch `executor.py`'s commit path and a new module;
  they do not depend on T001–T004 landing, but they edit the same file, so keep
  them sequential inside the WP.

### Dependencies

- None.

### Risks & Mitigations

- **Vacuous absence probe** — pair the "no `model_id`" assertion with a legacy
  positive control on the same fixture, and assert the key survives on the
  legacy line after parsing.
- **Half-fix stays green** — revert each half in turn (see T008); the schema
  half and the attribution half must each go red on their own.
- **Resolved-binding narrowing** — say it in the diff, the changelog and the PR
  body; do not let it change silently.

---

## Work Package WP02: Documentation, changelog and the generated CLI reference (Priority: P1)

**Goal**: An operator can find the new configuration key, understand that
historical records are immutable, and read a CLI reference that matches the
live Typer surface.
**Independent Test**: `check_docs_freshness --ci` reports zero errors and each
new key/flag is documented where an operator looks for it.
**Prompt**: `tasks/WP02-docs-and-changelog.md`
**Requirement Refs**: FR-004, FR-006, C-001, NFR-001

### Included Subtasks

T009 `docs/architecture/trail-model.md`: the field list, the immutable-history ruling, the trailer
T010 `docs/api/configuration.md` (`commit.co_author`) and `docs/api/profile-invocation.md` (`--co-author`)
T011 Regenerate `docs/api/cli-commands.md`; add the per-PR changelog fragment
T012 Docs freshness (`check_docs_freshness --ci`) and `tests/architectural/test_no_legacy_terminology.py`

### Implementation Notes

- The changelog is assembled from fragments since #6988: write
  `docs/changelog/unreleased/<pr>.fixed.md`; never edit
  `docs/changelog/CHANGELOG.md` directly. Read `docs/changelog/unreleased/README.md`
  for the required shape.
- Regenerate only `docs/api/cli-commands.md` (the surface `--co-author` changes);
  the generator produced no diff on a clean tree, so any diff is attributable.

### Parallel Opportunities

- None inside this WP; it runs after WP01 because the reference is generated
  from the implemented flag.

### Dependencies

- WP01 (the documented behaviour must exist and the flag must be registered).

### Risks & Mitigations

- **Stale generated reference** — run the freshness gate, do not eyeball the file.
- **Changelog shape** — the style gate rejects an `[Unreleased]` entry shape;
  copy the fragment shape from a recent `docs/changelog/unreleased/*.md`.
