---
work_package_id: WP05
title: Compile and consistency check through the identity index (#6433)
dependencies:
- WP04
requirement_refs:
- FR-016
- FR-017
planning_base_branch: issue-6457-activate-output-identity
merge_target_branch: issue-6457-activate-output-identity
branch_strategy: Planning artifacts for this mission were generated on issue-6457-activate-output-identity. During /spec-kitty.implement this WP may branch from a dependency-specific base, but completed changes must merge back into issue-6457-activate-output-identity unless the human explicitly redirects the landing branch.
base_branch: kitty/mission-activate-output-and-identity-01M5ZA9X
base_commit: 92e7d7d16926cc82050b102be16a69d7dd4200f7
created_at: '2026-10-28T05:28:44.803164+00:00'
subtasks:
- T020
- T021
- T022
- T023
phase: 'Phase 2 - #6527 local slice'
history:
- at: '2026-10-27T20:10:00Z'
  actor: system
  action: 'Prompt generated via /spec-kitty.tasks (operator scope addition #6527/#6433)'
agent_profile: python-pedro
authoritative_surface: src/charter/activation/
create_intent:
- tests/charter/activation/test_compile_check_identity_6433.py
execution_mode: code_change
owned_files:
- src/charter/activation/compiler.py
- src/charter/activation/consistency_check.py
- src/charter/activation/drg_activation.py
- tests/charter/test_compiler.py
- tests/charter/test_consistency_check.py
- tests/charter/activation/test_compile_check_identity_6433.py
role: implementer
tags: []
task_type: implement
tracker_refs: []
---

# Work Package Prompt: WP05 – Compile and consistency check through the identity index (#6433)

## ⚡ Do This First: Load Agent Profile

Use the `/spk-charter-profile-load` skill to load `python-pedro` (implementer, `claude`) before reading further.

## Review Feedback

*[Filled from the status event log when returned from review.]*

## Objectives & Success Criteria

- FR-016 / Decision `compile_unknown_token`: `compiler._resolve_config_activated_ids` (~:146-189, called ~7 times from `_resolve_config_activated_roots`) resolves activation tokens through ONE `IdentityIndex` built for the same roots **including the project layer** (thread it in; don't rebuild per call). Stems, declared ids and URNs (WP04 added URN support) resolve. A truly unknown token **still fails compile** (keep the raise and the activation-store-naming message at ~:297-303; C-006 "never silently drop" holds).
- FR-017 / Decision `unknown_token_consistency`: `consistency_check.py` uses one `IdentityIndex.build(repo_root)` (covers the project layer) for `_check_unknown_references` (known = index knows it), forward parity (~:791), graph-kind parity (~:860) and reverse paradigm parity (~:805-831, compare stems with stems). Unknown tokens are **warned and kept**, and reported **once** (not both in `unknown_references` and `verification_errors`). A stored declared id and a project-layer artifact are no longer reported unknown.
- T023: remove the `resolve_artifact_urn` fallback in `drg_activation.py` (~:337-346) only if, after WP04 (URN + step-contract indexing), the index covers everything the fallback caught — prove with a test; else leave it and say why. The `preset_application.py` fallback is WP04's file: leave it.
- **WP04 review hand-over (blocking for WP05):** WP04 stores a *known* declared id with no single stem as given (Decision `no_stem_id`), e.g. `DIRECTIVE_024` on the shadow fixture in `tests/charter/activation/test_stored_spelling_6527.py` (org directive file `024-locality-of-change` declaring `ACME_024`). Today `resolve_config_activated_roots` raises `UnknownArtifactIdError` on it. Compile must accept it (the index knows it: `declared_id == selection_id == 'DIRECTIVE_024'`) — resolve declared ids through the index, not `stem()` then `resolve_artifact_urn`. WP04 leaves an `xfail(strict=True)` test for this; WP05 must flip it to a passing test (remove the xfail).
- Pin one behaviour for unknown tokens per surface (runtime gate: warn+keep; consistency check: warn+keep; compile: refuse) in a test module docstring, so #6433's "pin one behaviour" is explicit.

## Context

- Grounding: `kitty-specs/activate-output-and-identity-01M5ZA9X/research-6527-grounding.md` §2 (call sites, verified defects: project-layer false unknowns, double report, reverse parity spelling, compile fails on URN). Experiments `e5.py`, `e6.py`, `e7.py` in `/tmp/claude-0/-home-user-spec-kitty/a2f65514-bbcc-5e59-8af7-d2f7cbbf45c4/scratchpad/exp/`.
- Existing tests that pin the compile raise stay valid for truly unknown tokens; re-pin only those that asserted a URN/declared-id/project-layer failure.

## Branch Strategy

- **Planning base / merge target**: issue-6457-activate-output-identity; lane worktree base includes WP04.

## Subtasks

- **T020** Red-first `tests/charter/activation/test_compile_check_identity_6433.py`: compile with a URN, a declared id and a project-layer stem≠id artifact succeeds; compile with an unknown token fails (positive control); consistency check on the W2-written list and a project-layer artifact reports no unknowns; an unknown token is reported once and kept.
- **T021** Compile.
- **T022** Consistency check.
- **T023** Fallback retirement (conditional) + gates.

## Gates

From the worktree root, NOT `uv run`:
```bash
/home/user/spec-kitty/.venv/bin/python -m pytest tests/charter/activation/test_compile_check_identity_6433.py tests/charter/test_compiler.py tests/charter/test_consistency_check.py tests/charter/activation/ -q -p no:cacheprovider -n auto --dist loadfile
/home/user/spec-kitty/.venv/bin/python -m pytest tests/charter/ tests/charter_offering/ tests/specify_cli/cli/commands/charter/ -q -p no:cacheprovider -n auto --dist loadfile
/home/user/spec-kitty/.venv/bin/ruff check <changed .py>; ruff format --check --force-exclude <changed .py>; ruff check --select C901 <changed src>
MYPYPATH=src /home/user/spec-kitty/.venv/bin/python -m mypy <changed src files>
```

## Review Guidance

- Compile still refuses unknown tokens; consistency check warns and keeps, reports once; project layer covered; one index per run; complexity <= 15.
