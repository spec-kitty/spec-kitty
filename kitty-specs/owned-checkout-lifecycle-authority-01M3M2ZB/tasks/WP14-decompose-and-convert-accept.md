---
work_package_id: WP14
title: Decompose and convert accept
dependencies:
- WP07
- WP08
- WP10
requirement_refs:
- FR-003
- FR-022
- FR-026
planning_base_branch: claude/sleepy-hamilton-5lelee
merge_target_branch: claude/sleepy-hamilton-5lelee
branch_strategy: Planning artifacts for this mission were generated on claude/sleepy-hamilton-5lelee. During /spec-kitty.implement this WP may branch from a dependency-specific base, but completed changes must merge back into claude/sleepy-hamilton-5lelee unless the human explicitly redirects the landing branch.
subtasks:
- T075
- T076
- T077
- T078
- T079
phase: Phase 4 - Conversion sweep
history:
- at: '2026-09-28T15:00:00Z'
  actor: system
  action: Prompt generated via /spec-kitty.tasks
agent_profile: python-pedro
authoritative_surface: src/specify_cli/cli/commands/accept.py
create_intent:
- tests/specify_cli/cli/commands/test_accept_decomposition.py
execution_mode: code_change
model: claude-sonnet-5
owned_files:
- src/specify_cli/cli/commands/accept.py
- tests/specify_cli/cli/commands/test_accept_decomposition.py
role: implementer
tags: []
task_type: implement
tracker_refs: []
---

# Work Package Prompt: WP14 – Decompose and convert accept

## ⚡ Do This First: Load Agent Profile

Use the `/ad-hoc-profile-load` skill to load the agent profile specified in the frontmatter (or any user-defined profile), and behave according to its guidance before parsing the rest of this prompt.

- **Profile**: `python-pedro`
- **Role**: `implementer`
- **Agent/tool**: `claude`

If no profile is specified, run `spec-kitty agent profile list` and select the best match for this work package's `task_type` and `authoritative_surface`.

Then load the action-scoped governance: `spec-kitty charter context --action implement --json`. The charter (`.kittify/charter/charter.md`) is binding; this prompt does not repeat it.

---

## ⚠️ IMPORTANT: Review Feedback

**Read this first if you are implementing this task!**

- **Has review feedback?**: Check the `review_ref` field in the event log (via `spec-kitty agent tasks status`) or the Activity Log below.
- **You must address all feedback** before your work is complete. Feedback items are your implementation TODO list.
- **Report progress**: As you address each feedback item, update the Activity Log explaining what you changed.

---

## Review Feedback

*[If this WP was returned from review, the reviewer feedback reference appears in the Activity Log below or in the status event log.]*

---

## Markdown Formatting

Wrap HTML/XML tags in backticks: `` `<div>` ``, `` `<script>` ``
Use language identifiers in code blocks: ````python`, ````bash`

---

## Objectives & Success Criteria

This WP is the IC-10a + IC-14a slice of the plan: the `accept` command stops being the largest over-limit function in the repository and stops carrying bare owned roots.

Done means all of the following hold at the tip of the WP:

1. **Characterisation first (T075).** `tests/specify_cli/cli/commands/test_accept_decomposition.py` exists, was committed **green against the undecomposed `accept()`** in its own commit, and pins every exit path of the command (exit code, JSON keys, side-effect order).
2. **Complexity restored (T076, FR-026).** `accept()` is ≤ 15 (it is 59 on the planning base, `src/specify_cli/cli/commands/accept.py:740`). No new helper exceeds 15. `C901` is removed from the `ruff.toml` per-file-ignore entry for `src/specify_cli/cli/commands/accept.py` (line 27 today: `["B904", "C901", "F401", "UP035"]` becomes `["B904", "F401", "UP035"]`). `uv run --frozen ruff check src/specify_cli/cli/commands/accept.py` is clean with that ignore gone.
3. **No re-validation (T077, FR-003).** `_stamp_birth_cutover_for_accept` no longer calls `resolve_owned_mission` (today `accept.py:339-342`). The fact validated once at the CLI edge is the only fact the command uses.
4. **Converted (T078, FR-001 via FR-022).** `accept.py` contains **zero** occurrences of the identifier `effective_root`, zero calls to `effective_root_kwargs`, zero `"effective_root"` string keys, zero `OwnedMission` references, zero legacy attribute reads (`.root`, `.primary`, `.directory`, `.slug`, `.target`) on the fact, and no direct `resolve_owned_mission` call. The `--owned-checkout` option is declared through WP08's `OwnedCheckoutOption` and resolved through `resolve_owned_or_adopt`.
5. **Ratchet (T079, FR-022).** Every existing accept test file listed under Test Strategy passes **without modification**, including the owned accept scenarios in `tests/integration/test_explicit_checkout_commands.py`.
6. ruff check, ruff format and `mypy --strict` are clean on the touched files; `make test-fast` passes.

**Mission-wide DoD (post-tasks squad):**
- `grep -rn "bridging: WP14 converts" src` is empty: every bridging call site marked for this WP is converted, including sites in other WPs' files (declared out-of-map edits).
- Every bridging call site this WP adds carries `# bridging: WP<n> converts`, naming the WP that converts it (never a free-form comment, never no marker).
- `TRANSITIONAL(WP18)` markers added by this WP (exact list; any deviation is amended here in the same PR, and WP18 T096 fails on unlisted markers): **0** markers.
- Red-first proofs are **commits**: the red test commit precedes its fix commit, and the reviewer verifies the order in `git log`.
- Error codes are imported from `OwnedRefusalCode` (WP01); no `OWNED_*` string literal is repeated in `src/` or new tests (Sonar S1192).

## Context & Constraints

