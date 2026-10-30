---
work_package_id: WP01
title: Relocation pairing, --fix, chain trim and docs
dependencies: []
requirement_refs:
- FR-001
- FR-002
- FR-003
- FR-004
- FR-005
- FR-006
- FR-007
- NFR-001
- NFR-003
planning_base_branch: issue-6642-untrusted-audit-relocation-pairing
merge_target_branch: issue-6642-untrusted-audit-relocation-pairing
branch_strategy: Planning artifacts for this mission were generated on issue-6642-untrusted-audit-relocation-pairing. During /spec-kitty.implement this WP may branch from a dependency-specific base, but completed changes must merge back into issue-6642-untrusted-audit-relocation-pairing unless the human explicitly redirects the landing branch.
base_branch: kitty/mission-untrusted-audit-relocation-pairing-01M66F6X
base_commit: 058673c97d861a7b8de8d8f6492d72cc7e2df9d3
created_at: '2026-10-30T13:37:38.919910+00:00'
subtasks:
- T001
- T002
- T003
- T004
- T005
- T006
- T007
- T008
- T009
history:
- '2026-10-30 maintainer-agent-i: WP created from plan.md IC-01/IC-02/IC-03 (single coupled surface)'
agent_profile: python-pedro
authoritative_surface: tests/architectural/untrusted_path_audit/
create_intent: []
execution_mode: code_change
owned_files:
- tests/architectural/untrusted_path_audit/audit.py
- tests/architectural/untrusted_path_audit/inventory.md
- tests/architectural/untrusted_path_audit/RULESET.md
- tests/architectural/test_untrusted_path_containment.py
- docs/changelog/CHANGELOG.md
role: implementer
tags: []
tracker_refs: []
---

## ⚡ Do This First: Load Agent Profile

Before reading anything else, load the implementer profile:

```bash
spec-kitty agent profile show python-pedro
spec-kitty charter context --action implement --include agent-profile:python-pedro
```

Follow the profile's rules for the whole work package.

## Objective

Make `tests/architectural/untrusted_path_audit/inventory.md` survive a pure sink
relocation (issue spec-kitty/spec-kitty#6642): when one ghost inventory row and
one missing live sink uniquely share `(token, untrusted source)`, the audit
reports a single "sink moved" finding instead of a ghost-overcount +
undercount pair, and `audit --fix` re-pins only the machine locator columns
(`file:line`, `qualname`). The ratchet keeps its teeth for every other case.
Also drop the hand-kept "line shifted N→M by mission …" chains from the
inventory rationale cells (git history already records them).

## Context

- Spec: `kitty-specs/untrusted-audit-relocation-pairing-01M66F6X/spec.md` (FR-001..FR-007, edge cases).
- Plan: `kitty-specs/untrusted-audit-relocation-pairing-01M66F6X/plan.md` (IC-01/IC-02/IC-03, testing strategy, seam signature).
- Research: `kitty-specs/untrusted-audit-relocation-pairing-01M66F6X/research.md` (D-1..D-5).
- Code: `tests/architectural/untrusted_path_audit/audit.py` (the audit), `inventory.md` (the curated table), `RULESET.md` (reproducibility contract), `tests/architectural/test_untrusted_path_containment.py` (the acceptance theater).
- Key existing seams (do NOT change their signatures or non-relocation error
  messages): `check_undercount(discovered_keys, inventory_keys)`,
  `check_overcount(discovered_keys, inventory_keys)`,
  `build_discovered_key_map`, `build_inventory_key_map`,
  `_parse_inventory_rows`, `composite_row_key`, `truncate_token`, `main`.
- RowKey = `(rel_path, qualname, token)`; token truncated at 60 chars with `…`.

## Detailed guidance

### T001 — Red-first pairing tests

Add tests to `tests/architectural/test_untrusted_path_containment.py` that
fail on the current tree: simulate a pure relocation by taking real discovered
and inventory key maps (or minimal synthetic ones consistent with the real
token/qualname derivation) where one sink moved (rel_path and/or qualname
changed, token + untrusted source unchanged) and assert the audit's new
behaviour: exactly ONE relocation finding naming both locators, and NO
ghost/undercount error for that sink. Record the red run (command + output
summary) in the WP history below.

### T002 — `pair_relocations` seam + `main` wiring

Add a PURE function to `audit.py`:

```python
def pair_relocations(
    discovered_rows: list[SinkRow],
    inventory_rows: list[dict[str, str]],
) -> tuple[list[tuple[RowKey, str, RowKey, str]], list[str]]:
    """Pair a pure move: one ghost + one missing sink sharing (token, source).
    Returns (pairs, notes); pairs are (ghost_key, ghost_locator, missing_key,
    missing_locator); notes are diagnostics for token-matches that did not pair."""
```

**Key-set semantics (mandatory):** the seam must dedupe to composite KEYS
(`build_discovered_key_map` / `build_inventory_key_map` semantics — two
discovered rows that collapse to one key count ONCE) and must exclude
`[inventory-only]` rows and rows with unparseable identity from the ghost side
before grouping, exactly as the overcount guard does. Counting raw rows
miscounts uniqueness.

Guards (from the spec, all mandatory):
- **Source comparand**: exact equality between the discovered row's
  `untrusted_source` and the inventory row's `source` cell (see T009 — the
  live rows' source cells are re-pinned to the canonical machine string, so
  this equality is meaningful). Empty or hand-prose source cells never pair.
