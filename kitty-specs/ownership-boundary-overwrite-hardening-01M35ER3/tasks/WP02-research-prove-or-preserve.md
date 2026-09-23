---
work_package_id: WP02
title: '#4926 research prove-or-preserve (all four assets) + arch-gate extension'
dependencies:
- WP01
- WP03
requirement_refs:
- FR-002
- FR-004
- FR-005
- NFR-001
- C-002
- C-003
- C-004
planning_base_branch: issue-4931-ownership-boundary-overwrite-hardening
merge_target_branch: issue-4931-ownership-boundary-overwrite-hardening
branch_strategy: Planning artifacts for this mission were generated on issue-4931-ownership-boundary-overwrite-hardening. During /spec-kitty.implement this WP may branch from a dependency-specific base, but completed changes must merge back into issue-4931-ownership-boundary-overwrite-hardening unless the human explicitly redirects the landing branch.
base_branch: kitty/mission-ownership-boundary-overwrite-hardening-01M35ER3
base_commit: 638e27d2fe4885511dc2b5597d8b65ff42292310
created_at: '2026-09-22T22:13:48.461332+00:00'
subtasks:
- T020
- T021
- T022
- T023
- T024
history:
- at: '2026-09-22T21:15:00Z'
  actor: claude
  note: Work package authored (tasks phase).
agent_profile: python-pedro
authoritative_surface: src/specify_cli/cli/commands/research.py
create_intent:
- tests/specify_cli/cli/commands/test_research_preservation.py
execution_mode: code_change
model: claude-sonnet-5
owned_files:
- src/specify_cli/cli/commands/research.py
- tests/architectural/test_mutation_ownership_routing.py
- tests/specify_cli/cli/commands/test_research_preservation.py
role: implementer
tags: []
tracker_refs: []
---

## ⚡ Do This First: Load Agent Profile

Before reading anything else, load your assigned profile:
`/ad-hoc-profile-load python-pedro` (or `spec-kitty agent profile show python-pedro` + `spec-kitty charter context --action implement --mission ownership-boundary-overwrite-hardening-01M35ER3 --json`). Apply the resolved initialization, boundaries, directives, and tactics, then state which you applied. Force `PYTHONPATH=$(pwd)/src` for pytest; use `.venv/bin/python -m pytest` (never a bare `uv run`).

## Objective

Stop `research` fabricating 0-byte "ready" artifacts and stop `--force` truncating user-authored research assets, for ALL FOUR assets (`research.md`, `data-model.md`, `research/evidence-log.csv`, `research/source-register.csv`) (#4926); and extend the removal-routing arch gate to police `research.py`, re-pinning any `init.py` allowlist lines WP03 shifted.

**You depend on WP01 and WP03** — branch from a base that includes both. From WP01 you consume `guard_destructive_overwrite` (`from specify_cli.asset_preservation import guard_destructive_overwrite`). From WP03 you inherit the shifted `init.py` line numbers that the arch gate pins.

Read first: `../spec.md` (FR-002, FR-004, US2), `../plan.md` (Design → FR-002, FR-004), `gh issue view 4926`. Repro at `…/scratchpad/repro_4926.sh`. Current destroyer: `research.py:167-188` (`_copy_asset`) + `:199-216` (CSV loop) — `if not template: if dest.exists(): dest.unlink(); dest.touch()`.

## Subtasks

### T020 — RED-first #4926 regression (write FIRST, watch it fail)
Create `tests/specify_cli/cli/commands/test_research_preservation.py`, `@pytest.mark.regression`, docstring-pin `#4926`. Through the `research` CLI on a fresh software-dev mission, assert (RED on base):
- plain `research` creates NO 0-byte file for ANY of the four assets (and does not report them "ready").
- for EACH of the four assets in turn: write real content, `research --force`, assert NOT truncated to 0 bytes.
Include controls: no-`--force` re-run preserves (existing), and a mission type whose template DOES resolve still copies real content.

### T021 — Route the copy through `guard_destructive_overwrite`; decide before unlink
In `_copy_asset` and the CSV loop, compute `substantive = template_path is not None and template_path.is_file()` and call `guard_destructive_overwrite(dest_path, project_root, replacement_substantive=substantive, authorized=force)`. On `proceed=False`: do NOT `unlink`, do NOT `touch`, do NOT append to `created_paths` (kills the false "ready"). DELETE the `if dest_path.exists(): dest_path.unlink()` + `dest_path.touch()` fabrication at `:180-182` and `:210-212`. The skip decision is taken BEFORE any filesystem mutation (never unlink-first).

### T022 — Honest reporting when nothing resolves [P]
When no asset resolves for the mission type, the command must report a clear "no research template for mission type <X>" outcome and NOT render the green "N artifacts ready" panel as success. Distinguish "skipped, preserved existing" from "created". Do not claim false success on the default (software-dev) type.

### T023 — Extend the arch gate + re-pin init lines (and make the "routed-away" claim real)
In `tests/architectural/test_mutation_ownership_routing.py`: add `research.py` to the scanned module set (`_module_set()` / alongside `_INIT_PY`). **Important — the census does NOT auto-enforce "routed away, not allowlisted" for research**, because research routes through `guard_destructive_overwrite`, a symbol `_calls_guard_destructive_removal()` does not recognize, so research.py will NOT be in `_ROUTED_MODULES`. Without an extra guard, an implementer could satisfy the gate by ADDING research's raw `unlink` to `_ALLOWLIST` with a rationale. So you MUST add an explicit research-specific assertion: **no `src/specify_cli/cli/commands/research.py:*` key may appear in `_ALLOWLIST`** — its raw removal literals must be routed away (deleted per T021), never allowlisted. This makes FR-004/SC-005's "census refuses to allowlist" claim actually backed for the one module WP02 adds.
ALSO re-pin any `init.py` allowlist entries whose line numbers shifted due to WP03's cleanup edits (only `init.py:1596:shutil.rmtree`, the scratch sweep, shifts — 136/453/677 are above the edit region). **Verify the init.py literal-set delta is LINE-SHIFT-ONLY** — same op-kinds and same COUNT as base — not merely bumping numbers, so a genuinely-new unrouted literal cannot hide as a "line shift". Keep the gate NON-VACUOUS: concrete floor + the existing self-mutation test (`test_removing_an_allowlist_entry_reproduces_a_gate_failure`) must still hold (R4). Do NOT weaken or blanket-allowlist.

### T024 — Unit/functional tests
Round out `test_research_preservation.py` with the four-asset matrix and controls. Confirm the templated-path control (research mission type) still copies real bytes (NFR-002).

## Definition of Done

- T020 RED on base, GREEN at final commit (all four assets, both fabrication + truncation); record evidence.
- `substantive` mirrors the current successful-copy predicate so the legitimate templated path never refuses (R1).
- Arch gate scans `research.py`, stays non-vacuous, and init line-pins reconciled → `tests/architectural/test_mutation_ownership_routing.py` GREEN.
- `ruff`/`ruff format`/`mypy --strict` clean; complexity ≤15; no new suppressions.
- Targeted tests: `tests/specify_cli/cli/commands/test_research_preservation.py tests/architectural/test_mutation_ownership_routing.py` + any research CLI test module — record commands + counts.

## Reviewer guidance

Verify decide-before-unlink (no `unlink` precedes the skip decision on ANY path). Verify all four assets are covered, not just `research.md`. Verify the gate extension is non-vacuous (dropping a real allowlist entry still reproduces a failure) and that research's fabrication was ROUTED AWAY, not allowlisted. Confirm the init line-pin reconciliation matches WP03's actual line shifts.
