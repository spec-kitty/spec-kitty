# Implementation Plan: Exit 0 means your data is intact

**Branch**: `claude/milestone-11-research-0rnnr4` (lanes topology; PR → `main`) | **Date**: 2026-09-28 | **Spec**: [spec.md](spec.md)
**Input**: Mission specification from `kitty-specs/exit-zero-data-intact-01M3KDAS/spec.md`

## Summary

Six independent defects share one invariant: a mutating command must never exit 0 while destroying, corrupting or mis-recording user data. Each is fixed at its canonical seam and proven red-first through the CLI entry point its issue names:

- **#4919:** the decisions fold learns the defer-then-resolve rule, and the health check and repair stop discarding a decision the fold can't reconcile.
- **#4900:** the mission number is written on the target branch after the squash and read back before it is announced.
- **#4933:** the dirty-tree exemption is keyed to Spec Kitty's own mission metadata location instead of any file named `meta.json`.
- **#4940:** the settings file is decoded only when its encoding is provable; anything else is refused and left untouched.
- **#4998:** skill rendering normalises line endings before looking for frontmatter.
- **#4964:** the `migrate` group callback forwards its flags or refuses them.

Two small, dependency-free text primitives, one for unambiguous decoding and one for newline normalisation, are extracted into `kernel` and reused. Those two extractions are the only shared code.

**Engineering alignment.** The failure policies were confirmed by the operator in Decision Moment `01M3KDD2GHGFS7J5616ZNQHE6Y`. The five design decisions below came from the post-spec adversarial squad (architecture, code-truth and fakeability lenses), and each follows from those confirmed policies. No further planning questions were needed.

## Technical Context

**Language/Version**: Python 3.11+
**Primary Dependencies**: typer/click (CLI), ruamel.yaml, `spec_kitty_events` 10.4.0 (read-only, unchanged per C-004), `charset_normalizer`. The last is already used by `charter.encoding_recovery`; it is not newly imported anywhere, and never into `kernel`.
**Storage**: Files in the user's repository: `status.events.jsonl` and `decisions/index.json` (decisions), `kitty-specs/<mission>/meta.json`, `.claude/settings.json`, and the installed skill files plus their install manifest.
**Testing**: pytest. Each issue gets a red-first regression test through the real CLI entry point, using `typer.testing.CliRunner` or a subprocess with the venv's `bin/` on `PATH` (the meta merge driver shells out to `spec-kitty`). Each is marked `@pytest.mark.regression` while red, then converted to focused unit and integration tests. Scoped runs only (C-005): targeted files, the named architectural gates, and `make test-fast`.
**Target Platform**: Linux, macOS and Windows consumer installs. All tests run on Linux CI; Windows conditions (CRLF, UTF-16, cp1252) are simulated with byte fixtures.
**Project Type**: single (the `src/` layered packages `kernel ← charter ← specify_cli`)
**Performance Goals**: no measurable regression. The new work is one extra read-back of a small JSON file per consolidation and one in-memory newline normalisation per rendered skill.
**Constraints**: C-001 through C-007 from the spec. Complexity stays ≤15 per function, new kernel code is standard-library only, no new suppressions, and changed lines reach ≥90% diff coverage.
**Scale/Scope**: 6 issues, about 12 source files and 7 test modules. Each fix is small to medium; no public API or schema changes.

## Charter Check

*GATE: must pass before Phase 0 research. Re-checked after Phase 1 design.*

