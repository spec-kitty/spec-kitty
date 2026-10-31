---
work_package_id: WP01
title: The rename authority carries an exclusion
dependencies: []
requirement_refs:
- FR-001
- FR-002
- FR-003
- FR-004
- FR-005
- NFR-001
- NFR-002
- C-001
- C-002
- C-003
- C-004
- C-005
- SC-001
- SC-002
- SC-003
- SC-004
planning_base_branch: kitty/mission-project-intent-deny-rename-01M68J6A
merge_target_branch: kitty/mission-project-intent-deny-rename-01M68J6A
branch_strategy: Planning artifacts for this mission were generated on kitty/mission-project-intent-deny-rename-01M68J6A. During /spec-kitty.implement this WP may branch from a dependency-specific base, but completed changes must merge back into kitty/mission-project-intent-deny-rename-01M68J6A unless the human explicitly redirects the landing branch.
created_at: '2026-10-31T08:50:00+00:00'
subtasks:
- T001
- T002
- T003
- T004
- T005
- T006
phase: Phase 1 - Core fix
history:
- at: '2026-10-31T08:50:00Z'
  actor: system
  action: Prompt generated via /spec-kitty.tasks
agent_profile: python-pedro
authoritative_surface: src/charter/activation/
create_intent: []
execution_mode: code_change
model: ''
owned_files:
- src/charter/activation/activation_ledger.py
- src/charter/activation/synthesizer/legacy_rename.py
- tests/charter/synthesizer/test_legacy_rename.py
- tests/architectural/test_deny_list_survives_upgrade.py
- tests/specify_cli/upgrade/migrations/test_m_4_0_0rc8_project_intent_directive_rename.py
role: implementer
tags: []
task_type: implement
tracker_refs:
- '#6565'
---

# Work Package Prompt: WP01 – The rename authority carries an exclusion

## ⚡ Do This First: Load Agent Profile

Use the `/spk-charter-profile-load` skill to load the agent profile specified in the frontmatter, and behave according to its guidance before parsing the rest of this prompt.

- **Profile**: `python-pedro`
- **Role**: `implementer`
- **Agent/tool**: `claude`

---

## ⚠️ IMPORTANT: Review Feedback

- **Has review feedback?** Check the `review_ref` field in the event log (`spec-kitty agent tasks status --mission project-intent-deny-rename-01M68J6A`).
- Address every feedback item before declaring the work complete, and record each with `spec-kitty agent tasks add-history WP01 --note "..."`.

---

## Objective

Issue #6565. `rename_legacy_project_intent_directive`
(`src/charter/activation/synthesizer/legacy_rename.py`) rewrites the legacy
`NNN-mission-type-scope-directive` stem everywhere the always-synthesized directive is named,
including the activation **allow** lists — but not the activation ledger's deny lists
(`deactivated_directives`). A project whose exclusion names the old stem therefore loses its
deactivation when the rename runs: the entry is reported as `DENY_UNKNOWN_ID` and the renamed
directive is back in force.

Make the rename carry the exclusion. The mapping already exists in the helper (`_rename_stem` /
`_target_filename`); the write already goes through `resolve_activation_write_target` →
`prepare_ledger_write`. Add exactly one sanctioned authority, `DenyListChoice.RENAME`, minted in the
helper's token step, and pin that one origin in the deny-list gate.

**Verified reproduction (on `main` 35318ef5, before your change):**

```text
ledger before: {'activated_directives': ['001-mission-type-scope-directive', 'DIRECTIVE_003'],
                'deactivated_directives': ['001-mission-type-scope-directive']}
rename report: ("rewrite 'activated_directives' stem token(s) in .kittify/charter/activation.yaml",)
ledger after:  {'activated_directives': ['001-project-intent-directive', 'DIRECTIVE_003'],
                'deactivated_directives': ['001-mission-type-scope-directive']}   # <- stale
```

## Files you own

| File | Why |
|---|---|
| `src/charter/activation/activation_ledger.py` | `DenyListChoice` gains `RENAME` |
| `src/charter/activation/synthesizer/legacy_rename.py` | the token step renames deny stems too |
| `tests/charter/synthesizer/test_legacy_rename.py` | behaviour of the deny rename |
| `tests/architectural/test_deny_list_survives_upgrade.py` | the pins and the positive control |
| `tests/specify_cli/upgrade/migrations/test_m_4_0_0rc8_project_intent_directive_rename.py` | the migration reaches the same end state |

Do **not** touch the migration module, the CLI commands, `pack_manager`, `preset_application`, or
`docs/` (WP02 owns the docs). Do **not** edit `AGENTS.md` / the changelog (WP02).

---

## T001 — Red-first: the rename carries a ledger deny entry

