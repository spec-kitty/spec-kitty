# Tasks: CLI Boundary Robustness

**Input**: Design documents from `kitty-specs/cli-boundary-robustness-01M2NQCB/`  
**Prerequisites**: `spec.md`, `plan.md`, `research.md`, `data-model.md`, `quickstart.md`, `contracts/`  
**Planning base / merge target**: `fix/cli-boundary-robustness`

## Subtask Index

| ID | Description | WP | Parallel |
|----|-------------|----|----------|
| T001 | Add red-first #4600 startup regressions through the installed CLI entry point | WP01 | [P] |
| T002 | Make the import-time config pointer read fail soft without weakening bootstrap purity | WP01 | |
| T003 | Harden sibling config/version reads and preserve actionable domain outcomes | WP01 | [P] |
| T004 | Add explicit encodings to the scoped git-metadata reads | WP01 | [P] |
| T005 | Prove healthy-path behavior and the two-second startup budget | WP01 | |
| T006 | Define red-first tests for the canonical error envelope and project-root helper | WP02 | [P] |
| T007 | Create the single shared JSON error-contract authority | WP02 | |
| T008 | Re-export the contract from the doctor compatibility seam | WP02 | [P] |
| T009 | Make shared project-root and git-resolution failures JSON-aware | WP02 | |
| T010 | Freeze exit-code fidelity, stream discipline, and human-mode compatibility | WP02 | |
| T011 | Add context no-subcommand and JSON boundary acceptance tests | WP03 | [P] |
| T012 | Resolve the no-subcommand callback defaults explicitly | WP03 | |
| T013 | Adopt the shared JSON contract across context error paths | WP03 | |
| T014 | Route context success JSON through the console transport seam | WP03 | [P] |
| T015 | Verify context happy-path parity and issue traceability | WP03 | |
| T016 | Scout mission-type registrations and add red-first #4600/#4598/#4601 tests | WP04 | |
| T017 | Contain malformed content-load failures in the command layer | WP04 | |
| T018 | Correct activated-only defaults across every mission-type alias | WP04 | [P] |
| T019 | Adopt canonical JSON failures for mission-type commands | WP04 | |
| T020 | Verify alias parity, inactive opt-in, and unchanged success payloads | WP04 | |
| T021 | Add red-first #4643 empty-mission and remaining-adoption regressions | WP05 | [P] |
| T022 | Restore the tasks-status data-builder/command rendering boundary | WP05 | |
| T023 | Adopt the JSON contract in glossary, archive, and materialize | WP05 | [P] |
| T024 | Opt all otherwise-unowned project-root callers into JSON-aware failures | WP05 | [P] |
| T025 | Verify empty-success shapes, exit codes, streams, and happy paths | WP05 | |
| T026 | Discover and classify the complete structural `--json` command surface | WP06 | |
| T027 | Encode the parse allow-list and adopted-shape error drivers | WP06 | |
| T028 | Encode extensible empty-path fixtures and exit-code comparisons | WP06 | [P] |
| T029 | Add the five-callback OptionInfo/ArgumentInfo output guard | WP06 | [P] |
| T030 | Record deferred non-parseable surfaces in test metadata and failure guidance | WP06 | |
| T031 | Run mission-wide contract, quality, and regression verification | WP06 | |

## Phase 1 – Independent boundary foundations

### WP01 – Startup config-read robustness and sibling folds

**Prompt**: [`tasks/WP01-startup-config-robustness.md`](./tasks/WP01-startup-config-robustness.md)  
**Goal**: Keep config-optional recovery commands alive under unreadable configuration while producing controlled outcomes at scoped sibling reads.  
**Priority**: P0 / MVP-first  
**Independent test**: issue-pinned corrupt-config CLI tests are red on the planning base and green after this package; valid-project startup remains under two seconds.  
**Requirements**: FR-001, FR-004, FR-012; NFR-002, NFR-003, NFR-005, NFR-006  
**Dependencies**: none  
**Estimated prompt size**: ~260 lines

- [ ] T001 Add red-first #4600 startup regressions through the installed CLI entry point (WP01)
- [ ] T002 Make the import-time config pointer read fail soft without weakening bootstrap purity (WP01)
- [ ] T003 Harden sibling config/version reads and preserve actionable domain outcomes (WP01)
- [ ] T004 Add explicit encodings to the scoped git-metadata reads (WP01)
- [ ] T005 Prove healthy-path behavior and the two-second startup budget (WP01)

