---
work_package_id: WP04
title: 'One stored activation spelling: stems (#6527 local, #6435)'
dependencies:
- WP01
requirement_refs:
- FR-011
- FR-012
- FR-013
- FR-014
- FR-015
planning_base_branch: issue-6457-activate-output-identity
merge_target_branch: issue-6457-activate-output-identity
branch_strategy: Planning artifacts for this mission were generated on issue-6457-activate-output-identity. During /spec-kitty.implement this WP may branch from a dependency-specific base, but completed changes must merge back into issue-6457-activate-output-identity unless the human explicitly redirects the landing branch.
base_branch: kitty/mission-activate-output-and-identity-01M5ZA9X
base_commit: 65ca28cf3b852224f51c7d1a342e0e03d428f10c
created_at: '2026-10-27T20:14:37.802355+00:00'
subtasks:
- T014
- T015
- T016
- T017
- T018
- T019
phase: 'Phase 2 - #6527 local slice'
history:
- at: '2026-10-27T20:10:00Z'
  actor: system
  action: 'Prompt generated via /spec-kitty.tasks (operator scope addition #6527)'
agent_profile: python-pedro
authoritative_surface: src/charter/activation/
create_intent:
- tests/charter/activation/test_stored_spelling_6527.py
execution_mode: code_change
owned_files:
- src/charter/activation/identity_index.py
- src/charter/activation/effective_set.py
- src/charter/activation/preset_application.py
- src/charter/activation/org_charter.py
- src/specify_cli/cli/commands/charter/interview.py
- tests/charter/activation/test_identity_index.py
- tests/charter/activation/test_effective_set.py
- tests/charter/activation/test_stored_spelling_6527.py
- tests/specify_cli/cli/commands/charter/test_activate_stem_writes_stem.py
- tests/specify_cli/cli/commands/test_charter_interview_promotion.py
role: implementer
tags: []
task_type: implement
tracker_refs: []
---

# Work Package Prompt: WP04 – One stored activation spelling: stems (#6527 local, #6435)

## ⚡ Do This First: Load Agent Profile

Use the `/spk-charter-profile-load` skill to load `python-pedro` (implementer, `claude`) before reading further.

## Review Feedback

*[Filled from the status event log when returned from review.]*

## Objectives & Success Criteria

Local acceptance of #6527 (operator ruling 2026-10-23, its body) plus #6435:

- FR-011: `IdentityIndex` accepts a `<kind>:<id>` URN wherever it accepts a stem or declared id (strip a matching kind prefix in one place, `_lookup`), so activate/deactivate/presets get URN input for free. Writers store the stem, never the URN.
- FR-012 (#6435): `effective_set` emits activation stems only — map service keys through `IdentityIndex.stem(kind, key) or key` (prefer mapping over dropping `_service_ids`, so a service-only artifact cannot vanish). Fix `_resolve_one` and `_fallback_ids`; update the module docstring and the `EffectiveSet.ids` docstring in `activation_engine.py` only if WP01 has already landed (it has — WP04 depends on it; a docstring-only edit there is an accepted out-of-map edit, note it).
- FR-013: presets (`preset_application.plan_preset_application` / `_target_state` / `_union` / `_org_required`) store stems for listed ids and unioned org-required ids, using the index already built there.
- FR-014: new `tests/charter/activation/test_stored_spelling_6527.py` — one parametrised test over every writer: activate explicit id, activate absent-key materialisation, `--only`, cascade (via an absent target kind), deactivate (deny list), preset (incl. org-required), interview promotion both modes, org-required union (`apply_org_charter_to_interview` path). Fixtures: an org stem≠id artifact (e.g. toolguide `acme-tool-file` / `acme-tool-id`, as in `test_activate_only_6408.py`), a project-layer stem≠id artifact (e.g. tactic `proj-tac` / `proj-tac-id`), and the built-in directive `024-locality-of-change` / `DIRECTIVE_024`. Assert no declared id and no URN is stored where a stem exists. Write it red first.
- Decision `no_stem_id`: a token with no single stem (e.g. an ambiguous directive id) is **kept as given with a warning** on every writer. `org_charter._normalize_required_ids` (~:294-340) switches from skip to keep (still warns).
- FR-015 / Decision `step_contracts`: `IdentityIndex` indexes built-in mission-step-contract files (`packs/built-in/missions/built_in_step_contracts/*.step-contract.yaml`); see how `list_available` finds them and how `kind_vocabulary._built_in_scan_dir(MISSION_STEP_CONTRACT)` returns None today. Prefer fixing the scan root at its single source; add an index unit test.
- Decision `ledger_migration`: **no** migration. Existing mixed lists normalise on their next write.
- C-005: no ACL/`to_contract`/`activation_invalid` work; no allow-list vs org-required-floor semantics change. Which artifacts are in force must not change, only the stored spelling.

## Context

- Full grounding with file:line and experiments: `kitty-specs/activate-output-and-identity-01M5ZA9X/research-6527-grounding.md` (read §0–§5 first). Experiment scripts: `/tmp/claude-0/-home-user-spec-kitty/a2f65514-bbcc-5e59-8af7-d2f7cbbf45c4/scratchpad/exp/e1.py`..`e8.py` (+ `e1lib.py`) — reuse their fixtures.
- Must stay green unchanged: `tests/charter/test_activation_preserves_effective_4253.py` (proves stems gate correctly). Do not edit `tests/acceptance/charter_pack_cutover/_effective_set.py` (digest-pinned).
- Re-pin (stale assertions of the bug, say so in the history note): `tests/charter/activation/test_effective_set.py:119-124` (procedure id spelling → stem, declared id absent); `test_activate_stem_writes_stem.py:48-51` comment + stale module docstring :4-5 (assert `qa-seven` absent); `test_charter_interview_promotion.py:327` if `_stem_spelled_effective` goes away.

## Out-of-map edits (allowed, with rationale)

- `src/charter/activation/pack_manager.py` `_narrow_inputs` (WP01-owned, approved before you start): remove the now-redundant stem mapping of `previous`/`artifact_id` only if the effective set now emits stems AND tests prove identical output; otherwise leave it (idempotent). One-line rationale in the commit.
- `tests/specify_cli/cli/commands/charter/test_activate_only_6408.py` (WP01-owned): tighten the `_ORG_ID` carve-outs at ~:93, :128, :157 to "no `_ORG_ID` in the written list".
- `src/charter/activation/activation_engine.py`: docstring of `EffectiveSet.ids` only.

## Branch Strategy

- **Planning base / merge target**: issue-6457-activate-output-identity. Lane worktree from `lanes.json`; its base includes WP01.

## Subtasks

- **T014** Red-first all-writers test (above). Record which writers fail before the fix.
- **T015** `IdentityIndex`: URN acceptance + step-contract indexing; unit tests in `test_identity_index.py`.
- **T016** Effective set stems; re-pin `test_effective_set.py`.
- **T017** Presets + `_normalize_required_ids` keep-with-warning.
- **T018** Remove compensations (`interview._stem_spelled_effective` — keep `_stem_spelled_config`, it still normalises legacy present lists; `_narrow_inputs` mapping per above); re-pin carve-outs.
- **T019** Gates.

## Test Strategy / Gates

From the worktree root, NOT `uv run`:
```bash
/home/user/spec-kitty/.venv/bin/python -m pytest tests/charter/activation/test_stored_spelling_6527.py tests/charter/activation/test_identity_index.py tests/charter/activation/test_effective_set.py tests/specify_cli/cli/commands/charter/ tests/specify_cli/cli/commands/test_charter_interview_promotion.py tests/charter/test_activation_preserves_effective_4253.py -q -p no:cacheprovider
/home/user/spec-kitty/.venv/bin/python -m pytest tests/charter/ tests/charter_offering/ -q -p no:cacheprovider -n auto --dist loadfile
/home/user/spec-kitty/.venv/bin/ruff check <changed .py>; /home/user/spec-kitty/.venv/bin/ruff format --check --force-exclude <changed .py>
MYPYPATH=src /home/user/spec-kitty/.venv/bin/python -m mypy <changed src files>
/home/user/spec-kitty/.venv/bin/ruff check --select C901 <changed src files>   # complexity <= 15
```
Baseline-red attribution: compare any failure against the WP base before claiming it.

## Review Guidance

- Red-first evidence for each writer; in-force set unchanged (only spelling); no migration; URN never stored; step contracts indexed; carve-out re-pins justified.