- **Mission docs**: `kitty-specs/owned-checkout-lifecycle-authority-01M3M2ZB/` → `spec.md` (FR-003, FR-022, FR-026), `plan.md` (Staging Strategy; IC-10a; IC-14a; "One owning WP per shared file": `cli/commands/accept.py` is owned by IC-10a = this WP), `research.md` R-16 (Complexity: `accept` 59 is the only over-limit function in its per-file-ignored file), `data-model.md` (OwnedCheckout fields), `contracts/owned-checkout-carrier.md` (§2 once per command, §3 no bare owned roots), `contracts/cli-owned-checkout-surface.md` (accept row: existing flag, single_branch, unchanged behaviour), `occurrence_map.yaml`.
- **What the earlier WPs give you** (read their landed code first; do not assume the shapes below, verify them):
  - WP01: `mission_runtime.OwnedCheckout` with canonical fields `repository_root`, `owned_root`, `mission_dir`, `mission_slug`, `topology`, `target_branch`, plus **transitional** legacy properties (`primary`, `root`, `directory`, `slug`, `target`) that WP18 deletes. Do not read the legacy properties in new code.
  - WP02: `specify_cli.core.owned_mission` is the sole minter; `OwnedMission` is a transitional legacy factory function (marked `TRANSITIONAL(WP18)`) returning an `OwnedCheckout`; `require_unstaged_index` accepts the fact.
  - WP08: `src/specify_cli/cli/commands/_owned_checkout.py` exposes `OwnedCheckoutOption`, `resolve_owned_or_adopt(...)` and `emit_owned_refusal(...)`. Read the module and its test file (`tests/specify_cli/cli/commands/test_owned_checkout_helper.py`) before wiring.
  - WP07: `TransitionRequest.owned` and friends. accept does not build a `TransitionRequest` directly, but its callees in `specify_cli.acceptance` and `specify_cli.consolidation.baseline` are converted by WP15 and WP17.
  - WP10: owns `ruff.toml` and removed the `core/mission_creation.py` C901 entry. Your `ruff.toml` edit happens after WP10 merged (that is why WP10 is a dependency).
- **Staging (plan: Staging Strategy)**: conversion is top-down. `accept()` holds the fact; any callee that is **not yet** converted when you start receives the bridging expression `effective_root=owned.owned_root if owned else None` — but only in a callee's **own** file, never in `accept.py`. Inside `accept.py` every helper you own takes `owned: OwnedCheckout | None`. For calls leaving `accept.py` into WP15/WP17 modules, see T078 step 5.
- **Behaviour preservation is the contract.** FR-026 is a pure refactor; FR-022 says the existing accept tests pass unchanged. The JSON payload keys (`error`, `error_code`, `diagnose`, the `result.to_dict()` shape, advisory notes) are `serialized_keys: do_not_change` in `occurrence_map.yaml`. Error-code strings (`OWNED_*`) are `logs_telemetry: do_not_change`.
- **Terminology (C-008)**: in any new docstring, comment or message write "repository root checkout" and "owned checkout", never bare "primary" as a checkout alias and never "feature". Existing identifiers such as `_primary_dirty_paths` / `_commit_primary_residuals` name the PRIMARY partition (a governed term, see `docs/context/orchestration.md#primary-partition`) and stay as they are.
- **Complexity ceiling 15, Sonar S1192**: repeated error-emission literals become one helper, not three copies.
- **No suppressions**: no new `# noqa`, `# type: ignore` or per-file ignores. The three existing `# noqa: BLE001` lines (`accept.py:76`, `accept.py:352`, `accept.py:1095`) keep their inline rationale and move with their code.

## Branch Strategy

- **Strategy**: Planning artifacts were generated on `claude/sleepy-hamilton-5lelee`; completed changes must merge back into `claude/sleepy-hamilton-5lelee`.
- **Planning base branch**: `claude/sleepy-hamilton-5lelee`
- **Merge target branch**: `claude/sleepy-hamilton-5lelee`
- **Execution lane**: assigned in `kitty-specs/owned-checkout-lifecycle-authority-01M3M2ZB/lanes.json` by `spec-kitty agent mission finalize-tasks`. Start with `spec-kitty implement WP14` and work only in the workspace path it prints; never reconstruct the worktree path yourself.

> These fields are populated automatically by `spec-kitty agent mission finalize-tasks`.
> Do NOT change them manually unless you are certain the branch topology has changed.

## Occurrence census for `accept.py` (planning base `df1588860`)

Every site below must be gone or converted at the end of the WP (T077/T078). Line numbers are for the planning base; they drift after T076, so re-run the census command at the end:

```bash
grep -nw "effective_root\|effective_root_kwargs\|OwnedMission\|resolve_owned_mission" src/specify_cli/cli/commands/accept.py
grep -nE "owned\.(root|primary|directory|slug|target)\b" src/specify_cli/cli/commands/accept.py
```

| Line | Kind | Site |
|---|---|---|
| 29-34 | import | `OwnedMission`, `effective_root_kwargs`, `resolve_owned_mission` from `specify_cli.core.owned_mission` |
| 120 | param | `_coord_worktree_root(..., *, effective_root: Path \| None)` |
| 147-148 | `effective_root_kwargs` + splat | `scope = effective_root_kwargs(effective_root)` → `resolve_artifact_surface(**scope)` |
| 167 | param | `_coord_status_feature_dir(..., *, effective_root)` |
| 208-209 | `effective_root_kwargs` + splat | into `resolve_artifact_surface` |
| 217 | `effective_root_kwargs` splat | `placement_seam(repo_root, mission_slug, **effective_root_kwargs(effective_root))` |
| 220 | param | `_coord_dirty_paths(..., *, effective_root)` |
| 232-235 | splat | `_coord_worktree_root(**effective_root_kwargs(effective_root))` |
| 270 | param | `_stamp_birth_cutover_for_accept(..., effective_root)` |
| 271 | param | `_stamp_birth_cutover_for_accept(..., owned: OwnedMission \| None)` |
| 320-321 | `effective_root_kwargs` + splat | `placement_seam(..., **scope)` |
| 334 | splat | `_coord_status_feature_dir(..., **scope)` |
| 337-342 | **re-validation** | `if owned is None and effective_root is not None: owned = resolve_owned_mission(...)` |
| 370 | param | `_record_pr_merge_for_accept(..., effective_root)` |
| 398-402 | keyword | `record_pr_merge_baseline_for_mission(effective_root=effective_root)` (callee in WP17) |
| 483 | param | `_commit_residual_acceptance_artifacts(..., *, effective_root)` |
| 498-501 | splat | `_coord_dirty_paths(**effective_root_kwargs(effective_root))` |
| 665 | param | `_collect_summary_with_optional_repair(..., effective_root)` |
| 677, 679, 695, 703 | `effective_root_kwargs` + 3 splats | into `collect_feature_summary` (×2) and `normalize_feature_encoding` (callees in WP15) |
| 721-737 | `OwnedMission` + direct validator call | `_owned_accept_context` → `resolve_owned_mission(primary, checkout, mission)` |
| 763 | inline option | `owned_checkout: Annotated[Path \| None, typer.Option("--owned-checkout", ...)]` |
| 825 | legacy attr | `repo_root = owned.root` |
| 864 | legacy attrs | `owned.slug, owned.directory` |
| 868 | **dict key** | `scope = {"effective_root": owned.root} if owned is not None else {}` |
| 906 | splat | `verify_pr_merge_evidence(..., **scope)` (callee in WP17) |
| 925 | splat | `_collect_summary_with_optional_repair(..., **scope)` |
| 1075 | splat | `_stamp_birth_cutover_for_accept(repo_root, mission_slug, **scope, owned=owned)` |
| 1086 | splat | `_record_pr_merge_for_accept(..., **scope)` |
| 1105 | splat | `_commit_residual_acceptance_artifacts(repo_root, mission_slug, **scope)` |

