---
title: "Follow-up mission preparation debrief — tasks.py render-seam + shim relocation"
description: "Scope, inventory, approach, and risks for the follow-up mission finishing the tasks.py degod (render seam + shim relocation), deferred from tasks-py-degod-01KWF08S."
doc_status: deprecated
updated: '2026-08-12'
---

> ⚠ **Retired 2026-08-12 (`doc_status: deprecated`).** Follow-up preparation debrief; shipped as mission `tasks-py-degod-wave2-01KWH9EQ` (PR #2308, closing #2305 / #2116). Content preserved as an audit-trail record.

# Follow-up mission preparation debrief — tasks.py render-seam + shim relocation

**Predecessor:** `tasks-py-degod-01KWF08S` (Wave 1 degod; branch `design/degod-tasks-2116`) — decomposed the `agent tasks` god-command's decision logic into pure tested cores behind injected ports, thinned all fat command bodies, byte-identical behavior. It **deferred** two goals to this follow-up (spec Deferred section + the 8/9 scoping decision).

**This follow-up's charter:** finish turning `tasks.py` into a true registration shim — unify rendering behind the Render seam (former FR-008) and relocate the accumulated orchestration out of `tasks.py` to hit the whole-file LOC ceiling (former SC-005/NFR-004 ≤1400). **Behavior-preserving (pure parity)**, same as the predecessor — the golden CLI-characterization harness is the guard.

## Why it was deferred (not a failure — a deliberate slice)

The predecessor delivered the *high-value, high-risk* work: the change-magnet **decision logic** is now in four pure, tested sibling modules (`tasks_transition_core` 574, `tasks_ports` 383, `tasks_status_view` 229, `tasks_mapping_core` 156 LOC), and every fat body is a thin orchestrator (move_task 88, map_requirements 56, status 24, mark_status 39, finalize_tasks 25 LOC). But `tasks.py` **grew 3617 → ~4547 LOC** during the rewrites: the decision logic left for the cores, while the `_do_<cmd>` orchestrators, ~50 small glue helpers, and the port-seam adapter classes accumulated *in* `tasks.py`. Hitting ≤1400 means relocating ~3150 LOC — mechanically large, orthogonal to the decision-extraction, and (unlike the cores) low-risk-*per-move*. Cramming it into the predecessor's closeout risked a sloppy 3000-LOC move; it earns its own reviewed mission.

## Scope (two work streams)

### Stream A — Render seam unification (former FR-008)

- **13 inline `json.dumps` sites** in `tasks.py` (live at predecessor time: lines 442/480/493/2035/2235/2726/2751/2765/2854/2926/3022/3264/3605 — **re-census at start**, they will have moved) → route through the `Render` port (`Render.json_envelope` / `Render.human`).
- The generic `RealRender.json_envelope` uses **compact** `json.dumps` (byte-identical to the many compact inline sites). `status` is the **one** site needing `indent=2` — the predecessor scoped a `_StatusRender(RealRender)` override for it. **Unify**: parameterize the Render seam's indent (or a `json_envelope_indented` capability) so the status override collapses into the generic seam. Byte-identity per site is the bar.
- Add an **AST-based** "0 inline `json.dumps`/aliased `dumps`" gate (a literal grep is bypassed by `from json import dumps`).

### Stream B — Shim relocation (former SC-005/NFR-004 ≤1400)

- Relocate out of `tasks.py` to sibling modules (the `mission.py`-degod per-command-module pattern is the template):
  - the `_do_<cmd>` **orchestrators** (`_do_move_task`, `_do_map_requirements`, `_do_status`, `_do_mark_status`, `_do_finalize_tasks`) + their `_mt_*`/`_mr_*`/`_st_*`/`_ms_*` **glue helpers**;
  - the **port-seam adapter classes** `_MoveTaskCoordRouter`, `_MapReqCoordRouter`, `_MarkStatusCoordRouter`, `_StatusRender` — fold these into `tasks_ports.py` (or a `tasks_command_adapters.py`), removing the "bound-to-tasks.py-module-symbols for `@patch`" trick if the tests can be re-pointed, OR preserve it deliberately.
- Leave `tasks.py` as thin `@app.command` registration wrappers delegating to the relocated orchestrators + a re-export sweep for any symbol imported elsewhere.
- Add the `tests/architectural/` **whole-file LOC gate**: `tasks.py` total ≤ (target — re-derive; ≤1400 was the predecessor's estimate — validate it against the real relocated size, or set an honest achievable ceiling with rationale). Per-body/per-helper ≤150 is already met by the predecessor.
- The 4 already-small bodies (`list_tasks`, `add_history`, `validate_workflow`, `list_dependents`) remain in `tasks.py` and count against the ceiling.

## Preconditions

- The predecessor mission (`design/degod-tasks-2116`) must be **merged first** — this follow-up bases on it. `tasks.py` = the merged WP01–WP09 state.
- `tasks.py` will be **unowned** after the predecessor (WP09 was descoped off it); this follow-up **owns `tasks.py`** end-to-end.
- The predecessor's golden harness (`test_tasks_cli_contract.py`, 42 cases) + the per-core unit tests + the WP03/WP04 timing regression tests + the WP08 non-import AST gate are all the guards — this follow-up keeps them green.

## Approach (low-risk-per-move discipline)

1. **Golden-first, always green.** Unlike the predecessor's cores, these are *pure relocations* — cut a function/class from `tasks.py`, paste into a sibling module, add an import. No logic change → golden stays byte-identical at every step. Any golden delta = a botched move, revert.
2. **One command family per WP** (the `mission.py` template): e.g. WP-move_task-relocate, WP-mapping+status-relocate, WP-coreless-relocate, then WP-render-seam, then WP-shim-finalize+LOC-gate. Each independently reviewable + golden-guarded.
3. **Preserve the `@patch` seams** (~900 tests patch `tasks.<sym>`): when moving the adapter classes / the seam-bound symbols, either re-point the patches or keep the module-level re-exports. Decide per-WP; the golden + the full suite catch breakage.
4. **Strict-mypy on src+test together** at every step (the predecessor's hard-won lesson — attr-defined on imported return types only surfaces when both are in mypy scope).

## Risks

- **Big mechanical move → merge-conflict / import-cycle risk.** Relocating adapters into `tasks_ports.py` could create an import cycle (ports ↔ command modules). Mitigate: a dedicated `tasks_command_adapters.py` rather than overloading `tasks_ports.py`.
- **The `@patch`-seam trick is load-bearing** for ~900 tests. Moving the bound symbols without re-pointing patches breaks them en masse. Handle deliberately, per-WP.
- **LOC ceiling may need re-baselining.** ≤1400 was a planning estimate. If the honest relocated `tasks.py` (registration wrappers + 4 small bodies + necessary module glue) lands higher, record the honest number + rationale rather than force an unsafe over-relocation.

## Reference

- Predecessor spec + Deferred section: `kitty-specs/tasks-py-degod-01KWF08S/spec.md`.
- Predecessor tracers: `kitty-specs/tasks-py-degod-01KWF08S/tracers/` (approach / design-decisions / tooling-friction — read `tooling-friction.md` before starting; it lists the traps).
- Template: the completed `mission.py` degod, `kitty-specs/decompose-mission-god-module-01KVXHF8/` (per-command sibling modules + shim finalization).
