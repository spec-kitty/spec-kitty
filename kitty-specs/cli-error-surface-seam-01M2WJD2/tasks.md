# Tasks — Canonical guarded-read + CLI error-presentation seam

**Mission**: cli-error-surface-seam-01M2WJD2 · **Branch**: `fix/cli-error-surface-seam`
**Umbrella**: #2899 · **Children**: #4746, #4738, #4724, #4637, #4739, #4720

MVP = **WP01** (the primitive + global hook + subclassing). Every adoption WP
(WP02–WP07) depends on it; **WP08** (the construction gate) is the integration
capstone after all adoption lands.

## Subtask Index

| ID | Description | WP | Parallel |
|----|-------------|----|----------|
| T001 | `GuardedReadError` base in `kernel/errors.py` (+`__all__`, path/reason, actionable `__str__`) | WP01 | |
| T002 | `read_guarded()` format-agnostic primitive in `kernel/guarded_read.py` (+ unit tests) | WP01 | |
| T003 | Refactor `meta_decode.decode_meta` onto `read_guarded` (preserve #4600/#4642) | WP01 | |
| T004 | Re-parent 7 legacy errors as `GuardedReadError` subclasses (in place) | WP01 | |
| T005 | `except`-site caller census (src+tests) + NFR-006 back-compat regression | WP01 | |
| T006 | Global Typer error hook on the top-level app; fold #4600/#4642 emitters | WP01 | |
| T007 | Red-first: `workflow import`/`export` bad-file tracebacks | WP02 | [P] |
| T008 | `WorkflowFileError` + guard `load_workflow_file` callers (import+export) | WP02 | [P] |
| T009 | Green incl. `--json` envelope | WP02 | [P] |
| T010 | Red-first: `mission close`/`accept` invalid `--mission`; `-f --discard` footgun | WP03 | [P] |
| T011 | Route `mission close` + `accept` through the hook (exit 1) | WP03 | [P] |
| T012 | Remove `-f`=`--mission` alias across the 4 sites | WP03 | [P] |
| T013 | Green (exit 1; `--help` shows no `-f`) | WP03 | [P] |
| T014 | Red-first: release prep missing file / missing `[project].version` / malformed TOML (+`--json`) | WP04 | [P] |
| T015 | `ReleasePyprojectError` + guard `payload.py` version read (3 modes) | WP04 | [P] |
| T016 | Green incl. `--json` object | WP04 | [P] |
| T017 | Red-first: `intake -` non-UTF-8 stdin (text-stream path) | WP05 | [P] |
| T018 | Guard the `stream.read()` text-stream path (parity with file path) | WP05 | [P] |
| T019 | Green (stdin == file-path handling) | WP05 | [P] |
| T020 | Red-first: `specify` `日本語`/`Ünïcödé`/`auth日本` `--json` (non-JSON/exit2/silent-drop) | WP06 | [P] |
| T021 | `NonAsciiNameError` + replace `typer.BadParameter` in `_slugify_feature_input`; reject non-ASCII, no partial write | WP06 | [P] |
| T022 | Route `specify --json` name-validation error as JSON on stdout via the hook | WP06 | [P] |
| T023 | Green: 3 scenarios + NFR-005 no-write + identifier-safety (accented-Latin + non-Latin) | WP06 | [P] |
| T024 | Red-first (through command entry points) for the 7 audit-tail readers | WP07 | [P] |
| T025 | Route each reader through `read_guarded`, preserving missing-vs-corrupt contract (D5) | WP07 | [P] |
| T026 | Replace `runtime_bridge` broad-except mask with the typed seam + companion assertion | WP07 | [P] |
| T027 | Green through command entry points; contract-preservation tests | WP07 | [P] |
| T028 | Gate `tests/architectural/test_cli_error_surface_seam.py`: hook registered + no in-scope read/decode/resolver outside primitive (AST/call-graph, concrete floor) | WP08 | |
| T029 | Self-mutation non-vacuity test (fails when hook removed OR unguarded read introduced) | WP08 | |
| T030 | Wire into the arch battery + shrink-only baseline allowlist | WP08 | |

## Work Packages

### WP01 — Foundation: guarded-read primitive + global hook + subclassing
- **Goal**: build the kernel `read_guarded` primitive + `GuardedReadError` base, the single global Typer error hook, re-parent the 7 legacy errors as subclasses, and land the `except`-site census + back-compat regression. Enabler for all other WPs.
- **Priority**: P1 (MVP). **Independent test**: primitive unit matrix; hook renders a domain error as text/JSON exit 1 and re-raises a non-domain error; `decode_meta` behavior unchanged; every legacy type still caught by its existing `except` sites.
- **Subtasks**: T001, T002, T003, T004, T005, T006
- **Dependencies**: none
- **Risks**: kernel dependency floor (no schema libs); `UnsafePathSegmentError` must stay `except ValueError`-catchable; `__init__.py` edit ⇒ version bump + CHANGELOG (coordinate the version with the PO — do not prescribe a number).
- **Prompt**: `tasks/WP01-foundation-guarded-read-seam.md` (~300 lines)

### WP02 — `workflow import`/`export` (#4738)
- **Goal**: guard `load_workflow_file` callers so bad workflow files present cleanly.
- **Priority**: P1. **Independent test**: malformed/wrong-schema/wrong-type/unreadable import → exit 1 typed error; export of a corrupt resolved workflow → typed error; `--json` envelope.
- **Subtasks**: T007, T008, T009 · **Dependencies**: WP01
- **Prompt**: `tasks/WP02-workflow-import-export-guard.md` (~200 lines)

### WP03 — `mission close` + `accept` + `-f` sweep (#4724)
- **Goal**: route `mission close` and `accept` through the hook on an invalid `--mission`; remove the `-f`=`--mission` alias across the 4 sites.
- **Priority**: P1. **Independent test**: invalid `--mission` → exit 1 typed error (both commands); `mission close -f --discard` no longer crashes; `--help` shows no `-f`.
- **Subtasks**: T010, T011, T012, T013 · **Dependencies**: WP01
- **Prompt**: `tasks/WP03-mission-close-accept-f-sweep.md` (~230 lines)

### WP04 — `agent release prep` 3-mode (#4637)
- **Goal**: clean typed error for missing pyproject, missing `[project].version`, malformed TOML (+`--json`).
- **Priority**: P1. **Independent test**: each of the 3 modes → exit 1 typed error; `--json` object.
- **Subtasks**: T014, T015, T016 · **Dependencies**: WP01
- **Prompt**: `tasks/WP04-release-prep-pyproject-guard.md` (~200 lines)

### WP05 — `intake -` stdin non-UTF-8 (#4739)
- **Goal**: guard the text-stream `stream.read()` so stdin matches the file-path handling.
- **Priority**: P2. **Independent test**: non-UTF-8 stdin → exit 1 (parity with file path).
- **Subtasks**: T017, T018, T019 · **Dependencies**: WP01
- **Prompt**: `tasks/WP05-intake-stdin-guard.md` (~180 lines)

### WP06 — `specify --json` + non-ASCII reject (#4720)
- **Goal**: replace `typer.BadParameter` with a hook-owned domain error; reject non-ASCII names explicitly with no partial write; consistent JSON envelope.
- **Priority**: P1. **Independent test**: `日本語`/`Ünïcödé`/`auth日本` `--json` rejected with JSON object exit 1; no identifier written; identifier-safety regression.
- **Subtasks**: T020, T021, T022, T023 · **Dependencies**: WP01
- **Prompt**: `tasks/WP06-specify-json-nonascii.md` (~230 lines)

### WP07 — Audit-tail readers + `runtime_bridge` mask (#4746)
- **Goal**: harden the 7 named readers through `read_guarded`, preserving the missing-vs-corrupt contract; replace the masking broad-except in `runtime_bridge`.
- **Priority**: P2. **Independent test**: each reader, via its real command entry point, presents a typed error on corrupt/non-UTF-8 input; absent-input `None`/empty preserved.
- **Subtasks**: T024, T025, T026, T027 · **Dependencies**: WP01
- **Prompt**: `tasks/WP07-audit-tail-readers.md` (~250 lines)

### WP08 — Non-vacuous construction gate (#4746 / FR-011)
- **Goal**: the architectural gate that keeps the class closed.
- **Priority**: P2 (capstone). **Independent test**: gate fails when the hook is removed OR an in-scope command reaches a read/decode/resolver outside the primitive; passes on the hardened tree.
- **Subtasks**: T028, T029, T030 · **Dependencies**: WP01, WP02, WP03, WP04, WP05, WP06, WP07
- **Prompt**: `tasks/WP08-construction-gate.md` (~220 lines)

## Parallelization

- **Wave 0 (sequential)**: WP01.
- **Wave 1 (parallel)**: WP02, WP03, WP04, WP05, WP06, WP07 — distinct owned files.
- **Wave 2 (capstone)**: WP08.
