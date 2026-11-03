# Mission Specification: ASCII-by-construction mission scaffolding

**Mission Branch**: `issue-6877-ascii-mission-scaffold`
**Created**: 2026-11-03
**Status**: Draft
**Input**: User description: "#6877 - the spec and task scaffolding instructs authors to write U+2014 into kitty-specs/, so validate-encoding flags every mission. Fix the core-owned scaffold (tasks/README.md), and pin it so core-generated scaffold text cannot regress to non-ASCII."

## Context and boundary

`spec-kitty validate-encoding --mission <slug>` scans `kitty-specs/<slug>/**/*.md` for the
characters in `specify_cli.text_sanitization.PROBLEMATIC_CHARS`. Because the *scaffold*
content is itself written with those characters, the gate refuses artifacts the tool
produced, before a human or agent has authored a single word.

Grounding on `main` (`f1e860a17f`) rendered every scaffold surface and ran
`detect_problematic_characters` over each. The defect splits across two owners:

| Scaffold file | Owner | Offending characters |
| --- | --- | --- |
| `tasks/README.md` | **core**, two emitters: `TASKS_README_TEMPLATE` (`src/specify_cli/core/mission_creation_scaffold.py`) and a hand-inlined copy in `setup_feature_directory` (`src/specify_cli/core/worktree.py`) | `–` U+2013 in the constant; the inline copy is ASCII but has drifted |
| `spec.md` | `packs/built-in/.../spec-template.md` | `—` U+2014 (x6) |
| `plan.md` | `packs/built-in/.../plan-template.md` | `—` U+2014 (x4) |
| `tasks.md` | `packs/built-in/.../tasks-template.md` | `–` U+2013, `—` U+2014 |
| `tasks/WP*.md` | `packs/built-in/.../task-prompt-template.md` | `–` U+2013, `—` U+2014 |
| specify/tasks step prompts | `packs/built-in/missions/mission-steps/` | `—`/`·` in copy-verbatim guidance |

