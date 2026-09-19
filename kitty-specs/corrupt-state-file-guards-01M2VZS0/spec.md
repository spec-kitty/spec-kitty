# Mission Specification: Corrupt per-mission state files fail closed, not crash

**Mission Branch**: `fix/4642-corrupt-state-file-guards`  
**Created**: 2026-09-19  
**Status**: Draft  
**Input**: GitHub issue #4642 (P0, MVP scope) — "corrupt per-mission state files crash `next` (meta.json) and `agent decision verify`/`resolve` (decisions/index.json) with uncaught tracebacks"

## Overview

A corrupt (malformed-JSON, non-UTF-8, or wrong-shape) per-mission state file must produce a single clean, operator-readable error and a non-zero exit — never an uncaught Python traceback. Corruption is realistic: a partial write, an interrupted process, or a merge conflict can leave `meta.json` or `decisions/index.json` unreadable. Two command paths crash today; sibling commands reading the same files already degrade gracefully, so this is a per-path guard gap, not a redesign.

**Root cause (shared surface):** there is no canonical *guarded-read → typed domain error → CLI-boundary presentation* primitive. Fail-closed handling rests on an unenforced two-half convention — the reader must wrap raw decode failures into a typed domain error, **and** the command boundary must catch it. A crash occurs the instant either half is skipped. The two reported instances fail on **opposite halves**, confirming a convention gap rather than a single missing line. Closing the whole convention gap (a shared primitive) is deliberately deferred (see Constraints); this mission lands the two operator-facing crashes on the proven `MissionMetaReadError` precedent.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - `next` survives a corrupt `meta.json` (Priority: P1)

An operator or the agent control loop runs `spec-kitty next --mission <slug>` against a mission whose `meta.json` was left malformed by a partial write or merge conflict. `next` is the central loop agents call repeatedly, so a raw traceback there breaks automation, not just one command.

**Why this priority**: `next` is the highest-traffic command and the agent control loop; an uncaught traceback here is the highest-impact arm of the P0.

**Independent Test**: corrupt `kitty-specs/<slug>/meta.json` with malformed JSON, run `spec-kitty next --mission <slug>`, and assert a non-zero exit with a clean fail-closed message and no traceback.

**Acceptance Scenarios**:

1. **Given** a mission whose `meta.json` is malformed JSON, **When** `spec-kitty next --mission <slug>` runs, **Then** the command exits non-zero with the fail-closed message naming the corrupt file and no Python traceback is printed.
2. **Given** a mission whose `meta.json` contains a non-UTF-8 byte, **When** `spec-kitty next --mission <slug>` runs, **Then** the same clean fail-closed error is presented (not a `UnicodeDecodeError`).
3. **Given** `--json`, **When** the corrupt-meta error is presented, **Then** stdout/stderr carries a valid JSON error payload that parses.

---

### User Story 2 - Decision commands survive a corrupt `decisions/index.json` (Priority: P1)

An operator runs `spec-kitty agent decision verify` or `resolve` (or any decision subcommand) against a mission whose `decisions/index.json` is corrupt. Today a raw `JSONDecodeError` / `UnicodeDecodeError` / pydantic `ValidationError` escapes.

**Why this priority**: two of the six decision subcommands crash today; the fix at the single reader (`load_index`) protects all six at once.

**Independent Test**: corrupt `kitty-specs/<slug>/decisions/index.json`, run `spec-kitty agent decision verify --mission <slug>`, and assert a clean non-zero exit with no traceback.

**Acceptance Scenarios**:

1. **Given** a corrupt `decisions/index.json` (malformed JSON), **When** `spec-kitty agent decision verify --mission <slug>` runs, **Then** the command exits non-zero with a clean error and no traceback.
2. **Given** a corrupt `decisions/index.json` (non-UTF-8 byte), **When** `spec-kitty agent decision resolve <id> --mission <slug> ...` runs, **Then** the same clean error is presented (not a `UnicodeDecodeError`).
3. **Given** a valid-JSON but wrong-shape `decisions/index.json` (e.g. `{"entries": "not-a-list"}`), **When** any decision subcommand reads it, **Then** the pydantic validation failure is presented as the clean fail-closed error, not a raw `ValidationError`.
4. **Given** a mission with no `decisions/index.json` at all, **When** a decision subcommand runs, **Then** behavior is unchanged (empty index; no error).

---

### User Story 3 - Consistent operator experience across both files (Priority: P2)

An operator hitting either corrupt file sees the same shape of guidance, so the recovery path is learnable.

**Why this priority**: consistency reduces operator confusion but is secondary to stopping the crashes.

**Independent Test**: trigger both corrupt-state errors and confirm both carry the fail-closed + `run: spec-kitty doctor` guidance.

**Acceptance Scenarios**:

1. **Given** either a corrupt `meta.json` or a corrupt `decisions/index.json`, **When** the error is presented, **Then** both include the fail-closed framing and the `run: spec-kitty doctor` remediation hint (Q1 decision: unify on the doctor-hint shape).

### Edge Cases

- **Non-UTF-8 bytes**, not just malformed JSON — the fix must read bytes and route through the kernel decoder so `UnicodeDecodeError` is covered, not only `JSONDecodeError`.
- **Wrong-shape but valid JSON** — a syntactically valid document that fails schema validation (pydantic) must also be caught.
- **Missing file** — must remain a non-error (empty index / normal not-found), never converted into a corrupt-state error.
- **Broad `RuntimeError` must not be swallowed** — the `next` catch must name `MissionMetaReadError` exactly; a blanket `except RuntimeError` would hide unrelated owned-checkout failures.
- **Downstream escape point** — the `next` meta parse escapes via the query-mode / `decide_next` calls, downstream of `_resolve_mission_slug`; the catch must wrap the actual escape site, not the slug-resolution try/except.

