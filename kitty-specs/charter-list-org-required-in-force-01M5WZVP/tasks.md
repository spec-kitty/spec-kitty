# Tasks: charter list shows org-required ids in force (#6417)

**Mission**: `charter-list-org-required-in-force-01M5WZVP`
**Planning / merge target branch**: `issue-6417-charter-list-org-required`
**Inputs**: [spec.md](spec.md), [plan.md](plan.md), [data-model.md](data-model.md),
[contracts/charter-list-json.md](contracts/charter-list-json.md), [research.md](research.md)

## Subtask Index

| ID | Description | WP | Parallel |
|----|-------------|----|----------|
| T001 | Red-first unit tests for `required_in_force` | WP01 | |
| T002 | `RequiredInForce` + shared base with `RequiredOmission` | WP01 | |
| T003 | `required_in_force(repo_root, *, strict)` reader | WP01 | |
| T004 | Re-export through `charter.activation.api` + identity gate row | WP01 | |
| T005 | Red-first CLI-level test + un-`@wip` scenario with corrected fixture | WP02 | |
| T006 | `list_cmd` renders in-force required ids (table) | WP02 | |
| T007 | `--json`: `activated`, `allow_list_present`, `schema_version` | WP02 | |
| T008 | Update existing list tests + help/docstring | WP02 | |
| T009 | Docs: `docs/api/charter-commands.md`, changelog, `PROMISES.md` | WP02 | |

## Phase 1 - Foundation

### WP01 — In-force required ids reader in the activation layer

**Goal**: one reader in `charter.activation` that answers which org-required ids are in force for
kinds with no allow key, derived from `PackContext.effective_ids` over the real availability.
**Priority**: P1. **Independent test**: `tests/charter/activation/test_required_in_force.py`.
**Prompt**: [tasks/WP01-required-in-force-reader.md](tasks/WP01-required-in-force-reader.md)

Included subtasks:

T001 Red-first unit tests for `required_in_force` (WP01)
T002 `RequiredInForce` + shared base with `RequiredOmission` (WP01)
T003 `required_in_force(repo_root, *, strict)` reader (WP01)
T004 Re-export through `charter.activation.api` + identity gate row (WP01)

Implementation sketch: tests first (red, committed), then the dataclass, the reader (lazy imports:
`pack_context` imports `activation_ledger`), the api re-export.
Dependencies: none. Risks: import cycle; spelling space (stems).

## Phase 2 - User Story 1 and 2

### WP02 — `charter list` names in-force required ids; JSON contract v2; acceptance scenario

**Goal**: the listing names the in-force required ids on absent-key rows and versions the JSON
contract; the acceptance scenario gates with an honest fixture.
**Priority**: P1. **Independent test**: `tests/specify_cli/cli/commands/charter/test_list_required_in_force.py`.
**Prompt**: [tasks/WP02-charter-list-in-force-required.md](tasks/WP02-charter-list-in-force-required.md)

Included subtasks:

T005 Red-first CLI-level test + un-`@wip` scenario with corrected fixture (WP02)
T006 `list_cmd` renders in-force required ids (table) (WP02)
T007 `--json`: `activated`, `allow_list_present`, `schema_version` (WP02)
T008 Update existing list tests + help/docstring (WP02)
T009 Docs: `docs/api/charter-commands.md`, changelog, `PROMISES.md` (WP02)

Implementation sketch: red tests and scenario first (committed), then extract row-building helpers
from `list_cmd` and wire `required_in_force`, then docs.
Dependencies: WP01. Risks: `list_cmd` complexity; consumers pinning `activated: null`.