**Implementation sketch**: Commit the failing acceptance coverage first, widen only the import-time pointer-read guard, then harden the named sibling reads and campsite encoding sites. Preserve the read-site fail-soft/fail-loud partition.  
**Parallel opportunities**: T003 and T004 touch disjoint files after T001 establishes the baseline.  
**Risks**: Catching too broadly can conceal required configuration failures; importing command-layer utilities into bootstrap breaks the purity architecture.

### WP02 – Shared JSON contract seam

**Prompt**: [`tasks/WP02-shared-json-contract.md`](./tasks/WP02-shared-json-contract.md)  
**Goal**: Establish one canonical JSON error-envelope authority and a backward-compatible JSON-aware project-root helper.  
**Priority**: P1 / foundational  
**Independent test**: shared seam tests prove canonical shape, stdout-only JSON, per-command exit fidelity, and unchanged prose mode.  
**Requirements**: FR-005, FR-007, FR-008, FR-012; NFR-004, NFR-006  
**Dependencies**: none  
**Estimated prompt size**: ~260 lines

- [ ] T006 Define red-first tests for the canonical error envelope and project-root helper (WP02)
- [ ] T007 Create the single shared JSON error-contract authority (WP02)
- [ ] T008 Re-export the contract from the doctor compatibility seam (WP02)
- [ ] T009 Make shared project-root and git-resolution failures JSON-aware (WP02)
- [ ] T010 Freeze exit-code fidelity, stream discipline, and human-mode compatibility (WP02)

**Implementation sketch**: Freeze behavior before promotion, move the #4242 envelope into `cli/json_contract.py`, retain doctor imports by re-export, then add a defaulted `json_output=False` helper parameter and converge the touched git failure.  
**Parallel opportunities**: T008 can follow T007 while helper tests are completed. WP01 and WP02 are entirely parallel.  
**Risks**: A second envelope definition or uniform exit-code policy would violate the ratified contract.

## Phase 2 – Parallel command adoption

### WP03 – Context command adoption and resolved defaults

**Prompt**: [`tasks/WP03-context-boundary-adoption.md`](./tasks/WP03-context-boundary-adoption.md)  
**Goal**: Make every owned context path honor the shared machine contract and make bare `context` equivalent to `context info`.  
**Priority**: P1  
**Independent test**: bare-context parity plus unresolvable-workspace and not-in-project JSON cases pass without placeholder leakage.  
**Requirements**: FR-005, FR-007, FR-008, FR-009, FR-011, FR-012  
**Dependencies**: WP02  
**Estimated prompt size**: ~250 lines

- [ ] T011 Add context no-subcommand and JSON boundary acceptance tests (WP03)
- [ ] T012 Resolve the no-subcommand callback defaults explicitly (WP03)
- [ ] T013 Adopt the shared JSON contract across context error paths (WP03)
- [ ] T014 Route context success JSON through the console transport seam (WP03)
- [ ] T015 Verify context happy-path parity and issue traceability (WP03)

**Implementation sketch**: Add issue-pinned tests, pass concrete defaults from the callback, then replace prose-before-JSON and bare-print sites with the shared helper/console seams.  
**Parallel opportunities**: Runs in parallel with WP04 and WP05 after WP02.  
**Risks**: Existing success payloads are public and must remain byte/shape compatible.

### WP04 – Mission-type and mission alias adoption

**Prompt**: [`tasks/WP04-mission-type-boundary-adoption.md`](./tasks/WP04-mission-type-boundary-adoption.md)  
**Goal**: Gracefully contain malformed config loads, restore activated-only defaults, and unify JSON failures across every mission-type alias.  
**Priority**: P1  
**Independent test**: malformed-but-parseable config yields a named non-traceback error; all four list registrations agree; unknown-type JSON uses the canonical envelope.  
**Requirements**: FR-002, FR-003, FR-005, FR-007, FR-008, FR-010, FR-011, FR-012  
**Dependencies**: WP02  
**Estimated prompt size**: ~290 lines

- [ ] T016 Scout mission-type registrations and add red-first #4600/#4598/#4601 tests (WP04)
- [ ] T017 Contain malformed content-load failures in the command layer (WP04)
- [ ] T018 Correct activated-only defaults across every mission-type alias (WP04)
- [ ] T019 Adopt canonical JSON failures for mission-type commands (WP04)
- [ ] T020 Verify alias parity, inactive opt-in, and unchanged success payloads (WP04)

