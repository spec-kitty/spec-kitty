# Work Packages: In-Harness Feedback Survey

**Inputs**: Design documents from `kitty-specs/in-harness-feedback-survey-01M3PK9W/`
**Prerequisites**: plan.md, spec.md, research.md, data-model.md, contracts/, quickstart.md

**Tests**: Required. The charter binds ATDD-first (C-011): every work package opens with a red-first acceptance or contract test committed before its implementation, and new code must reach 90%+ coverage with mypy `--strict` and ruff clean.

**Organization**: Fine-grained subtasks (`Txxx`) roll up into work packages (`WPxx`). Each work package is independently deliverable and testable.

**Prompt Files**: Each work package references a matching prompt file in `tasks/`. This file is the high-level checklist; implementation detail lives in the prompt files.

## Subtask Format: `[Txxx] [P?] Description`

- **[P]** marks a subtask that can proceed in parallel (different files or components).
- Subtasks are **reference rows**, not checkboxes. Record completion with `spec-kitty agent tasks mark-status <Txxx> --status done`.

## Path Conventions

- Source: `src/specify_cli/feedback/` (new bounded context), thin adapters in `src/specify_cli/cli/commands/`.
- Tests: `tests/specify_cli/feedback/` (unit, contract, acceptance) plus existing test homes of each touched module.

---

## Work Package WP01: Feedback Domain Core — Models, Preferences, Offer Eligibility (Priority: P0)

**Goal**: Own the survey's value types, the hardened per-user `feedback.json`, and the single locked "may an automatic survey be offered now?" decision.
**Independent Test**: Table-driven tests prove the weekly throttle, "don't ask again", clock-skew, corrupt-file, and lock-contention rules through `claim_offer()` without any CLI or network.
**Prompt**: `tasks/WP01-feedback-domain-core.md`
**Requirement Refs**: FR-011, FR-013, FR-018, NFR-003, NFR-005, NFR-007, C-005, C-006

### Included Subtasks

T001 Red-first acceptance tests for offer rules at the `claim_offer()` seam (WP01)
T002 [P] Value types in `feedback/models.py`: SurveyTrigger, Rating, SurveyAnswers, Harness, OfferDecision, OfferReason (WP01)
T003 Hardened preferences read in `feedback/preferences.py` (path, size cap, symlink/owner/mode checks, schema version, unreadable sentinel) (WP01)
T004 Hardened preferences write + `set_automatic_prompts()` (atomic replace, 0600/0700) (WP01)
T005 Pure `decide_offer()` in `feedback/eligibility.py` (WP01)
T006 `claim_offer()` check-and-mark transaction under a non-blocking machine lock (WP01)
T007 Unit tests: models, preferences failure modes, eligibility table, two-process contention (WP01)

### Implementation Notes

- Build on kernel primitives (`read_guarded`, `no_follow`, `atomic_write`, `machine_file_lock`); do not copy `compat/cache.py` private helpers.
- `claim_offer()` writes `last_shown_at` before returning `prompt` for automatic triggers; `on_demand` never writes.

### Parallel Opportunities

- T002 can be written alongside T003/T004 once the file layout is agreed.

### Dependencies

- None (starting package).

### Risks & Mitigations

- Lock contention must never stall a trigger → non-blocking acquire; contention returns `lock_busy`.
- Windows has no POSIX owner/mode semantics → mode/owner checks are POSIX-only, covered by platform-conditional tests.

---

## Work Package WP02: Endpoint Resolution & Distribution Seam (Priority: P0)

**Goal**: Resolve the effective Feedback Endpoint (env > user override > distribution default > none) and keep the upstream build dormant and vendor-neutral.
**Independent Test**: Unit tests cover precedence, HTTPS/loopback validation, the stock and degraded profiles resolving to "no endpoint", and a guard that the feedback package hard-codes no URL.
**Prompt**: `tasks/WP02-endpoint-resolution-distribution-seam.md`
**Requirement Refs**: FR-016, FR-017, NFR-006, C-004

### Included Subtasks