Add to `tests/charter/synthesizer/test_legacy_rename.py` (this file owns the rename contract; do not
create a new issue-named test file):

```python
def test_the_rename_carries_a_deny_entry(tmp_path: Path) -> None: ...
```

Fixture: a git-initialised project with `.kittify/config.yaml` and a seeded ledger via
`tests._factories.activation_ledger.seed_activation_ledger` (it passes
`DenyListChoice.DEACTIVATE` for deny keys), holding
`activated_directives=[_LEGACY_STEM, "DIRECTIVE_003"]`, `deactivated_directives=[_LEGACY_STEM]`.
Run `rename_legacy_project_intent_directive(tmp_path)` and assert
`read_activation_ledger(tmp_path)["deactivated_directives"] == [_NEW_STEM]`.

Run it on the unmodified tree and record the failure (you need this for the PR body). Then commit the
test alone:

```bash
git add tests/charter/synthesizer/test_legacy_rename.py
git commit -m "test(6565): the project-intent rename must carry a deny entry (red)"
```

## T002 — `DenyListChoice.RENAME`

`src/charter/activation/activation_ledger.py`: add `RENAME = "rename"` to `DenyListChoice`, and widen
the class docstring from "the four explicit choices" to the five paths, naming the rename as the one
**narrowing** authority: it moves an entry between two spellings of the same artifact and never adds
or removes a denial. Keep ADR `2026-10-19-1` Decision 4 as the reference.

No other change in that module: `prepare_ledger_write` already compares deny lists as normalised sets
and raises `DenyListWriteRefused` when the change has no choice. The member is already re-exported by
`charter.activation.api`; do not add another export.

## T003 — The token step renames deny stems (ledger only)

`src/charter/activation/synthesizer/legacy_rename.py`, the last step (`_check_tokens` /
`_apply_tokens` / `_step` tuple):

1. Replace `_legacy_token_keys(data)` with a function that returns the keys holding a legacy stem —
   every key in `ACTIVATION_YAML_KEYS` (as today) plus, **only when the resolved write target is the
   activation ledger**, every key in `DENY_KEYS`. Compare the resolved `target_path` with
   `kernel.activation_ledger_store.activation_ledger_path(repo_root)`; that is exactly the triple's
   own decision, and it keeps an unmigrated project's hand-written legacy deny key untouched (its
   save refuses a deny change, and the key was never applied there — ADR `2026-10-19-1` Amendment
   2026-10-20).
2. In `_apply_tokens`, after rewriting the tokens, compute the authority once and pass it to the
   existing single save:

   ```python
   choice = DenyListChoice.RENAME if deny_keys else None
   save(target_path, data, deny_change=choice)
   ```

   One write, one choice. `_renamed_tokens` already de-duplicates, so "both spellings denied" and a
   duplicated entry collapse to one target entry; `prepare_ledger_write` normalises (sorted, unique,
   empty key removed) — add no extra normalisation.
3. `_check_tokens` must report the deny rewrite as its own action line through the same
   `rewrite '<key>' stem token(s) in <path>` format, so `dry_run` and the migration's
   `changes_made` name it.
4. Update the module docstring's "What moves" list: the activation write target's **allow and deny**
   stem tokens move, and the deny one only on the ledger.

Import `DENY_KEYS` and `DenyListChoice` lazily inside the function, matching the module's existing
`# deferred: import cycle` comments (`pack_manager` imports this package's siblings, so the module
keeps those imports inside the function). Do **not** import `specify_cli` (layer ratchet C-001).

Run T001 now: it must be green.

## T004 — Behaviour tests

Extend `tests/charter/synthesizer/test_legacy_rename.py`:

- `test_a_legacy_surface_deny_key_is_left_alone` — the existing legacy-surface fixture (pointer
  `charter.yaml`, no ledger) with an added hand-written `deactivated_directives` naming the legacy
  stem: the rename succeeds (no `LegacyRenameRefusedError`), the deny key is byte-identical, and the
  allow list is still renamed.
- `test_a_second_run_does_not_rewrite_the_deny_entry` — after the first run, capture the ledger bytes,
  run again, assert `RenameReport(actions=())` and identical bytes (NFR-001).
- `test_other_deny_entries_are_untouched` — a fixture with `deactivated_tactics`,
  `deactivated_skills` and a declared-id directive entry (`DIRECTIVE_003`): only the legacy stem
  changes (SC-002).
- `test_both_spellings_of_the_deny_entry_collapse` — deny lists both the legacy and the target stem;
  the result holds exactly one target entry.
- `test_a_dry_run_names_the_deny_rewrite_and_writes_nothing` — `dry_run=True` reports the
  `deactivated_directives` line, and the ledger bytes are unchanged.

