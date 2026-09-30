---
title: 'Issue #2007 — Debugger Debbie repro/triage on CURRENT HEAD'
description: "Debugger Debbie's read-only repro/triage of #2007 on the current HEAD: per-row static root-cause citations against the live tree."
doc_status: deprecated
updated: '2026-06-16'
---
# Issue #2007 — Debugger Debbie repro/triage on CURRENT HEAD

**Branch:** `feat/naming-rider-3-2-1` (HEAD `d17d5f0ee` ≈ upstream/main + naming-rider docs/scope)
**Method:** Static root-cause triage (read-only) against the live tree. Each row cites the
exact `file:line` that is the root cause (still broken) or the fix (already closed).
**Status legend:** REPRODUCES = still broken on HEAD · PARTIAL = some paths fixed, gaps remain ·
ALREADY-FIXED = cannot reproduce on HEAD · NEEDS-LIVE-REPRO = not statically determinable.

## Triage table

| # | Bug (short) | Status on HEAD | Root-cause / fix `file:line` | Severity | Effort | Note |
|---|-------------|----------------|------------------------------|----------|--------|------|
| 1 | `doctrine list`/`show` command drift | **REPRODUCES** | Phantom in `src/doctrine/skills/spec-kitty-charter-doctrine/SKILL.md:113-120,348,439-441`; registered `doctrine` group has NO `list`/`show` (`src/specify_cli/cli/commands/doctrine.py:86,190,532,687` + subgroups `pack`/`org`/`mission-type` only; `mission-type list` at `:952`) | P1 | M | Shipped skill instructs nonexistent surface; agents fabricate doctrine IDs. Needs snippet→Typer CI guard (the structural class fix). |
| 2 | Charter stale/status loop; `entity_pages` DRG warning; status side-effects | **PARTIAL** | Side-effect STILL present: `_collect_charter_sync_status` calls `GlossaryEntityPageRenderer(repo_root).generate_all()` AND mutating `ensure_charter_bundle_fresh(repo_root)` inside a read-only status (`src/specify_cli/cli/commands/charter/_status_collectors.py:36,38-42`). `last_sync` reads raw YAML `timestamp_utc` (`:86`) — JSON-datetime hazard not guarded here. | P1 | M | Status is not side-effect-free; "stale/noop" + "merged DRG not found" originate here. Hash-unification (sync vs status) unverified — left as gap. |
| 3 | Specify `NO_BRIEF`/`NO_TICKET` bootstrap ambiguity | **NEEDS-LIVE-REPRO** | No `NO_BRIEF`/`NO_TICKET` typed state in `src/specify_cli/` — prompt-side string only. | P2 | S | UX/typed-state improvement, not a hard code defect. Acceptable-fallback per issue. |
| 4 | `setup-plan` requires `--mission` though prompt/docs say no-flag | **REPRODUCES** | `_find_feature_directory` hard-requires the handle: `raw_handle` None → `raise ActionContextError("FEATURE_CONTEXT_UNRESOLVED", "--mission <slug> is required")` (`src/specify_cli/cli/commands/agent/mission.py:1248-1250`). NO exact-one auto-select. setup-plan calls it at `:2053-2057`. | P0 | M | I hit this THIS SESSION. Confirmed real on HEAD. Either auto-select on exactly-one or make every prompt/doc require `--mission`. |
| 5 | `agent context resolve` requires undocumented `--action` | **REPRODUCES** | Command requires `--action` validated vs `ACTION_NAMES` (`src/specify_cli/cli/commands/agent/context.py:99-104,123-126`); plan prompt advertises it WITHOUT `--action`: `src/doctrine/missions/mission-steps/software-dev/plan/prompt.md:267`. (The 6 other doctrine prompts DO include `--action`.) | P1 | S | Single prompt-line fix + snippet CI guard. Plan prompt is the only drift site. |
| 6 | Submodule/`.git`-file root misresolution → `SPEC_KITTY_REPO_NOT_INITIALIZED` | **ALREADY-FIXED** | `_is_worktree_gitdir` only follows `.git/worktrees/<name>` topology; submodule `.git` (`.git/modules/<mod>`) fails it and falls through to `.kittify` boundary match (`src/specify_cli/core/paths.py:15-28,102-118,120-131`). | — | — | Closed by #1944/#1965 (recent HEAD commit). Do NOT re-scope. |
| 7 | `spec_committed:false` while committed — wrong branch authority | **ALREADY-FIXED** | setup-plan uses ref-aware overload: `is_committed(spec_file, repo_root, placement=_spec_placement)` with `_resolve_planning_placement(repo_root, mission_slug)` (`src/specify_cli/cli/commands/agent/mission.py:2107-2114`; resolver at `:731`). FR-003 / #1884. | — | — | I observed auto-commit-not-firing THIS SESSION — but the spec_committed *check authority* is fixed on HEAD. Residual symptom likely the auto-commit trigger, not this gate. NEEDS-LIVE-REPRO if symptom persists. |
| 8 | `decision open` rejects valid mission handle (`path would escape kitty-specs/`) | **REPRODUCES** | `resolve_feature_dir_for_mission` returns the coord-aware feature_dir via `resolve_action_context` (`src/specify_cli/missions/feature_dir_resolver.py:50-67`); `cmd_open`'s helper then rejects any path not under primary `kitty-specs/`: `if not str(resolved).startswith(str(base)+"/") ... raise "Mission path would escape kitty-specs/"` (`src/specify_cli/cli/commands/decision.py:103-109`). Coord-worktree paths fail this. | P0 | M | Validate identity BEFORE path check; allow sanctioned `.worktrees/*-coord/kitty-specs` surfaces; keep raw-path traversal rejection. |
| 9 | Raw `python -c "from specify_cli.core.templates import ..."` fails | **ALREADY-FIXED** (in SOURCE) | No such import snippet anywhere in `src/doctrine/` or `docs/` (only the engineering-notes describe it). Witnessed failure was operator out-of-venv shell, not a prompt. | P2 | S | Not reproducible from prompts on HEAD. Residual = prompt-hygiene guard wanted (keep prompts on CLI surfaces); not a live drift. |
| 10 | `finalize-tasks --validate-only` exit 1 on zero-match globs | **ALREADY-FIXED** | `validate.py` splits hard errors (literal-path zero-match) from soft warnings (glob zero-match) via `_path_is_glob_pattern` (`src/specify_cli/ownership/validation.py:50,57-64`); finalize routes glob zero-match → warning, literal zero-match → error with `create_intent` remediation, `create_intent` threaded + in JSON (`src/specify_cli/cli/commands/agent/mission.py:3344-3366,3347-3348`). | — | — | All fix directions implemented (glob warns, create_intent diagnostics in JSON). Do NOT re-scope the glob-vs-error semantics. Note: distinct from #1888 (phantom-path existence). |
| 11 | `finalize-tasks` reads planning artifacts from wrong surface | **ALREADY-FIXED** (read-path) | finalize-tasks routes through `_find_feature_directory` → `resolve_mission_read_path` (coord→primary priority, fail-closed) (`src/specify_cli/cli/commands/agent/mission.py:2752-2756,1255-1261`; resolver `src/specify_cli/missions/_read_path_resolver.py:137-175,226+`). | — | — | I worried about this THIS SESSION; on HEAD the read uses the single typed resolver, not a coord-hardcoded path. The `meta.json not found` symptom was the shipped-3.2.0 finalizer. NEEDS-LIVE-REPRO only if symptom recurs. |
| 12 | Explicit `--mission` error flattened into generic "pass --mission" | **REPRODUCES** | When `--mission` IS set but resolution fails, both setup-plan (`:2058-2068`) and finalize-tasks (`:2757-2772`) call `_build_setup_plan_detection_error(...)`, which unconditionally overwrites `error` with the candidate-count message and never branches on `mission_flag` being present (`src/specify_cli/cli/commands/agent/mission.py:1328-1336`). Original error code + checked paths lost. | P1 | S | When `mission_flag` set, preserve underlying `FEATURE_CONTEXT_UNRESOLVED`/checked paths; candidate-count remediation only when selector missing/ambiguous. |
| 13 | Broken coord-worktree recovery → phantom `agent worktree repair` | **REPRODUCES** | `doctor.py` emits ``Run `spec-kitty agent worktree repair --mission ...` `` at `src/specify_cli/cli/commands/doctor.py:3082,3106,3199,3215,3235` — but NO such command is registered (no `worktree` subgroup under `agent`). Real command is `spec-kitty doctor workspaces --fix` (`doctor.py:1024-1043`). | P1 | M | Existing ticket **#1890**. Repoint all 5 hints to `doctor workspaces --fix` (or register a real repair alias); never instruct manual recursive deletion. |
| 14 | `STATUS_READ_PATH_NOT_FOUND` for valid mission; no primary fallback | **REPRODUCES (by design)** | Fail-closed is intentional: coord materialized + primary declares `coordination_branch` + coord dir absent → return None → `StatusReadPathNotFound` (`src/specify_cli/missions/_read_path_resolver.py:166-175,60-86`; #1718). | P1 | M | Keep fail-closed but add a TYPED repair/remediation path and ensure every caller preserves the code (see #15). Symptom of read-path/coord-topology class (zone of #1832/#1716/#1619). |
| 15 | `spec-kitty next` hides real failure → `MISSION_NOT_FOUND` | **REPRODUCES** | `query_current_state` collapses `ActionContextError` (which wraps `STATUS_READ_PATH_NOT_FOUND`/`FEATURE_CONTEXT_UNRESOLVED`) into `MissionNotFoundError(mission_slug)` (`src/runtime/next/runtime_bridge.py:3128-3134`). next_cmd then emits `MISSION_NOT_FOUND` + `mission list` remediation (`src/specify_cli/cli/commands/next_cmd.py:469-473`). Checked paths + typed code discarded. | P0 | M | Preserve `STATUS_READ_PATH_NOT_FOUND` / `warnings.charter_preflight` + checked paths through JSON; `MISSION_NOT_FOUND` only for true resolver miss. Partial scaffolding exists (`QueryModeValidationError` path at `next_cmd.py:474-491`) but the read-path miss takes the wrong branch. |
| 16 | `implement` surface mismatch — `--json` on internal, rejected by `agent action implement` | **REPRODUCES** | Canonical `agent action implement` has NO `--json` option (`src/specify_cli/cli/commands/agent/workflow.py:1139-1162`); internal top-level `implement` DOES (`--json`, `src/specify_cli/cli/commands/implement.py:896`) and self-documents as internal (`:918-922`) yet is registered plainly, not hidden (`src/specify_cli/cli/commands/__init__.py:208`). | P1 | M | Existing ticket **#1891** (names this exact residual). Add `--json` to `agent action implement`/`review` OR document text-only + hide top-level `implement`. |

## Counts

- **REPRODUCES (still broken):** 8 → bugs **1, 4, 5, 8, 12, 13, 14, 15** (#16 also reproduces but is a known/ticketed residual → counted below)
- **REPRODUCES (known/ticketed residual):** 1 → **16** (#1891). Total reproducing = **9**.
- **PARTIAL:** 1 → bug **2**.
- **ALREADY-FIXED:** 4 → bugs **6, 7, 9, 10** (and **11** read-path is fixed; classed already-fixed → 5 if counting #11). Treat 6/7/9/10/11 as DO-NOT-RE-SCOPE on the cited surfaces.
- **NEEDS-LIVE-REPRO:** 1 → bug **3** (typed-state UX). (#7 and #11 carry a residual NEEDS-LIVE-REPRO caveat on the *symptom*, but the cited authority is fixed.)

## Three highest-severity STILL-REAL bugs (P0)

1. **#15 — `next` reclassifies read-path miss as `MISSION_NOT_FOUND`.**
   `src/runtime/next/runtime_bridge.py:3128-3134` collapses `ActionContextError` →
   `MissionNotFoundError`, swallowing `STATUS_READ_PATH_NOT_FOUND` + checked paths;
   surfaced at `src/specify_cli/cli/commands/next_cmd.py:469-473`. Highest blast radius —
   `next` is the primary agent entrypoint and it lies about the failure.
2. **#8 — `decision open` rejects valid coord-aware mission handles.**
   `src/specify_cli/cli/commands/decision.py:103-109` validates a coord-worktree path
   against primary `kitty-specs/` and raises "Mission path would escape kitty-specs/".
   Blocks decision-point opening for any mission in coord topology.
3. **#4 — `setup-plan` (and all `agent mission` callers) hard-require `--mission`.**
   `src/specify_cli/cli/commands/agent/mission.py:1248-1250` — no exact-one auto-select,
   contradicting prompts/docs. Blocks the plan-phase bootstrap I hit this session.

## Already-fixed — do NOT re-scope these surfaces

- **#6** submodule root detection — fixed (`core/paths.py:15-28`, #1944/#1965).
- **#7** spec_committed authority — fixed (`agent/mission.py:2107-2114`, #1884). *Symptom caveat: the auto-commit-not-firing I observed is a separate trigger, not this gate.*
- **#9** `specify_cli.core.templates` import — not present in any prompt/doc; only a guard-hardening residual remains.
- **#10** finalize zero-match glob warn-vs-error + `create_intent` diagnostics — fully implemented (`ownership/validation.py:57-64`, `agent/mission.py:3344-3366`). Distinct from #1888.
- **#11** finalize-tasks read surface — now routes through the single typed `resolve_mission_read_path` (`agent/mission.py:2752-2756`, `_read_path_resolver.py`). Coord-hardcoded read is gone.

## Structural convergence (Debbie verdict)

The 9 reproducing bugs collapse into **two structural classes**, exactly as the epic's
architectural diagnosis states:

- **Command-contract drift (1, 5, 13, 16, +9-guard):** prompts/skills/docs/hint-strings name
  CLI surfaces/flags that do not exist on the registered Typer tree. ONE fix = a
  snippet-vs-Typer CI guard plus the handful of literal repoints. Cheap, high-leverage.
- **Mission read-path / error-fidelity (4, 8, 12, 14, 15, +2 side-effect):** callers either
  validate the resolved (coord-aware) path against the wrong primary base (#8), discard the
  typed read-path error (#12, #15), or never auto-select the single mission (#4). The single
  typed resolver `resolve_mission_read_path` ALREADY exists and is correct (#6/#7/#10/#11 prove
  adoption works) — the remaining bugs are **non-adoption / reclassification at the call-site
  seam**, not a missing resolver. Fix = make every caller (`next`, `decision open`, `setup-plan`,
  the error-builder) consume the resolver's typed code verbatim instead of flattening it.
