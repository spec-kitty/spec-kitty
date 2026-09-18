# Implementation Plan: Consistent Mission-Handle Resolution

**Branch**: `issue-4631-4682-mission-handle-resolution` | **Date**: 2026-09-18 | **Spec**: [spec.md](./spec.md)
**Input**: Feature specification from `kitty-specs/mission-handle-resolution-consistency-01M2TPWG/spec.md`

## Summary

Make CLI mission-handle behavior uniform. A nonexistent `--mission` handle must
produce one clean `mission not found: <handle>` across `plan`, `tasks`,
`research`, and `merge` (today they diverge, and `research` phantom-writes a
mission directory); and a *missing* `--mission` on the advancement command
(`next`) must trigger discovery (auto-select on 1, a legible list on many, a
setup nudge on 0) instead of a usage error.

Technical approach (**reuse-first**, per post-plan brownfield squad): the
building blocks already exist and are reused rather than re-invented. Each
misbehaving command is corrected at its **own call site** by adding an existence
gate mirroring the existing correct exemplar `materialize.py` (`Mission not
found: <handle>`), and the missing-handle discovery for `next` reuses the
existing single-mission auto-select convention. The lenient path-composition
seam (`mission_runtime/resolution.py::read_dir`) is **not** modified — its
leniency is depended on elsewhere (notably `merge --abort`).

The one genuinely shared piece is a **mission-population definition** for
discovery, enriched with `friendly_name`; and a **canonical not-found format**
`Mission not found: <handle>` applied only to the fixed commands + `next`, never
collapsing the richer identity/backfill or dossier envelopes.

## Technical Context

**Language/Version**: Python 3.11+
**Primary Dependencies**: existing CLI stack only — `typer`, `click`, `rich` (no new dependency added or upgraded)
**Storage**: filesystem — the `kitty-specs/` mission tree (no database)
**Testing**: `pytest` — existing suites `tests/next/`, `tests/research/`, `tests/merge/`, `tests/specify_cli/cli/commands/agent/`, `tests/tasks/`
**Target Platform**: Linux/macOS developer CLI
**Project Type**: single (CLI tool under `src/specify_cli/`)
**Performance Goals**: N/A — interactive CLI; all touched paths are sub-second and add at most one directory scan already performed by the correct commands
**Constraints**: no new dependency; every touched function stays ≤ complexity 15; new/changed code passes `ruff` + `mypy` with zero issues and zero suppressions; the `read_dir` placement seam contract is unchanged; `merge --abort` retains its non-raising tolerance
**Scale/Scope**: ~6 command call-sites + 1 shared helper module + focused tests; no schema, no migration, no user-data change

## Supply-Chain Security (Planning)

No dependency is added, upgraded, or removed by this mission. The
supply-chain-install-safety directive/tactic therefore has **no applicable
decision surface** here; recorded explicitly rather than left silent. No
adversarial supply-chain evidence pass is required on that basis. (The
brownfield adversarial-squad point-cut requested for this mission is a separate,
design-level challenge pass, run post-plan.)

## Constitution / Charter Check

*GATE: Must pass before Phase 0 research. Re-checked after Phase 1 design.*

| Charter item | Verdict | Note |
|--------------|---------|------|
| DIRECTIVE_024 Locality of Change | ✅ | Fixes are applied at each command's own call site; blast radius is caller-local. |
| DIRECTIVE_025 Boy Scout / in-domain debt | ✅ | Message-wording drift across the *already-correct* commands is in the mission's primary domain (handle-resolution legibility) and is folded in via the shared message constant. |
| Terminology Canon (Mission vs Feature) | ✅ | All new identifiers/messages use "mission"; no `feature*` aliases introduced. |
| Shared Package Boundary | ✅ | New helper lives in `src/specify_cli/context/` (top adapter layer); it consumes `FsMissionResolver` already in that layer. No import-direction change; `mission_runtime`/`runtime` ledgers untouched. |
| Mission Identity Model WP07 (no silent fallback) | ✅ | The core fix *removes* a silent fallback (plan/tasks dropping an unmatched handle); no new fallback is introduced. |
| ATDD-First (C-011) | ✅ | Each FR gets a red acceptance test before implementation. |
| `__all__` convention (C-007) | ⚠️ plan | Any new public symbol (the discovery helper) must be added to its module `__all__` and covered by the dead-symbol gate. Tracked as an implementation checklist item. |