`packs/built-in/` is gitignored, digest-pinned to `spec-kitty-open-packs@a79c363`, and
`CLAUDE.md` forbids editing it in core ("Do not edit files under `packs/built-in/` or
`packs/internal/` in core; they are regenerated"). So this mission fixes and pins the
**core-owned** surface, and the pack-owned half is a separate upstream mission plus a pin
bump that needs an explicit operator decision (standing ruling 2026-11-01T09:35Z,
`OPERATOR-DECISIONS.md` #9). It is filed and cited, not silently smoothed over.

What this mission is *not*: it is not a transliteration pass at the write boundary. #6579
settled that a blanket sanitizer would rewrite a maintainer's authored prose, so the
invariant is **ASCII by construction in the source text**, never repair on the way out.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - A new mission's own scaffold passes its own gate (Priority: P1)

An operator runs `spec-kitty specify` and immediately checks the mission artefacts. The
core-generated scaffold text is ASCII, so nothing under `kitty-specs/` is refused by
`validate-encoding` that the tool itself wrote.

**Why this priority**: This is the reported defect. A gate that fails on the tool's own
output trains operators to run `--fix` reflexively, which then rewrites authored prose
too. Fixing the scaffold is what makes the gate trustworthy for the content it is meant
to police.

**Independent Test**: Create a mission in a temp project and read every file core wrote.
Assert `tasks/README.md` is ASCII and that `detect_problematic_characters` finds nothing
in it. Before the fix, `tasks/README.md` contains `–` U+2013 on the
`# Work Package Prompt: WP01 – Work Package Title` line.

**Acceptance Scenarios**:

1. **Given** a freshly created mission, **When** `render_tasks_readme_content(branch)` is
   rendered, **Then** every byte is `< 0x80` for every branch name supplied.
2. **Given** a freshly created mission, **When** the `create` entry point scaffolds it,
   **Then** `tasks/README.md` on disk contains no character that
   `detect_problematic_characters` reports.

---

### User Story 2 - The scaffold cannot regress to a non-ASCII emitter (Priority: P1)

A future contributor edits `TASKS_README_TEMPLATE` (or adds a sibling core-authored
scaffold renderer) and reintroduces a typographic glyph. CI fails at the source, naming
the offending line, before a mission is ever created.

**Why this priority**: The defect exists because nothing pinned the character class of
scaffold text. A one-line fix without a pin re-opens the hole the first time someone
pastes prose into the template.

**Independent Test**: Mutate `TASKS_README_TEMPLATE` to contain `\u2014` in a subprocess
and assert the pin fails, then restore it and assert it passes (the self-mutation
requirement for a non-vacuous architectural gate).

**Acceptance Scenarios**:

1. **Given** the pin test, **When** the shipped template is ASCII, **Then** it passes.
2. **Given** the pin test, **When** a glyph is injected into `TASKS_README_TEMPLATE`,
   **Then** it fails and its message names the offending line.

---

### User Story 3 - One authority for the scaffold text (Priority: P2)

A contributor changing what `tasks/README.md` says changes it in one place, and both
scaffold entry points serve the same text.

**Why this priority**: core renders this file from two different literals today (see
`research.md` D-6). A pin over one of them would be a vacuous gate over the other, and
the two have already drifted in the WP-frontmatter example and in the section set.

**Independent Test**: call `setup_feature_directory()` and `render_tasks_readme_content()`
and assert the `tasks/README.md` bytes each produces come from the same constant.

**Acceptance Scenarios**:

1. **Given** `setup_feature_directory()` on a fresh directory, **When** it writes
   `tasks/README.md`, **Then** the content equals
   `render_tasks_readme_content(<mission dir name>)`.
2. **Given** a change to the scaffold text, **When** it is made, **Then** exactly one
   literal holds it.

---

### User Story 4 - The author's own prose is untouched (Priority: P2)

An operator writes a spec, plan or task note containing a real en dash or an ellipsis.
The value survives verbatim; the tool never rewrites it.

**Why this priority**: Guards against the tempting wrong fix. #6579 already established
this boundary for decision records; the scaffold fix must not violate it.

**Independent Test**: Sanitise/render a mission artefact whose *authored* content
contains non-ASCII and assert it round-trips byte-identically through the scaffold and
create paths.

**Acceptance Scenarios**:

1. **Given** an authored file with non-ASCII content, **When** the mission create and
   scaffold paths run, **Then** the authored bytes are unchanged.

---

### Edge Cases

- A branch name (interpolated into `tasks/README.md`) that itself contains non-ASCII: the
  pin asserts ASCII over the rendered output, so a non-ASCII branch name would fail it.
  Document the assumption rather than sanitising the branch name (a branch name is
  authored input, and `git check-ref-format` is the authority that constrains it).
- An override template installed at `.kittify/templates/` or `.kittify/overrides/` (tier
  1/2 of the resolver chain) is *user* content, not core scaffold: the pin covers core's
  own template constant, not a user override.
- A mission created before this fix keeps its glyphs; `validate-encoding --fix` still
  repairs them and this mission does not migrate history.

## Requirements *(mandatory)*

### Functional Requirements

| ID | Title | User Story | Priority | Status | Delivery | No-op passable? |
|----|-------|------------|----------|--------|----------|-----------------|
| FR-001 | ASCII `tasks/README.md` scaffold | As an operator, I want the core-generated `tasks/README.md` to be pure ASCII so that a fresh mission does not fail `validate-encoding` on text the tool wrote. | High | Open | [ratchet] | no - the gate string changes |
| FR-002 | Scaffold ASCII pin | As a maintainer, I want a test that renders the scaffold and asserts every byte is `< 0x80` so that a future edit cannot reintroduce a typographic glyph. | High | Open | [ratchet] | no - a green test does not prove the glyph is caught |
| FR-003 | Self-mutation proof | As a reviewer, I want the pin shown to fail when a glyph is injected, so that the gate is proven non-vacuous rather than merely present. | High | Open | [ratchet] | no |
| FR-004 | Authored prose preserved | As an operator, I want non-ASCII in content I authored to survive verbatim, so that the fix does not become a silent rewriter. | Medium | Open | [ratchet] | no |
| FR-005 | Pack-owned remainder recorded | As a maintainer, I want the pack-owned half of #6877 filed upstream and cited in the PR, so that the mission does not claim to close more than it fixed. | Medium | Open | [folded] | yes - a citation-only requirement can be satisfied by writing it |
| FR-006 | Single scaffold authority | As a maintainer, I want both `tasks/README.md` emitters to render from `TASKS_README_TEMPLATE`, so that the pin covers every producer and the text cannot drift again. | Medium | Open | [ratchet] | no - two identical producers would still leave the duplicate literal |
| FR-007 | WP frontmatter example matches the pack | As an agent reading the scaffold, I want the documented `history:` entry to use the field names the pack template uses (`at`/`actor`), so that copying the example produces valid frontmatter. | Low | Open | [ratchet] | no |

### Non-Functional Requirements

| ID | Title | Requirement | Category | Priority | Status |
|----|-------|-------------|----------|--------|--------|
| NFR-001 | No new write-boundary sanitising | The change adds zero calls to `sanitize_markdown_text` on the mission create/scaffold path; verified by diff inspection and by FR-004's round-trip test. | Correctness | High | Open |
| NFR-002 | Pin cost | The new test adds no more than one second to the fast suite: it renders in-process, with no mission create, no git operation and no filesystem walk. | Performance | Medium | Open |

### Constraints

| ID | Title | Constraint | Category | Priority | Status |
|----|-------|------------|----------|--------|--------|
| C-001 | Never edit `packs/built-in` in core | `packs/built-in/` is gitignored, digest-pinned and regenerated by `make sync-packs`; `CLAUDE.md` forbids editing it here. | Technical | High | Open |
| C-002 | No unilateral pin bump | Moving `packs/built-in.source.yaml` is subject to the standing ruling of 2026-11-01T09:35Z and operator decision #9; this mission does not bump it. | Business | High | Open |
| C-003 | Single authority for the scaffold text | The ASCII scaffold text keeps exactly one owner, `TASKS_README_TEMPLATE` in `mission_creation_scaffold.py`; the pin reads it, never a copy. | Technical | High | Open |
| C-004 | `setup_feature_directory` keeps its signature and side effects | `worktree.py` is consolidated onto the canonical renderer only; its parameters, the symlink/memory handling and the `.gitkeep` creation stay untouched. | Technical | High | Open |

### Key Entities

- **`TASKS_README_TEMPLATE`**: the single core-owned scaffold text rendered into
  `kitty-specs/<slug>/tasks/README.md` by `render_tasks_readme_content(planning_branch)`.
- **Pin test**: an in-process render plus a byte-range assertion over the rendered output,
  with a self-mutation case proving it can fail.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: `render_tasks_readme_content(branch)` returns text whose every byte is `< 0x80`, for at least the branch names `main`, `feature/x` and `release-4.0.0` - [ratchet] | no-op passable: no
- **SC-002**: `detect_problematic_characters(render_tasks_readme_content("main"))` returns an empty list - [ratchet] | no-op passable: no
- **SC-003**: The pin test fails when `TASKS_README_TEMPLATE` is mutated to contain U+2013 or U+2014, and passes unmutated - [ratchet] | no-op passable: no
- **SC-004**: A freshly scaffolded mission's `tasks/README.md` on disk passes `spec-kitty validate-encoding` for that file - [ratchet] | no-op passable: no
- **SC-005**: The upstream open-packs issue for the four template files and the step prompts exists and is named in the PR's `## Deferred` section - [folded] | no-op passable: yes
- **SC-006**: `setup_feature_directory()` writes `tasks/README.md` bytes identical to `render_tasks_readme_content(<dir name>)`, and no second literal of the scaffold text remains in `src/` - [ratchet] | no-op passable: no
- **SC-007**: The scaffold's documented `history:` example uses `at:`/`actor:`, matching `packs/built-in/missions/software-dev/templates/task-prompt-template.md` - [ratchet] | no-op passable: no