## Requirements *(mandatory)*

### Functional Requirements

| ID | Title | User Story | Priority | Status |
|----|-------|------------|----------|--------|
| FR-001 | `next` catches corrupt-meta at the real escape site | As the agent control loop, I want `spec-kitty next` to present a clean fail-closed error on a corrupt `meta.json` (catching `MissionMetaReadError` around the query-mode/`decide_next` calls, not the slug-resolution except-list) so that the loop degrades gracefully instead of crashing. | High | Open |
| FR-002 | `load_index` wraps decode/validate into a typed error | As an operator, I want `decisions/store.py:load_index` to wrap malformed-JSON, non-UTF-8, and wrong-shape failures into a new `DecisionIndexReadError` (reusing kernel `decode_meta(read_bytes)` for JSON+UTF-8 and a pydantic-`ValidationError` wrap) so that every decision subcommand fails closed at one reader. | High | Open |
| FR-003 | Decision boundary presents the typed error | As an operator, I want the `decision.py` command boundary to catch `DecisionIndexReadError` for all six subcommands (verify, resolve, open, list, defer, cancel) and present it cleanly. | High | Open |
| FR-004 | Unified doctor-hint error shape | As an operator, I want both corrupt-state errors (meta and decisions) to carry the fail-closed framing plus the `run: spec-kitty doctor` remediation hint so both read identically. | Medium | Open |
| FR-005 | Structured `--json` error output | As an automation consumer, I want the corrupt-state errors to emit a valid JSON error payload under `--json` so orchestrator-api consumers do not break. | Medium | Open |

### Non-Functional Requirements

| ID | Title | Requirement | Category | Priority | Status |
|----|-------|-------------|----------|----------|--------|
| NFR-001 | Zero uncaught tracebacks | For each named entry point × each of the 3 corruption classes (malformed JSON, non-UTF-8 byte, wrong-shape), the command exits with code 1 and `result.exception` is `None` or a `SystemExit`/`typer.Exit` — 0 raw `JSONDecodeError`/`UnicodeDecodeError`/`ValidationError`/uncaught `MissionMetaReadError`. | Reliability | High | Open |
| NFR-002 | No happy-path or sibling regression | Valid-input behavior is unchanged (byte-identical parse result); missing-file still returns an empty index; the graceful sibling commands (`accept`, `review`, `mission list`, `agent status show`, `materialize`) continue to degrade gracefully. Verified by existing suites remaining green. | Compatibility | High | Open |
| NFR-003 | Maintainability ceilings held | Touched functions stay at cyclomatic complexity ≤ 15; no bare `except Exception`; no empty handlers; no new `# noqa`/`# type: ignore`; the JSON→object decode reuses canonical `kernel.meta_decode.decode_meta` rather than a parallel decoder. | Maintainability | Medium | Open |

### Constraints

| ID | Title | Constraint | Category | Priority | Status |
|----|-------|------------|----------|----------|--------|
| C-001 | Mirror the canonical precedent, no new primitive | The fix mirrors the existing `MissionMetaReadError` + `load_meta_fail_closed` precedent. It MUST NOT introduce a new generic `read_json_state` kernel primitive — that consolidation is the deferred hardening mission. | Technical | High | Open |
| C-002 | Respect the enforced layer chain | `DecisionIndexReadError` lives in `specify_cli/decisions` (with its reader), not in `kernel` — the reader-level infra error mirrors where `MissionMetaReadError` sits, keeping the `kernel <- ... <- specify_cli` direction. | Technical | High | Open |
| C-003 | Bounded scope — deferrals are explicit | `core/wps_manifest.py` (its `next`-reachable call site is already guarded by a broad `except`; real exposure is `finalize-tasks`), the partial-guard non-UTF-8 tail (`decisions/service.py`, `merge/state.py`, `review/baseline.py`), and the fully-unguarded `review/lock.py`/`review/artifacts.py`/`status/validate.py` are OUT of scope, deferred to a hardening mission that subsumes #4600 + #4642. | Business | High | Open |
| C-004 | Red-first per ADR 2026-07-17-1 | Each instance lands an issue-pinned `@pytest.mark.regression` reproduction that is RED through the pre-existing real command entry point before the fix, then greens. Transitional repros become focused unit tests or move to a functional home; none are left marked `regression`. | Technical | High | Open |

### Key Entities

- **Per-mission state file**: a JSON/YAML file under `kitty-specs/<slug>/` describing mission state. In scope: `meta.json` (mission identity/metadata) and `decisions/index.json` (decision-moment index).
- **Corrupt-state domain error**: a typed, fail-closed error (`MissionMetaReadError`; new `DecisionIndexReadError`) carrying the offending path and a `run: spec-kitty doctor` remediation hint, presented cleanly at the command boundary.
- **Corruption classes**: malformed JSON, non-UTF-8 bytes, and valid-JSON-wrong-shape — all three must fail closed.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: For the named entry points (`next`, `agent decision verify`, `agent decision resolve`), 100% of the 3 corruption fixtures produce a non-zero exit with a readable message and **zero** raw tracebacks.
- **SC-002**: All six decision subcommands are protected by the single `load_index` reader fix (verified by driving the reader-level failure).
- **SC-003**: Zero regressions — the happy path, the missing-file path, and the previously-graceful sibling commands remain green in the existing suites.
- **SC-004**: #4642 is closable; a separate deferred hardening mission (canonical guarded-read primitive + wider corrupt-state audit, subsuming #4600) is filed and linked from the PR.
