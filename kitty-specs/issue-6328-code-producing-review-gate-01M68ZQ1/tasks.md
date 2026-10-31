# Tasks: Enforce the implementation-commit review prerequisite from the `code_producing` capability

**Mission**: `issue-6328-code-producing-review-gate-01M68ZQ1` · **Branch**: `issue-6328-code-producing-review-gate` (planning base and merge target)
**Inputs**: [spec.md](spec.md), [plan.md](plan.md), [data-model.md](data-model.md), [research.md](research.md), [quickstart.md](quickstart.md)

## Subtask Index

| ID | Description | WP | Parallel |
|----|-------------|----|----------|
| T001 | Failing tests: `code_producing` field, built-in map, declared-value precedence, conservative default | WP01 | |
| T002 | `MissionType.code_producing: bool \| None = None` + docstring | WP01 | [P] |
| T003 | `BUILTIN_CODE_PRODUCING` map + `ResolvedMissionType.code_producing` cached facet + `_resolve_code_producing` | WP01 | |
| T004 | `code_producing_for` accessor, re-exported from `charter.activation.api`, in both `__all__`s | WP01 | |
| T005 | Laziness proof: an `action_sequence`-only read triggers no extra roster read; neutral bundle answers `False` | WP01 | |
| T006 | Resolution-failure proof: a raising resolver falls back to the built-in default (never raises) | WP01 | |
| T007 | Failing test through the pre-existing entry point: a custom code-producing type with no lane commit is refused | WP02 | |
| T008 | Swap the `mission_type == MISSION_TYPE_SOFTWARE_DEV` guard for the capability; drop the now-unused import | WP02 | |
| T009 | Same-fixture positive control: the same custom type with a lane commit passes | WP02 | |
| T010 | Built-in parity ratchet: `software-dev` blocked, `research`/`documentation`/`plan` not applied | WP02 | |
| T011 | `--force` still short-circuits before the capability is consulted | WP02 | |
| T012 | Re-run the existing neighbour suites that construct the pre-flight (research bypass, parsing validation) | WP02 | |
| T013 | Empty-diff proof for the `#6715`/`#5939` gate modules; record it for the PR body | WP02 | |
| T014 | `[Unreleased]` changelog entry citing `#6328` (and `#6327` for the capability) | WP03 | |
| T015 | Docs freshness check on the surfaces this diff changes | WP03 | |

## Phase 1 — Foundation

### WP01 — The `code_producing` capability and its public accessor

**Goal**: a resolved mission type answers "do I produce code?" through one built-in map, one resolver and one public accessor, without adding a read to the FSM hot path. **Priority**: P1. **Prompt**: [tasks/WP01-code-producing-capability.md](tasks/WP01-code-producing-capability.md)
**Independent test**: `tests/charter/test_code_producing_capability.py` — built-ins (`software-dev` true; `research`/`documentation`/`plan` false), a custom type declaring either value, a custom type declaring nothing (`false`), the neutral bundle, and a raising resolver falling back to the default.

T001 Failing tests: `code_producing` field, built-in map, declared-value precedence, conservative default (WP01)
T002 `MissionType.code_producing: bool | None = None` + docstring (WP01)
T003 `BUILTIN_CODE_PRODUCING` map + `ResolvedMissionType.code_producing` cached facet + `_resolve_code_producing` (WP01)
T004 `code_producing_for` accessor, re-exported from `charter.activation.api`, in both `__all__`s (WP01)
T005 Laziness proof: an `action_sequence`-only read triggers no extra roster read; neutral bundle answers `False` (WP01)
T006 Resolution-failure proof: a raising resolver falls back to the built-in default (never raises) (WP01)

Dependencies: none. Risk: `MissionType` is `extra="forbid"`, so the field must be declared before any test YAML may set it; and the lazy facet must not move the roster read onto the hot path.

### WP02 — The review-readiness prerequisite keyed on the capability

**Goal**: the review-readiness pre-flight applies its worktree-state prerequisite to any code-producing mission type, and to nothing else. **Priority**: P1. **Prompt**: [tasks/WP02-review-readiness-gate.md](tasks/WP02-review-readiness-gate.md)
**Independent test**: `tests/specify_cli/cli/commands/agent/test_ready_for_review_code_producing_gate.py` — a custom `code_producing: true` type with no lane commit is refused with the implementation-commit guidance; the same fixture with a commit passes; the `false` twin is not applied; the built-ins keep today's verdicts.

T007 Failing test through the pre-existing entry point: a custom code-producing type with no lane commit is refused (WP02)
T008 Swap the `mission_type == MISSION_TYPE_SOFTWARE_DEV` guard for the capability; drop the now-unused import (WP02)
T009 Same-fixture positive control: the same custom type with a lane commit passes (WP02)
T010 Built-in parity ratchet: `software-dev` blocked, `research`/`documentation`/`plan` not applied (WP02)
T011 `--force` still short-circuits before the capability is consulted (WP02)
T012 Re-run the existing neighbour suites that construct the pre-flight (research bypass, parsing validation) (WP02)
T013 Empty-diff proof for the `#6715`/`#5939` gate modules; record it for the PR body (WP02)

Dependencies: WP01. Risk: `_validate_ready_for_review`'s collaborator signature is a live monkeypatch contract — no required parameter may be added; `tests/integration/test_coord_loop_depgraph.py`'s research bypass must stay green untouched.

## Phase 2 — Record

### WP03 — Changelog and docs freshness

**Goal**: the user-facing change is recorded in one `[Unreleased]` entry, and the docs surfaces this diff touches are verified fresh. **Priority**: P2. **Prompt**: [tasks/WP03-changelog-and-docs.md](tasks/WP03-changelog-and-docs.md)
**Independent test**: `uv run python -m scripts.docs.check_docs_freshness --ci` reports `errors=0`, and the changelog entry is present under `[Unreleased]` with the `(#6328)` reference and a bold impact-first lead.

T014 `[Unreleased]` changelog entry citing `#6328` (and `#6327` for the capability) (WP03)
T015 Docs freshness check on the surfaces this diff changes (WP03)

Dependencies: WP01, WP02. Risk: a full `docs/api/cli-commands.md` rebuild reads a shared global cache other agents rewrite concurrently — regenerate only what this diff changes and verify with the freshness check rather than trusting a rebuild.

## Parallelisation

WP01 and WP02 are sequential by intent (WP02's red test cannot be written before
the accessor exists — that is the point of the prerequisite). WP03 is independent of
both in content but describes their outcome, so it lands last. There is no
meaningful parallelism to exploit in a diff this size, and forcing it would make the
red-first proof harder to read.

## MVP scope

WP01 + WP02. WP01 alone is a capability nothing consumes; WP02 alone cannot be
written. Together they are the whole defect fix. WP03 is the record.