Keep every new test on a real seeded ledger (`tests/_factories/activation_ledger.py`), not a raw YAML
write: the point is that the write goes through the seam.

## T005 — Pin the one new origin in the deny-list gate

`tests/architectural/test_deny_list_survives_upgrade.py`:

- `CHOICE_ORIGINS` += `("src/charter/activation/synthesizer/legacy_rename.py", "_apply_tokens", "RENAME")`.
- `DENY_CHANGE_FORWARDS` += `(same module, "_apply_tokens", "choice")` — the step passes its chosen
  value to `save`, it does not mint a second one.
- `DENY_KEY_MODULES` += the same module.
- Update the module docstring: "no migration and no built-in preset removes a deny entry" becomes
  "… except the pinned project-intent rename, which moves one entry between two spellings of the same
  artifact", with `#6565` cited.
- Add the **positive control** (the non-vacuity pairing for the allowance):
  `test_a_rename_carries_the_deny_entry_and_nothing_else`. Reuse the existing fixture helpers
  (`post_ledger_fixture`, `seed_activation_ledger`, `_build_legacy_project_intent_stem`'s shape):
  add `deactivated_directives: [<legacy stem>]` to `FIXTURE_DENY`-style entries, run the
  `4.0.0rc8_project_intent_directive_rename` migration through `run_and_compare_deny`'s scope
  machinery but asserting the *expected* delta: the legacy stem is gone, the target stem is present,
  and the other fixture deny entries (`003-decision-documentation-requirement`, `acceptance-test-first`,
  `fixture-skill`) are byte-identical.

Do **not** relax the existing dynamic half: `test_a_migration_leaves_the_deny_entries_unchanged` must
still pass unchanged for every builder (the rename's own builder has no legacy deny entry), and
`test_a_deny_dropping_migration_fails_the_dynamic_check` must still fail its rogue offender.

## T006 — Migration-level end state and the blast radius

`tests/specify_cli/upgrade/migrations/test_m_4_0_0rc8_project_intent_directive_rename.py`: add
`test_apply_carries_a_ledger_deny_entry` — a project with the legacy artifact file **and** a seeded
ledger whose deny list names the legacy stem; `detect()` is true, `apply()` succeeds, and the deny
entry names the target stem. Also assert `detect()` is true for a project that carries *only* the
stale deny entry (the helper's dry-run preflight now sees it) and that a second `apply()` changes
nothing (SC-004).

Then run the affected suites and record the results:

```bash
uv run pytest tests/charter/synthesizer/test_legacy_rename.py -q
uv run pytest tests/architectural/test_deny_list_survives_upgrade.py -q
uv run pytest tests/specify_cli/upgrade/migrations/test_m_4_0_0rc8_project_intent_directive_rename.py -q
uv run pytest tests/charter/activation -q -x
uv run pytest tests/specify_cli/cli/commands/charter/test_synthesize_dry_run_evidence_6443.py \
              tests/agent/cli/commands/test_charter_synthesize_cli.py -q
uv run ruff check src/charter/activation tests/charter/synthesizer tests/architectural \
                    tests/specify_cli/upgrade/migrations
uv run ruff format --check src/charter/activation tests/charter/synthesizer tests/architectural \
                          tests/specify_cli/upgrade/migrations
```

Do not run a full heavy suite (charter `NO_FULL_HEAVY_SUITES_IN_MISSION`). If a test fails for a
reason outside your diff, reproduce it on pristine `origin/main` in a scratch worktree before you say
so.

## Definition of Done

- [ ] T001's test was RED on the planning base and is GREEN now; the failure output is quoted in your
      completion note.
- [ ] The deny rename happens in the **same single** ledger write as the allow rename; no second
      `save`, no raw YAML write, no new module, no second mapping.
- [ ] `DenyListChoice.RENAME` is minted in exactly one function and forwarded once; the gate pins both.
- [ ] A legacy surface's deny key is untouched and does not refuse the rename.
- [ ] The positive control fails if the helper stops renaming the entry, and the gate's rogue-offender
      test still fails a deny-dropping migration.
- [ ] All suites above pass; `ruff check` and `ruff format --check` are clean.
- [ ] No `kitty-specs/` path is in `owned_files`; no edit outside your owned files without a one-line
      rationale in your completion note.

## Reviewer guidance

Check, in order: (1) the predicate that decides "ledger only" — is it the triple's own resolution and
not a second one? (2) is there exactly one write and one choice? (3) do the pins name both the origin
and the forward, in both directions? (4) is the positive control on the same fixture family as the
dynamic half, so the allowance cannot be stale? (5) does any wording suggest synthesis may now clear a
denial (it may not)?