No violations requiring Complexity Tracking.

## Project Structure

### Documentation (this mission)

```
kitty-specs/mission-handle-resolution-consistency-01M2TPWG/
├── plan.md              # This file
├── research.md          # Phase 0 output
├── data-model.md        # Phase 1 output
├── quickstart.md        # Phase 1 output
├── contracts/           # Phase 1 output (cli-behavior.md)
└── tasks.md             # Phase 2 output (/spec-kitty.tasks — NOT created here)
```

### Source Code (repository root)

```
src/specify_cli/
├── context/
│   └── mission_resolver.py          # + list_missions_for_selection() (spec/meta population + mid8/friendly_name enrich); hoist canonical "Mission not found: <handle>" constant  (SHARED SEAM — Concern A)
├── cli/commands/
│   ├── research.py                  # + .exists() gate before scaffold/mkdir            (Concern B, FR-001)
│   ├── merge.py                     # fresh/resume entry: not-found gate                 (Concern D, FR-004)
│   ├── next_cmd.py                  # missing-handle discovery; route not-found via seam (Concern E, FR-006..FR-010)
│   └── agent/
│       ├── mission_feature_resolution.py   # _build_setup_plan_detection_error: honor explicit handle  (Concern C, FR-002/003)
│       ├── mission_setup_plan.py           # call-site: don't overwrite clean not-found (Concern C)
│       └── mission_check_prerequisites.py  # call-site: don't overwrite clean not-found (Concern C)
└── merge/
    └── resolve.py                   # fresh/resume path signals not-found; --abort stays raw-tolerant (Concern D, FR-004/005)

tests/
├── next/                            # test_next_command_integration.py, test_query_mode_unit.py, test_runtime_bridge_unit.py
├── research/                        # test_research_workflow_integration.py  (+ phantom-write guard)
├── merge/                           # test_resolve_seam.py (+ command-level not-found / abort-tolerance)
├── tasks/                           # test_check_prerequisites_surface_agreement.py
└── specify_cli/cli/commands/agent/  # test_mission_feature_resolution.py, test_mission_setup_plan_phases.py, test_mission_check_prerequisites.py
```

**Structure Decision**: Single-project CLI. One new shared helper
(`list_missions_for_selection`, name chosen to avoid the `mission.py:809`
`discover_missions` collision) co-located with the existing resolver in
`src/specify_cli/context/mission_resolver.py` — import direction verified legal
(intra-`specify_cli`, no cycle; `mission_resolver` never imports `cli`). Chosen
over reaching into the agent layer's private `_sole_mission_slug_or_none` /
`_list_feature_spec_candidates` helpers (cross-package private import), but it
reuses the SAME population rule they use so counts agree. All other edits are
localized existence gates at the six call-sites above.

## Design Decisions (Phase 1 summary — revised after brownfield squad)

1. **Shared mission-population, not a new `discover_missions()`.** The name
   `discover_missions()` is already taken (`src/specify_cli/mission.py:809`, for
   mission *types*) — a new one collides. The enumeration substrate is
   deliberate: `FsMissionResolver.all_missions()` **silently drops missions
   lacking a `mission_id`**, so building purely on it would make `next`
   miscount legacy/un-backfilled missions and disagree with the plan/tasks
   auto-detect (which counts `spec.md`-or-`meta.json` dirs via
   `_list_feature_spec_candidates`). The shared population therefore counts any
   directory bearing `spec.md` or `meta.json`, reading `mission_id`/`mid8`/
   `friendly_name` best-effort (friendly_name → slug fallback), and surfaces a
   "N need `backfill-identity`" nudge when identity-less missions are present.
   Implementation reuses the existing walk; the new helper is a thin
   enrichment, not a fresh `kitty-specs/` scan (keeps clear of
   `tests/architectural/test_mission_resolver_walker_gate.py`). Candidate home:
   `context/mission_resolver.py` (import-direction verified legal — intra-
   `specify_cli`, no cycle); pick a non-colliding name (e.g.
   `list_missions_for_selection`).
