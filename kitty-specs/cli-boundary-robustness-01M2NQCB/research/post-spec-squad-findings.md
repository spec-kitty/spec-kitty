# Post-spec brownfield squad findings — planning input

> Bounded profile-loaded squad at the post-spec point-cut (paula-patterns, planner-priti,
> reviewer-renata). Folded into spec.md; the plan-actionable residue is captured here.

## Confirmed (no change needed)
- Envelope promotion `_doctor_shared.py` → `cli/json_contract.py` (re-export) is **arch-safe**: intra-`specify_cli` edge, no LayerRule/`test_cli_console_single_seam.py`/`_doctor_shared` sibling-import violation.
- WP file-slicing holds no-overlap: A+B co-locate per file (context.py→WP03; mission_type.py+charter/mission_type.py→WP04); #4600 two-WP split (WP01 bootstrap / WP04 charter callee) is clean.
- OptionInfo class is near-closed: only the two OLD-style call sites (#4597/#4598) leak; all other direct-call sites pass params explicitly.
- Red-first discipline (NFR-003) reaches the real import entry point.

## PLAN MUST resolve/state (folded into spec, restated for the planner)
1. Exit code = each command's own non-json exit (frozen #4242 is per-command: mostly 1, exit 2 only for doctor shim-registry/contracts/tool-surfaces). `get_project_root_or_exit` stays exit 1. (C-001 corrected.)
2. Gate = parse-universal + shape-on-adopted; discover via structural Typer introspection over 4 flag vocabularies (`json_output`/`--json`/`json: bool`/`output_json`); explicit+extensible empty-case fixture list. (C-006/NFR-001.)
3. `get_project_root_or_exit` gains defaulted `json_output: bool = False`; assign its 5 otherwise-unowned caller files (`verify.py`, `validate_encoding.py`, `research.py`, `validate_tasks.py`, `dashboard.py`) to a WP. (FR-008.)
4. WP01 env_file stays import-pure (stdlib+kernel, no import-time os.environ); loud message in the command layer. (C-009.)
5. #4643 ownership: `agent_utils/status.py` returns pure data (no console.print, no `error` key); command owns the stream decision. (FR-006.)
6. #4598 fix at the call site (`mission_type.py:1572` pass `include_inactive=False`), not callee coercion. (C-005.)
7. Verify `doctrine mission-type list` (`doctrine.py:114`) routes through the corrected callee. (Edge case.)
8. Converge `cli/helpers.py:474` `exit_git_resolution_failure` divergent envelope onto canonical in WP02, else NFR-004 unmet.
9. OptionInfo guard parameterized over ALL 5 `invoke_without_command=True` callbacks (`__init__.py`, `migrate_cmd.py` ×2, `context.py`, `charter/list_cmd.py`); output-based only. (C-005.)
10. Update `_doctor_shared.py` module docstring on promotion (it self-declares stdlib+rich+_profile_health_render only). (DIRECTIVE_003.)

## Campsite census (SO#2 tidy-first — DOMAIN-MATCHED folds only)
FOLD (domain-matched, same touched file):
- `bootstrap/env_file.py:213-216` widen `except OSError` → `(OSError, UnicodeDecodeError)` (matches sibling `_read_tier:177`). [WP01]
- `cli/helpers.py:426-434` json-aware; `:473-474` converge envelope. [WP02]
- `context.py:86-91` prose-before-json; `:95,146,163,284,321` bare `print(json.dumps)` → seam; `:353-358` OptionInfo; `[red]Error:[/red]` ×10 S1192 consolidates as error-emit routes to shared helper. [WP03]
- `mission_type.py:1572/1607-1610/440/1693`; `charter/mission_type.py:199/137-138/190-191/213-214`; `[red]Error:[/red]` ×15 S1192. [WP04]
- `agent/tasks_status_cmd.py:417-419`; `agent_utils/status.py:186-188` (drop `error` key, prose→err_console — SURGICAL, inside a 104-stmt fn, do NOT refactor the fn). [WP05]
- `glossary.py:316-334,423-426` (error paths), `:439,454,462` (bare print/`[]` — assess vs D1). [WP05]
- `charter/activation/consistency_check.py:308-315` (one-line guard, surgical); `runtime/doctor.py:66` (encoding + guard). [WP01]

BASELINE (orthogonal — do NOT fold, freeze):
- `helpers.py:422` empty `except Exception: pass` (nag notifier).
- `status.py:399` `_display_status_board` complexity; `status.py:56` `show_kanban_status` (surgical fold only).
- `glossary.py:171,517` `# noqa: C901` (extraction/resolve logic, off the error/empty axis).
- PLR0912/PLR0915 hits in status.py/glossary.py/mission_type.py — freeze unless a fold naturally reduces one.

SCOUT during implement: `mission_type.py` (1720 lines, multi-sibling `--json` adoption in WP04).

## Tracker hygiene (for plan/close-out)
- Fold Closes: #4533 (+ add archive.py/materialize.py to gate surfaces), #4532.
- Parent link: #4646 (OptionInfo family) — #4597/#4598 are closed instances; #2779 stays open/deferred.
- #2899 is a SIBLING epic (traversal-guard ValueError, `core/paths.py`), not a parent — do not link as child.
- Assign the 5 filed issues to HiC + mission-naming comment at implement start (charter Tracker Ticket Assignment Rule).
