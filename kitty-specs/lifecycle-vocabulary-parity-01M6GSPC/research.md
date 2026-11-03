# Discovery findings — #6876 (batch 10, agent C7)

Grounded against `origin/main` at `7c50fd38be` (2026-11-03), in
`/home/exedev/work/sk-6876`.

## D-1 (#6876's premise is stale in core): the two frozen tools no longer exist

Evidence:

- `ls contracts/` on `7c50fd38be` → `fixtures` only. `contracts/tools/`,
  `contracts/mission-status`, `contracts/mission-write`, `contracts/lint` are gone.
- `git log --diff-filter=D -1 -- 'contracts/tools/*'` →
  `a212ccdf550813eedd2517636db88cecc0a22e6a`, 2026-11-01, *"refactor!: remove core's
  copies of the events service and contracts"* (`Refs #6915`, `Refs #6117`). The
  commit body names "the D-9 freeze gate (its own exit clause)" and deletes
  `tests/architectural/test_events_import_frozen.py` (152 lines), `.github/workflows/contracts.yml`,
  and `tests/contract/test_event_mapping_check.py`, `tests/contract/test_citation_check.py`.
- ADR `docs/adr/4.x/2026-10-29-1-the-events-domain-and-its-java-services-live-in-spec-kitty-events.md`,
  D-9 "Exit": "the gate is removed together with `services/` at the cut-over. That exit
  is tracked by #6117" — executed by the commit above.
- `rg -l _FROZEN_OBJECTS` finds only kitty-specs/ADR prose, no gate.

Consequence: `python contracts/tools/event_mapping_check.py` cannot run in core, and the
two CI surfaces #6876 names (`contracts.yml` → `python-checks`, `ci-router` →
`tests (contract tools)`) no longer exist. Neither option (a)'s in-core `_FROZEN_OBJECTS`
re-pin nor option (c)'s generator has a core contract to satisfy any more.

## D-2: #6447 owns the literal deletion; this mission must not touch that file

- #6447 is OPEN, assigned, labelled `status:blocked`, `taken-by-human`; its mission
  `lifecycle-event-constants-import-6447-01M68JAS` exists in the batch-7 clone
  (`git branch issue-6447-lifecycle-event-constants`) with a parked WP and a recorded
  red-first sentinel design (mutate the package attributes to sentinels, assert the CLI
  constants follow). Its last comment: "Parked pending a frozen-path decision — see #6876."
- Therefore the boundary: #6876 records *why* it is no longer blocked and lands the piece
  the deleted tools' assertion used to provide; #6447 lands the import. Editing
  `src/specify_cli/status/lifecycle_events.py` here would collide with that branch and
  duplicate its work (C-001).

## D-3: the surviving risk is silent drift, and core has no pin for it

- `rg -n "spec_kitty_events" tests/status/*.py` finds no comparison between the twelve
  CLI constants and the package's constants; `tests/status/test_lifecycle_events.py`
  imports only the CLI names.
- Verified the package floor exports all twelve at top level with identical values:
  `spec-kitty-events 11.3.0` (`pyproject.toml`: `>=11.3.0,<12`) →
  `ProjectInitialized, MissionCreated, SpecifyStarted, SpecifyCompleted, PlanStarted,
  PlanCompleted, TasksStarted, TasksCompleted, WPCreated, ReviewerSelfApproval,
  MissionReopened, FollowUpRecorded`.
- The package's own vocabulary is wider (`CANONICAL_LIFECYCLE_EVENT_TYPES`), which is why
  the CLI's membership must stay a deliberate, asserted subset rather than being derived.

## D-4 (recorded, not changed): the frozen reader moved upstream and still points at core

- In `spec-kitty/spec-kitty-events`, `contracts/tools/event_mapping_check.py` still carries
  `DEFAULT_LIFECYCLE_SOURCE = Path("src")/"specify_cli"/"status"/"lifecycle_events.py"`
  and the same `ast`-only `read_lifecycle_types`. It only bites if that repo runs the tool
  against a core checkout; `service.yml` checks out core only for `lock-interop`, and the
  `cross-repo-harness-tests` lane checks out the e2e harness, not core's contracts.
- Cross-repo, so out of scope here (C-003). Recorded in the issue matrix so #6447's owner
  knows to re-check before relying on the import upstream.

## D-5: op records are per-record files

- ADR `docs/adr/4.x/2026-11-01-2-op-lifecycle-records-are-one-file-per-record.md`: each
  record lands in `kitty-ops/lifecycle/<ulid>.json`; the legacy `kitty-ops/lifecycle.jsonl`
  "stays tracked and readable, and is never written again". This mission's `next` runs were
  checked to write only per-record files.

## Open questions for specify/plan

- None blocking. The only judgement left is the exact shape of the strict-subset assertion
  against the package's wide set (documented in the spec as FR-003).
