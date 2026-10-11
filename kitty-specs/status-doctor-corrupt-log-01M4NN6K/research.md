# Discovery and research: status doctor corrupt log

Audience: software-engineer and automation-agent. Updated: 2026-10-11.

## Confirmed intent and scope

Operator approved “start work. only open a pr do not merge. make sure to review thoroughly” after #5924 and issue-5924-status-doctor-corrupt-log were presented. No further interview is necessary for this small defect. #5924 is assigned to Ivan-Melck and claimed with a mission comment (verified by the parent operator). See #5304 for context only, not work owed here. One bounded WP; no product architecture work.

## Evidence register

- E1: Debugger Debbie investigation, session-local subagent output (not retained) (2026-10-11). Profile/research context resolved with checkout CLI rc7. `git rev-parse HEAD origin/main` and `git ls-remote origin refs/heads/main` all gave `063fc81808996bd66db2ee89c79b6b390ea30947` before mission creation. Existing `run_doctor` in a TemporaryDirectory with `{not json\n`: absent snapshot returned healthy=True, has_errors=False, findings=[]; present `{"work_packages": {}}` raised StoreError from drift replay, invalid JSON on line 1. Both paths preserved bytes. This is prior executed evidence, not a new planner test run.
- E2: Planner Priti scope investigation, session-local subagent output (not retained). Full issue/comments/native links read: #5924 OPEN P1, parent #3893, no blocking links. See #5304: OPEN P3 sibling, not prerequisite. PR #5901 deferred #5924; PR #5305 fixed a dependency (see #4919), not the sibling (see #5304). No directly overlapping open fix found. PR #5953 overlaps store/emit identity; PR #6038 overlaps status exports/merge, so avoid unnecessary store changes.
- E3: Current source inspected: `src/specify_cli/status/doctor.py` loads snapshot first, suppresses event-read/reduction errors in fallback, gates drift replay on snapshot, and suppresses reconciliation read errors. `src/specify_cli/status/store.py` is canonical strict mixed-stream reader. `AGENTS.md` and `.kittify/charter/charter.md` read completely. Local `.venv/bin/spec-kitty --version` is 4.0.0rc7; branch contract resolves current/base/target to issue-5924-status-doctor-corrupt-log, topology single_branch.

## Decisions and rationale

1. D1: Log unreadability must yield an ERROR regardless of snapshot. Snapshot state cannot establish authoritative-log health (E1/E3).
2. D2: Retain canonical reader authority; no doctor-local JSON parser or shared cross-doctor abstraction. Only if canonical schema/encoding errors lack truthful record location may store.py receive a narrow location-preserving change (E2/E3).
3. D3: Corruption is not an empty log. Avoid dependent drift/reconciliation/backfill advice when history is unreadable; independent non-log checks may still run.
4. D4: Read-only preservation is part of acceptance. Recovery says preserve evidence, restore trusted authoritative history or fix access, then rerun. Never advise blind deletion or automatic repair.
5. D5: Tests first: commit failing acceptance tests through existing run_doctor/CLI before any production fix; regression markers only transitional and removed when fixed. Verify absent/present snapshot halves independently and same-fixture repaired positive controls.
6. D6: Smallest viable surface is doctor.py and tests/status/test_doctor.py, optionally a focused status test file; no architectural intervention, reducer changes, decision-doctor fix, version or dependency changes. Opening campsite review may conclude no enabler is necessary; any tidy work is distinct and behavior-preserving.

## Risk and validation inventory

Invalid JSON; non-object rows; schema failures; UTF-8 decode failure; file I/O failure. Exercise each with snapshots absent/present. Use physical 1-based lines with preceding blank rows where available; never derive file-I/O lines or JSON inner-document lines as JSONL record lines. Valid mixed lifecycle/status/annotation records must remain accepted. Missing/empty/blank-only logs retain current behavior. Existing materialization drift and WP reconciliation remain covered. CLI text/JSON: exit 1, healthy false, diagnostic path/reason and safe guidance, no traceback. Assert exact bytes and absent-file preservation.

## Open questions

No stakeholder decision remains. Parent synthesis during planning verified `store.read_events` delegates the annotation-aware canonical parser and already catches JSON/non-object/schema/unknown-kind failures with correct physical line numbers including blank rows. Ordinary parse locations need no store edit; the separately witnessed annotation AttributeError normalization is approved below in E6/D8. Strict read independent of snapshot; exactly StoreError/OSError/UnicodeError translated into an actionable Finding; suppress log-dependent initialization/backfill/drift/membership guidance on failure, while independent issue-matrix/sparse/frontmatter checks continue. Exact finding category/message is implementer-local, not a new public abstraction. Independent reviewer must verify final diff and red-to-green history.

## Phase 0/1 planning evidence extension

- E4: Parent baseline report: tests/status/test_doctor.py 55 passed; make test-fast 2501 passed, 5 skipped, one environment stale-local-path failure from retired ignored dashboard __pycache__; environment report https://github.com/spec-kitty/spec-kitty/issues/6050. Parent removed only verified generated pyc/empty retired dirs, then named test_no_retired_subsystems.py 12 passed. No code edits. Formatter baseline 3623 files green and strict mypy doctor.py green. Planner did not duplicate these tests.
- E5: Canonical helpers resolved/scaffolded plan and accepted substantive plan; no new architecture, dependency or stakeholder question. Runtime issuance timeout persisted plan before prompt output; query confirmed issued plan and completed discovery/specify. Canonical source prompt plus setup-plan executed that issued work without state edits or replaying success.
- Decision D7 (initial, superseded by D8 for annotations): Narrow implementation to doctor.py plus tests; required ordinary parse locations already have canonical authority.
- E6/D8: Parent and preimplementation reviewer dd4f44a2 subsequently found check_reviewer_self_approval also reads status.events.jsonl, so it must skip on failed canonical read to prevent UTF-8 escape. Parent witnessed valid kind=annotation envelope with delta=[] raising AttributeError (`list` lacks `get`) from canonical read_events, not StoreError. Approved fold: add AttributeError to existing exception tuple only around InnerStateChanged.from_dict, preserving physical-line StoreError. Add direct tests/status/test_store.py and doctor malformed delta/subtasks cases. This is directly #5924 corruption diagnosis; no broad catches/model refactor or cross-doctor work. Note PR #5953 overlap when store.py is touched. This supersedes the earlier no-store-change conclusion.