T008 Red-first tests for endpoint precedence and the dormant upstream default (WP02)
T009 Add optional `feedback_endpoint` to `DistributionProfile` (stock and degraded = None) (WP02)
T010 `resolve_feedback_endpoint()` + URL validation in `feedback/endpoint.py` (WP02)
T011 `describe_endpoint()` (effective URL + source label) for `--status` (WP02)
T012 Tests: distribution profile field, endpoint unit matrix, vendor-neutrality guard (WP02)

### Implementation Notes

- `endpoint.py` takes the override as a plain `str | None` parameter so it does not depend on preferences internals.

### Parallel Opportunities

- T009 (distribution module) and T010 (feedback module) touch different files.

### Dependencies

- Depends on WP01 (the `specify_cli.feedback` package must exist).

### Risks & Mitigations

- Existing distribution-profile tests compare dataclass fields → add the field with a default so equality and entry-point construction keep working.

---

## Work Package WP03: Submission Payload & Fire-and-Forget Sender (Priority: P1) 🎯 MVP core

**Goal**: Build the allowlisted, versioned Feedback Submission and deliver it in one detached, bounded, silent HTTPS attempt.
**Independent Test**: Against a loopback test server, a confirmed submission arrives once with only allowlisted fields and no auth header. Against a hanging, refusing, or erroring endpoint, the parent returns in under 1 s with no output.
**Prompt**: `tasks/WP03-submission-payload-sender.md`
**Requirement Refs**: FR-002, FR-003, FR-004, FR-014, FR-020, FR-021, NFR-001, NFR-002, NFR-004, NFR-007, C-003

### Included Subtasks

T013 Red-first acceptance: consent gate, allowlist, silent failure, sub-second return (WP03)
T014 `feedback/payload.py`: validation (rating, 2,000-char comment cap, email shape), context collection, allowlisted builder (WP03)
T015 `feedback/sender.py` child entry point: stdin JSON → one httpx POST (5 s) → exit 0 always (WP03)
T016 `hand_off()` detached spawn (POSIX session / Windows detached flags), payload via stdin, never waits or raises (WP03)
T017 Tests: allowlist + positive control, no credential headers, failure matrix, latency, argv hygiene, Windows flag path (WP03)
T018 [P] Contract test: built payloads validate against `feedback-submission.schema.json` (WP03)

### Implementation Notes

- The parent never logs or prints answers; the child's stdout/stderr go to the null device.

### Parallel Opportunities

- T018 can be written in parallel with T015/T016 once T014 exists.

### Dependencies

- Depends on WP01 (models) and WP02 (endpoint).

### Risks & Mitigations

- Detached-process semantics differ on Windows → isolate spawn flags in one function and test it with a monkeypatched `subprocess.Popen`.

---

## Work Package WP04: Agent Protocol Service (Priority: P1)

**Goal**: Implement the harness handshake — `agent_check`, `agent_submit`, `agent_choice` — exactly as specified in the agent contracts.
**Independent Test**: Contract tests validate every response shape against `agent-check.schema.json` / `agent-submit.schema.json`; `agent_submit` without explicit consent sends nothing.
**Prompt**: `tasks/WP04-agent-protocol-service.md`
**Requirement Refs**: FR-001, FR-003, FR-010, FR-012, FR-013, FR-018

### Included Subtasks

T019 Red-first contract tests for agent-check / agent-submit / agent-choice shapes (WP04)
T020 `agent_check()` — claims the offer, returns fixed survey wording and `comment_max_length` (WP04)
T021 `agent_submit()` — explicit consent required; validate → build → hand off; status mapping (WP04)
T022 `agent_choice()` — `skip` / `never` handling (WP04)
T023 Shared survey wording constants + harness key normalization (WP04)

### Implementation Notes

- `agent_check` gates on CI and endpoint/throttle/prompts, **not** on `is_interactive()`: agents drive the CLI non-interactively by design, and the agent is the human's intermediary.

### Parallel Opportunities

- T022 is independent of T021 once T020 exists.

### Dependencies

- Depends on WP03.

### Risks & Mitigations

- Agent auto-answering → the wording and the prompt block (WP07) state that answers must come from the human; `agent_submit` requires `consent="yes"` explicitly.

