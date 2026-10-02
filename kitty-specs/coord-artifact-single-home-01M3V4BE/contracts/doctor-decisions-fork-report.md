# Contract: `doctor decisions` fork report, repair, and verify

**Detector:** `src/specify_cli/decisions/fork.py` (new), `detect_decision_forks(repo_root, mission_slug) -> DecisionsForkReport` and `coordination_only_ledger(repo_root, mission_slug) -> LedgerHomeFinding`.
**Consumers:**
- `cli/commands/_decisions_doctor.py`: `_diagnose` (L372), `_repair` (L404), `run_decisions_reconciliation` (L529);
- `decisions/verify.py::verify` (L104), via `decision verify` (`cli/commands/decision.py:567`);
- `coordination/teardown.py::teardown_coordination_topology` (L222);
- `consolidation/executor.py::_pre_mutation_safety_preflight` (L3450).

**Requirements:** FR-009c, FR-010, FR-010a, FR-011; SC-004; NFR-002. Decisions: `forked-log-recovery`, `fork-check`, `legacy-ledger`.

## Inputs read

| Surface | Worktree (preferred when present) | Ref (fallback, fresh clone) |
|---------|-----------------------------------|-----------------------------|
| PRIMARY | the repository root checkout's Mission dir (`read_dir(PRIMARY_METADATA)`) | `git show <target_branch>:kitty-specs/<dir>/<file>` |
| COORD | the coordination worktree's Mission dir (`CoordinationWorkspace.worktree_path`) | `git show <coordination_branch>:kitty-specs/<dir>/<file>` |

The prefix/fork comparison reuses the pure classifier in `coordination/event_prefix.py`; there is no second classifier. The streams are `status.events.jsonl` (decision events filtered by `event_type`) and `decisions.events.jsonl`. The ledger is `decisions/index.json` plus `decisions/DM-*.md`.

The detector never writes and never materializes; it is read-only and safe on any checkout.

## Report

The value objects are defined in `data-model.md` §4. The JSON envelope adds fields to the existing `doctor decisions --json` output:

```json
{
  "mission_slug": "m-01ABCDEF",
  "forked": true,
  "streams": [
    {"stream": "status.events.jsonl", "state": "forked",
     "primary": {"source": "worktree", "path": "...", "event_count": 4},
     "coordination": {"source": "ref", "ref": "kitty/mission-m-01ABCDEF", "event_count": 3},
     "decisions_only_on_primary": ["01J…A"], "decisions_only_on_coordination": ["01J…B"], "decisions_on_both": []}
  ],
  "ledger": {"state": "primary", "entries_only_on_coordination": [], "dm_files_only_on_coordination": []},
  "orphaned_in_index": [],
  "missing_from_index": [],
  "reconcile_steps": ["…"]
}
```

`state` values: `single_home`, `prefix`, `forked`, `absent`. Text output prints one line per stream and per surface, then the reconcile steps.

## Rules

1. **Orphan rule.** An index entry is orphaned only when its decision id is absent from every stream on both surfaces.
2. **`--repair` never removes** an entry whose events exist on either surface (FR-011). When `forked` is true, `--repair` performs no index rewrite for the forked decisions. It prints `reconcile_steps` and exits 1. There is no automatic re-sequencing (C-003).
3. **`--repair` on an unforked Mission** still repairs a genuine orphan (positive control) and still adds `missing_from_index` entries, as today.
4. **Coordination-only ledger.** When `ledger.state == "coordination_only"` (or `both` with entries only on the coordination side), `doctor decisions` reports `DECISION_LEDGER_ONLY_ON_COORDINATION`. `--repair` copies the missing `DM-*.md` files and merges the index entries into the PRIMARY ledger dir with the shared pure `union_decision_index(ours, theirs)` (`consolidation/drivers.py`, the same function as the merge driver). The merge is additive and runs under the ledger's `index.json.lock`. The repair prints the commit hint (`spec-kitty spec-commit -m … kitty-specs/<dir>/decisions/`) and creates no commit (FR-009b; the ledger committers are spec-commit and accept).
5. **`decision verify`** adds the finding `DECISION_LOG_FORKED` whenever `detect_decision_forks(...).forked`. It exits 1 by default and appears in `findings[]` of the JSON output.
6. **Teardown and consolidation** call `coordination_only_ledger`. A non-empty result raises `ProjectionTeardownAbort` with `error_code="COORDINATION_LEDGER_UNREPAIRED"` and the hint `spec-kitty doctor decisions --repair`.

## Error and finding codes

| Code | Kind | New or existing |
|------|------|-----------------|
| `DECISION_LOG_FORKED` | doctor finding plus verify finding | new |
| `DECISION_LEDGER_ONLY_ON_COORDINATION` | doctor finding | new |
| `COORDINATION_LEDGER_UNREPAIRED` | teardown and consolidation refusal (`ProjectionTeardownAbort`) | new code on an existing exception |
| `DEFERRED_WITHOUT_MARKER`, `MARKER_WITHOUT_DECISION`, `STALE_MARKER` | verify findings | existing, unchanged |

## Compatibility

- Additive JSON keys only.
- `decision verify` can newly exit 1, for forked Missions only (FR-010a).
- `doctor decisions --repair` can newly exit 1, for forked Missions only.
