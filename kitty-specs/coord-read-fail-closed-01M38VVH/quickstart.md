# Quickstart — verifying Coord Reads Fail Closed

All runs from the repo root; lane worktrees build their venv on first `uv run --frozen` (~40s, normal). ATDD red-first per ADR 2026-07-17-1.

## Finding A — seam raise + tracer never clobbers (#4959)

```bash
# Seam contract:
uv run --frozen python -m pytest tests/mission_runtime/test_coord_read_seam.py \
  tests/mission_runtime/test_resolution_typed_errors.py \
  tests/mission_runtime/test_read_path_create_window_invariant.py -q
# Tracer fail-closed:
uv run --frozen python -m pytest tests/specify_cli/retrospective/test_tracer_writer.py \
  tests/specify_cli/retrospective/test_tracer_writer_coord_e2e.py -q
```
Expect: UNMATERIALIZED coord read raises `CoordinationWorktreeUnmaterialized` (AC-S1); DELETED still raises `CoordinationBranchDeleted` (AC-S2); tracer-append on a populated file from an unmaterialised checkout leaves it byte-intact (AC-T1); undecodable byte refuses (AC-T2). Red-first: each fails against pre-fix code (empty-PRIMARY / clobber).

## Finding B — decision ledger resolves to PRIMARY; accept unblocks (#4966)

```bash
uv run --frozen python -m pytest tests/specify_cli/decisions/test_service_idempotency.py \
  tests/specify_cli/cli/commands/test_decision_single_authority.py \
  tests/specify_cli/test_acceptance_needs_clarification.py \
  tests/integration/test_accept_matrix_coord_partition.py -q
```
Expect: `decision open` on a materialised-husk coord mission resolves (no `MISSION_NOT_FOUND`, AC-D1); a deferred→resolved decision lets `accept` proceed (AC-D2). Red-first shows `MISSION_NOT_FOUND` / permanent block pre-fix. (Note: this very mission hit #4966 during its own planning — see tracer-tooling-friction.md.)

## Blast-radius regression (seam raise didn't break callers)

```bash
uv run --frozen python -m pytest tests/mission_runtime/ tests/specify_cli/coordination/ \
  tests/status/ tests/integration/test_coord_topology_smoke.py -q
```
Expect: sanctioned read-only degraders still degrade; already-safe catchers unchanged; ~25 no-catch coord `STATUS_STATE` readers fail loud at sane boundaries; non-coord/flat unchanged (NFR-002).

## Whole-mission gates (pre-hand-off)

```bash
uv run ruff check . && uv run ruff format --check .
uv run python -m pytest tests/architectural/test_no_legacy_terminology.py -q     # after prose
PYTHONPATH=. uv run python -m scripts.docs.check_docs_freshness --ci             # after ADR/docs (errors=0)
```
Plus the changed-file + owning-subsystem suites per the charter test policy, and the ADR frontmatter description 50–180 char (unique, non-boilerplate) SEO gate.
