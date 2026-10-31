---
work_package_id: WP02
title: The repair migration
dependencies:
- WP01
requirement_refs:
- FR-001
- FR-002
- FR-004
- FR-005
- FR-006
- FR-007
- FR-008
- NFR-001
- NFR-002
- NFR-003
- C-001
- C-002
- C-004
- SC-001
- SC-002
- SC-003
- SC-004
- SC-005
planning_base_branch: main
merge_target_branch: main
branch_strategy: Planning artifacts for this mission were generated on main. During /spec-kitty.implement this WP may branch from a dependency-specific base, but completed changes must merge back into main unless the human explicitly redirects the landing branch.
base_branch: kitty/mission-repair-historical-sweep-mission-overrides-01M68ZHQ
base_commit: 7323374ac695d6db299f0af1416d106f45853621
created_at: '2026-10-31T12:50:00.000000+00:00'
subtasks:
- T004
- T005
- T006
- T007
- T008
phase: Phase 2 - The repair
history:
- at: '2026-10-31T12:50:00Z'
  actor: system
  action: Prompt generated via /spec-kitty.tasks
agent_profile: python-pedro
authoritative_surface: src/specify_cli/upgrade/migrations/
create_intent:
- src/specify_cli/upgrade/migrations/m_4_0_0rc8_repair_historical_sweep_overrides.py
- tests/upgrade/migrations/test_m_4_0_0rc8_repair_historical_sweep_overrides.py
execution_mode: code_change
model: ''
owned_files:
- src/specify_cli/upgrade/migrations/m_4_0_0rc8_repair_historical_sweep_overrides.py
- src/specify_cli/upgrade/migrations/order_manifest.txt
- tests/upgrade/migrations/test_m_4_0_0rc8_repair_historical_sweep_overrides.py
- tests/architectural/test_mutation_ownership_routing.py
role: implementer
tags: []
task_type: implement
tracker_refs:
- '#6548'
- '#4961'
- '#5280'
- '#5450'
---

# Work Package Prompt: WP02 – The repair migration

## ⚡ Do This First: Load Agent Profile

Use the `/spk-charter-profile-load` skill to load the agent profile specified in the frontmatter
(`python-pedro`), and behave according to its guidance before parsing the rest of this prompt.

## Objective

Ship `4.0.0rc8_repair_historical_sweep_overrides`, a new migration that repairs overrides an older
`2.0.6_consistency_sweep` created under `.kittify/overrides/missions/<type>/…`.

**The issue's shape** (already witnessed on this baseline, `dfe9efb0e8`): a project at `4.0.0rc8`
carrying `.kittify/overrides/missions/software-dev/templates/spec-template.md` (byte-identical to
`packs/built-in/missions/software-dev/templates/spec-template.md`) and a deliberately outdated
`plan-template.md` keeps both across `spec-kitty upgrade`, and `resolve_template` keeps answering
`OVERRIDE` for both. `2.0.7_fix_stale_overrides` says "not needed" and
`4.0.0rc8_retire_stale_mission_template_forks` says "not needed" (it only knows the 15
documentation/research fork names). The ledger then records both as settled, so no later upgrade
revisits them.

**Provenance verdicts, and what each authorizes:**

| Verdict | Test | Action |
|---|---|---|
| identical | bytes equal the shipped counterpart at `<package missions root>/<type>/<rest>` | remove through `guard_destructive_removal` |
| differs | a shipped counterpart exists, bytes differ | preserve byte-for-byte, name it in a warning |
| no counterpart | no shipped file at that mission-relative path | never read, never named, never touched |

## Subtasks

- **T004 — red first.** Write `tests/upgrade/migrations/test_m_4_0_0rc8_repair_historical_sweep_overrides.py`
  with the reproduction that drives the **real `spec-kitty upgrade` command**
  (`typer.testing.CliRunner` + `contextlib.chdir`, the `test_retired_hosted_target.py` pattern): a
  bare project at `4.0.0rc8` (`.kittify/metadata.yaml` + `git init`), the two planted overrides,
  `--yes --no-worktrees`, then assert the identical override is gone, the differing one is
  byte-identical and named in the output, and `resolve_template` no longer reports `OVERRIDE` for
  the removed name. Run it and record the failure — it must be red before any production edit.
  Also record the **before** state (`spec-template.md -> OVERRIDE …`) in the WP notes: it is the
  reproduction evidence the issue's remaining acceptance item asks for.