- **Truncation**: a token containing `TOKEN_ELLIPSIS` never auto-pairs.
- **Uniqueness**: a `(token, source)` group pairs only when it contains
  exactly one ghost key AND exactly one missing key; otherwise both guards
  stay red and a note is emitted.

Wire into `main`: after `check_undercount`/`check_overcount`, compute pairs;
suppress the two underlying errors for paired keys and emit ONE finding per
pair (still an error → non-zero exit): `sink moved: <old locator> (qualname,
token) → <new locator>; disposition and rationale carry over — re-run with
--fix to re-pin the locator columns`. Unpaired token-matches emit their note.
The plain audit's output on a GREEN tree must be byte-identical to before
(NFR-001) — on a green tree there are no unmatched keys, so pairing is a no-op.

### T003 — Teeth tests

Through the same seams, prove red stays red: genuine removal (ghost, no
missing); genuine new sink (missing, no ghost); token-changed move (no
pairing); ambiguous 2-ghosts/1-missing and 1-ghost/2-missing in one
`(token, source)` group; ghost + missing sharing token but different source
cells (plus the non-pairing note); truncated token never pairs even when
otherwise unique; two ghosts sharing `(token, source)` with zero missing.

### T004 — `--fix`

`main(argv: list[str] | None = None)` (keep calling it `main`; add an optional
argv parameter so tests can drive it without process-wide argv patching; the
`__main__` entry stays `raise SystemExit(main())`). Accept `--fix`. In fix
mode: compute pairs; rewrite ONLY cell 0 (`file:line`) and cell 1 (`qualname`)
of each paired ghost row in the markdown (match rows by their parsed identity;
the parser must therefore return or the rewriter must re-derive the row's line
index in the file). Then re-run EVERY audit check against the would-be new
text IN MEMORY (parse the rewritten text, rebuild key maps, run all checks);
write the file ONLY if the result is fully green, else report the errors and
exit non-zero WITHOUT writing. With no relocations, `--fix` behaves exactly
like a plain run and writes nothing (idempotent).

### T005 — `--fix` tests

On `tmp_path` copies of the real inventory, driving the simulated relocation
the way the existing theater tests do: monkeypatch the **audit module's**
`INVENTORY_PATH` (i.e. `tests.architectural.untrusted_path_audit.audit.INVENTORY_PATH`,
not the test-module import binding) to the tmp copy, and monkeypatch
`discover_rows` in the same module to return rows with the relocated key.
Assert: after `--fix`, the paired row's token/source/sink-op/disposition/
rationale cells are byte-identical, `file:line` + `qualname` updated, and a
plain audit run exits 0; with an unrelated error present (e.g. an invalid
disposition elsewhere), `--fix` writes nothing and reports; `--fix` twice
writes once; two distinct simultaneous relocations both fixed.

### T006 — Chain guard + trim