**Implementation sketch**: Scout the 1,700-line module before editing, freeze all registrations in tests, wrap content-load calls at the command boundary, pass `include_inactive=False` at the leaking call site, and route error emissions through WP02.  
**Parallel opportunities**: Runs in parallel with WP03 and WP05 after WP02.  
**Risks**: The doctrine alias delegates separately; changing the callee default instead of the call site can alter library callers.

### WP05 – Remaining JSON adoption and empty-success repair

**Prompt**: [`tasks/WP05-remaining-json-adoption.md`](./tasks/WP05-remaining-json-adoption.md)  
**Goal**: Repair #4643’s exit-zero masking and adopt the shared boundary in every remaining explicitly owned caller.  
**Priority**: P1  
**Independent test**: a zero-WP mission returns parseable success JSON at exit zero; all owned not-in-project paths return canonical errors and preserve existing happy payloads.  
**Requirements**: FR-005, FR-006, FR-007, FR-008, FR-012  
**Dependencies**: WP02  
**Estimated prompt size**: ~310 lines

- [ ] T021 Add red-first #4643 empty-mission and remaining-adoption regressions (WP05)
- [ ] T022 Restore the tasks-status data-builder/command rendering boundary (WP05)
- [ ] T023 Adopt the JSON contract in glossary, archive, and materialize (WP05)
- [ ] T024 Opt all otherwise-unowned project-root callers into JSON-aware failures (WP05)
- [ ] T025 Verify empty-success shapes, exit codes, streams, and happy paths (WP05)

**Implementation sketch**: Land the issue-pinned red test first; make status data pure and let the command select transport; adopt helper/envelope behavior in the explicitly listed command files without refactoring unrelated complexity.  
**Parallel opportunities**: T023 and T024 are disjoint after the shared tests exist; WP05 runs parallel to WP03/WP04.  
**Risks**: Bare-list glossary success is intentional; success payload normalization is out of scope.

## Phase 3 – Class-closure gates

### WP06 – Structural enumeration and placeholder guards

**Prompt**: [`tasks/WP06-class-closure-gates.md`](./tasks/WP06-class-closure-gates.md)  
**Goal**: Close the adopted class by construction with deterministic structural enumeration, parse/shape gates, and the bounded placeholder-leak guard.  
**Priority**: P1 / terminal  
**Independent test**: the architectural gate discovers all `--json` options structurally, all allow-listed drivers parse, adopted drivers have canonical shape, and all five bare callbacks contain no placeholder repr.  
**Requirements**: FR-005, FR-006, FR-007, FR-008, FR-009, FR-010, FR-011, FR-012; NFR-001, NFR-002, NFR-004, NFR-006  
**Dependencies**: WP03, WP04, WP05  
**Estimated prompt size**: ~320 lines

- [ ] T026 Discover and classify the complete structural `--json` command surface (WP06)
- [ ] T027 Encode the parse allow-list and adopted-shape error drivers (WP06)
- [ ] T028 Encode extensible empty-path fixtures and exit-code comparisons (WP06)
- [ ] T029 Add the five-callback OptionInfo/ArgumentInfo output guard (WP06)
- [ ] T030 Record deferred non-parseable surfaces in test metadata and failure guidance (WP06)
- [ ] T031 Run mission-wide contract, quality, and regression verification (WP06)

**Implementation sketch**: Begin with discovery/triage, make classification explicit and reviewable, then add data-driven error/empty cases and the five-callback output guard. Run the full mission verification matrix only after all adoption lanes land.  
**Parallel opportunities**: T028 and T029 can be authored independently after T026; the WP itself waits for all adoption packages.  
**Risks**: Treating known non-parseable deferred commands as adopted makes the gate permanently red; name matching without Typer option introspection misses aliases and false-positives parameters.

## Dependency and lane summary

```text
WP01 (independent P0) ───────────────────────────────┐
WP02 (shared JSON seam) ─┬─> WP03 (context) ─────────┤
                         ├─> WP04 (mission type) ─────┼─> WP06 (class gates)
                         └─> WP05 (remaining JSON) ───┘
```

- WP01 and WP02 can start together with disjoint ownership.
- WP03, WP04, and WP05 can run concurrently after WP02.
- WP06 is terminal and requires the three adoption packages; it does not depend on WP01 at the file/lane level, though final mission verification includes WP01 outcomes.

## MVP recommendation

Land WP01 first as the independently shippable P0 recovery-path hotfix. The full mission MVP is WP01 + WP02 + WP03/WP04/WP05 + WP06; the machine-contract closure claim is not complete until WP06 is green.