---

## Work Package WP05: `spec-kitty feedback` Command & Terminal Form (Priority: P1)

**Goal**: Ship the lean user-facing command: the on-demand form, `--status`, `--prompts on|off`, and the hidden agent flags. Includes the reusable terminal form (with the timed first question used by inline triggers).
**Independent Test**: CliRunner tests submit on demand to a loopback endpoint, show the status content, toggle prompts, print the dormant message, and delegate hidden flags to the protocol service.
**Prompt**: `tasks/WP05-feedback-command-terminal-form.md`
**Requirement Refs**: FR-001, FR-002, FR-003, FR-008, FR-009, FR-012, FR-017, FR-019, FR-020, NFR-007, NFR-008, C-007

### Included Subtasks

T024 Red-first CLI integration tests for the command surface (WP05)
T025 `feedback/terminal_form.py`: four-step form (rating, comment, email, consent), validation re-prompts, timed first (rating) question for inline offers (WP05)
T026 `cli/commands/feedback.py`: bare form, `--status`, `--prompts`, hidden agent flags → JSON (WP05)
T027 Register the command in `cli/commands/__init__.py` (WP05)
T028 Regenerate the completion manifest and the CLI reference docs (WP05)
T029 Terminal-form unit tests incl. timed auto-skip on POSIX and Windows code paths (WP05)

### Implementation Notes

- The bare command refuses to prompt when `is_interactive()` is false and prints a one-line hint instead.

### Parallel Opportunities

- T025 and T026 can be developed in parallel against the WP04 service.

### Dependencies

- Depends on WP04.

### Risks & Mitigations

- The completion-manifest and CLI-reference parity gates go red if T028 is skipped → regenerate with the documented commands and run both gate files.

---

## Work Package WP06: Inline Trigger Hooks for Humans (Priority: P2)

**Goal**: Offer the survey inline after `consolidate`, `finalize-tasks`, and `profile-invocation complete` (done/failed) in a real terminal, without changing any outcome, exit status, or JSON output.
**Independent Test**: Each trigger offers the survey when interactive (positive control), and never under non-interactive, `--json`, or CI runs. `profile-invocation complete --json` output is byte-identical.
**Prompt**: `tasks/WP06-inline-trigger-hooks.md`
**Requirement Refs**: FR-005, FR-006, FR-007, FR-015, FR-018

### Included Subtasks

T030 Red-first acceptance tests for the three hooks (offer / no-offer / outcome unchanged) (WP06)
T031 `feedback/hooks.py`: `offer_after_trigger()` — contained, never raises, Ctrl-C = skip (WP06)
T032 Mission-end hook in `consolidate` after `_run_real_merge` (WP06)
T033 Planning-complete hook in `finalize_tasks` after the success report (not `--validate-only`) (WP06)
T034 Op-close hook in `profile-invocation complete` (done/failed, human output only) (WP06)
T035 Hook unit tests + complexity check on touched functions (WP06)

### Implementation Notes

- Each hook is one straight-line call; all conditions live inside `offer_after_trigger()` so complexity of the host functions does not grow.

### Parallel Opportunities

- T032, T033, and T034 touch different files and can proceed in parallel after T031.

### Dependencies

- Depends on WP05.

### Risks & Mitigations

- `finalize_tasks` already carries a C901 suppression → no new branches there; the hook call is unconditional and self-gating.

---

## Work Package WP07: Agent Guidance Block Across Harness Surfaces (Priority: P2)

**Goal**: Make every agent surface for the trigger commands carry the Feedback Survey Check block, and add the Op-close guidance to the dispatch capsule. The block is sourced once and never hand-edited into generated copies.
**Independent Test**: Surface tests prove the block is present in every render path for `tasks`, `tasks-finalize`, and `consolidate`, and absent for non-trigger commands. A drift test proves the pack prompts carry the canonical block verbatim.
**Prompt**: `tasks/WP07-agent-guidance-block-surfaces.md`
**Requirement Refs**: FR-005, FR-006, FR-007, FR-009, FR-010, C-002, C-008

### Included Subtasks

