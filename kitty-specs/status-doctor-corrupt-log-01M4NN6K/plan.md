# Implementation Plan: Status Doctor Corrupt Log

**Branch**: `issue-5924-status-doctor-corrupt-log` | **Date**: 2026-10-11 | **Spec**: [spec.md](spec.md)  
**Input**: `kitty-specs/status-doctor-corrupt-log-01M4NN6K/spec.md`  
**Audience**: software-engineer and automation-agent.

## Summary

Deliver #5924 in one bounded WP01: authoritative log corruption/read failure must become an ERROR regardless of snapshot state, with truthful file/reason/location, safe recovery and unchanged bytes. Existing reader, CLI output shapes, supported event families and normal health checks remain authoritative. This plan sequences the supplied investigation/approved constraints; it introduces no product architecture or cross-doctor abstraction.

Engineering alignment is already confirmed by the supplied small-defect scenario and approved start: Python repository, existing status-store authority, read-only doctor, text/JSON failure, targeted red-first verification and PR only. No further technology/interview decision remains.

## Technical Context

**Language/Version**: Python 3.11+; checkout CLI `.venv/bin/spec-kitty` 4.0.0rc7
**Primary Dependencies**: Existing typer/rich CLI, Pydantic and spec_kitty_events consumed through existing status store; no additions/upgrades/removals
**Storage**: Existing `status.events.jsonl` authority and derived `status.json`; doctor performs no writes
**Testing**: Existing pytest doctor/CLI entry points; failing-first regression commit, five-class/two-snapshot matrix and controls
**Target Platform**: Existing Linux/macOS/Windows CLI; deterministic I/O error fixtures independent of chmod privileges
**Project Type**: Single existing Python CLI repository
**Performance Goals**: Preserve existing synchronous doctor behavior; no new scans, network access or benchmark effort for this bounded defect
**Constraints**: ERROR not false healthy/crash; path/reason and physical 1-based record line when available; no fabricated I/O lines; new-code coverage ≥90%; no full heavy local suite
**Scale/Scope**: One issue, one WP, doctor.py plus status tests; store.py only the approved annotation/transition decoder AttributeError tuple additions, with direct store regressions

## Charter Check

*Entry and post-plan review: pass; no new architecture/dependency decision.*

- Canonical authority: reuse store reader, no doctor-local parser. Source packs own templates when old global prompts drift.
- ATDD first: acceptance tests committed RED before any production fix; transitional regression markers removed with fix.
- Locality: candidate files doctor.py and test_doctor.py, optional focused status test; store.py and test_store.py only for witnessed annotation/transition decoder normalization. Opening campsite check is a preceding distinct step or recorded no-enabler conclusion; no unrelated cleanup.
- Evidence preservation: no repair writes or blind deletion guidance. Independent reviewer proves both snapshot halves and byte integrity.
- Mission hygiene: three canonical-helper tracer seeds; issue-matrix.json #5924 in-mission, WP01, owner Ivan-Melck recorded in evidence_ref because canonical schema has no owner column. Assignment/claim verified by parent.
- Git: current/base/mission target all issue-5924-status-doctor-corrupt-log, resolver match true, single_branch. PR to main only; NO merge/consolidate, local main changes or main push. Leave eventual approved/accepted mission pending PR integration.
- Advisory squads: not dispatched by this planner (profile prohibits agent management); no claim of independent review. Parent must supply independent aggregate/implementation review before PR handoff.
- Supply-chain controls not applicable: no dependency decision. No versions, hosted, general reducer or decision-doctor changes.

## Project Structure

### Documentation (this mission)

```text
kitty-specs/status-doctor-corrupt-log-01M4NN6K/
├── spec.md
├── checklists/requirements.md
├── plan.md
├── research.md
├── reasons-canvas.md
├── data-model.md
├── quickstart.md
├── contracts/status-doctor.md
├── issue-matrix.json
├── traces/{approach,design-decisions,tooling-friction}.md
└── tasks.md + tasks/WP01-status-doctor-log-errors.md (tasks phase)
```

### Source Code (repository root)

```text
src/specify_cli/status/doctor.py        # candidate production change
src/specify_cli/status/store.py         # narrow annotation/transition decoder AttributeError normalization
tests/status/test_store.py              # direct canonical reader regression
src/specify_cli/cli/commands/agent/status.py  # existing CLI contract, no planned production edit
tests/status/test_doctor.py             # existing doctor + CLI coverage
tests/status/test_doctor_log_errors.py  # optional focused tests; create_intent if created
```

**Structure Decision**: Keep existing status-domain ownership and CLI adapter. No new package, shared abstraction, event family or schema. Refer to [data-model.md](data-model.md) for existing contract facts only.

## Phase 0: Research Consolidation

[research.md](research.md) contains E1–E3 and D1–D6 from real prior investigation. False health and snapshot-present crash independently reproduced through `run_doctor`; no planner rerun or implementation evidence claimed. No unresolved stakeholder questions. Parent verified canonical JSON/non-object/schema/unknown-kind physical-line handling, then witnessed a valid annotation envelope with delta=[] escaping as AttributeError. Approved fold: add AttributeError only to the existing catch tuple around InnerStateChanged.from_dict, preserving StoreError record line. Add direct store and doctor malformed delta/subtasks regressions. This is #5924 corruption normalization, not model refactor; coordinate overlap with PR #5953.

