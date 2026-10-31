# Tasks — untrusted-audit-relocation-pairing-01M66F6X

**Issue**: spec-kitty/spec-kitty#6642
**Branch contract**: planning on `issue-6642-untrusted-audit-relocation-pairing`; PR merge target `main` on the canonical remote (operator merges).

## Subtask Index

| ID | Description | WP | Parallel |
|----|-------------|----|----------|
| T001 | Red-first: failing relocation-pairing tests through the real seams (pure move → single moved finding) | WP01 | no |
| T002 | Implement `pair_relocations` pure seam + `main` wiring (report-only; source-comparand, truncation and uniqueness guards) | WP01 | no |
| T003 | Teeth tests: removal / new sink / token change / ambiguity / source mismatch / truncated token / two-ghosts-no-missing | WP01 | no |
| T004 | Implement `--fix`: argparse flag, cell rewrite of `file:line` + `qualname` only, fail-closed in-memory re-audit, idempotence | WP01 | no |
| T005 | `--fix` tests on a temp inventory copy: human columns byte-identical, green after fix, no-write on unrelated errors, double-run no-op, multiple simultaneous relocations | WP01 | no |
| T006 | Rationale line-shift chain guard (audit check + test) and one-time trim of the chains in `inventory.md` | WP01 | no |
| T007 | Docs: `audit.py` module docstring, `inventory.md` header notes, `RULESET.md` freshen-path section, `docs/changelog/CHANGELOG.md` `[Unreleased]` entry | WP01 | no |
| T008 | Verify the full containment test module passes unchanged in its existing assertions and the audit is green on the trimmed inventory | WP01 | no |
| T009 | Source-cell canonicality: audit check + test that every live non-[inventory-only] row's source cell equals the discovered `untrusted_source`; re-pin the six hand-tuned cells | WP01 | no |

## Work Packages

### WP01 — Relocation pairing, `--fix`, chain trim and docs

- **Summary**: Teach `tests/architectural/untrusted_path_audit/audit.py` to recognise a pure sink relocation (unique `(token, untrusted source)` pairing between one ghost row and one missing live sink), report it as a single "moved" finding, and re-pin only the locator columns via a fail-closed `--fix`; keep every other tripwire exactly as strict; drop the hand-kept line-shift chains from the inventory rationale cells; update the docs. Priority: High. The audit must be green on the delivered tree (SC-005) and red-first proof recorded (C-004).
- **Included subtasks**: T001–T008.
- **Independent test**: `uv run pytest tests/architectural/test_untrusted_path_containment.py -q` green, plus `uv run python -m tests.architectural.untrusted_path_audit.audit` exits 0; the new tests prove both the relocation path and the teeth.
- **Implementation sketch**: (1) write the failing pairing tests against the current seams; (2) add `pair_relocations(discovered_rows, inventory_rows)` returning `(pairs, notes)` with the source-comparand, truncation and uniqueness guards; wire it into `main` after `check_undercount`/`check_overcount` so paired keys produce one "sink moved" finding instead of two errors; (3) teeth tests; (4) `--fix` — parse `argv`, rewrite only cells 0/1 of paired rows, re-audit the would-be text in memory, write only if fully green; (5) `--fix` tests on `tmp_path` copies; (6) add the rationale-chain check (regex `\d+\s*→\s*\d+` on sink-table rationale cells) with its test, then trim the chains from `inventory.md`; (7) docs + changelog; (8) full verification.
- **Parallel opportunities**: none — single tightly-coupled surface (the audit module and its inventory must reconcile green in one WP).
- **Dependencies**: none.
- **Risks**: pairing the wrong rows (guarded by uniqueness + exact source match + truncation exclusion); writing a non-green inventory (guarded by the in-memory re-audit); over-trimming rationale prose (guarded by the pattern-defined trim + green audit).
- **Prompt file**: `tasks/WP01-relocation-pairing-and-fix.md`

## Issue matrix

| Issue | Claim | Verdict |
|-------|-------|--------|
| spec-kitty/spec-kitty#6642 | claimed 2026-10-30 by Ivan-Melck (status:claimed, taken-by-human) — https://github.com/spec-kitty/spec-kitty/issues/6642#issuecomment-6523717122 | pending (in-mission; set at wrap-up via `spec-kitty agent issue-verdict`) |

## Requirement coverage

- FR-001 (pairing finding) → WP01 (T001, T002, T009)
- FR-002 (`--fix` locator-only rewrite) → WP01 (T004, T005)
- FR-003 (`--fix` fail-closed) → WP01 (T004, T005)
- FR-004 (removal still fails) → WP01 (T003)
- FR-005 (new sink still fails) → WP01 (T003)
- FR-006 (ambiguous/token-changed fails) → WP01 (T003)
- FR-007 (drop line-shift chains) → WP01 (T006)
- NFR-001 (green-tree no-op) → WP01 (T008)
- NFR-002 (runtime within 2×) → WP01 (T008)
- NFR-003 (pure seams) → WP01 (T002)
