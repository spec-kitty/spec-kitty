# Implementation Plan: Mission walkers share one residue rule

**Branch**: `issue-5875-mission-walker-is-mission-dir` | **Date**: 2026-10-27 | **Spec**: [spec.md](spec.md)
**Input**: Mission specification from `kitty-specs/mission-walker-residue-rule-01M5ZC0X/spec.md`

All planning questions are answered. See `research.md` §4 (D1–D4) and the four resolved Decision Moments.

## Summary

Add one read-side predicate in `mission_resolver.py`, `is_selectable_mission_dir`: a `meta.json` exists on disk **and** `is_mission_dir` accepts the folder. Selection (`list_missions_for_selection`) and the agent-side candidates (`_list_feature_spec_candidates`) filter through it. The doctor walkers (`identity_audit.audit_repo`, `find_duplicate_prefixes`, `_mission_type_audit.audit_mission_types`) get one shared tidy-first walk helper. On top of that helper, `doctor identity` classifies rejected children as a new `residue` state, with a remedy, and `doctor mission-type` skips them. A parity test pins selection, the two audits and the agent candidates to one answer.

## Technical Context

**Language/Version**: Python 3.11+
**Primary Dependencies**: none new. Reuses `is_mission_dir`, `tracked_mission_paths`, `probe_tracked_mission_paths` and `_carries_identity` (`mission_resolver.py`).
**Storage**: files (`kitty-specs/<slug>/meta.json`) and the git index (one batch `git ls-files`)
**Testing**: pytest, red-first, real `git init` fixtures (as in `tests/context/test_is_mission_dir.py`)
**Target Platform**: CLI (Linux, macOS, Windows)
**Project Type**: single
**Performance Goals**: NFR-001 (no git call when every child has an identity; at most one batch probe per walk) and NFR-002 (200 Missions in under 3 s)
**Constraints**: C-001 to C-005; complexity at or below 15; no new suppressions
**Scale/Scope**: about 5 source files, plus tests, a changelog entry and doc touch-ups

### Predicate design

```python
def is_selectable_mission_dir(path, *, repo_root, tracked=_UNSET) -> bool:
    """Read-side Mission test (#5875): meta.json on disk AND is_mission_dir."""
    if not (path / "meta.json").is_file():
        return False                     # spec.md-only, or meta deleted on disk -> residue
    if _carries_identity(path):
        return True                      # common case: no git call (NFR-001)
    if isinstance(tracked, _Unset):
        tracked = probe_tracked_mission_paths(repo_root)
    if tracked is None:
        return True                      # non-git / unusable git: existence fallback (meta exists)
    return is_mission_dir(path, repo_root=repo_root, tracked=tracked)
```

- Walkers compute `tracked` **lazily, once per walk**. They probe only when the first child without an identity turns up. A small per-walk memo (a closure, or a `_LazyTracked` holder) keeps every walker at no more than one probe.
- Selection and mission-type use `probe_tracked_mission_paths` (hardened: degrades to `None` with one warning). `doctor identity` is a read-only reporter. It passes `tracked_mission_paths` results, so a broken index raises, matching the audit engine's posture (`probe_tracked_mission_paths` docstring).
- `tracked is None` takes the existence fallback. For a nested untracked project or a non-git root this matches `is_mission_dir`'s own fallback, because `meta.json` exists.

### doctor identity `residue` state

- `IdentityStateLabel` gains `"residue"`. `classify_mission` (the per-directory meta classifier, also used by `audit/identity_adapter.py`) is **unchanged** (C-004). Walk-level classification is a new `_classify_walk_entry(entry, is_selectable)`: it returns a residue `IdentityState(state="residue", error=None)` when the predicate rejects the entry, and `classify_mission(entry)` otherwise.
- `summarize` zero-fills `residue` in `counts` and adds `residue_paths`.
- `find_duplicate_prefixes` and `find_ambiguous_selectors` drop residue (FR-005). `find_ambiguous_selectors` takes `states`, so filter there. `find_duplicate_prefixes` walks again, so it goes through the same helper and predicate.
- `_scope_to_mission` (`--mission <slug>`): the filtered list already carries residue. The direct-classify fallback path (a placement-seam dir not in the walk) applies the same predicate.
- Renderer: the summary table gains the `residue` row (style `[yellow]`). A "Residue folders (not Missions; selection does not list them)" section prints each path and then the one remedy (module constant `RESIDUE_REMEDY`, FR-004). JSON: `summary.residue` and a top-level `"residue_remedy"` string, present only when residue exists. `--fail-on` help lists `residue`.
- Docstrings: the module header's "Four-state classifier" becomes four Mission states plus `residue` for non-Missions. NFR-002's "no subprocesses" becomes "at most one batch `git ls-files`".

### Remedy text (FR-004, one constant)

> Not a Mission: no meta.json, or an untracked meta.json without a mission_id, so Mission selection does not list it. If it is leftover residue, delete the folder. If it is a real Mission, restore its meta.json from git history (`git log --diff-filter=D -- <path>/meta.json`, then `git checkout <sha>^ -- <path>/meta.json`), or re-create it with `spec-kitty agent mission create` and move its spec.md into the new folder.

It stays separate from `RESIDUE_NOTICE` (C-002). That notice is the write-seam text, and the regex in `residue_notice_path` depends on its exact wording.

## Charter Check

