# Mission Specification: Reject `--mission` on non-mission-scoped migrate commands

**Mission Branch**: `fix/migrate-reject-mission-flag`
**Created**: 2026-10-17
**Status**: Draft
**Input**: Issue #5294 (P1, milestone "4.0.0 release scope"). Operator-triaged small fix.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - An agent is not silently misled by a flag it was told to pass (Priority: P1)

Spec Kitty's own mission-step skills instruct an agent to pass `--mission <handle>`
to *every* `spec-kitty` command in a multi-mission repo. Five `migrate`
subcommands mutate corpus-wide or repo-wide content and are **not**
mission-scoped, yet today they silently *accept and ignore* `--mission`: the
flag parses, the command runs across the whole corpus/repo, and it exits `0`
with no indication the flag did nothing. The agent believes it scoped a
mutation to one mission when it actually rewrote everything.

**Why this priority**: This is the same exit-zero false-success class as the
4.0.0 GA gate — a destructive-by-surprise rewrite triggered by an instruction
the product itself gives. It is the entire reason the mission exists.

**Independent Test**: Invoke each of the five commands with `--mission <handle>`
and assert a non-zero exit (exit 2) plus a "not mission-scoped" message, instead
of a silent corpus/repo-wide run at exit 0.

**Acceptance Scenarios**:

1. **Given** `backfill-provenance` (a non-mission-scoped command), **When** an agent runs `spec-kitty migrate backfill-provenance --mission some-handle`, **Then** the command exits 2 with an explicit message that the command is not mission-scoped and the flag should be dropped — it does **not** run across the corpus.
2. **Given** any of the five commands, **When** `--mission=some-handle` (equals form) is passed, **Then** it is rejected identically to the space-separated form.
3. **Given** any of the five commands, **When** it is run **without** `--mission` (e.g. `--dry-run --json`), **Then** its behavior is byte-for-byte unchanged from before this mission.

---

### User Story 2 - A real contributor's `--mission` on other commands keeps working (Priority: P2)

The accept-and-ignore mechanism (#3953) exists precisely so the "pass `--mission`
to every command" instruction does not make mission-agnostic commands exit 2.
This mission carves out a narrow exception for five mutating commands; it must
not regress that invariant for the dozens of other mission-agnostic leaf
commands.

**Why this priority**: A regression here would re-open #3953 (every
mission-agnostic command exiting 2 on `--mission`), a worse defect than the one
being fixed.

**Independent Test**: Walk the assembled CLI tree; assert every leaf command
*except* the five-command reject-set still accepts `--mission` (real option or
accept-and-ignore), and the five reject it.

**Acceptance Scenarios**:

1. **Given** the full command tree, **When** `--mission` is offered to every leaf command, **Then** only the five reject-set commands exit 2; all others accept it.
2. **Given** a genuinely mission-scoped command (e.g. `backfill-identity`), **When** `--mission <handle>` is passed, **Then** the handle still reaches the callback and scopes the work (unchanged).

### Edge Cases