- **T005** — Add the migration module. Shape:

  ```python
  MIGRATION_ID = "4.0.0rc8_repair_historical_sweep_overrides"
  TARGET_VERSION = "4.0.0rc8"

  @MigrationRegistry.register
  class RepairHistoricalSweepOverridesMigration(BaseMigration): ...
  ```

  - Scan: `.kittify/overrides/missions/**` only. Refuse (warn + change nothing) when a component of
    `.kittify`, `overrides` or `missions` is a symlink or not a directory; skip and name a symlinked
    file; never create or remove a directory.
  - Counterpart: `shipped_mission_counterpart(rel, get_package_asset_root())` from WP01, with `rel`
    relative to `.kittify/overrides/`.
  - Removal: `guard_destructive_removal(path, project_path, prover=CanonicalContentProver(canonical=shipped_bytes, check_marker=False))`.
    The module must contain **no** raw `unlink`/`rmtree`/`rmdir` literal — the guard removes.
  - `detect()`: true when any candidate has a shipped counterpart (identical → removable, differs →
    must be named). `can_apply()`: refuse visibly when the package asset root cannot be located.
  - `apply()`: one change line per removal (`"Removed stale override: …"`), one warning per kept
    differing file and per refused path; an `OSError` while reading → warning/error, never a
    removal. Idempotent: a second run finds no candidates.
  - Warnings must be actionable and name the path, e.g. "Kept `<rel>`: it differs from the template
    Spec Kitty ships, so it is treated as your edit. Delete it to use the shipped template." — read
    the sibling `kept_warning()` in `m_4_0_0rc8_retire_stale_mission_template_forks.py` for the
    house voice and keep this one distinguishable (it is about a mission override, not a fork).
  - Module docstring: the historical shape, why `2.0.7` cannot see it, why this is a new id
    (DIRECTIVE_044), and the three verdicts above.
- **T006** — Register the id in `order_manifest.txt` as the last `4.0.0rc8` entry with a tie
  annotation explaining it runs after `4.0.0rc8_retire_stale_mission_template_forks` so the named
  fork repairs happen first and this step handles everything else. Add the new module to
  `_ROUTED_MODULES` in `tests/architectural/test_mutation_ownership_routing.py` with a comment
  saying it removes a proven-identical override through the guard
  (`test_pinned_routed_module_set_is_complete` fails until you do).
- **T007 — unit tests** (same file, `pytestmark = pytest.mark.fast` for the unit ones):
  identical → removed + resolver no longer `OVERRIDE`; differing → bytes unchanged + named;
  identical and differing in one project → one step, only the identical removed; no counterpart
  (custom mission `erp`, extra file) → untouched and unnamed; symlinked override tree → refused,
  nothing changed; symlinked override file → skipped and named; CRLF copy of the shipped file →
  preserved and named (exact-byte comparison, pinned deliberately); second `apply()` → no changes;
  `can_apply()` refuses when `get_package_asset_root` raises `FileNotFoundError`; the new id is
  registered and appears once in the order manifest; `migrate ledger` lists it.
- **T008** — Run the targeted gates (see *Verification*).

## Files You Own

- `src/specify_cli/upgrade/migrations/m_4_0_0rc8_repair_historical_sweep_overrides.py` (new)
- `src/specify_cli/upgrade/migrations/order_manifest.txt` (one line + its annotation)
- `tests/upgrade/migrations/test_m_4_0_0rc8_repair_historical_sweep_overrides.py` (new)
- `tests/architectural/test_mutation_ownership_routing.py` (the routed-module pin only)

Do **not** edit `m_2_0_7_fix_stale_overrides.py`, `m_4_0_0rc8_retire_stale_mission_template_forks.py`,
`runtime/migrate.py` (WP01 owns it) or any other shipped migration body (C-001, DIRECTIVE_044).

## Constraints

- `.kittify/missions/**` legacy copies are **out of scope** (C-004): the classifier already handles
  them, and `4.0.0rc8_retire_stale_mission_template_forks` owns the fork names there.
- No resolver change (C-002): the fix is the files, not the precedence.
- Never delete or rewrite an override whose bytes are not proven identical (#4961).
- The scan reads only `.kittify/overrides/missions/**` and the shipped counterparts (NFR-001).

## Verification

```bash
uv run --frozen pytest tests/upgrade/migrations/test_m_4_0_0rc8_repair_historical_sweep_overrides.py -q
uv run --frozen pytest tests/upgrade/ -q -x
uv run --frozen pytest tests/architectural/test_mutation_ownership_routing.py \
  tests/architectural/test_migration_order_manifest.py -q
uv run --frozen ruff check src/specify_cli/upgrade/migrations tests/upgrade/migrations
uv run --frozen ruff format --check --force-exclude src/specify_cli/upgrade/migrations tests/upgrade/migrations
uv run --frozen mypy src/specify_cli/upgrade/migrations/m_4_0_0rc8_repair_historical_sweep_overrides.py
```

## Definition of Done

- [ ] The red-first CLI test existed and failed before the module landed; the failure is quoted in
      the WP notes
- [ ] Identical → removed through the guard; differing → byte-identical + named; no counterpart →
      untouched
- [ ] No raw destructive literal in the new module; routed-module pin updated
- [ ] Manifest entry with tie annotation; order/registry gates green
- [ ] Idempotent second apply; symlink and unreadable paths fail closed
- [ ] Targeted suites, ruff, format and mypy clean
