# Work Packages: Declaration-first repo_root/branch resolution entry (#6142, Increment 1)

**Inputs**: `kitty-specs/declaration-first-repo-root-resolution-01M4TB21/` — spec.md, plan.md, research/code-grounding.md, tracers/
**Prerequisites**: spec.md, plan.md

**Tests**: required. Red-first per charter SO #4 / C-011: the behaviour-correcting WP commits its failing test(s) before the fix. The enabler WPs are behaviour-preserving and land first (tidy-first, SO #2).

**Organization**: subtasks (`Txxx`) roll up into work packages (`WPxx`). Each WP has its own prompt in `tasks/`.

## Subtask Format: `[Txxx] [P?] Description`

Record completion with `spec-kitty agent tasks mark-status <Txxx> --status done`.

## Subtask Index

| ID | Description | WP | Parallel |
|----|-------------|----|----------|
| T001 | Add `TargetProvenance` enum + frozen `CommandRepoTarget` value in new `src/specify_cli/core/command_target.py` | WP01 | |
| T002 | Implement `resolve_command_repo_target` — repo_root via `resolve_canonical_root`/`get_main_repo_root`; branch declaration-first via `read_target_branch_from_meta` → validated `resolve_primary_branch(bias=False)` fallback; provenance + fail-closed | WP01 | |
| T003 | Unit tests over every branch (declaration / validated-fallback / corrupt-meta fail-closed / worktree→primary collapse / provenance) | WP01 | |
| T004 | `__all__`, docstrings naming the `primary`/`merge`/`routing` senses; ruff + mypy clean, complexity ≤ 15 | WP01 | [P] |
| T005 | Route the selected mission-scoped command-entry `repo_root`/branch seed(s) through the entry (behaviour-preserving at routed sites) | WP02 | |
| T006 | Fold the hand-placed "never `Path.cwd()`" assertion(s) at routed sites into the typed call (invariant by construction) | WP02 | |
| T007 | Per-routed-site tests: target comes from the entry; no ambient `Path.cwd()`/branch seed remains at the site | WP02 | |
| T008 | Red-first behaviour test: a routed mission-scoped command whose ambient location disagrees with the declaration resolves to the declaration (fails on pre-fix tree, passes after) | WP03 | |
| T009 | Negative tests: #3128 `enforce_checkout_identity` + #3328 `resolve_checkout_identity` still refuse; `get_status_read_root` READ contract untouched | WP03 | |
| T010 | Deferred-scope hygiene: file-and-link follow-up issue; Refs #2802/#5114; append tracers | WP03 | [P] |

---

## Work Package WP01: The typed declaration-first resolution entry (Priority: P1)

**Goal**: One typed `(repo_root, target_branch, provenance)` producer exists in
`specify_cli.core.command_target`, built on the existing public resolvers, declaration-first
on branch with a validated non-ambient fallback, fail-closed on corruption, and with the
"never `Path.cwd()`" invariant held by construction.
**Independent Test**: `tests/specify_cli/core/test_command_target.py` exercising every
resolution branch directly over `tmp_path` git fixtures.
**Prompt**: `tasks/WP01-typed-declaration-first-entry.md`
**Requirement Refs**: FR-001, FR-002, FR-003, NFR-001, NFR-002, NFR-003, NFR-004, SC-001, SC-003

### Included Subtasks

T001 Add the enum + frozen value (WP01)
T002 Implement the resolver (WP01)
T003 Unit tests over every branch (WP01)
T004 `__all__` + docstrings + quality gates (WP01)

### Dependencies

- None.

### Risks & Mitigations

- The validated fallback must not reintroduce the ambient-HEAD bias — use
  `resolve_primary_branch(repo_root, bias=False)` and assert in a unit test that a
  disagreeing checked-out branch never becomes the target.

---

## Work Package WP02: Route the command-entry seeds + fold the assertions (Priority: P1)

**Goal**: The bounded, named set of mission-scoped command-entry `Path.cwd()`/branch seeds
is produced by the entry, and the hand-placed "never `Path.cwd()`" assertions at those
sites are folded into the typed call (invariant by construction, not duplicated).
**Independent Test**: per-routed-site tests asserting the target comes from the entry and
no ambient seed remains at the site.
**Prompt**: `tasks/WP02-route-seeds-fold-assertions.md`
**Requirement Refs**: FR-004, FR-005, C-004, SC-001, SC-002

### Included Subtasks

T005 Route the selected seed(s) (WP02)
T006 Fold the assertion(s) (WP02)
T007 Per-routed-site tests (WP02)

### Dependencies

- WP01 (the entry must exist before any site can route through it).

### Risks & Mitigations

- Routing is behaviour-preserving EXCEPT in the ambient-disagreement case (the intended
  correction, witnessed in WP03). Apply the IC-2 selection criteria per site; do NOT route
  consolidation/merge sites, the `implement_claim` #2453-deferred guard, create-time, or
  honest-identity-input sites — file-and-link them (WP03 T010).

---

## Work Package WP03: Red-first behaviour correction + fail-closed preservation (Priority: P2)

**Goal**: The ambient-disagreement behaviour correction is proven red-first, and the
existing #3128/#3328 fail-closed refusals and worktree-invocation behaviour are proven
unchanged; the deferred out-of-scope sites are filed-and-linked.
**Independent Test**: the red-first behaviour test (RED on the pre-fix tree, GREEN after)
plus the negative refusal tests.
**Prompt**: `tasks/WP03-red-first-correction-failclosed.md`
**Requirement Refs**: FR-006, FR-007, FR-008, C-002, C-003, SC-004

### Included Subtasks

T008 Red-first behaviour test (WP03)
T009 Negative fail-closed tests (WP03)
T010 Deferred-scope hygiene (WP03)

### Dependencies

- WP02 (the correction is exhibited at a routed site).

### Risks & Mitigations

- Keep the red-first test in its own file, distinct from WP02's per-site tests, so the
  RED→GREEN witness is unambiguous.
- Negative tests must assert the EXISTING refusals are byte-for-byte unchanged (ratchet,
  not rewrite).