Alternatives rejected: snapshot-only diagnosis (masks authority failure); doctor-local parse loop (duplicate authority); blanket exception-to-empty fallback (repeats bug); auto repair/deletion (destroys evidence); decision-doctor/shared utility expansion (outside approved issue).

## Phase 1: Existing Contracts and Implementation Sequencing

- [contracts/status-doctor.md](contracts/status-doctor.md) specifies existing public command/finding envelope plus changed failure semantics, not a new API.
- [quickstart.md](quickstart.md) gives safe temporary repro and targeted validation.
- Candidate behavior boundary: validate canonical log readability independent of snapshot presence. Translate expected canonical parse/decode/read failures into a Finding and avoid dependent misleading checks; valid logs continue through existing checks. Precise local control-flow/category choices belong to implementer, bounded by spec.
- Parent synthesis: strict canonical read occurs independently of snapshot before dependent checks. Translate exactly StoreError/OSError/UnicodeError into actionable findings, not broad Exception. Suppress ALL log-dependent checks, including initialization/backfill/drift/membership and check_reviewer_self_approval (it reads status.events.jsonl too), while continuing independent issue-matrix/sparse/frontmatter checks. Canonical parser supplies required record lines; approved store delta is only annotation/transition decoder AttributeError normalization. No guessed line values for I/O/decode when unavailable. Guard later log-dependent reads with the same expected exception types; discard partial dependent findings after failure and continue independent checks.
- Red acceptance tests precede functional production edits. Use real malformed files for parsing/encoding; inject only filesystem boundary errors when permissions are nondeterministic. Never mock run_doctor/reduce into success.
- Review verifies each independent snapshot path, safe recovery, CLI exit/output, bytes, repaired-history controls and existing drift/WP reconciliation.

## Validation and Evidence Handoff

Parent baseline (not duplicated by planner): formatter baseline 3623 files green and strict mypy doctor.py green.  `tests/status/test_doctor.py` 55 passed; `make test-fast` 2501 passed, 5 skipped, 1 stale-local-path failure from ignored retired dashboard __pycache__. Environment issue https://github.com/spec-kitty/spec-kitty/issues/6050 filed; only verified generated pyc/empty retired dirs removed. Named `tests/architectural/test_no_retired_subsystems.py` then 12 passed. No product changes. Do not call this baseline fully green or claim a post-cleanup fast-suite rerun.

WP01 targeted checks after implementation:

```bash
.venv/bin/python -m pytest tests/status/test_doctor.py tests/status/test_store.py -q
# Also run every new/changed focused status test file.
.venv/bin/python -m pytest tests/status -m '(fast or unit) and not slow and not e2e and not integration and not regression and not distribution and not live_adapter and not stress and not timing and not windows_ci and not platform_darwin' -q
make test-fast
.venv/bin/ruff check src/specify_cli/status/doctor.py tests/status/test_doctor.py
.venv/bin/ruff format --check --force-exclude src/specify_cli/status/doctor.py tests/status/test_doctor.py
.venv/bin/mypy --strict src/specify_cli/status/doctor.py src/specify_cli/status/store.py
# Include store.py, test_store.py and every new/changed focused status test file in lint/format checks.
```

Record exact commands/counts, changed-line coverage ≥90%, and strict type-check diagnostics; classify/report any pre-existing failure per charter rather than suppressing it. Existing broad typing debt is not license for blanket ignores. Review test commands against current Makefile/pyproject config. Formatting before push uses `make format-check`; terminology prose gate is the named `tests/architectural/test_no_legacy_terminology.py` when applicable. No `make test-full`, full architectural/e2e/performance sweep or duplicate concurrent tests. If store.py changes, run direct test_store.py and strict mypy/lint/format on it; no other store change.

## Risks and Mitigations

| Risk | Mitigation |
|------|------------|
| One snapshot branch still masks/crashes | Separate absent/present tests with RED evidence, final same-fixture controls |
| JSON inner-line mistaken for JSONL record | Preceding valid/blank physical lines; canonical reader location test if changed |
| Valid mixed event family rejected | Lifecycle/status/annotation control via canonical builders/fixtures |
| Corrupt history triggers backfill/materialize advice | Assert safe action and absence of misleading dependent findings |
| I/O case falsely passes as privileged user | Filesystem-boundary injected OSError, no chmod-only test |
| Scope drifts to sibling doctor/store overhaul | C-001/C-002 review; store diff only the two approved decoder tuple additions, note PR #5953 overlap |
| Runtime prompt loss on timeout | Already traced: issued plan persisted; no success replay. Use canonical source prompt plus setup-plan for issued work |

## Review Cycle 1 Amendment

Independent correctness review witnessed an otherwise valid transition with mission_slug=123 escaping as AttributeError, plus expected late-read failures in drift and reviewer-self-approval. Fold both within existing FR-001/FR-003: add AttributeError to the existing transition decoder catch, guard all dependent rereads with StoreError/OSError/UnicodeError, discard partial dependent advice on failure, and preserve independent checks. Add RED-first direct/store/doctor/CLI and late-read tests. Fold the readable ReviewerSelfApproval corruption/restoration control. Earlier annotation-only statements in the research history describe the first implementation, not the amended current constraint.

## Complexity Tracking

No charter violations requiring an exception; no additional architectural concern map is warranted for this single local defect. Tests/implementation/review sequencing remains within one WP.