2. **Gate at callers, exemplar = `materialize.py:94-99`.** Each command resolves
   via the lenient seam, then `.exists()`-gates and emits the canonical
   `Mission not found: <handle>` (materialize's existing form — capital M) before
   any read/write/lanes-load — never inside `read_dir`.
3. **Canonical message is a shared *format*, scoped.** Reuse the existing
   `Mission not found: <handle>` form (materialize / next's
   `_emit_mission_not_found_error`), hoisted to one source constant consumed by
   the fixed commands + `next`. **Explicitly excluded** (keep their richer
   envelopes): `MissionNotFoundError` (must keep its FR-005
   `spec-kitty migrate backfill-identity` remediation — collapsing it regresses
   the identity model), `reconcile`'s semantically-distinct "dossier not found",
   and the audit/doctor family. NFR-002/SC-003 are scoped accordingly (see spec
   revision).
4. **`next` missing-handle keeps complexity low.** `_resolve_mission_slug`
   returns the sole slug (1 mission) or **raises a typed missing-handle
   discovery signal** carrying the listing (N) / empty (0); the caller's
   existing except-chain (`next_cmd.py:195-217`) emits + exits, preserving JSON
   parity and keeping `_resolve_mission_slug` ≤ complexity 15 (do not inline
   list-building/JSON formatting into it). Nonexistent-but-present handle keeps
   its existing clean not-found (regression-guarded). Assert usage *semantics*
   (exit code / absence of required-flag message), not the version-fragile
   literal "Invalid value". Verify the charter preflight (`next_cmd.py:188`,
   before resolution at `:196`) does not pre-empt the 0-mission nudge — add one
   FR-009 test that does **not** bypass preflight.
5. **`merge` gate placement (footgun).** Add the `.exists()` gate at BOTH
   `_dispatch_resume` (`merge.py:391`, **before** the "No interrupted merge to
   resume" no-state check) **and** the fresh path (`merge.py:628`) — NOT inside
   the shared `_resolve_slug_or_exit` and NOT at `_dispatch_abort` (`:337`),
   which must stay tolerant (C-003). `merge/resolve.py` keeps returning the raw
   slug on a miss for the `--abort` recovery window. Two red-first tests: fresh
   and resume.
6. **JSON parity is scoped to existing surfaces (FR-011).** Apply to `next`, the
   plan/tasks agent commands, and materialize. **research has no `--json`**
   (human-only) and **merge's `--json` is dry-run-only** — both are out of the
   parity claim; adding new JSON surfaces is out of scope. Do not write
   research/merge JSON not-found tests that cannot pass. Keep plan/tasks'
   existing `available_missions` **string-list** shape (pinned by
   `tests/agent/test_agent_feature.py:1006,1189`); `next` renders the richer
   `slug + mid8 + friendly_name`.
7. **`__all__` discipline.** `context/mission_resolver.py` has no `__all__`
   today; if one is added it must enumerate the full existing public surface
   (`ResolvedMission`, `AmbiguousHandleError`, `MissionNotFoundError`,
   `FsMissionResolver`, `FakeMissionResolver`, `resolve_mission`) plus the new
   helper — not just the new symbol (dead-symbol gate).

## Squad Dispositions (post-plan brownfield point-cut)

Three independent lenses (reuse/prior-art, boundary/ownership `paula-patterns`,
test-strategy `reviewer-renata`). All contested findings dispositioned; none
dropped.

| Finding | Severity | Disposition |
|---------|----------|-------------|
| Message "unification everywhere" over-reaches; must exclude identity/backfill + reconcile/dossier + audit; ~40 pinned tests | blocker/major | **changed** — DD3 + spec NFR-002/FR-006/SC-003 rescoped |
| `all_missions()` drops legacy (no `mission_id`) missions → `next` miscount + divergence from plan/tasks count | major | **changed** — DD1 shared population counts spec/meta dirs; spec edge-case + FR-012 updated; legacy-mission acceptance test required |
| Canonical literal was lowercase `mission not found` — matches no existing message, reds pinned tests | blocker | **changed** — adopt existing `Mission not found: <handle>` form (capital M) |
| FR-011 JSON parity unsatisfiable for research (no `--json`) and merge (dry-run-only) | major | **changed** — FR-011 rescoped to JSON-bearing commands |
| FR-012 dict-shape collides with pinned string-list `available_missions` | major | **changed** — plan/tasks keep string list; `next` gets rich shape; unify later |
| `merge` gate would break `--abort`/`--resume` if put in shared helper / only at fresh path | major | **changed** — DD5 names the two exact call-sites |
| helper home / import direction / no cycle; `friendly_name` from meta.json; research is the only mission-scoped scaffolder; plan/tasks is a single chokepoint; NFR-001 snapshot assertable via in-process CliRunner | confirmations | **accepted** — carried into DD1/DD2 and test guidance |
| complexity risk on `_resolve_mission_slug` | minor | **changed** — DD4 raises a typed signal, listing stays in the seam |
| FR-009 nudge may be pre-empted by charter preflight; friendly_name fallback | minor | **accepted** — DD1/DD4 note the fallback + a no-bypass test |

## Complexity Tracking

*No Constitution Check violations — table intentionally empty.*

## Parallel Work Analysis / Implementation Concern Map

### Dependency Graph

```
Concern A: shared population (list_missions_for_selection) + hoisted canonical not-found constant   [FOUNDATION]
        │
        ├────────────┬───────────────┬───────────────┬───────────────┐
        ▼            ▼               ▼               ▼               ▼
Concern B        Concern C        Concern D        Concern E        Concern F
research gate    plan/tasks       merge not-found  next discovery   message
(FR-001)         truthful         + abort scope    + not-found      unification +
                 (FR-002/003)     (FR-004/005)     (FR-006..010)    regression guards
                                                                     (FR-013, NFR-002)
```

### Work Distribution

- **Sequential (must be first)**: Concern A — the shared discovery helper and
  canonical message. Every other concern imports it.
- **Parallel streams after A**: B, C, D, E are file-disjoint (research.py / the
  three agent-layer files / merge pair / next_cmd.py) and can proceed
  concurrently. F (message unification across already-correct commands +
  cross-command regression net) integrates last because it touches or asserts
  across several commands.
- **File ownership** (avoids lane conflicts): A→`context/mission_resolver.py`;
  B→`research.py`; C→`agent/mission_feature_resolution.py` + `mission_setup_plan.py` + `mission_check_prerequisites.py`;
  D→`merge/resolve.py` + `cli/commands/merge.py`; E→`next_cmd.py`;
  F→cross-command message constant adoption + `tests/` regression battery.

### Coordination Points

- **Integration test** (owned by F): one cross-command test asserting a nonexistent
  handle yields the canonical `Mission not found: <handle>` across the FIXED commands,
  and that `kitty-specs/` is unchanged after each (the NFR-001 snapshot guard, most
  important for `research`). Use in-process `typer.testing.CliRunner`, not the
  subprocess `run_cli` fixture (avoids the stale-install false-red + ~90s cost).
- **Legacy-mission test** (owned by A/E): a workspace whose sole mission lacks a
  `mission_id` — bare `next` must auto-select it (not report "no missions"), and the
  `next` count must equal the plan/tasks count. Guards the DD1 population decision.
- **FR-009 no-bypass test** (owned by E): a 0-mission `next` that does NOT monkeypatch
  the charter preflight, to confirm the no-missions nudge is actually reachable.
- **Regression guard**: the no-handle *multi-mission* `disambiguate` message for
  plan/tasks (correct in that different case) must remain (pinned by
  `test_mission_feature_resolution.py:103-120`, `test_agent_feature.py:1006,1189`);
  `merge --abort` tolerance must remain (`tests/merge/test_resolve_seam.py`); and the
  pre-existing correct-command not-found tests (`test_next_fail_closed.py:125`,
  `test_coordination_doctor.py:1385`) must stay green.
