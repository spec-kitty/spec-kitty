# Implementation Plan: Corrupt per-mission state files fail closed, not crash

**Branch**: `fix/4642-corrupt-state-file-guards` | **Date**: 2026-09-19 | **Spec**: [spec.md](./spec.md)
**Input**: Feature specification from `kitty-specs/corrupt-state-file-guards-01M2VZS0/spec.md`

## Summary

Stop two CLI command paths from crashing with an uncaught traceback on a corrupt per-mission state file, mirroring the already-proven `MissionMetaReadError` + `load_meta_fail_closed` precedent rather than inventing a parallel mechanism. Two seams: catch `MissionMetaReadError` at the real escape site in `next`, and wrap `decisions/store.py:load_index` into a new typed `DecisionIndexReadError` presented at the `decision.py` boundary. Reuse the canonical kernel decoder `kernel.meta_decode.decode_meta` for the JSON+UTF-8 layer. No new generic primitive (deferred hardening mission). Red-first per ADR 2026-07-17-1.

## Technical Context

**Language/Version**: Python 3.11+
**Primary Dependencies**: typer (CLI boundary), pydantic (schema validation), ruamel.yaml (unrelated here); **no new dependencies added or changed**
**Storage**: per-mission JSON files on disk (`kitty-specs/<slug>/meta.json`, `kitty-specs/<slug>/decisions/index.json`)
**Testing**: pytest; `@pytest.mark.regression` red-first entry-point tests + focused unit tests; drive real commands via typer `CliRunner`
**Target Platform**: Linux/macOS CLI (spec-kitty-cli 4.0.0rc3)
**Project Type**: single project (CLI tool)
**Performance Goals**: N/A — error-path guard only; happy-path parse result byte-identical
**Constraints**: complexity ≤ 15 on touched functions; no bare `except`; no new `# noqa`/`# type: ignore`; reuse canonical `decode_meta`; respect layer chain `kernel <- charter <- {glossary, runtime, mission_runtime} <- specify_cli`
**Scale/Scope**: 2 fix sites, 1 new error type, ~6 decision-subcommand boundary arms via one shared handler

## Constitution / Charter Check

*GATE: Must pass before Phase 0. Re-check after design.*

- **Canonical sources**: mirror `MissionMetaReadError` (`core/paths.py`) + reuse `kernel.meta_decode.decode_meta`; no improvised parallel decoder. ✅
- **Tiered rigour**: reader/boundary error handling is core-path; add focused tests for every new branch/helper (Sonar new-code gate). ✅
- **ATDD / red-first (ADR 2026-07-17-1)**: each instance lands an issue-pinned `@pytest.mark.regression` repro RED through the real command before the fix. ✅
- **Scope discipline**: no new generic `read_json_state` primitive; `wps_manifest.py` + wider audit deferred (C-003). ✅
- **Terminology**: no forbidden terms introduced. ✅

No violations → Complexity Tracking table not required.

## Project Structure

### Documentation (this mission)

```
kitty-specs/corrupt-state-file-guards-01M2VZS0/
├── plan.md              # this file
├── research.md          # Phase 0 (dossier consolidation)
├── data-model.md        # Phase 1 (error-type + corruption-class model)
├── quickstart.md        # Phase 1 (how to reproduce + verify)
└── tasks.md             # Phase 2 (/spec-kitty.tasks — NOT created here)
```

### Source Code (repository root)

```
src/specify_cli/
├── decisions/
│   ├── store.py         # FIX: load_index → _decode_index helper wrapping decode_meta(read_bytes) + ValidationError → DecisionIndexReadError
│   └── __init__.py      # export DecisionIndexReadError
├── cli/commands/
│   ├── next_cmd.py      # FIX: catch MissionMetaReadError around query-mode/_run_query_mode + decide_next; add _emit_meta_read_error
│   └── decision.py      # FIX: _handle_index_read_error + except arms on 6 subcommands
├── core/paths.py        # REFERENCE: MissionMetaReadError precedent (unchanged)
src/kernel/meta_decode.py # REUSE: decode_meta (unchanged)

tests/
├── specify_cli/next/                    # regression: next on corrupt meta.json
├── specify_cli/cli/commands/test_decision.py  # regression: decision cmds on corrupt index.json
└── specify_cli/decisions/test_store.py  # unit: load_index raises DecisionIndexReadError per fixture; missing-file still empty
```

**Structure Decision**: single-project CLI; changes confined to `src/specify_cli/{decisions,cli/commands}` with a read-only reuse of `src/kernel/meta_decode.py`. No new modules or packages.

## Implementation Concern Map (feeds /spec-kitty.tasks)

| Concern | Files | Notes | Depends on |
|---------|-------|-------|------------|
| IC-1: decisions reader fails closed | `decisions/store.py`, `decisions/__init__.py` | `_decode_index` helper + `DecisionIndexReadError` (path + fail-closed + doctor hint); reuse `decode_meta(read_bytes)`; preserve missing-file→empty branch | — |
| IC-2: decisions boundary presents typed error | `cli/commands/decision.py` | shared `_handle_index_read_error` (JSON `{code,error,details}` + doctor hint + Exit 1); except arm on verify/resolve/open/list/defer/cancel | IC-1 |
| IC-3: `next` catches corrupt-meta at real escape site | `cli/commands/next_cmd.py` | exact `except MissionMetaReadError` around `_run_query_mode`(232)/`decide_next`(252); `_emit_meta_read_error` honoring `--json`/plain; NOT the `:215` slug-resolution try | — |
| IC-4: red-first regression + unit tests | `tests/specify_cli/next/`, `.../cli/commands/test_decision.py`, `.../decisions/test_store.py` | 3 fixtures (malformed JSON, non-UTF-8, wrong-shape); assert exit 1, `result.exception` None/SystemExit, message names file, `--json` parses; RED before fix | IC-1..3 |
| IC-5: docs/changelog + deferred-mission link | `docs/changelog/CHANGELOG.md`, PR body | `[Unreleased]` entry (#4642), impact-first; file+link the deferred hardening mission | IC-1..4 |

## Parallel Work Analysis

Small mission. IC-1→IC-2 are sequential (reader before boundary); IC-3 is independent of the decisions pair; IC-4 red-first tests precede each fix; IC-5 closes out. Single lane is appropriate — no parallel fan-out needed.

```
IC-4(red, next) → IC-3(next fix) ┐
IC-4(red, decisions) → IC-1(reader) → IC-2(boundary) ┘ → IC-5(docs/changelog)
```

## Risks

- Broadening the `next` catch to `RuntimeError` would swallow unrelated owned-checkout errors — catch the exact type only.
- `read_text`→`read_bytes` switch in `load_index` must stay behavior-identical on valid UTF-8 (guarded by a happy-path unit test).
- Wrong-shape fixture for decisions must be a **dict** (`{"entries": "not-a-list"}`) so it reaches pydantic validation rather than being rejected as non-object by `decode_meta`.
- `--json` error payloads must remain valid JSON for orchestrator-api consumers.
