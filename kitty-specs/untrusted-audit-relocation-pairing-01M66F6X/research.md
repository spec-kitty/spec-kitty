# Research — untrusted-audit-relocation-pairing-01M66F6X

## Decisions

- **D-1 — The defect is real and unsuperseded on main@512567ee.**
  Reproduced empirically (2026-10-30, clone `/home/exedev/work/sk-6642`): with
  the audit green (`AUDIT OK: 45 inventory rows (39 AST-discovered, 6
  inventory-only)`), relocating one discovered sink to a renamed module
  (rel_path changed, qualname + token unchanged) produces exactly one
  `check_undercount` error ("discovered sink … is MISSING from inventory.md")
  and one `check_overcount` error ("inventory row … has NO live discovered
  sink"). Supersession check: the changelog's relocation-tolerance work
  ("Relocation-hardened architectural dead-code scanners", #2546/#2547/#2072/
  #2548/#2077) re-keyed the *dead-symbol allow-lists and other WS1 ratchet
  allow-lists* onto content descriptors — it did **not** touch
  `tests/architectural/untrusted_path_audit/`. `git log -S "rekey_inventory"`
  shows no live `rekey_inventory.py` consumer in the tree. Nothing else in
  `docs/changelog/CHANGELOG.md` mentions the untrusted-path inventory's
  relocation friction (#6642 is itself deferred from #5015, PR #6622's
  "Proposal (not implemented)" section).
- **D-2 — Mechanism: issue proposal 1 (automatic pure-move pairing + `--fix`), not proposal 2 (format split).**
  Proposal 2 restructures `inventory.md` into a key-stable human file plus a
  generated locator table; that changes the audit's contract with every
  downstream consumer (`test_untrusted_path_containment.py`, RULESET.md's
  reproducibility promise, the hand-curation workflow) for no additional
  acceptance value over pairing. Pairing keeps the single hand-curated file as
  the disposition source of truth and adds a machine-maintained *refresh path*
  for the two locator columns. Proposal 3 (drop the hand-kept "line shifted
  N→M" chains from rationale cells) rides along: it is a one-time trim plus a
  workflow rule, and git history already records the line shifts.
- **D-3 — Pairing key: `(token, untrusted source)`, uniqueness required.**
  The token is the joined-segment code (already the drift-proof part of the
  composite row identity) and the untrusted source names the taint; both are
  invariant under a pure move (module rename, function relocation). Rel_path
  and qualname are exactly the columns a move changes, so they cannot be part
  of the pair key. Uniqueness within the unmatched sets (exactly one ghost and
  exactly one missing sink per `(token, source)` group) is mandatory: the
  current inventory already contains live rows that share a `(token, source)`
  pair across sites (e.g. the two `consolidation/done_bookkeeping.py:523/:525`
  rows), so any weaker condition could pair the wrong rows. Those duplicates
  only matter when they land in the unmatched sets — the uniqueness condition
  covers that case and fails red.
- **D-4 — A paired relocation still exits red; `--fix` is the re-pin.**
  The finding collapses two misleading failures into one actionable "sink
  moved from X to Y" message, but the audit exit code stays non-zero until the
  inventory is re-pinned (issue acceptance: "green after one `--fix` run").
  `--fix` rewrites only the paired rows' `file:line` and `qualname` cells, is
  fail-closed (full in-memory re-audit of the would-be file must be green
  before any write), and never touches token/source/sink-op/disposition/
  rationale cells — the #3011 `rekey_inventory.py` precedent (overwriting
  hand-adjudicated rows) is the failure mode to avoid.
- **D-5 — Teeth preserved by construction.** A genuine removal has no missing
  sink to pair with → overcount fires. A genuine new sink has no ghost to pair
  with → undercount fires. A changed token breaks the pair key → both fire.
  Ambiguity (2 ghosts vs 1 missing, or 1 ghost vs 2 missing, in one
  `(token, source)` group) → both fire. Existing pure seams
  `check_undercount`/`check_overcount` keep their signatures and messages
  (C-003); the pairing is a new pure seam layered above them that `main`
  itself calls.

## Evidence

- Reproduction script and output: see D-1 (inline; no artifacts needed).
- Baseline audit run on pristine main: exit 0, `AUDIT OK: 45 inventory rows
  (39 AST-discovered, 6 inventory-only); TODO(fix)=3 safe=23 trusted=10
  unreachable=9`.
- Rationale-chain offender named by the issue confirmed:
  `cli/commands/agent/tasks_move_task.py:296` row's rationale carries a dozen
  "line shifted N→M by mission …" entries; `coordination/surface_resolver.py`
  and `consolidation/mission_number/bake.py` rows carry shorter chains.
- Consumers of the audit seams (must keep working):
  `tests/architectural/test_untrusted_path_containment.py` imports
  `check_undercount`, `check_overcount`, `build_discovered_key_map`,
  `build_inventory_key_map`, `_parse_inventory_rows`, `main`, `truncate_token`.

## Open questions

- None blocking. (Truncation collision across different sinks sharing a
  60-char token prefix is handled by the uniqueness condition plus the
  fail-closed in-memory re-audit in `--fix`; recorded as a spec edge case.)