- **Bare `--mission` with no value** on a reject-set command: typer's own parser already errors "requires an argument" (exit 2) before the scope post-check runs. Still a loud, non-zero failure — acceptable; the message differs from the scoped-rejection message. Documented, not a regression.
- **Two click eras**: `typer>=0.24.1,<0.28` spans the real `click` package (typer ≤0.25) and typer's vendored `typer._click` (0.26+). The rejection must produce a clean exit 2 in *both*, never a traceback — by resolving the `UsageError` class from the invoking context's own click universe (the existing #4964 machinery).
- **`rewrite-opposed-by` is pack-scoped** (`--pack`), not corpus-scoped; **`repin-hooks` is repo-repair**. A message that says "corpus-wide" is inaccurate for these two — the shared message must be the scope-neutral "this command is not mission-scoped".
- **`--help`**: because the intercepted option stays `hidden=True`, `--help` output is unchanged, so no docs-retrieval-index regeneration is required.
- **Group-position `--mission`** (`spec-kitty migrate --mission <h> <sub>`, flag *before* the subcommand): the `migrate` group callback declares no `--mission` and it is not a forwardable group flag, so click fails it with its own generic "No such option: --mission" (exit 2) at the group level — a *different* message than the leaf-level scoped rejection. Still a loud, non-zero failure; not a regression and not in scope to unify.

## Requirements *(mandatory)*

### Functional Requirements

| ID | Title | User Story | Priority | Status | Delivery | No-op passable? |
|----|-------|------------|----------|--------|----------|-----------------|
| FR-001 | Reject `--mission` on the five non-mission-scoped commands | As an agent, I want `spec-kitty migrate <cmd> --mission <h>` to fail loudly for `backfill-provenance`, `charter-encoding`, `rebaseline-dossier-hashes`, `rewrite-opposed-by`, and `repin-hooks` so that I am never silently given an unscoped mutation. | High | Open | [build] | no — RED on current main (those commands exit 0 today); paired with FR-003 positive control |
| FR-002 | Reject the `--mission=<value>` equals form identically | As an agent, I want the equals form rejected the same way as the space form so that neither syntax silently slips through. | High | Open | [build] | no — exercises both parse forms against the same reject fixture |
| FR-003 | Preserve each command's normal (no-`--mission`) behavior | As an operator, I want each of the five commands to behave exactly as before when `--mission` is absent so that the fix narrows strictly to the flag. | High | Open | [ratchet] | yes — same-fixture positive control for FR-001/FR-002; proves the reject path does not break the command's real work (`--dry-run`/`--json`) |
| FR-004 | Actionable, scope-neutral rejection message | As an agent, I want the error to state the command is not mission-scoped and tell me to drop `--mission` so that I can self-correct without reading source. | Medium | Open | [build] | no — asserts message content, absent on current main |
| FR-005 | Preserve the #3953 accept-and-ignore invariant for all other leaf commands | As a contributor, I want every mission-agnostic command *outside* the reject-set to keep accepting `--mission` so that #3953 is not regressed. | High | Open | [ratchet] | no — tree-wide walk asserts exactly the five reject and the rest accept; a fix that over-rejected would fail |

### Non-Functional Requirements

| ID | Title | Requirement | Category | Priority | Status |
|----|-------|-------------|----------|----------|--------|
| NFR-001 | Two-click-era clean exit | The rejection exits with code exactly `2` (a parsed `UsageError`, never an uncaught traceback) under both the real-`click` and vendored `typer._click` eras across the declared `typer>=0.24.1,<0.28` range; no new option/command class references the real `click` package directly. | Compatibility | High | Open |
| NFR-002 | `--help` byte-stability | `spec-kitty migrate <cmd> --help` stdout for each of the five commands is unchanged by this mission (the intercepting option stays hidden), so no docs-freshness regeneration is required. | Compatibility | Medium | Open |

### Constraints

| ID | Title | Constraint | Category | Priority | Status |
|----|-------|------------|----------|----------|--------|
| C-001 | Reuse existing refusal machinery; no walker edit | The rejection reuses the #4964 helpers (`_given_on_command_line`, `_usage_error_class`, `_COMMANDLINE_SOURCE`) in `migrate_cmd.py`; it is implemented as a `TyperCommand` subclass so `make_leaf_commands_mission_agnostic` leaves it alone via its documented left-alone contract — the generic walker in `cli/helpers.py` is **not** edited. | Technical | High | Open |
| C-002 | Quality gates in the same PR | New class/helpers carry focused tests in the same PR (Sonar new-code gate); cyclomatic complexity ≤ 15; no blanket `# noqa` / `# type: ignore` / Sonar suppressions to pass gates. | Technical | High | Open |
| C-003 | Scope-neutral message | The shared rejection message is scope-neutral ("not mission-scoped"), accurate for corpus-walk, pack-scoped (`rewrite-opposed-by`), and repo-repair (`repin-hooks`) commands alike. | Technical | Medium | Open |

### Key Entities

- **Reject-set**: the five `migrate` subcommands that mutate state but take no mission scope — `backfill-provenance`, `charter-encoding`, `rebaseline-dossier-hashes`, `rewrite-opposed-by`, `repin-hooks`.
- **Mission-agnostic leaf command**: a CLI leaf command without its own real `--mission`; today retargeted to `MissionAgnosticCommand`/`MissionAgnosticGroup` which accept-and-ignore `--mission` (#3953).

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: An agent passing `--mission <handle>` to any of the five reject-set commands gets a non-zero exit (2) and an explicit not-mission-scoped message 100% of invocations, versus the current silent `exit 0` corpus/repo-wide run. — [build] · no-op passable: no
- **SC-002**: Zero regression of the tree-wide #3953 invariant: every mission-agnostic leaf command outside the five still accepts `--mission` (0 new offenders in the tree walk). — [ratchet] · no-op passable: no

## Scope Boundary / Deferred (explicit non-goals)

- **Real per-mission scoping is OUT of scope** (operator triage 2026-10-08): adding a working `--mission` that narrows the walk for the three corpus-walking commands (`backfill-provenance`, `charter-encoding`, `rebaseline-dossier-hashes`) is a separate, larger piece of work. This mission only closes the silent-no-op door. A follow-up issue should be filed for the scoping work.
- **`rewrite-opposed-by` and `repin-hooks` per-mission scoping are non-goals by design** (pack-scoped and repo-repair respectively — no mission concept applies).

## Related Work / Issue Matrix

- **#5294** — this mission's governing issue (owns the work; gating issue-matrix row).
- **#3953** (context only) — introduced the accept-and-ignore mechanism this mission narrows.
- **#4964** (context only, closed via PR #5305) — sibling false-success door (group-flag forward-or-refuse); its refusal machinery is the reuse template.