T036 Red-first surface tests (present for trigger commands, absent otherwise) across installer, shims, and runtime prompts (WP07)
T037 `feedback/agent_block.py`: canonical block, trigger→command map, idempotent `append_feedback_survey_check()` (WP07)
T038 Wire into the CLI-wrapper skill body (`consolidate`) and the shim generator (Markdown + TOML); refresh the twelve-agent baselines (WP07)
T039 Append the block (between markers) to the `tasks` and `tasks-finalize` source prompts; drift test; regenerate the pack graph/manifest (WP07)
T040 Op-close guidance: dispatch capsule human text + the shipped `spec-kitty` skill's close section (WP07)
T041 Domain-matched campsite: re-point the vacuous doctrine-snippet gate glob to `packs/built-in/...` (revert and file an issue if it surfaces unrelated drift) (WP07)

### Implementation Notes

- The `spec-kitty next` runtime cannot import `specify_cli`, so prompt-backed commands get the block through their pack source prompts; CLI-driven commands get it through the Python helper.

### Parallel Opportunities

- T038, T039, and T040 touch disjoint files after T037.

### Dependencies

- Depends on WP05 (snippets must reference a registered command).

### Risks & Mitigations

- Regression baselines and pack-manifest gates will flag the change → update baselines and regenerate the graph in the same WP.

---

## Work Package WP08: Documentation, Glossary, Changelog & End-to-End Validation (Priority: P3)

**Goal**: Make the feature discoverable and consent informed, in canonical, vendor-neutral language, and prove the quickstart end to end.
**Independent Test**: The docs build and gates pass (terminology guard, env-var reference), and the `quickstart.md` walkthrough succeeds on a clean user profile.
**Prompt**: `tasks/WP08-docs-glossary-changelog-validation.md`
**Requirement Refs**: FR-019, C-001, C-007

### Included Subtasks

T042 Glossary entries (Feedback Survey, Feedback Submission, Survey Trigger, Feedback Endpoint) in `docs/context/` (WP08)
T043 How-to guide: give feedback and control the Feedback Survey (WP08)
T044 Reference updates: env var, `feedback.json` fields, `DistributionProfile.feedback_endpoint` packager note (WP08)
T045 `CHANGELOG.md` entry (WP08)
T046 Run the `quickstart.md` walkthrough, the real-harness check (Claude Code, Cursor, Codex, plain terminal; SC-006), and the terminology guard; record evidence and tracer entries (WP08)

### Implementation Notes

- One Divio type per page, `updated:` frontmatter, descriptive alt text for any diagram.

### Parallel Opportunities

- T042–T045 are independent documents.

### Dependencies

- Depends on WP06 and WP07.

### Risks & Mitigations

- Vendor identity leaking into docs → reviewer greps for company names before approval.

---

## Dependency & Execution Summary

- **Sequence**: WP01 → WP02 → WP03 → WP04 → WP05 → {WP06 ∥ WP07} → WP08.
- **Parallelization**: WP06 (inline hooks) and WP07 (agent surfaces) run in parallel after WP05. Within WPs, the `[P]` subtasks can split.
- **MVP Scope**: WP01–WP05 deliver a working on-demand survey plus the agent protocol. WP06–WP07 add the automatic triggers; WP08 documents and validates.

---

## Requirements Coverage Summary

| Requirement ID | Covered By Work Package(s) |
|----------------|----------------------------|
| FR-001 | WP04, WP05 |
| FR-002 | WP03, WP05 |
| FR-003 | WP03, WP04, WP05 |
| FR-004 | WP03 |
| FR-005 | WP06, WP07 |
| FR-006 | WP06, WP07 |
| FR-007 | WP06, WP07 |
| FR-008 | WP05 |
| FR-009 | WP05, WP07 |
| FR-010 | WP04, WP07 |
| FR-011 | WP01 |
| FR-012 | WP04, WP05 |
| FR-013 | WP01, WP04 |
| FR-014 | WP03 |
| FR-015 | WP06 |
| FR-016 | WP02 |
| FR-017 | WP02, WP05 |
| FR-018 | WP01, WP04, WP06 |
| FR-019 | WP05, WP08 |
| FR-020 | WP03, WP05 |
| FR-021 | WP03 |
| NFR-001 | WP03 |
| NFR-002 | WP03 |
| NFR-003 | WP01 |
| NFR-004 | WP03 |
| NFR-005 | WP01 |
| NFR-006 | WP02 |
| NFR-007 | WP01, WP03, WP05 |
| NFR-008 | WP05 |
| C-001 | WP08 |
| C-002 | WP07 |
| C-003 | WP03 |
| C-004 | WP02 |
| C-005 | WP01 |
| C-006 | WP01 |
| C-007 | WP05, WP08 |
| C-008 | WP07 |