- **Single canonical authority**: one read-side predicate in `mission_resolver.py`, consumed by every read walker. The write-seam rule stays the authority for write seams, and the difference is documented (FR-008). PASS.
- **Architectural alignment**: no layer change. `status/identity_audit.py` and `cli/commands/_mission_type_audit.py` already import from `specify_cli`. The `mission_resolver` import goes `status → context`. Verify that no import cycle appears (`status` already imports `context` elsewhere: check at implement time). Walker-gate allowlist entries stay valid. PASS.
- **ATDD-first / red-first**: the parity test and the selection cases are written failing first. PASS.
- **Terminology**: Mission, never feature. PASS.
- **NO_FULL_HEAVY_SUITES_IN_MISSION**: targeted tests + blast radius + `make test-fast` only. PASS.

## Project Structure

### Documentation (this mission)

```
kitty-specs/mission-walker-residue-rule-01M5ZC0X/
├── spec.md
├── plan.md
├── research.md
├── data-model.md
├── contracts/doctor-identity-residue.md
└── tasks.md / tasks/  (by /spec-kitty.tasks)
```

### Source Code (repository root)

```
src/specify_cli/context/mission_resolver.py           # is_selectable_mission_dir; selection filter; docstrings (FR-001, FR-008)
src/specify_cli/cli/commands/agent/mission_feature_resolution.py  # _list_feature_spec_candidates (FR-002)
src/specify_cli/status/identity_audit.py              # walk helper, residue state, collisions (FR-003, FR-005)
src/specify_cli/cli/commands/_identity_audit.py       # render residue + remedy, JSON (FR-003, FR-004)
src/specify_cli/cli/commands/doctor.py                # --fail-on help + docstring (FR-003)
src/specify_cli/cli/commands/_mission_type_audit.py   # skip residue (FR-006)
tests/context/test_is_mission_dir.py                  # parity case (FR-007)
tests/specify_cli/context/test_mission_selection.py   # selection rule cases (FR-001)
tests/specify_cli/cli/commands/agent/test_mission_feature_resolution.py  # candidates (FR-002)
tests/doctor/test_identity_audit.py, tests/specify_cli/cli/commands/test_identity_audit.py  # residue state (FR-003..005)
tests/specify_cli/cli/commands/test_doctor_mission_type.py  # skip residue (FR-006)
docs/changelog/CHANGELOG.md, docs/api/cli-commands.md, docs/migrations/mission-id-canonical-identity.md  # FR-009
```

## Complexity Tracking

No charter violations.

## Implementation Concern Map

### IC-01 — Tidy-first walk helper (behaviour-preserving)

- **Purpose**: one `_iter_kitty_specs_children(repo_root)` in `status/identity_audit.py`, reused by `audit_repo`, `find_duplicate_prefixes` and `audit_mission_types`. It keeps the exact `safe_is_dir` + `OSError` fail-soft posture, so the residue filter can land in one place.
- **Relevant requirements**: prepares FR-003, FR-005, FR-006.
- **Affected surfaces**: `status/identity_audit.py`, `cli/commands/_mission_type_audit.py`.
- **Sequencing/depends-on**: none. It is its own first commit, and the existing tests stay green unchanged.
- **Risks**: the `#3194` unstattable-entry tests must keep passing. Do not change the order or the skip semantics. The walker gate checks raw `kitty-specs` walks by file, so the helper stays in an allowlisted file.

### IC-02 — Read-side predicate and selection

- **Purpose**: `is_selectable_mission_dir` plus a lazy per-walk tracked memo. `list_missions_for_selection` and `_list_feature_spec_candidates` filter through it.
- **Relevant requirements**: FR-001, FR-002, FR-008, NFR-001.
- **Affected surfaces**: `context/mission_resolver.py`, `cli/commands/agent/mission_feature_resolution.py`, and their tests. The fixtures in other tests that rely on spec.md-only folders being listed must be updated to write a `meta.json` (find them with `grep -rn 'spec.md' tests/` near `next`/`setup-plan` auto-select).
- **Sequencing/depends-on**: none (independent of IC-01).
- **Risks**: blast radius in tests that build spec.md-only fixtures for `next`, `setup-plan` or `agent tasks status`. The `backfill-wp-status` exact-slug short-circuit (`known_mission_slugs`) no longer matches a spec.md-only folder: it falls through to the canonical resolver's not-found error. That is the intended behaviour, covered by a test.

### IC-03 — doctor residue state and mission-type skip

- **Purpose**: the `residue` state, the remedy, collision exclusion and the `--fail-on` value, plus the mission-type skip, all built on IC-01's helper and IC-02's predicate.
- **Relevant requirements**: FR-003, FR-004, FR-005, FR-006, NFR-002.
- **Affected surfaces**: `status/identity_audit.py`, `cli/commands/_identity_audit.py`, `cli/commands/doctor.py`, `cli/commands/_mission_type_audit.py`.
- **Sequencing/depends-on**: IC-01, IC-02.
- **Risks**: the JSON contract (additive only: a new count key, an optional `residue_remedy`). Check `audit/identity_adapter.py` stays unaffected (it calls `classify_mission` directly). Check for an import cycle `status → context.mission_resolver`.

### IC-04 — Parity test, docs and changelog

- **Purpose**: the FR-007 parity case, the FR-009 changelog entry and the doc updates (`doctor identity` states).
- **Relevant requirements**: FR-007, FR-009.
- **Affected surfaces**: `tests/context/test_is_mission_dir.py`, `docs/changelog/CHANGELOG.md`, `docs/api/cli-commands.md`, `docs/migrations/mission-id-canonical-identity.md`.
- **Sequencing/depends-on**: IC-02, IC-03.
- **Risks**: none significant.
