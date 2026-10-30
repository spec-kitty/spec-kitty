# Discovery & Research — doctor decisions: tolerated duplicate openings (#6764)

Mission: `doctor-decisions-duplicate-openings-01M66YMR`
Grounded on `main` @ `512567eee7` (2026-10-30). Issue: spec-kitty/spec-kitty#6764.

## D-1 The issue still reproduces on current main

Evidence:

- `grep -rn "duplicate_openings\|duplicate_openings_tolerated" src/` → no match. The
  finding does not exist in any form.
- `src/specify_cli/cli/commands/_decisions_doctor.py` — `DecisionsReconciliationReport`
  carries `missing_from_index`, `orphaned_in_index`, `lossy_attribution`,
  `malformed_folds`, `status_mismatch`, `findings` — nothing about duplicate openings.
  `_emit_json` emits those same keys plus `remedy`. `_emit_human` prints one line per
  non-empty condition. Neither mentions duplicates.
- `src/specify_cli/decisions/index_fold.py::_select_opened_event` (#4848) accepts
  openings whose payloads are equal after removing `recorded_at`, folding the earliest
  by `(payload.recorded_at, event_id)`. The acceptance is silent: nothing records that
  more than one opening was present.
- `tests/decisions/test_decisions_reconciler.py::test_doctor_and_repair_accept_identical_duplicate_openings`
  (added by PR #6762) already proves the current behaviour end-to-end: doctor exits 0,
  `malformed_folds == []`, `--repair` rebuilds the index and never rewrites the log. It
  asserts nothing about a duplicate finding, because none exists.

So: the read side tolerates the rows (correct), and the doctor is silent about them
(the gap). Reproduced.

## D-2 Not superseded

- PR #6762 (`[#4848] One opening per decision; duplicated decision logs read again`) is
  MERGED into `main` (2026-10-29T07:04:43Z). It fixed the write side and the fold; it did
  not add the report.
- `docs/changelog/CHANGELOG.md:120` records #4848 and says nothing about a duplicate
  finding.
- `kitty-specs/decision-log-integrity-01M5ZAW0/research.md` R-7 records the pre-PR squad
  finding verbatim: "Doctor silently tolerates identical duplicates (no informational
  finding) | Deferred: optional; no reader currently needs it." #6764 is the deferred
  follow-up, filed by the mission owner.
- No ADR covers doctor findings on duplicate openings. The relevant prior art is #4919
  (`malformed_folds` / `status_mismatch` reported on the read-only diagnose path), and
  #5023/WP17 (`findings` codes `DECISION_LOG_FORKED` /
  `DECISION_LEDGER_ONLY_ON_COORDINATION`) — both additive JSON keys with the same shape.

Conclusion: not resolved, not superseded, squarely in scope.

## D-3 Where the duplicate predicate belongs (single authority)

`_select_opened_event` already owns the rule "several openings are tolerable iff their
payloads are equal apart from `recorded_at`", keyed on the module-private
`_opened_identity()` and `_OPENED_VOLATILE_FIELD`. The doctor must not re-implement
`{k: v for k, v in payload.items() if k != "recorded_at"}` — that is exactly the
"second reducer" the module docstring forbids ("Single fold, no second reducer").

Decision: add one small public helper to `specify_cli/decisions/index_fold.py` that
answers "how many openings does this group hold beyond the first tolerated one", built on
the same `_opened_identity()` the fold uses, and export it. The doctor imports it on the
per-decision loop it already runs (`_fold_diagnostics`), so:

- no extra read of `status.events.jsonl` (NFR-001),
- no extra fold pass (the fold already materialises the same envelope list),
- a differing-payload duplicate still raises `FoldError` inside `fold_events` first, so it
  can never be reported as an informational duplicate (FR-005 / SC-003).

## D-4 Reporting shape (consistency with existing findings)

#4919 established the shape the issue asks for, and the mission reuses it rather than
inventing a new one:

| Surface | Existing (#4919) | New |
| --- | --- | --- |
| report dataclass | `malformed_folds: list[str]`, `status_mismatch: list[dict]` | `duplicate_openings_tolerated: list[str]` |
| human line | `_emit_malformed_fold_warning`, `_emit_status_mismatch_warning` | `_emit_duplicate_openings_notice` |
| `--json` | always-present keys with `[]` defaults | `duplicate_openings_tolerated`, always present, `[]` default |
| `clean` | computed from the error conditions only | unchanged — duplicates are NOT in `clean` |
| exit code | diagnose always 0 | unchanged |
| `--repair` | exits 1 only on malformed/forked | unchanged |

Naming: the issue proposes `duplicate_openings_tolerated`; the field/list names the
decision ids and the human line says `informational` explicitly, so a reader cannot
mistake it for an error (typer colour: not red).

## D-5 Blast radius surveyed

Files the change touches:

- `src/specify_cli/decisions/index_fold.py` — one exported helper plus its `__all__`
  entry. No behaviour change to `fold_events`.
- `src/specify_cli/cli/commands/_decisions_doctor.py` — one report field, one collector
  call in `_fold_diagnostics`, one human emit, one JSON key, one docstring paragraph.
- `tests/decisions/test_decisions_reconciler.py` — red-first tests beside the existing
  #4848 test.
- `docs/api/cli-commands.md` — the `doctor decisions` section documents the reported
  fields.
- `docs/changelog/CHANGELOG.md` — `[Unreleased]` entry.

Other callers of `_select_opened_event`: only `_fold_events`. Other consumers of
`DecisionsReconciliationReport`: the doctor command, plus
`tests/status/test_authoritative_non_lane_registry_4897.py` and
`tests/decisions/test_decision_fork_detector.py`, which drive `_diagnose` directly — a
new field with a `default_factory` default keeps them working. There is no second
consumer that enumerates the JSON keys except
`tests/architectural/test_json_contract_enumeration.py`, which enumerates commands and
error arms, not report keys.

## D-6 Open questions resolved

- **Q: should the finding be a `findings` code (like `DECISION_LOG_FORKED`) instead of its
  own field?** No. `findings` codes are non-clean conditions (`clean` includes
  `not self.findings`), so a code there would flip `clean: false` and violate FR-003.
- **Q: does anything gate on the exact `--json` key set?** Checked
  `tests/architectural/test_json_contract_enumeration.py` (command/error-arm inventory)
  and `tests/specify_cli/cli/commands/test_doctor_cli_surface_golden.py` (command
  surface, not payload keys). The new key is additive, the same way #4919's keys were.
- **Q: does `doctor decisions` appear in a docs index that must be regenerated?** The doc
  edit is to an existing page (`docs/api/cli-commands.md`), so no index regeneration is
  required; `check_docs_freshness --ci` is still run at wrap-up.