Add an audit check: no sink-table rationale cell may contain a line-number
shift chain — the guard must catch BOTH the arrow form and the signed-shift
prose form (compile once at module level, e.g.
`re.compile(r"\d+\s*→\s*\d+|\bshifted\s+[+−-]?\d+")`). Emit a named error per
offending row. Add its test. THEN trim the existing chains from
`inventory.md` rationale cells: remove only the mechanical "line shifted
X→Y by mission Z" / "then X→Y by …" / "shifted −11 by …" history; keep every
disposition justification and provenance note. The audit must be green after
the trim (row identity columns untouched). ALSO reconcile the hand-kept
**"Disposition summary"** table at the foot of `inventory.md`: its counts are
already stale (claims 41/36/5 and safe=19; the live audit prints 45/39/6 and
safe=23) and its cells cite per-row locators that go stale on every future
`--fix`. Correct the counts to the live values, strip the stale per-row
locator citations from the summary cells (the per-row detail lives in the
sink table; the audit's `AUDIT OK` line is the live count source), and leave
the `disposition | count | meaning` shape intact.

### T007 — Docs

- `audit.py` module docstring: document the relocation pairing, the pair-key
  guards, and `--fix` (with the never-touches-human-columns rule).
- `inventory.md` header: extend the "Freshen path" note — a pure move is
  re-pinned by `audit --fix`; never hand-type a token; do not log line shifts
  in rationale cells (git history records them).
- `RULESET.md`: same freshen-path update in the reproducibility section.
- `docs/changelog/CHANGELOG.md`: `[Unreleased]` entry under the `### Fixed`
  subsection of `## [Unreleased] - 4.0.0rc8` — bold impact-first lead with
  `(#6642)`, before/after, under 1,200 characters.

### T009 — Source-cell canonicality (pair-key precondition)

Six live inventory rows have a hand-tuned `untrusted source` cell that does
NOT equal the discovered row's machine `untrusted_source` (verified on main:
`audit/engine.py`, `mission_finalize.py`, `tasks_move_task.py`, two
`backfill_runtime_state.py` rows, `cutover_guard.py` — e.g. inventory
`resolved.mission_slug` vs discovered `mission_slug`). Exact-equality pairing
would silently never fire for them. Add an audit check: every non-
`[inventory-only]` inventory row whose composite key IS discovered must carry
a source cell exactly equal to that discovered row's `untrusted_source`
(named error per offending row; ghost rows are exempt — the pairing rule
governs them). Add its test. Then re-pin the six source cells to the machine
string, folding any hand annotation that is not already in the rationale into
the rationale cell (e.g. the `(operator `--mission` selector)` provenance
stays, in the rationale).

### T008 — Verification

`uv run pytest tests/architectural/test_untrusted_path_containment.py -q`
green (existing assertions unchanged), `uv run python -m
tests.architectural.untrusted_path_audit.audit` exits 0, and `uv run python -m
tests.architectural.untrusted_path_audit.audit --fix` on the green tree writes
nothing / exits 0. Run ruff + mypy on the touched files per repo convention.
Measure the audit runtime before (main) and after (branch) with
`time uv run python -m tests.architectural.untrusted_path_audit.audit` and
record both numbers in the history block (NFR-002: within 2×).

## Branch Strategy

Planning branch: `issue-6642-untrusted-audit-relocation-pairing`. Final merge
target: `main` on the canonical remote (the operator merges; never merge or
push `main` yourself). Execution worktrees are allocated per computed lane
from `lanes.json` by `spec-kitty next`.

## Test Strategy

All tests through the real seams (`pair_relocations`, `check_undercount`,
`check_overcount`, `main(argv)`) — no reimplementation of the matcher in
tests. Red-first proof recorded in the history block. Do not run the full
heavy suite (NO_FULL_HEAVY_SUITES_IN_MISSION); the containment module plus
focused runs suffice.

## Definition of Done

- All FR-001..FR-007 acceptance scenarios covered by tests, red-first proof recorded.
- Audit green on the delivered tree; existing containment tests unchanged and green.
- No human column ever rewritten by `--fix`; no gate weakened, skipped or xfailed.
- Docs and changelog updated.

## Risks / Reviewer Guidance

- Reviewer: verify the uniqueness + exact-source + truncation guards are
  actually enforced (not just documented), that `--fix` cannot write a
  non-green inventory, and that the trim only removed mechanical history.
- Watch for: `main` signature change breaking `test_audit_passes_on_fixed_tree`
  (it calls `_audit_main()` with no args — keep that working).

## History