---

## Subtask Index (Reference)

| Subtask ID | Summary | Work Package | Priority | Parallel? |
|------------|---------|--------------|----------|-----------|
| T001 | Red-first offer-rule acceptance tests | WP01 | P0 | No |
| T002 | Value types (models.py) | WP01 | P0 | Yes |
| T003 | Hardened preferences read | WP01 | P0 | No |
| T004 | Hardened preferences write | WP01 | P0 | No |
| T005 | Pure decide_offer() | WP01 | P0 | No |
| T006 | claim_offer() locked transaction | WP01 | P0 | No |
| T007 | WP01 unit tests | WP01 | P0 | No |
| T008 | Red-first endpoint tests | WP02 | P0 | No |
| T009 | DistributionProfile.feedback_endpoint | WP02 | P0 | Yes |
| T010 | resolve_feedback_endpoint() + validation | WP02 | P0 | Yes |
| T011 | describe_endpoint() | WP02 | P0 | No |
| T012 | WP02 tests + neutrality guard | WP02 | P0 | No |
| T013 | Red-first sender acceptance | WP03 | P1 | No |
| T014 | payload.py | WP03 | P1 | No |
| T015 | sender.py child entry point | WP03 | P1 | No |
| T016 | hand_off() detached spawn | WP03 | P1 | No |
| T017 | WP03 tests | WP03 | P1 | No |
| T018 | Submission contract test | WP03 | P1 | Yes |
| T019 | Red-first agent contract tests | WP04 | P1 | No |
| T020 | agent_check() | WP04 | P1 | No |
| T021 | agent_submit() | WP04 | P1 | No |
| T022 | agent_choice() | WP04 | P1 | Yes |
| T023 | Wording constants + harness normalization | WP04 | P1 | No |
| T024 | Red-first CLI integration tests | WP05 | P1 | No |
| T025 | terminal_form.py | WP05 | P1 | Yes |
| T026 | cli/commands/feedback.py | WP05 | P1 | Yes |
| T027 | Command registration | WP05 | P1 | No |
| T028 | Completion manifest + CLI reference regen | WP05 | P1 | No |
| T029 | Terminal-form unit tests | WP05 | P1 | No |
| T030 | Red-first hook acceptance tests | WP06 | P2 | No |
| T031 | hooks.py offer_after_trigger() | WP06 | P2 | No |
| T032 | consolidate hook | WP06 | P2 | Yes |
| T033 | finalize-tasks hook | WP06 | P2 | Yes |
| T034 | profile-invocation complete hook | WP06 | P2 | Yes |
| T035 | Hook unit tests + complexity check | WP06 | P2 | No |
| T036 | Red-first surface tests | WP07 | P2 | No |
| T037 | agent_block.py | WP07 | P2 | No |
| T038 | CLI-wrapper skill + shim generator wiring | WP07 | P2 | Yes |
| T039 | Pack source prompts + drift test + graph regen | WP07 | P2 | Yes |
| T040 | Op-close guidance (dispatch + skill) | WP07 | P2 | Yes |
| T041 | Snippet-gate glob campsite | WP07 | P2 | No |
| T042 | Glossary entries | WP08 | P3 | Yes |
| T043 | How-to guide | WP08 | P3 | Yes |
| T044 | Reference updates | WP08 | P3 | Yes |
| T045 | CHANGELOG entry | WP08 | P3 | Yes |
| T046 | Quickstart walkthrough + evidence | WP08 | P3 | No |