| Charter rule | Status | How the plan satisfies it |
|---|---|---|
| Single canonical authority / DIRECTIVE_044 | PASS | Decode and newline logic is extracted once into `kernel` and reused by `charter`. The decisions transition rule gets one home, shared by the service and the fold. The bookkeeping exemption stays in `coherence.is_self_bookkeeping_churn`. The mission number goes through the existing bake/bookkeeping-commit seam. |
| Architectural alignment / DIRECTIVE_001 | PASS | The new kernel module imports only the standard library (C-002). No `specify_cli → kernel` reverse edges. `git/ref_advance.py` keeps receiving the classifier as a parameter. |
| ATDD-first / DIRECTIVE_034, 041 | PASS | Each FR has a red-first CLI repro (NFR-001) and a same-fixture positive control. Tests are converted after green (ADR `2026-07-17-1`). |
| Campsite cleaning (Standing order 2) | PASS | Each work package opens with a behaviour-preserving tidy step on the functions it touches. That covers the 8 pre-existing mypy `no-any-return` findings in `decisions/service.py`, `_decisions_doctor.py`, `skills/installer.py` and `skills/verifier.py`, plus any extraction needed to keep functions ≤15. |
| Locality of change / DIRECTIVE_024 | PASS | Out-of-scope siblings are filed as follow-ups rather than folded in: `conflict_resolver.py:94` take-theirs on `*/meta.json`, the live-work capability-probe crash, and the events-reducer RESOLVED→RESOLVED anomaly. |
| Terminology canon | PASS | "Mission", and "local lane consolidation (`spec-kitty consolidate`)" rather than bare "merge". `test_no_legacy_terminology.py` is in the gate list. |
| Architectural gate discipline / DIRECTIVE_043 | PASS | Named gate files are run per work package (listed below), never the bare directory. |
| NO_FULL_HEAVY_SUITES_IN_MISSION | PASS | No `make test-full`, no whole `tests/architectural/` run. |

## Design Decisions (recorded)