Totals: 7 parameters, 1 inline option, 7 `effective_root_kwargs(...)` calls, 14 splats/keywords, 1 dict key, 4 legacy attribute reads, 2 validator calls (`:342`, `:732`).

## Subtasks & Detailed Guidance

### Subtask T075 – Characterisation tests for `accept()`

- **Purpose**: Freeze the observable behaviour of `accept()` before it is taken apart, so T076 is provably behaviour-preserving (DIRECTIVE_034 test-first; FR-026 "behaviour-preserving … with focused tests"). The existing suites cover many paths end to end, but none pins the side-effect **order** in the `finally` block or every JSON error envelope in one place.
- **Steps**:
  1. Create `tests/specify_cli/cli/commands/test_accept_decomposition.py`. Put `unit` + `fast` markers on the characterisation tests **per test or per class**, not as a module-level `pytestmark`, because T079 appends an `integration` + `git_repo` test to the same file.
  2. Invoke the command through Typer exactly as `tests/integration/test_explicit_checkout_commands.py:24-25` does:
     - `accept_app = typer.Typer(); accept_app.command()(accept)`;
     - `CliRunner().invoke(accept_app, [...])`.
  3. Isolate the command from git and the filesystem by monkeypatching **module attributes of `specify_cli.cli.commands.accept`** only:
     - `show_banner`, `find_repo_root`, `resolve_mission_dir_with_bare_modern_fold`, `choose_mode`;
     - `_collect_summary_with_optional_repair`, `verify_pr_merge_evidence`, `perform_acceptance`, `resolve_acceptance_actor`, `_stranded_verdict_provenance_note`;
     - `_stamp_birth_cutover_for_accept`, `_record_pr_merge_for_accept`, `_commit_residual_acceptance_artifacts`.
     Use tiny fakes: a `SimpleNamespace` summary with `ok`, `to_dict()`, `warnings`; a fake `AcceptanceResult` with `to_dict()`, `notes`, `commit_created`, `summary`. Record every helper call into one `calls: list[str]` so ordering is assertable.
  4. Write one test per exit path; each asserts the exit code, and for `--json` runs the exact top-level key set of the printed JSON:
     - `--mission` omitted → exit 2, `{"error": "--mission <slug> is required"}`.
     - `find_repo_root` raises `TaskCliError` → exit 1, `{"error"}` only.
     - owned entry raises `ActionContextError("OWNED_BRANCH_REFUSED", ...)` → exit 1, keys `{"error_code", "error"}` (simulate by patching `_owned_accept_context`; after T078 you patch the WP08 helper instead — see step 6).
     - `--merge-commit` with a resolved mode other than `pr` → exit 2, message contains `only valid with --mode pr`.
     - `verify_pr_merge_evidence` raises `PrMergeEvidenceError` → exit 1, `Cannot record PR merge for`.
     - summary collection raises each of `Pre30LayoutError`, `AcceptanceError`, `AcceptanceMatrixParseError` → exit 1, `{"error"}` (parametrise).
     - `--diagnose --json` → exit 0, payload has `"diagnose": true`; `perform_acceptance` never called.
     - `--mode checklist` with `summary.ok` True/False → exit 0/1; `perform_acceptance` never called.
     - `summary.ok` False, with and without `--allow-fail` → exit 1 both ways.
     - `perform_acceptance` raises `AcceptanceError` → exit 1; **pin that `_commit_residual_acceptance_artifacts` still runs** (today's `finally` runs the residual commit whenever `commit_required`) and that the stamp and PR-merge recording do **not** run.
     - stamp raises `AcceptanceError` → exit 1, `Birth-cutover stamp refused:`; PR merge raises → `PR merge recording failed:`; residual raises → `Residual artifact commit failed:`. When more than one fails, the stamp message wins over the PR-merge message, which wins over the residual message (today's `if` order at `accept.py:1108-1130`).
     - happy path, `--mode pr --merge-commit abc`: `calls == ["perform_acceptance", "stamp", "record_pr_merge", "residual"]`; `result.notes` gains the `PR merge recorded:` note.
     - `--no-commit` with `--merge-commit`: gains the `re-run without --no-commit` note, calls neither stamp nor residual, and `perform_acceptance` receives `auto_commit=False`.
  5. Assert the stamp is called with the same `owned` object the CLI edge produced (identity: `is`); T077 relies on it.
  6. Centralise the patching in one fixture so T078 only swaps the owned-entry patch target in one place. Keep each fake minimal; no real git.
  7. Run the file against the **planning-base** `accept.py` and commit it alone: `test(accept): characterise accept() exit paths before decomposition (WP14/T075)`.
- **Files**:
  - `tests/specify_cli/cli/commands/test_accept_decomposition.py` (new).
  - Read-only references: `src/specify_cli/cli/commands/accept.py:740-1159`; `tests/specify_cli/cli/commands/test_accept_merge_commit.py` (merge-commit fakes to borrow); `tests/specify_cli/cli/commands/test_accept_clean_tree.py`.
- **Parallel?**: No. It must land before T076.
- **Validation checklist**:
  - [ ] The file is green on the undecomposed `accept()` (run it before touching `accept.py`).
  - [ ] Every `raise typer.Exit(...)` in `accept()` (16 on the planning base) is reached by at least one test. Check with `uv run --frozen pytest tests/specify_cli/cli/commands/test_accept_decomposition.py --cov=specify_cli.cli.commands.accept --cov-report=term-missing` and confirm no uncovered line inside `accept()`.
  - [ ] Tests assert key sets, exit codes and call order, never rich console formatting.
- **Edge cases**:
  - The human (non-JSON) path calls `show_banner()` and a `StepTracker`; test at least one human-mode failure so the tracker-error branches are covered.
  - `--normalize-encoding` together with `--diagnose` is refused only in owned mode (`_owned_accept_context`); pin that refusal too.
  - `requested_mode` is lower-cased before `choose_mode`; include one upper-case `--mode PR` run so the decomposition cannot drop it.

### Subtask T076 – Decompose `accept()` to ≤ 15; drop the `accept.py` C901 ignore

- **Purpose**: FR-026. `accept()` sits at complexity 59 (`ruff check --isolated --select C901` on the planning base). The plan (IC-14a) requires a behaviour-preserving decomposition **before** the functional conversion (tidy-first), and removal of the per-file suppression that has hidden it. It is the only over-limit function in `accept.py` (R-16), so removing `C901` from the per-file ignore is safe once it is fixed.
- **Steps**:
  1. Introduce one small frozen carrier for the run, for example `@dataclass(frozen=True) class _AcceptRun` holding `json_output`, `tracker`, `repo_root`, `mission_slug`, `mission_dir`, `owned`, `actual_mode`, `commit_required`, `provenance_note`. Keep `owned` typed as whatever the current code uses at this point; T078 retypes it.
  2. Extract one error emitter, for example `_fail(run_or_json, message, *, code=1, tracker_step=None)`, replacing the eight near-identical "print JSON error or tracker error + console" blocks:
     - `accept.py:852-859` (missing `--mission`, exit 2);
     - `:897-903` and `:912-917` (merge-commit mode / evidence errors);
     - `:944-952`, `:953-960`, `:971-978` (summary collection errors);
     - `:1044-1052` (perform-acceptance error);
     - `:1109-1130` (stamp / PR merge / residual errors).
     It raises `typer.Exit(code)`. Preserve each block's exact message text and whether the tracker is rendered (Sonar S1192: one helper, not eight copies).
  3. Extract phase helpers, each ≤ 15 with a single responsibility (suggested names; keep them private):
     - `_resolve_accept_entry(...)` → `(repo_root, owned)`; owns the `ActionContextError` / `TaskCliError` handling at `:815-836`.
     - `_resolve_mission_identity(...)` → `(mission_slug, mission_dir)`; owns the exit-2 missing-handle branch (`:849-859`) and the owned/non-owned split (`:863-867`).
     - `_verify_merge_commit(...)` → `PrMergeEvidence | None` (`:888-917`).
     - `_collect_summary_or_exit(...)` → `AcceptanceSummary`; the three `except` arms (`:936-978`) collapse onto `_fail` via one `except (Pre30LayoutError, AcceptanceError, AcceptanceMatrixParseError)` **only if** the three arms behave identically (they do on the planning base; confirm).
     - `_exit_early_for_report_modes(...)` for diagnose / checklist / not-ok (`:982-1015`).
     - `_perform_and_finalize(...)` → a small `_FinalizeOutcome` dataclass (`result`, `accept_exc`, `stamp_exc`, `pr_merge_exc`, `residue_exc`, `pr_merge_recorded`); it owns the `try/except/finally` at `:1031-1107` and **keeps the same ordering**: stamp → PR merge → residual, with the residual commit still running after an `AcceptanceError`.
     - `_raise_on_finalize_errors(...)` (`:1108-1130`) and `_render_accept_result(...)` (`:1134-1159`).
  4. `accept()` itself becomes a linear sequence of those calls plus the Typer option declarations. The Typer signature, option names, help strings, defaults and metavars do **not** change (`cli_commands: manual_review` — no flag is renamed or removed).
  5. Remove `"C901"` from the `src/specify_cli/cli/commands/accept.py` entry at `ruff.toml:27`, leaving `["B904", "F401", "UP035"]`. `ruff.toml` is owned by WP10, so this is a **one-line out-of-map edit**. Put the rationale in the commit message and the Activity Log: "FR-026 / IC-14a: accept() decomposed to ≤15; its per-file C901 suppression is removed in the same WP that removes the violation (ruff.toml is WP10-owned; one-line out-of-map edit)." Do not touch any other `ruff.toml` line; the other three codes are out of scope.
  6. Commit as a pure refactor: `refactor(accept): decompose accept() to complexity ≤15 (WP14/T076, FR-026)`. No behaviour change and no owned-root conversion in this commit.
- **Files**:
  - `src/specify_cli/cli/commands/accept.py` — `accept` (`:740-1159`) and the new private helpers, placed above it.
  - `ruff.toml:27` — out-of-map, one line.
- **Parallel?**: No; depends on T075.
- **Validation checklist**:
  - [ ] `uv run --frozen ruff check --isolated --select C901 --config 'lint.mccabe.max-complexity=15' src/specify_cli/cli/commands/accept.py` reports nothing.
  - [ ] `uv run --frozen ruff check src/specify_cli/cli/commands/accept.py` is clean with the ignore removed.
  - [ ] The T075 file is green and unchanged; every accept test file in the Test Strategy list is green and unchanged.
  - [ ] `git diff` of the `accept()` Typer parameter block is empty apart from moved lines.
  - [ ] `_print_acceptance_result` (13 on the planning base) is not made more complex.
  - [ ] `uv run --frozen mypy --strict src/specify_cli/cli/commands/accept.py` is clean (new dataclasses fully typed).
- **Edge cases**:
  - `typer.Exit` raised inside a helper must propagate unchanged; do not wrap helpers in `try/except Exception`.
  - An `AcceptanceError` inside `perform_acceptance` still triggers the residual commit; an unexpected exception type from `perform_acceptance` still propagates after the `finally` ran. Keep both.
  - `assert result is not None` (`:1132`) becomes explicit narrowing on the outcome object, not a silently removed assert.
  - The three `# noqa: BLE001` handlers move with their code and keep their inline rationale.

### Subtask T077 – Stop re-validating at `accept.py:342`; consume the fact

- **Purpose**: FR-003 and `contracts/owned-checkout-carrier.md` §2: ownership is validated exactly once per command, and every downstream function receives the fact and never re-validates. `_stamp_birth_cutover_for_accept` still carries a fallback that re-runs `resolve_owned_mission` whenever it holds only an `effective_root` (`accept.py:336-342`). That fallback is also a gate G2 offender: a validator call outside `_owned_checkout.py` / `owned_mission.py`. The plan (IC-04) names this exact site: "`cli/commands/accept.py:342`: stop re-validating".
- **Steps**:
  1. Change the signature to `_stamp_birth_cutover_for_accept(repo_root: Path, mission_slug: str, *, owned: OwnedCheckout | None = None) -> None`.
  2. Delete the `effective_root` parameter, the whole `if owned is None and effective_root is not None:` block, and its local `from specify_cli.core.paths import resolve_canonical_root` import.
  3. Replace `scope = effective_root_kwargs(effective_root)` and `placement_seam(repo_root, mission_slug, **scope)` (`:320-321`) with the WP04 seam keyword: `placement_seam(repo_root, mission_slug, owned=owned)`.
  4. Replace `_coord_status_feature_dir(repo_root, mission_slug, **scope)` (`:334`) with `_coord_status_feature_dir(repo_root, mission_slug, owned=owned)`. That helper is converted in T078; do both in one commit, or convert the helper first.
  5. The `stamp_accept_cutover(..., **({"owned": owned} if owned is not None else {}))` call (`:344-348`): `stamp_accept_cutover` already defaults `owned=None`, so pass `owned=owned` as a plain keyword. If WP17 has not yet retyped it from the `OwnedMission` alias to `OwnedCheckout`, mypy may complain on the type; in that case keep the call as `owned=owned` and note the type bridge in the Activity Log for WP17/WP18.
  6. Keep the owned-versus-best-effort error semantics exactly:
     - owned → any stamp exception becomes `AcceptanceError("Owned birth-cutover failed: ...")`, and an unflipped result raises the same;
     - non-owned → `logger.warning(...)` and return;
     - `MissingMissionIdError` always propagates.
  7. Update the two comments that justify the fallback (`:335-338` and `:1073-1074`) so they say the fact comes from the CLI edge. Do not leave a comment describing a code path that no longer exists.
  8. Update the call site in the finalize helper from T076 to `_stamp_birth_cutover_for_accept(run.repo_root, run.mission_slug, owned=run.owned)`.
  9. Commit: `fix(accept): stamp birth-cutover from the CLI-edge fact, no re-validation (WP14/T077, FR-003)`. This commit is the first behaviour-relevant change after the T076 refactor; keep it small so the reviewer can see that only the fallback disappeared.
- **Files**:
  - `src/specify_cli/cli/commands/accept.py` — `_stamp_birth_cutover_for_accept` (planning-base `:266-362`) and its call site in the finalize helper from T076.
- **Parallel?**: No; after T076.
- **Validation checklist**:
  - [ ] `grep -n "resolve_owned_mission\|resolve_canonical_root" src/specify_cli/cli/commands/accept.py` returns nothing.
  - [ ] Positional callers still work: `tests/architectural/test_lifted_cli_accept_coord_surface_anchor.py:74` and `tests/specify_cli/cli/commands/test_accept_birth_cutover_seam.py:184` call `_stamp_birth_cutover_for_accept(repo_root, handle)` and pass unchanged.
  - [ ] `tests/integration/test_explicit_checkout_commands.py::test_accept_commits_metadata_matrix_and_cutover_only_in_owned` passes; it wraps the real `stamp_accept_cutover`.
  - [ ] `tests/specify_cli/cli/test_accept_birth_cutover.py` and `tests/architectural/test_lifted_cli_accept_birth_cutover.py` pass unchanged.
  - [ ] The T075 identity assertion (stamp receives the CLI-edge object) still holds.
  - [ ] G2 would no longer list `accept.py:342` (run WP01's scanner on the file, or grep: no `resolve_owned_mission(` anywhere in `accept.py` after T078).
- **Edge cases**:
  - A non-owned run passes `owned=None` all the way down; today's `**scope` is `{}`. The seam call with `owned=None` must be exactly equivalent to the old call without the keyword. Check WP04's seam: `owned=None` must select the non-owned arm.
  - `tests/architectural/test_single_mission_surface_resolver.py:341-347` pins that the COORD leg comes from `_coord_status_feature_dir`; keep that routing and do not inline the seam call.
  - The stamp is best-effort for non-owned missions, but for owned missions the command must fail; do not merge the two arms into one handler.

### Subtask T078 – Convert `accept.py` owned roots; option migration

- **Purpose**: FR-001 (no bare owned roots anywhere in `src/`); `contracts/cli-owned-checkout-surface.md` (all eight inline `--owned-checkout` declarations move onto the shared option, and `accept.py:763` is one of them); gate G2 (no direct validator call outside `_owned_checkout.py` / `owned_mission.py`).
- **Steps**:
  1. **Imports.** Replace the `specify_cli.core.owned_mission` import block (`:29-34`) with:
     - `from mission_runtime import OwnedCheckout` (public surface; MR-1/MR-2 forbid submodule imports);
     - `require_unstaged_index` from `specify_cli.core.owned_mission`;
     - `OwnedCheckoutOption`, `resolve_owned_or_adopt` (and `emit_owned_refusal` if used) from `specify_cli.cli.commands._owned_checkout`.
     Drop `effective_root_kwargs` and `OwnedMission`.
  2. **Option.** Replace the inline `owned_checkout: Annotated[Path | None, typer.Option("--owned-checkout", ...)]` at `:763` with `owned_checkout: OwnedCheckoutOption = None`. If WP08's help text differs from today's ("Explicit owned checkout for a single-branch mission."), the golden contract test decides: run `tests/specify_cli/cli/commands/agent/test_mission_cli_golden_contract.py` and report any drift in the Activity Log instead of editing goldens here.
  3. **Entry.** Rewrite `_owned_accept_context` (planning-base `:721-737`):
     - call `resolve_owned_or_adopt(...)` with `LIFECYCLE_OWNED_TOPOLOGIES` (accept is single_branch only per the CLI contract);
     - keep the `OWNED_OPTION_UNSUPPORTED` refusal for `--diagnose --normalize-encoding`;
     - keep `require_unstaged_index(owned)` for non-diagnose runs;
     - return `OwnedCheckout | None`.
     Route refusals through `emit_owned_refusal` **only if** it prints the same `{"error_code", "error"}` envelope accept prints today (`:826-831`); otherwise keep accept's own printing. The envelope keys are `serialized_keys: do_not_change`. Flagless runs follow FR-021 through the helper; from the repository root checkout they must behave exactly as today (`test_accept_without_opt_in_keeps_primary_resolution`).
  4. **Helpers.** Convert every parameter in the census table to `owned: OwnedCheckout | None = None` (keyword-only, default `None`, so positional test callers keep working):
     - `_coord_worktree_root` (`:120`), `_coord_status_feature_dir` (`:167`), `_coord_dirty_paths` (`:220`);
     - `_record_pr_merge_for_accept` (`:370`), `_commit_residual_acceptance_artifacts` (`:483`), `_collect_summary_with_optional_repair` (`:665`).
     Inside them, calls to `placement_seam` and `resolve_artifact_surface` use `owned=owned` (check that WP04 gave `resolve_artifact_surface` an `owned` keyword; if not, apply step 5's bridge). Delete every `scope = effective_root_kwargs(...)` local and every `**scope` / `**effective_root_kwargs(...)` splat.
  5. **Calls that leave `accept.py`.** These callees are converted by WPs that depend on this one (WP15 and WP17 land **after** WP14), so on your lane base they are not yet converted:
     - `collect_feature_summary`, `normalize_feature_encoding` — WP15 (`acceptance/__init__.py:1388`, `:1031`);
     - `verify_pr_merge_evidence`, `record_pr_merge_baseline_for_mission` — WP17 (`consolidation/baseline.py:497`, `:814`);
     - `stamp_accept_cutover` — WP17 (`migration/runtime_state_cutover.py:486`).
     Check each callee's signature on your lane base. If it already takes `owned`, pass `owned=owned`. If it still takes `effective_root`, pass the bridging expression `effective_root=owned.owned_root if owned else None` **as a plain keyword** (never a dict splat, never `effective_root_kwargs`). Mark each such call `# bridging: WP<n> converts`, naming the WP that owns the callee (WP15 or WP17), and also list every bridge (file:line, callee) in the Activity Log so the callee WP (WP15/WP17, which then flip this call as a one-line out-of-map edit) or WP18/T097 can flip it. This is the only form in which the identifier may survive in `accept.py`, and only until the callee converts.
  6. **Legacy attributes.** `owned.root` → `owned.owned_root` (`:825`, `:868`); `owned.slug` → `owned.mission_slug` and `owned.directory` → `owned.mission_dir` (`:864`).
  7. **Dict key.** Delete `scope = {"effective_root": owned.root} if owned is not None else {}` (`:868`) outright; the run carrier from T076 already holds `owned`.
  8. Commit: `refactor(accept): consume the validated OwnedCheckout fact end to end (WP14/T078)`.
- **Files**:
  - `src/specify_cli/cli/commands/accept.py` only (every census row).
- **Parallel?**: The committing-path count test (step 5) is written and committed red **before** T077; the rest runs after T077.
- **Validation checklist**:
  - [ ] The census commands print only the bridge lines listed in the Activity Log (ideally nothing).
  - [ ] `grep -n '"effective_root"' src/specify_cli/cli/commands/accept.py` prints nothing.
  - [ ] `uv run --frozen mypy --strict src/specify_cli/cli/commands/accept.py src/specify_cli/cli/commands/_owned_checkout.py src/specify_cli/acceptance/__init__.py src/specify_cli/consolidation/baseline.py src/specify_cli/migration/runtime_state_cutover.py` is clean. Pass them in **one** invocation: `pyproject.toml` sets `follow_imports = "skip"` for `specify_cli.*`, so a keyword mismatch between `accept.py` and a callee is only visible when both files are on the command line.
  - [ ] The T075 file is green; only the owned-entry patch target moved, in the shared fixture.
  - [ ] `tests/integration/test_explicit_checkout_commands.py -k accept` passes unchanged.
- **Edge cases**:
  - `repo_root` is reassigned to the owned root today (`:825`) and every later read uses it: `choose_mode(requested_mode, repo_root)`, `_primary_dirty_paths(repo_root, ...)`, `_commit_primary_residuals`. Keep that: the run carrier's `repo_root` is `owned.owned_root` when owned.
  - `_coord_worktree_root` compares `worktree_root.resolve() == repo_root.resolve()`; do not start comparing against `owned.repository_root`.
  - The owned refusal must still happen before any read or write (`_owned_accept_context` runs first); do not move validation later in the flow.

### Subtask T079 – FR-022 accept ratchet

- **Purpose**: FR-022 / SC-005: the existing owned accept tests and all non-owned accept tests pass **unchanged** after the rewire onto the single validator. This subtask is verification plus the one new assertion the ratchet needs: accept validates ownership exactly once (FR-003, NFR-002).
- **Steps**:
  1. Run the full accept list from the Test Strategy with no test-file edits. Any red that also reproduces on the planning base is baseline red: classify it per CLAUDE.md "Test-run baseline-red gotcha" and note it in the Activity Log; do not fix it here.
  2. Get the fixtures. The WP02 fixtures (`owned_checkouts`, `r_snapshot`) live in `tests/integration/conftest.py`, which pytest applies only under `tests/integration/`. From `tests/specify_cli/cli/commands/` import them explicitly and re-export them through `__all__`, the same pattern `tests/integration/test_owned_checkout_mark_status.py:13-22` uses for `checkouts` (this satisfies ruff F401 without a `noqa`). If WP02 documented a different sanctioned way to consume the fixtures outside `tests/integration/`, use that instead.
  3. Add one test to `tests/specify_cli/cli/commands/test_accept_decomposition.py` that counts ownership validations:
     - monkeypatch `specify_cli.core.checkout_ownership.resolve_ownership_claim` with a counting wrapper around the real function (the validator imports it lazily inside `resolve_owned_mission`, so the module-attribute patch is observed);
     - call `specify_cli.workspace.context.clear_workspace_resolution_caches()` first;
     - run an owned `accept --diagnose --json --owned-checkout P --mission <slug>` on the fixture;
     - assert the count is exactly 1 and the exit code is 0.
     Mark this test `integration` + `git_repo` (it builds real repositories), not `fast`.
  4. On the same run, assert the repository root checkout is untouched with the WP02 `r_snapshot` fixture (0 differences, NFR-001).
  5. **Mandatory committing-path count (`--mode local`, without `--diagnose`).** This is the path that re-validates at `accept.py:342`, so it carries the FR-003 red. Borrow the `ready_accept_checkouts` fixture shape from `tests/integration/test_explicit_checkout_commands.py:388-530` (a local helper in this file on top of the WP02 fixtures, never an import from that test module) so the fixture reaches `summary.ok`. Assert exactly **1** validation and exit 0. **Red-first as a commit:** this test is committed **before** T077's fix commit, and on that red commit it fails with count **2** (the CLI edge plus the stamp's re-validation); record the observed count in the red commit's message. The red commit precedes T077 in `git log`; the reviewer verifies it. No Activity-Log-only or stash-based proof.
  6. If any existing test **must** change, stop: that is a behaviour change, which FR-022 forbids. Record it in the Activity Log and ask the reviewer before editing a file you do not own.
- **Files**:
  - `tests/specify_cli/cli/commands/test_accept_decomposition.py` (append).
  - Read-only: `tests/integration/conftest.py` (WP02 fixtures); `tests/integration/test_explicit_checkout_commands.py:388-530` (owned accept scenarios, including the `ready_accept_checkouts` fixture you can borrow for step 5).
- **Parallel?**: No; last.
- **Validation checklist**:
  - [ ] Every file in the Test Strategy list is green, and `git diff --stat -- tests/ ':!tests/specify_cli/cli/commands/test_accept_decomposition.py'` is empty.
  - [ ] The committing-path count test was committed red (count 2) before T077 and is green (count 1) after it.
  - [ ] Mutation check (non-vacuity): re-adding a second `resolve_owned_mission` call turns both count tests red (count 2); revert it and record the check in the Activity Log.
  - [ ] The exactly-once test fails if you temporarily bypass validation (count 0).
  - [ ] Record the exact pytest command and pass counts for the whole accept list in the Activity Log (PR *Tests run* section).
- **Edge cases**:
  - The diagnose path does not call `require_unstaged_index`, so the owned diagnose run must succeed even with staged changes in the owned checkout; do not stage anything in the fixture to "help" it.
  - Workspace-resolution caches are process-global; clear them before counting or a warm cache from an earlier test hides a second validation.
  - Flagless accept from the repository root checkout must perform **zero** validations; add that negative assertion alongside the positive one.
  - The counting wrapper must delegate to the real function and return its result unchanged; a stub that returns a fake claim would let a broken validator pass.
  - Keep the owned test independent of test order (no module-level state); the characterisation tests in the same file monkeypatch module attributes and must not leak into it.

## Test Strategy

Targeted tests (run all; none of the existing files may change):

```bash
uv run --frozen pytest -q \
  tests/specify_cli/cli/commands/test_accept_decomposition.py \
  tests/integration/test_explicit_checkout_commands.py -k accept \
  tests/specify_cli/cli/commands/test_accept_birth_cutover_seam.py \
  tests/specify_cli/cli/commands/test_accept_clean_tree.py \
  tests/specify_cli/cli/commands/test_accept_guidance_liveness.py \
  tests/specify_cli/cli/commands/test_accept_lenient_help.py \
  tests/specify_cli/cli/commands/test_accept_merge_commit.py \
  tests/specify_cli/cli/commands/test_accept_normalize_encoding.py \
  tests/specify_cli/cli/commands/test_accept_readiness_no_write.py \
  tests/specify_cli/cli/commands/test_accept_residual_partition.py \
  tests/specify_cli/cli/commands/test_accept_stranded_verdict_note.py \
  tests/specify_cli/cli/commands/test_accept_warnings_render.py \
  tests/specify_cli/cli/commands/test_accept_guard.py \
  tests/specify_cli/cli/commands/test_issue_4891_accept_missing_lanes.py \
  tests/specify_cli/cli/commands/test_bare_modern_slug_ambiguity_cli.py \
  tests/specify_cli/cli/commands/test_lifecycle_read_seam_migration.py \
  tests/specify_cli/cli/test_accept_birth_cutover.py \
  tests/specify_cli/cli/test_accept_coord_surface_anchor.py \
  tests/specify_cli/test_accept_no_commit_readonly.py \
  tests/specify_cli/test_acceptance_regressions.py \
  tests/specify_cli/acceptance/test_accept_idempotency.py \
  tests/specify_cli/acceptance/test_accept_contracts_dedup.py \
  tests/regressions/test_issue_4968_accept_encoding.py \
  tests/integration/test_accept_matrix_coord_partition.py \
  tests/agent/test_commands.py
```

Specific architectural gates implicated by `accept.py` (run these files, not the directory):

```bash
uv run --frozen pytest -q \
  tests/architectural/test_lifted_cli_accept_coord_surface_anchor.py \
  tests/architectural/test_single_mission_surface_resolver.py \
  tests/architectural/test_cli_error_surface_seam.py \
  tests/architectural/test_owned_checkout_gate_selftest.py \
  tests/architectural/test_ruff_format_enforcement.py
```

Baseline and quality gates:

```bash
make test-fast
uv run --frozen ruff check src/specify_cli/cli/commands/accept.py tests/specify_cli/cli/commands/test_accept_decomposition.py ruff.toml
uv run --frozen ruff format --check src/specify_cli/cli/commands/accept.py tests/specify_cli/cli/commands/test_accept_decomposition.py
uv run --frozen mypy --strict src/specify_cli/cli/commands/accept.py src/specify_cli/cli/commands/_owned_checkout.py src/specify_cli/acceptance/__init__.py src/specify_cli/consolidation/baseline.py src/specify_cli/migration/runtime_state_cutover.py tests/specify_cli/cli/commands/test_accept_decomposition.py
```

Record the exact commands and pass/fail counts in the Activity Log and the PR's *Tests run* section. A passing test run does not replace the mypy result: a mypy failure fails the WP.

## Risks & Mitigations

- **Silent behaviour drift during decomposition.** Mitigation: T075 lands first and green; T076 is a separate refactor-only commit; reviewers diff behaviour against the T075 file, not against intuition.
- **`finally`-block ordering.** The residual commit must still run after an `AcceptanceError`, and the stamp must run before the residual commit so its writes are swept into it (R4 in the docstring). Mitigation: the call-order assertions in T075.
- **Callee conversion after this WP (WP15, WP17).** Both depend on WP14 and convert functions `accept.py` calls. Mitigation: T078 step 5 bridges each such call and logs it; WP15/WP17 flip the call when they convert the callee; WP18/T097 removes any leftover.
- **mypy blind spot.** `follow_imports = "skip"` for `specify_cli.*` hides cross-module signature errors unless both files are checked together. Mitigation: the single multi-file mypy command above.
- **Help-text or envelope drift from the shared helper.** Mitigation: T078 step 2/3; the golden-contract test is the arbiter.

## Review Guidance

- Confirm the T075 commit precedes the T076 commit and that the T075 file did not change in T076 (except the one fixture patch target in T078).
- Run `uv run --frozen ruff check --isolated --select C901 --config 'lint.mccabe.max-complexity=15' src/specify_cli/cli/commands/accept.py` yourself; expect no output.
- Check the `ruff.toml` diff is exactly one line (C901 removed from the `accept.py` entry) and carries the out-of-map rationale.
- Grep for `effective_root`, `effective_root_kwargs`, `OwnedMission`, `resolve_owned_mission` and legacy attribute reads in `accept.py`; anything left must be a logged bridge to an unconverted callee.
- Confirm no existing test file changed (`git diff --stat -- tests/ ':!tests/specify_cli/cli/commands/test_accept_decomposition.py'` is empty).
- Confirm the implementer ran the multi-file mypy command and it passed.
- Terminology: new prose says "owned checkout" / "repository root checkout", never "feature".

## Activity Log

> **CRITICAL**: Activity log entries MUST be in chronological order (oldest first, newest last).

### How to Add Activity Log Entries

**When adding an entry**:

1. Scroll to the bottom of this Activity Log section
2. **APPEND the new entry at the END** (do NOT prepend or insert in middle)
3. Use exact format: `- YYYY-MM-DDTHH:MM:SSZ – agent_id – <action>`
4. Timestamp MUST be current time in UTC (check with `date -u "+%Y-%m-%dT%H:%M:%SZ"`)
5. Agent ID should identify who made the change (claude-sonnet-4-5, codex, etc.)

**Format**:

```
- YYYY-MM-DDTHH:MM:SSZ – <agent_id> – <brief action description>
```

**Initial entry**:

- 2026-09-28T15:00:00Z – system – Prompt created.

---

### Updating Status

Status is managed via `status.events.jsonl`. Use `spec-kitty agent tasks move-task <WPID> --to <status>` to change WP status.
- 2026-09-29T09:06:30Z – claude – shell_pid=18745 – Blocked (awaiting decision, all code committed): flagless adoption via resolve_owned_or_adopt makes tests/integration/test_explicit_checkout_commands.py::test_accept_without_opt_in_keeps_primary_resolution red (that test runs flagless FROM the owned checkout, not from the repository root checkout). FR-021 vs FR-022; not adapting the test. Also: dispatch's expected red count 2 is not reproducible on the lane base (count is 1); conditional owned kwargs kept for non-owned call shapes (3 existing test doubles pin them).
- 2026-09-29T09:20:06Z – claude – shell_pid=18745 – Rulings applied: flagless test split (adoption row red at d503bc309), owned kwarg unconditional + test doubles updated, OwnedRefusalCode gained OWNED_OPTION_UNSUPPORTED/OWNED_INPUT_INVALID. Bridges G4=5 (marked), G5=0, G2/mint/claim=0. Held before for_review: emit_owned_refusal cannot reproduce accept's current refusal byte format (compact JSON vs indent=2; stdout '[red]code: msg[/red]' vs stderr 'Error: [code] msg'); awaiting coordinator.
- 2026-09-29T09:23:33Z – claude – shell_pid=18745 – PR body: accept owned refusals now go through emit_owned_refusal. JSON keys/codes unchanged; JSON whitespace is indent=2 and the human lane is 'Error: [CODE] msg' on stderr (was '[red]CODE: msg[/red]' on stdout). Also: flagless test split (FR-021 adoption row / FR-022 control); OwnedRefusalCode gained OWNED_OPTION_UNSUPPORTED, OWNED_INPUT_INVALID; 5 bridges (WP15 x3, WP17 x2); out-of-map: ruff.toml, mission_runtime/owned_checkout.py, 7 test files.