- 2026-10-30 maintainer-agent-i: WP created.
- 2026-10-30 maintainer-agent-i (T001 red run, recorded per review M-1): wrote the
  red-first tests before any implementation. Red evidence, two layers:
  (a) Defect on pristine main (grounding): simulating a pure relocation of the
  `review/cycle.py:52` sink (same content, same line, renamed module) through
  `discover_rows` + `composite_key_from_file` redirection made
  `python -m tests.architectural.untrusted_path_audit.audit` exit 1 with exactly
  TWO failures — one `check_undercount` (the moved sink is a new undocumented
  key) and one `check_overcount/ghost` (the old row) — the #6642 defect.
  (b) New tests against the unimplemented feature: `uv run --frozen pytest
  tests/architectural/test_untrusted_path_containment.py -q` failed at
  collection with `ImportError: cannot import name 'pair_relocations' from
  tests.architectural.untrusted_path_audit.audit` (1 error), and the core
  main()-level test could not reach its "exactly one `sink moved:` finding"
  assertion (two errors instead). Both red runs reproduced before the audit.py
  changes landed; after implementation the same suite is green (see below).
- 2026-10-30 maintainer-agent-i (T008 verification, recorded per review M-1):
  module `tests/architectural/test_untrusted_path_containment.py` 30/30 passed
  (pre-review-fix round); architectural-fast battery (`pytest tests/architectural
  -m "not performance and not stress and not timing" -n 4 --dist loadfile ...
  --battery-part fast`) 878 passed, 1 skipped; `test_no_legacy_terminology.py`
  98 passed (after per-worktree `make sync-packs`); `ruff check` + `ruff format
  --check` clean; `mypy --strict` clean on both touched files; plain audit green
  with a byte-identical summary line (`AUDIT OK: 45 inventory rows (39
  AST-discovered, 6 inventory-only); TODO(fix)=3 safe=23 trusted=10
  unreachable=9`); `--fix` verified a no-op on the green tree (no write).
- 2026-10-30 maintainer-agent-i (NFR-002 runtime, recorded per review M-1):
  baseline (pristine lane venv, pre-change) ~5.16s wall for the plain audit;
  first implementation 7.16s (the pairing seam recomputed `SinkRow.key()` per
  row — a second file read + AST parse per sink); after memoising
  `SinkRow._key_cache` (excluded from eq/hash/repr per review m-1) 5.69s —
  1.10x baseline, within the 2x NFR-002 budget. Independent reviewer measured
  3.6s vs 3.9s baseline on their run. Commands: `time uv run --frozen python -m
  tests.architectural.untrusted_path_audit.audit`.
- 2026-10-30 maintainer-agent-i (design note, review n-2): `pair_relocations`
  deviates from T002's illustrative signature (`list[SinkRow]`, `list[dict]` in;
  plain tuples out). It takes rich KEY-deduped maps — `Mapping[RowKey,
  tuple[locator, untrusted_source]]` (discovered) and `Mapping[RowKey,
  tuple[locator, source cell]]` (inventory, `[inventory-only]` excluded) — and
  returns `list[RelocationPair]`. The richer inputs are what make the
  exact-source equality comparison and key-set (not row-count) semantics
  possible with no file access in unit tests; `main()` builds both maps via
  `_build_rich_discovered` / `_build_rich_inventory` and passes them to the
  seam it itself consumes (NFR-003 holds).
- 2026-10-30 maintainer-agent-i (review round 1, reviewer-renata REJECT):
  findings B-1 (no red-direction tests for the two new hygiene guards — added
  six tests: red-direction through `main()` on scratch inventories for
  check 5 and both chain forms of check 6, a regex unit test covering both
  forms and clean prose, and green-tree assertions that both guards hold on
  the committed inventory), M-1 (this history block + the NFR-002/red records
  above), M-2 (test file was `mypy --strict`-dirty: 14 errors — annotated all
  new test code, removed two dead helper functions, and referenced
  `composite_key_from_file` via its owning module
  `tests.architectural._ratchet_keys`), m-1 (`_key_cache` now
  `field(compare=False, repr=False)`), m-2 (restored the #2091 fail-closed
  provenance on `coordination/surface_resolver.py:552`/`:504` without the line
  arithmetic), m-3 (the near-miss note now names every same-token/
  different-source candidate, not an arbitrary first match). Post-fix
  verification: module 36/36 passed; `mypy --strict` clean on both files;
  ruff clean; plain audit green with the same summary line.
