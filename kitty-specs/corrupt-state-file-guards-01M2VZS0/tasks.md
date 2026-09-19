# Tasks: Corrupt per-mission state files fail closed, not crash

**Mission**: `corrupt-state-file-guards-01M2VZS0` | **Issue**: #4642 (P0, MVP)
**Planning branch**: `fix/4642-corrupt-state-file-guards` | **Merge target**: `fix/4642-corrupt-state-file-guards`

Single lane. Red-first (`@pytest.mark.regression`, ADR 2026-07-17-1) lives inside each fix WP.

## Subtask Index

| ID | Description | WP | Parallel |
|----|-------------|----|----------|
| T001 | Red-first unit tests: `load_index` raises `DecisionIndexReadError` per corruption class; missing-file still empty | WP01 | |
| T002 | Define `DecisionIndexReadError(RuntimeError)` (path + fail-closed + doctor hint) | WP01 | |
| T003 | Extract `_decode_index` helper (reuse `decode_meta(read_bytes)` + wrap `ValidationError`) | WP01 | |
| T004 | Rewire `load_index`; export `DecisionIndexReadError` from `decisions/__init__.py` | WP01 | |
| T005 | Confirm unit tests green + happy-path byte-identical | WP01 | |
| T006 | Red-first entry-point regression: decision verify/resolve on corrupt index.json (3 fixtures) | WP02 | |
| T007 | Add `_handle_index_read_error` (structured `{code,error,details}` + doctor hint + Exit 1) | WP02 | |
| T008 | `except DecisionIndexReadError` arm on all six subcommands | WP02 | |
| T009 | Confirm regression green | WP02 | |
| T010 | Red-first entry-point regression: `next` on corrupt meta.json (malformed + non-UTF-8) | WP03 | [P] |
| T011 | Add `_emit_meta_read_error` honoring `--json`/plain | WP03 | [P] |
| T012 | Exact `except MissionMetaReadError` around query-mode/`decide_next` (not `:215`, not broad RuntimeError) | WP03 | [P] |
| T013 | Confirm regression green + no sibling regression | WP03 | [P] |
| T014 | `[Unreleased]` CHANGELOG entry (#4642), impact-first before→after | WP04 | |
| T015 | File + link the deferred hardening mission (guarded-read primitive + corrupt-state audit; subsumes #4600/#4642) | WP04 | |

## Work Packages

### WP01 — Decisions reader fails closed (IC-1)
- **Goal**: `decisions/store.py:load_index` wraps malformed-JSON / non-UTF-8 / wrong-shape into a typed `DecisionIndexReadError`; missing-file still returns empty index.
- **Priority**: P1 · **Independent test**: drive `load_index` directly against the three corruption fixtures.
- **Subtasks**: T001–T005 · **Depends on**: — · **Est**: ~260 lines
- **Prompt**: `tasks/WP01-decisions-reader-fail-closed.md`

### WP02 — Decisions boundary presentation (IC-2)
- **Goal**: `decision.py` presents `DecisionIndexReadError` cleanly for all six subcommands (verify/resolve/open/list/defer/cancel).
- **Priority**: P1 · **Independent test**: red-first CliRunner regression on verify/resolve.
- **Subtasks**: T006–T009 · **Depends on**: WP01 · **Est**: ~300 lines
- **Prompt**: `tasks/WP02-decisions-boundary-presentation.md`

### WP03 — `next` catches corrupt-meta at the real escape site (IC-3)
- **Goal**: `next` presents `MissionMetaReadError` cleanly, catching it around the query-mode/`decide_next` calls.
- **Priority**: P1 · **Independent test**: red-first CliRunner regression on `next` with corrupt meta.json.
- **Subtasks**: T010–T013 · **Depends on**: — (parallel with WP01/WP02) · **Est**: ~280 lines
- **Prompt**: `tasks/WP03-next-corrupt-meta-catch.md`

### WP04 — Docs/CHANGELOG + deferred-mission filing (IC-5)
- **Goal**: `[Unreleased]` CHANGELOG entry; file & link the deferred hardening mission.
- **Priority**: P2 · **Independent test**: CHANGELOG entry present + issue link recorded.
- **Subtasks**: T014–T015 · **Depends on**: WP01, WP02, WP03 · **Est**: ~150 lines
- **Prompt**: `tasks/WP04-docs-changelog-deferred-mission.md`

## Dependencies

```
WP01 → WP02 ┐
WP03 ───────┼→ WP04
```

## MVP scope
WP01+WP02 (decisions arm) and WP03 (next arm) are each independently shippable; together they close #4642. WP04 is closeout.