| # | Decision | Chosen | Rejected alternatives |
|---|---|---|---|
| D1 | Decode rule for user-owned text (#4940) | `kernel.text_decode.decode_unambiguous(data: bytes) -> tuple[str, str] \| None` returns `(text, source_encoding)` only when a byte-order mark or strict UTF-8 proves the encoding. BOMs are checked UTF-32 before UTF-16, because the UTF-32-LE BOM begins with the UTF-16-LE BOM, and `recover()` mis-decodes that input today. It never guesses. UTF-32 BOMs are a deliberate, recorded extension of the operator's "provable encodings" policy, since a BOM is proof. `charter.encoding_recovery.recover()` delegates its BOM detection to `kernel.text_decode.detect_bom` and keeps decoding itself, so a BOM followed by undecodable bytes still raises (pinned). There is one definition. A charter test pins the UTF-32 correction. | Calling `recover()` directly: it guesses cp1252 via `charset_normalizer`, which violates the policy. Returning `str` only: `recover()` and the D6 backup need the encoding. Changing `kernel.meta_decode`: its strict rule is pinned by `test_meta_decode_l1.py`. |
| D2 | Mission number (#4900) | (a) One leaf definition, `is_assigned_mission_number` (integer ≥1), replaces the two disagreeing ones (`ordering.py:257`, which accepts 0 and negatives, and `mission_check_prerequisites.py:176`). `drivers.py` imports it without pulling in `ordering`. (b) In the driver, an unassigned target-owned `mission_number` is treated as unset (`drivers.py:295-297`). (c) Following the planning-only precedent (`_assign_planning_only_mission_number_if_needed`, `ordering.py:774-793`), the number is written into the **target-tree** `meta.json` and recorded in `run.mission_number_meta_path`, so it is committed by `commit_merge_bookkeeping(destination_ref_override=target)` in `_phase_commit_and_assert`. (d) A read-back sibling of `assert_baseline_merge_commit_on_target` reads the value via `baseline._read_committed_meta_json`, right after the baseline assert. On mismatch it prints `Error:` and exits 1. (e) The "Assigned" console line moves after the read-back. The `mission_number_baked` flag is set only once the number is verified on the target, and `--resume` re-reads the expected number from mission meta. The `_surface_unbaked_mission_number` warn paths (coord fallback, `ordering.py:397-420`) are unchanged: they announce no number, so they make no false claim. | `_bake_mission_number_on_primary_tree`: it is the coord fallback, uses a raw `git add`/`commit` on the root checkout's current branch, and has no compare-and-swap. A driver-only fix: FR-005 would still depend on squash ordering. Setting the flag before verification: `--resume` would then exit 0 with null. |
| D3 | Decisions fold (#4919) | One transition rule, defined next to the fold and imported by `service._is_allowed_terminal_reopen`. The fold is **order-independent**, because the event-log merge driver (`status/event_log_merge.py:62-68`) re-sorts by `(at, event_id)`. Exactly one `deferred` outcome plus one `resolved` outcome folds to `resolved`, whatever their order. Any other multi-outcome combination (for example two `resolved`, or `resolved` + `canceled`) is malformed. Diagnose runs the fold and compares each folded **status** (not just the id set) with the index, reporting `malformed_folds` and stale entries. With `--repair`, malformed decisions are kept and the command exits non-zero (`_decisions_doctor.py:419` stops hard-coding exit 0 in that case). Under `--json`, the report is emitted and then the command exits 1 (no second JSON document). Fixtures use step_id-origin decisions, to avoid the #4817 slot_key `lossy_attribution` refusal. | Ordering by position or `at`: the merge driver re-sorts, which is the #4941 class. Changing the emitter: existing logs stay broken, and it would touch the events contract (C-004). |
| D4 | Bookkeeping exemption (#4933) | In `coherence.is_self_bookkeeping_churn`, `meta.json` is exempt only when its path matches `(?:^|/)kitty-specs/[^/]+/meta\.json$` (depth-exact; allows a monorepo subdirectory) or is the legacy `.kittify/meta.json`. The literals stay inside the function (C9 / `test_exemption_registry_ratchet.py`). Every caller inherits the fix; the destructive gates and refusal gates listed in research R3 are covered by tests. | Repo-root anchoring (`^kitty-specs/`): git porcelain paths are relative to the git root, so monorepo users would be newly blocked. Adding `meta.json` to `mission_runtime._MISSION_FILE_KIND_BY_BASENAME`: it would widen `bookkeeping_projection` and the reconciliation class guard. |
| D5 | Newline normalisation (#4998) | `kernel.text_decode.normalize_newlines(text) -> str` (CRLF and lone CR → LF, nothing else). `charter.hasher.hash_content` calls it. `skills/command_renderer.ensure_skill_frontmatter` and the command-skill `render()` path normalise right after decoding. A `.gitattributes` `eol=lf` rule covers `src/charter/offering/skills/**` and `packs/built-in/missions/mission-steps/**`. | Reusing `hash_content`'s normalisation: it also strips the BOM and trims whitespace, which would corrupt rendered content. Relying on `.gitattributes` alone: it doesn't help sdist/zip installs or checkouts that already exist. |
| D6 | Settings file (#4940) | All three decode paths of `ClaudeCodeHookRegistrar` use `decode_unambiguous`: `_load` (used by `is_registered`, `register` and `unregister`) and `prepare_commands`/`apply_prepared` (the init/upgrade path via `writers/claude_code.py:65`). When the source encoding is not plain UTF-8, the original bytes are kept via the canonical byte-exact `asset_preservation.backup.backup_before_overwrite` (its timestamped `<path>.<ts>` naming is accepted) before `_save` writes UTF-8. `_preserve_invalid` writes decoded text, so it is not reused for this. Undecodable bytes raise `SettingsNotDecodableError(GuardedReadError)`, defined in `session_presence` (the CLI hook maps it to exit 1). **Mutating paths** (sync-hooks, live-work install/uninstall, init/upgrade writer) refuse non-zero. **Read-only probes** (`tool_surface/providers/session_presence.py:712`, `writers/claude_code.py:89` `has_presence`) report the file as undecodable in their finding or status instead of crashing, and are tested. | Keeping UTF-16 on write: hosts read UTF-8. Reusing `_preserve_invalid`: not byte-preserving. Having `is_registered` return False on decode failure: it would let `register` overwrite. |
| D7 | Migrate group flags (#4964) | A helper extracted out of the group callback (which already carries `noqa: C901` at `migrate_cmd.py:120`). For each group flag whose `ctx.get_parameter_source(name)` is COMMANDLINE and when `ctx.invoked_subcommand` is set, look up `ctx.command.get_command(ctx, sub).params`. If the subcommand declares the flag, forward it via `ctx.default_map[sub]` (a trailing flag still wins). Otherwise raise `click.UsageError` (exit 2) before the subcommand runs. Verified by experiment on typer 0.24.2 / click 8.3.3. | Per-subcommand edits: 11 sites would drift. Always rejecting: not the operator's choice. |

## Project Structure

### Documentation (this mission)

```
kitty-specs/exit-zero-data-intact-01M3KDAS/
├── spec.md
├── plan.md              # this file
├── research.md          # Phase 0: squad evidence, caller census, decisions
├── data-model.md        # Phase 1: entities, invariants, transition rule
├── quickstart.md        # Phase 1: red-first repro recipes per issue
├── contracts/
│   └── failure-surface.md   # exit codes, error codes and message contract per entry point
└── tasks.md             # /spec-kitty.tasks
```

### Source Code (repository root)

```
src/kernel/
└── text_decode.py                      # NEW: decode_unambiguous, normalize_newlines (stdlib only)
src/charter/
├── encoding_recovery.py                # delegate BOM + strict-UTF-8 steps to kernel.text_decode
└── hasher.py                           # hash_content calls normalize_newlines
src/specify_cli/
├── decisions/index_fold.py             # transition rule + log-order fold
├── decisions/service.py                # import the shared transition rule
├── cli/commands/_decisions_doctor.py   # diagnose runs the fold; repair refuses non-zero
├── cli/commands/doctor.py              # help/docstring: exit contract (C-007)
├── consolidation/drivers.py            # null target mission_number is unset
├── consolidation/ordering.py           # bake on target post-squash + read-back before announcing
├── consolidation/executor.py           # wire read-back / non-zero on mismatch (if the seam lives here)
├── coordination/coherence.py           # depth-exact meta.json anchor
├── session_presence/hooks/claude_code_hook.py  # decode via kernel; backup; typed refusal
├── skills/command_renderer.py          # normalise newlines before frontmatter regexes
├── skills/installer.py / verifier.py   # campsite typing; convergence covered by tests
└── cli/commands/migrate_cmd.py         # group-flag forward-or-refuse
.gitattributes                          # eol=lf for shipped skill sources + command templates
tests/
├── kernel/test_text_decode.py                      # NEW
├── charter/test_encoding_recovery.py, test_hasher* # delegation non-regression
├── specify_cli/decisions/ + tests/decisions/       # fold + doctor repros
├── consolidation/ (driver + ordering)              # #4900 repros
├── coordination/ + consolidation preflight tests   # #4933 repros (both arms)
├── session_presence/                               # #4940 repros (+ live-work install)
├── specify_cli/skills/                             # #4998 repros + convergence
└── cli/commands/test_migrate*                      # #4964 parametrised repro
```

**Structure Decision**: single project. The fixes land in the existing modules above. The only new module is `src/kernel/text_decode.py`, with its test module.

## Implementation Concern Map

> Concerns are not work packages. `/spec-kitty.tasks` turns them into WPs.

### IC-01 — Shared text primitives

- **Purpose**: Give the settings-file and skill-render fixes one canonical, dependency-free way to decode user bytes without guessing and to normalise newlines.
- **Relevant requirements**: FR-014, FR-015, FR-016 (enabler), C-002, C-003
- **Affected surfaces**: `src/kernel/text_decode.py` (new), `src/charter/encoding_recovery.py`, `src/charter/hasher.py`, `tests/kernel/`, `tests/charter/`
- **Sequencing/depends-on**: none
- **Risks**: `test_encoding_recovery_unification.py` may pin where BOM detection lives, so update it deliberately and don't bypass it. Kernel "stdlib only" is not enforced by a test (`kernel/yaml_io.py` already imports ruamel), so review must check it.

### IC-02 — Decisions fold, health check and repair

- **Purpose**: Make the documented defer-then-resolve flow fold correctly for new and existing logs, and make diagnose and repair truthful and non-destructive.
- **Relevant requirements**: FR-001–FR-004, C-004, C-007
- **Affected surfaces**: `decisions/index_fold.py`, `decisions/service.py`, `cli/commands/_decisions_doctor.py`, `cli/commands/doctor.py` (help text), `tests/specify_cli/decisions/`, `tests/decisions/`
- **Sequencing/depends-on**: none
- **Risks**: The repro must make the index diverge (delete `index.json`), or it passes on today's code. The documented "doctor decisions always exits 0" contract changes. The fixture for merged logs (out-of-order events) must be deterministic.

### IC-03 — Truthful mission numbering

- **Purpose**: Persist the mission number consolidation announces, on the target branch, and fail loudly on mismatch.
- **Relevant requirements**: FR-005–FR-007
- **Affected surfaces**: a leaf module for `is_assigned_mission_number`, `consolidation/drivers.py` (`reconcile_meta_payloads`), `consolidation/ordering.py` (target-tree write, announce after verify, baked flag), `consolidation/executor.py` (`_MergeRunState` threading, read-back after the baseline assert), `consolidation/baseline.py` (reuse `_read_committed_meta_json`), `mission_check_prerequisites.py` (use the shared definition), `tests/consolidation/test_merge_time_number_assignment.py`, `test_merge_drivers.py`, `test_ordering_bake_seam.py`
- **Sequencing/depends-on**: none
- **Risks**: Highest-risk concern, because it touches the terminus gate path. The write must ride the existing MERGE_BOOKKEEPING commit (`_phase_porcelain_invariant` whitelist, `executor.py:1770`), so the reconciliation gate still attributes it. `--resume` after a failed read-back must re-verify rather than skip. Read-back via `kernel.meta_decode` (`test_inline_meta_read_gate.py`). The driver subprocess needs a fresh editable install on `PATH`.

### IC-04 — Dirty-tree exemption keyed to Spec Kitty-owned metadata

- **Purpose**: Stop consolidation from treating a user's `meta.json` as bookkeeping, in both the root checkout and lane worktrees.
- **Relevant requirements**: FR-008–FR-010
- **Affected surfaces**: `coordination/coherence.py`, with the callers covered by tests: `consolidation/executor.py` (primary and worktree gates), `consolidation/git_probes.py`, `lanes/consolidation.py`, `review/dirty_classifier.py`
- **Sequencing/depends-on**: none
- **Risks**: 14 callers share the predicate (research R3). Consumers that should stay exempt (`kitty-specs/<mission>/meta.json`, including under a monorepo subdirectory) need [ratchet] tests. `test_exemption_registry_ratchet.py` pins the literals' location.

### IC-05 — Agent settings file preservation

- **Purpose**: Never replace a user's `.claude/settings.json`: merge it when its encoding is provable, refuse it untouched when it isn't.
- **Relevant requirements**: FR-011–FR-014
- **Affected surfaces**: `session_presence/hooks/claude_code_hook.py` (`_load`, `prepare_commands`, `apply_prepared`, `register`, `unregister`, `is_registered`), `session_presence/writers/claude_code.py` (`has_presence`), `tool_surface/providers/session_presence.py` (read-only probe), `cli/commands/agent/config.py` (`_sync_claude_hooks` error surfacing), `live_work/install.py` (install/uninstall callers), `tests/specify_cli/session_presence/test_claude_code_hook.py`, `tests/specify_cli/cli/commands/test_lint_hooks.py`
- **Sequencing/depends-on**: IC-01
- **Risks**: The typed refusal must reach the CLI error presenter as a non-zero exit (`test_cli_error_surface_seam.py`). `CliRunner` bypasses `_run_app_with_error_hook`, so tests assert the exception type or use a subprocess. Don't regress the existing `.invalid.<uuid>` path for invalid JSON. The refusal also blocks uninstall and lint-disable for undecodable files; that's intended, and it's tested.

### IC-06 — Line-ending-safe skill rendering

- **Purpose**: Make CRLF sources render identically to LF sources for doctrine skills and command skills, and make existing corrupted installs converge on repair.
- **Relevant requirements**: FR-015–FR-019
- **Affected surfaces**: `skills/command_renderer.py` (`ensure_skill_frontmatter`; the command-skill render must normalise at the decode (`:436`), before `apply_spdd_blocks_for_project` (`:442`) and `_extract_frontmatter_description` (`:366`), not at the strip), `skills/installer.py` / `verifier.py` (typing campsite; convergence behaviour verified), `.gitattributes`, `tests/specify_cli/skills/`
- **Sequencing/depends-on**: IC-01
- **Risks**: Repair converges only for files that still match the manifest hash (`installer.py` `unchanged_owned`). Tests must seed a manifest recording the corrupted bytes. `test_merge_reconciliation_class_guard.py` parses `.gitattributes`. Shipped skill sources live in `src/charter/offering/skills/`.

### IC-07 — Migrate group flags

- **Purpose**: Make `migrate --dry-run|--force|--verbose <subcommand>` either forward the flag to a subcommand that declares it or refuse with a usage error.
- **Relevant requirements**: FR-020–FR-022
- **Affected surfaces**: `cli/commands/migrate_cmd.py` (group callback), `tests/cli/commands/` (migrate tests)
- **Sequencing/depends-on**: none
- **Risks**: The test must be parametrised over every registered subcommand (11 today) so new subcommands are covered automatically. The no-subcommand form, which runs the group's own migration, must be unchanged.

## Gate files per concern (targeted, never the bare directory)

| Concern | Gate files |
|---|---|
| all | `tests/architectural/test_layer_rules.py`, `tests/architectural/test_no_legacy_terminology.py`, `tests/architectural/test_ruff_format_enforcement.py`, `make test-fast` |
| IC-01 | `tests/architectural/test_encoding_recovery_unification.py`, `tests/architectural/test_meta_decode_l1.py`, `tests/charter/test_encoding_recovery.py`, `tests/kernel/` |
| IC-02 | `tests/architectural/test_cli_error_surface_seam.py`, `tests/architectural/test_status_module_boundary.py` |
| IC-03 | `tests/architectural/test_inline_meta_read_gate.py`, `tests/architectural/test_trio_seam_only.py`, `tests/architectural/test_merge_reconciliation_class_guard.py` |
| IC-04 | `tests/architectural/test_exemption_registry_ratchet.py`, `tests/architectural/test_destructive_op_routing.py` |
| IC-05 | `tests/architectural/test_cli_error_surface_seam.py`, `tests/architectural/test_overwrite_ownership_routing.py` |
| IC-06 | `tests/architectural/test_merge_reconciliation_class_guard.py`, `tests/cross_cutting/packaging/test_packaging_safety.py` |
| IC-07 | `tests/architectural/test_cli_error_surface_seam.py` |

## Follow-ups (filed at PR time, not in scope)

- `consolidation/conflict_resolver.py:94` resolves any `*/meta.json` take-theirs. `resolve_owned_conflicts` has no callers in `src/`, so this is dead-code removal, not data loss; it will be noted on #2907 (the conflict_resolver taxonomy issue) rather than filed as a new issue.
- `.gitattributes` / `init.py:75` route `kitty-specs/**/meta.json` (any depth) through the metadata merge driver, which overlays target keys onto a user's nested `meta.json`. D4's depth-exact anchor is deliberately narrower. Aligning the two needs a migration.
- `cli/commands/agent/config.py:762-777` `_load_cursor_hooks`: a non-object is replaced with no backup, and a decode failure crashes. Same class, different agent file.
- `cli/helpers.py:182-214` `make_leaf_commands_mission_agnostic` silently ignores `--mission` on 4 mutating migrate subcommands.
- `live_work/capability.py:322` crashes on an undecodable settings file. It loses no data.
- The `spec_kitty_events` reducer flags RESOLVED→RESOLVED as `invalid_transition`, and the second resolved event also reaches Zeitgeist. This is upstream work (C-004).

## Post-plan squad amendments (folded)

planner-priti (foldables and sizing), python-pedro (feasibility) and debugger-debbie (split-brain residual hunt) passed the plan with amendments. All are now in D1, D2, D3, D6, D7, IC-03, IC-05 and IC-06 above. No open issue qualified for folding in. Related issues, not folded: see #4817, #4848, #2600, #2527, #4807, #3864 and #4946.

## Complexity Tracking

No charter violations to justify.
