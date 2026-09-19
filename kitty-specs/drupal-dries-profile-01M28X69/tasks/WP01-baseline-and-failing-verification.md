---
work_package_id: WP01
title: Baseline and failing verification
dependencies: []
requirement_refs:
- FR-013
- NFR-002
- NFR-003
planning_base_branch: feat/drupal-dries-profile
merge_target_branch: feat/drupal-dries-profile
branch_strategy: Planning artifacts for this mission were generated on feat/drupal-dries-profile. During /spec-kitty.implement this WP may branch from a dependency-specific base, but completed changes must merge back into feat/drupal-dries-profile unless the human explicitly redirects the landing branch.
created_at: '2026-09-11T19:28:35+00:00'
subtasks:
- T001
- T002
- T003
- T004
- T005
- T006
history:
- at: '2026-09-11T19:28:35Z'
  actor: system
  action: Prompt generated via /spec-kitty.tasks
agent_profile: python-pedro
authoritative_surface: tests/doctrine/
create_intent:
- tests/doctrine/agent_profiles/test_drupal_dries_profile.py
- tests/doctrine/drg/test_drupal_dries_lineage.py
- tests/doctrine/styleguides/test_drupal_styleguide_presence.py
execution_mode: code_change
owned_files:
- tests/doctrine/agent_profiles/test_drupal_dries_profile.py
- tests/doctrine/drg/test_drupal_dries_lineage.py
- tests/doctrine/styleguides/test_drupal_styleguide_presence.py
role: implementer
tags: []
task_type: implement
tracker_refs: []
---

# Work Package Prompt: WP01 – Baseline and failing verification

## ⚡ Do This First: Load Agent Profile

Use the `/ad-hoc-profile-load` skill to load the agent profile specified in the frontmatter, and behave according to its guidance before parsing the rest of this prompt.

- **Profile**: `python-pedro`
- **Role**: `implementer`

## Objective

Establish a trustworthy environment and write the assertions that **must fail now** and pass at WP07.
This is the red half of red-first discipline.

It exists because of something Phase 0 actually observed rather than suspected: the globally installed
`spec-kitty` reports graph freshness for the pack bundled **inside its own venv**, exits 0, and says
nothing whatsoever about this repository. An implementer who trusts that green will believe their work
is verified when it is not.

## Context

- **Spec**: FR-013 (load failures must be observable), NFR-002 (zero skipped profiles), NFR-003 (≥90% diff coverage)
- **Research**: [research.md](../research.md) R-003 is this package's entire justification — read it first
- **Contracts**: [contracts/profile-contract.md](../contracts/profile-contract.md) C-P1, C-P2, C-P4, C-P5

Nothing this WP writes depends on the Drupal artifacts existing. The tests must fail with a clean
"profile not found", never with a collection or import error — a test that errors proves nothing.

## Branch Strategy

- **Planning branch**: `feat/drupal-dries-profile`
- **Final merge target**: `feat/drupal-dries-profile`
- Execution worktrees are allocated per computed lane from `lanes.json`. Do not create one by hand;
  `spec-kitty implement WP01` resolves it.

---

### Subtask T001: Sync the dev environment

**Purpose**: Nothing below is meaningful without it. This checkout has no `.venv`, and the
repository's own code does not currently import.

**Steps**:

1. From the repository root:
   ```bash
   make dev-setup          # or: uv sync --frozen --all-extras
   ```
2. Confirm the repository's code imports:
   ```bash
   uv run python -c "import charter.offering.drg.migration.extractor as e; print(len(e._CURATED_ARTIFACT_EDGES))"
   ```
   Expect an integer (25 at planning time). A `ModuleNotFoundError: spec_kitty_events.diary` means the
   sync did not take — re-run it. **Do not** record that as a pre-existing failure; per CLAUDE.md's
   baseline-red gotcha it is category 4, a stale venv, and is indistinguishable from real breakage in
   raw pytest output.

**Validation**:
- [ ] The import prints a count
- [ ] `uv run pytest --collect-only tests/doctrine/ -q` collects without import errors

---

### Subtask T002: Establish the repo-pack graph freshness baseline

**Purpose**: Know whether the fragments are fresh **before** you change anything, so WP07 can attribute
any staleness correctly.

**Steps**:

1. Run the check through the repository's code, never a global binary:
   ```bash
   uv run spec-kitty doctrine regenerate-graph --check
   ```
2. **Read the path in the output.** It must point inside
   `/Users/nicolas/Projects/spec-kitty/packs/built-in`. If it names a `pipx` or site-packages path,
   you ran the wrong binary — the result is about a different pack and must be discarded.
3. Record the exit code and the path in the WP notes.

**Validation**:
- [ ] Output path is the repository's `packs/built-in`
- [ ] Exit code recorded

**Edge case**: If the baseline is already **stale on a clean tree**, stop and report it. That is a
pre-existing condition on `main`, not something to fold silently into this mission's diff — the
distinction matters because WP07's diff review depends on knowing what was already there.

---

### Subtask T003: Capture the profile-load health baseline

**Purpose**: A before-picture for NFR-002.

**Steps**:

1. ```bash
   uv run spec-kitty doctor doctrine --json > /tmp/doctrine-baseline.json
   ```
