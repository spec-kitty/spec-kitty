---
description: "Work package task list for charter-service pin release line"
---

# Work Packages: charter-service pin release line

**Inputs**: Design documents from `kitty-specs/charter-service-pin-line-01M6BTXZ/`
**Prerequisites**: plan.md (required), spec.md, research.md, quickstart.md

**Tests**: Included explicitly. This mission changes a trust path (pin defaults and
provenance) and adds an install-time proof the issue asks for; every production change has
a red-first test through the production entry point.

**Organization**: Fine-grained subtasks (`Txxx`) roll up into work packages (`WPxx`). Each
work package is independently deliverable and testable.

**Prompt Files**: `tasks/WP01-charter-pin-surface.md`, `tasks/WP02-docs-and-changelog.md`.

## Subtask Index

| ID | Description | WP | Parallel |
|----|-------------|----|----------|
| T001 | Red tests for the attestation seam; new `attestation.py` module with stable codes | WP01 | |
| T002 | Red tests for the per-service default repository; `DEFAULT_REPOSITORIES` + resolver | WP01 | [P] |
| T003 | Wire the provenance check into `_verified_asset`; vendor tests for pass/refuse/`file://` | WP01 | |
| T004 | `--no-attestation` flag, `--tag`/`--repository` help and docstring name the owning repository | WP01 | |
| T005 | Retire the provisional prefix comment; prefix ratchet test on all three services | WP01 | [P] |
| T006 | Charter-service fixture-pin fetch tests (verified digest + tampered refusal) | WP01 | |
| T007 | Run the touched modules and the two ownership gates; fix what is red | WP01 | |
| T008 | Update `pins/README.md` for per-service release homes and provenance | WP02 | |
| T009 | Update the service-pins how-to: automatic check, refusal codes, manual second source | WP02 | |
| T010 | Changelog `[Unreleased]` entry under 1,200 characters | WP02 | |
| T011 | Docs freshness/terminology checks for the touched docs | WP02 | |

---

## Work Package WP01: Pin surface — defaults, provenance, charter proof (Priority: P1)

**Goal**: The pin model names each service's own release repository and refuses to write a
pin for a release whose build attestation does not verify; a charter-service fixture pin is
proven end to end through `service fetch`.
**Independent Test**: `uv run pytest tests/specify_cli/services/test_attestation.py
tests/specify_cli/services/test_vendor.py tests/specify_cli/services/test_service_cli.py
tests/kernel/test_service_pin.py -q` passes, and the provenance tests fail if the seam call
is removed.
**Prompt**: `tasks/WP01-charter-pin-surface.md`
**Requirement Refs**: FR-001, FR-002, FR-003, FR-004, FR-005, NFR-001, NFR-002, NFR-003, C-001, C-002, C-003, SC-001, SC-002, SC-003

### Included Subtasks

T001 Red tests for the attestation seam; new `attestation.py` module with stable codes
T002 Red tests for the per-service default repository; `DEFAULT_REPOSITORIES` + resolver
T003 Wire the provenance check into `_verified_asset`; vendor tests for pass/refuse/`file://`
T004 `--no-attestation` flag, `--tag`/`--repository` help and docstring name the owning repository
T005 Retire the provisional prefix comment; prefix ratchet test on all three services
T006 Charter-service fixture-pin fetch tests (verified digest + tampered refusal)
T007 Run the touched modules and the two ownership gates; fix what is red

### Implementation Notes

- Order: T001 (seam) -> T002 (defaults) -> T003 (wiring) -> T004 (CLI) -> T005/T006 -> T007.
  T005 and T006 touch different files and may proceed in parallel after T003.
- Red-first: write and run each test before its production change; record the red output in
  the WP history note.
- Keep `kernel` free of `gh` and repository identities (C-002); the seam lives in
  `specify_cli.services.attestation`.
- `file://` repositories must make zero subprocess calls (NFR-001) - the existing offline
  tests are the proof, and they must stay green without a fake `gh`.

### Parallel Opportunities

- T005 (kernel comment + prefix test) is independent of T003/T004.
- T006 (service_cli fixture tests) only needs the branch, not the provenance code.

### Dependencies

- None. WP02 depends on this WP.

### Risks & Mitigations

- A mandatory `gh` step could break a maintainer bump: the refusal code names the remedy,
  `--no-attestation` is documented as the explicit escape, and `file://` skips.
- A helper-only test could pass while the vendor wiring is missing: the provenance tests go
  through `vendor_pin`/the CLI, not just the seam.

---

## Work Package WP02: Docs — release homes, provenance, changelog (Priority: P2)

**Goal**: An operator reading `pins/README.md`, the service-pins how-to or the changelog
learns which repository each service releases from and that a bump verifies provenance.
**Independent Test**: `pins/README.md` and `docs/development/how-to/service-pins.md` name
spec-kitty-charter for `charter-service` and contain no statement that every service
defaults to spec-kitty-events; `uv run python -m scripts.docs.check_docs_freshness --ci`
reports `errors=0`.
**Prompt**: `tasks/WP02-docs-and-changelog.md`
**Requirement Refs**: FR-004, SC-004

### Included Subtasks

T008 Update `pins/README.md` for per-service release homes and provenance
T009 Update the service-pins how-to: automatic check, refusal codes, manual second source
T010 Changelog `[Unreleased]` entry under 1,200 characters
T011 Docs freshness/terminology checks for the touched docs

### Implementation Notes

- Docs describe the shipped behaviour of WP01 (the flag and codes exist by then).
- The changelog entry is impact-first, cites `(#6909)`, gives before/after, and stays under
  1,200 characters.
- Do not edit ADRs: the accepted records stay as written; the charter repository's
  ADR-0046 sentence is noted in the PR hand-off, not edited here.

### Parallel Opportunities

- T008, T009 and T010 touch different files and can proceed in parallel; T011 runs last.

### Dependencies

- WP01 (the documented behaviour and codes must exist).

### Risks & Mitigations

- Doc drift from the implementation: T011 re-reads the help output and the code's code
  constants against the prose.
- The generated docs index is shared host state: regenerate only the touched surfaces (see
  the brief) and verify with the freshness check rather than a blind rebuild.