2. Extract and record the skipped-profile count and the profile total.
3. Note the count in the WP notes. It should be 0 skipped; if not, report which profiles are already
   failing to load — again a pre-existing condition, not yours.

**Validation**:
- [ ] Baseline JSON captured
- [ ] Skipped count and total recorded

---

### Subtask T004: Failing test — the profile loads and is not skipped [P]

**Purpose**: C-P1. Assert both that the profile loads *and* that a broken one would be visible —
FR-013 is about failure being observable, and a happy-path-only test would pass against a loader that
silently swallows everything.

**Steps**:

1. Create `tests/doctrine/agent_profiles/test_drupal_dries_profile.py`.
2. Follow the conventions already in that directory — read `test_profile_resolution.py` first for the
   repository fixture and loading idiom. Do not invent a new way to load the pack.
3. Assert, in the positive case:
   - a profile with `profile-id` `drupal-dries` is present
   - it is **not** in `AgentProfileRepository.skipped_profiles`
   - its `roles` include `implementer`
   - its declared `applies_to_languages` include `php`
4. Assert, in the negative case, using a **fixture** copy — never the shipped pack:
   - a deliberately malformed profile appears in `skipped_profiles`
   - the health report does not describe that pack as healthy

**Files**: `tests/doctrine/agent_profiles/test_drupal_dries_profile.py` (~90 lines)

**Validation**:
- [ ] Positive assertions fail now with a clear "profile not found", not an error
- [ ] The negative case passes now and keeps passing — it does not depend on this mission
- [ ] Quad-A structure, per `python-conventions`: arrange, assumption-check, act, assert

---

### Subtask T005: Failing test — lineage resolves and the DAG holds [P]

**Purpose**: C-P2. FR-005's inheritance property, and the endpoint-form trap CLAUDE.md documents as
having once silently dropped a documented edge.

**Steps**:

1. Create `tests/doctrine/drg/test_drupal_dries_lineage.py`. Read `test_builtin_graph_seam.py` in
   that directory first for the graph-loading idiom.
2. Assert:
   - exactly one `specializes_from` edge from `agent_profile:drupal-dries`, targeting
     `agent_profile:implementer-ivan`
   - `requires` edges exist to `directive:DIRECTIVE_010`, `_024`, `_025`, `_030`, `_034`, `_051`
   - `requires` edges exist to `tactic:dependency-hygiene`, `tactic:tdd-red-green-refactor`,
     `tactic:supply-chain-install-safety`, `tactic:bug-fixing-checklist`
   - the `specializes_from` subgraph remains acyclic
   - every edge endpoint resolves to an existing node

**Files**: `tests/doctrine/drg/test_drupal_dries_lineage.py` (~80 lines)

**Validation**:
- [ ] All assertions fail now for absence, not error
- [ ] Endpoint form `<kind>:<id>` is asserted explicitly, not assumed

---

### Subtask T006: Failing test — inventory rises by exactly four [P]

**Purpose**: C-P5, and a guard on NFR-007 — if a fifth node appears, something was added that this
mission did not sanction.

**Steps**:

1. Create `tests/doctrine/styleguides/test_drupal_styleguide_presence.py`.
2. Assert the four new artifacts are present and load:
   - `styleguide:drupal-conventions`
   - `styleguide:drupal-security-performance`
   - `toolguide:drupal-review-checks`
   - `agent_profile:drupal-dries`
3. Assert the `suggests` edges of C-S7: each styleguide suggests the profile;
   `drupal-conventions` also suggests `toolguide:drupal-review-checks`.
4. Read `tests/doctrine/_builtin_inventory.py` before writing the count assertion. It derives
   expectations by **globbing source files**, independently of the graph under test — preserve that
   anti-tautology property. Do not assert a frozen literal; those were deliberately removed.

**Files**: `tests/doctrine/styleguides/test_drupal_styleguide_presence.py` (~70 lines)

**Validation**:
- [ ] Fails now for absence
- [ ] The count assertion derives from the filesystem, not a hardcoded number

---

## Definition of Done

- [ ] Dev environment synced; repository code imports
- [ ] Graph freshness baseline recorded, with the path proving it was the repository's pack
- [ ] Profile-load health baseline captured
- [ ] Three test files created; all new assertions fail for **absence**, none for error
- [ ] `uv run pytest tests/doctrine/ -q` runs to completion with only the expected new failures
- [ ] `uv run ruff check tests/doctrine/` and `uv run ruff format --check tests/doctrine/` both clean
- [ ] Any pre-existing red is reported and classified, never silently absorbed

## Risks

| Risk | Mitigation |
|------|-----------|
| Running a global `spec-kitty` instead of the repo's | T002 requires reading the path in the output — the only reliable tell |
| Tests error instead of failing | An erroring test proves nothing; fix collection before declaring red-first done |
| Freezing a literal node count | `_builtin_inventory.py` removed those on purpose; glob-derive instead |

## Reviewer Guidance

Check the tests fail **for the right reason**. Run them and read the output: "profile `drupal-dries`
not found" is correct; `ImportError` or a collection error is not. Confirm T004's negative case uses a
fixture rather than mutating the shipped pack, and that no assertion hardcodes a node count.
