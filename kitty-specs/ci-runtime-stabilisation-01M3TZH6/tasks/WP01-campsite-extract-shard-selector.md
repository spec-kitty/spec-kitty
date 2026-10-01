---
work_package_id: WP01
title: 'Campsite: extract the shard selector without behaviour change'
dependencies: []
requirement_refs:
- FR-005
- C-010
planning_base_branch: issue-5510-ci-runtime-stabilisation
merge_target_branch: issue-5510-ci-runtime-stabilisation
branch_strategy: Planning artifacts for this mission were generated on issue-5510-ci-runtime-stabilisation. During /spec-kitty.implement this WP may branch from a dependency-specific base, but completed changes must merge back into issue-5510-ci-runtime-stabilisation unless the human explicitly redirects the landing branch.
subtasks:
- T001
- T002
- T003
- T004
- T005
phase: Phase 1 - Foundations
history:
- at: '2026-10-01T07:30:00Z'
  actor: system
  action: Prompt generated via /spec-kitty.tasks
agent_profile: python-pedro
authoritative_surface: scripts/ci/
create_intent:
- scripts/ci/shard_select.py
- tests/ci/test_shard_select.py
execution_mode: code_change
model: claude-sonnet-5-5
owned_files:
- scripts/ci/shard_select.py
- tests/ci/test_shard_select.py
- .github/workflows/module-tests.yml
- scripts/ci/capture_shard_timings.py
- tests/ci/test_capture_shard_timings.py
- scripts/ci/recapture_charter_shard_timings.py
- .github/workflows/ci-charter-shard-recapture.yml
- tests/architectural/test_module_shard_registry.py
role: implementer
tags: []
task_type: implement
tracker_refs: []
---

# Work Package Prompt: WP01 – Campsite: extract the shard selector without behaviour change

## ⚡ Do This First: Load Agent Profile

Use the `/ad-hoc-profile-load` skill to load the agent profile specified in the frontmatter (or any user-defined profile), and behave according to its guidance before parsing the rest of this prompt.

- **Profile**: `python-pedro`
- **Role**: `implementer`
- **Agent/tool**: `claude`

If no profile is specified, run `spec-kitty agent profile list` and select the best match for this work package's `task_type` and `authoritative_surface`.

---

## ⚠️ IMPORTANT: Review Feedback

**Read this first if you are implementing this task!**

- **Has review feedback?**: Check the `review_ref` field in the event log (via `spec-kitty agent tasks status` or the Activity Log below).
- **You must address all feedback** before your work is complete. Feedback items are your implementation TODO list.
- **Report progress**: As you address each feedback item, update the Activity Log explaining what you changed.

---

## Review Feedback

*[If this WP was returned from review, the reviewer feedback reference appears in the Activity Log below or in the status event log.]*

---

## Markdown Formatting

Wrap HTML/XML tags in backticks: `` `<div>` ``, `` `<script>` ``
Use language identifiers in code blocks: ````python`,````bash`

---

## Objectives & Success Criteria

This is a **tidy-first** work package (charter Standing Order #2, campsite cleaning). It changes
**no shard assignment** anywhere. It moves the one live LPT shard selector out of an inline
workflow heredoc into an importable, tested module so later work packages (WP02 loud mismatch +
file granularity, WP05 battery partition plugin) extend one authority instead of copying it
(C-010, research D-01).

Done means:

1. `scripts/ci/shard_select.py` exists, stdlib-only at import time, and holds:
   - `MODULE_SELECTION_MARKER_EXPR = "not performance and not stress"` — the single marker
     authority for module-row selection;
   - `lpt_assign(...)` — the greedy LPT algorithm, byte-identical in output to the heredoc;
   - `lpt_loads(...)` — bin loads for the registry skew gate;
   - a `module` CLI subcommand that reproduces the heredoc step exactly.
2. `.github/workflows/module-tests.yml` step `select` calls the module; the inline `<<'PY'`
   heredoc is gone.
3. `tests/architectural/test_module_shard_registry.py::_lpt_bin_pack` delegates to `lpt_loads`.
4. `scripts/ci/capture_shard_timings.py` selects with the shared constant
   (`not performance and not stress`), closing the drifted `"not performance"` copy.
5. The stale "latent selection mismatch" prose in `recapture_charter_shard_timings.py` and
   `ci-charter-shard-recapture.yml` is rewritten to describe the aligned state.
6. A characterization test proves identical shard assignment for **every** registry module row
   at its `shard_count`, over the committed `.github/ci-shard-timings.json`.

FR-005's *loud* mismatch is **not** in this WP (WP02). Here the uniform-weight fallback stays
silent, exactly as today — that is what "no behaviour change" means.

## Context & Constraints

- Read first: `.kittify/charter/charter.md`; `kitty-specs/ci-runtime-stabilisation-01M3TZH6/tasks.md`
  (global rules); `research.md` decision log D-01, D-18, D-20, D-25, D-31, D-33 and R1 §1 "D-SEL";
  `contracts/battery-partition.md` ("Single sources" → Selector); `plan.md` IC-01.
- **No local heavy suites** (C-009): never run `pytest tests/architectural` as a whole or
  `make test-full`. Run the specific gate files listed under Test Strategy.
- **Lane discipline**: in a lane worktree use `uv run --frozen …`; never `git stash`.
- **Terminology**: "Mission", never "feature"; say "gate selection" or "CI path routing", never
  bare "routing".
- **Workflow count** is 17/20 — add no workflow file.
- Python 3.11+, `ruff` + `mypy --strict` clean, functions ≤ 15 cyclomatic complexity (Sonar
  S3776 / ruff C901). Repeated literals (≥ 3 uses) become module constants.

### Current-state anchors (verified 2026-10-01 at `00d94d0af9`)

| What | Where |
|---|---|
| Inline selector step | `.github/workflows/module-tests.yml`, job `test`, step `id: select` "Select this shard's tests (greedy-LPT bin-packing over the registry shard structure)", lines 169-266 |
| Heredoc invocation | line 183: `"$venv_python" - "$module" "$idx" "$total" "$venv_python" "$registry_test_dirs" <<'PY'` |
| Test-dir resolution | lines 192-206 (registry `test_dirs` JSON, keep only existing dirs, else `tests/{module}`; exit 64 with `::error::` if none) |
| Collect-only | lines 221-227: `[venv_python, "-m", "pytest", *test_dirs, "-m", "not performance and not stress", "--collect-only", "-q"]`, `check=True`; node ids = lines containing `"::"`; exit 64 on zero |
| Silent fallback | lines 251-252: `if len(durations) != len(node_ids): durations = [1.0] * len(node_ids)` (the #5092 defect, fixed loudly in WP02) |
| LPT core | lines 254-260: `sorted(zip(node_ids, durations), key=lambda p: p[1], reverse=True)`; least-loaded bin via `min(range(total), key=lambda k: loads[k])` (lowest index wins ties) |
| Output | lines 262-265: writes `shard_tests.txt` (newline-joined, no trailing newline) and prints `module-tests: selected X/Y tests for M shard i/n` |
| Run-step marker (stays literal) | line 348: `-m "not performance and not stress"` in step "Run pytest for this shard" — do **not** touch this step; the gate model parses it |
| Algorithm twin | `tests/architectural/test_module_shard_registry.py:108-120` `_lpt_bin_pack(durations, n) -> list[float]`, used by `test_inter_shard_skew_within_twenty_percent` (:269) |
| Drifted marker | `scripts/ci/capture_shard_timings.py:76` `SELECTION_MARKER_EXPR = "not performance"`; docstring lines 14-25 misquote the consumer's selection |
| Length-gate copy | `tests/architectural/test_module_length_agreement.py:111` `_CONSUMER_MARKER_EXPR` (WP02 re-points it; not owned here) |
| Recapture tests (post-#5503, D-37) | `tests/ci/test_recapture_charter_shard_timings.py:479` `test_pr_body_template_renders_substitutions_and_names_timings_file` and `:492` `test_run_capture_phase_invokes_capture_shard_timings_with_module_charter` replaced the verbatim PR-body / commit-message / `MODULE` copy-pins; the second stubs `capture_shard_timings.main` and asserts its argv starts `["--module", "charter"]`. `recapture_charter_shard_timings.py` itself is byte-identical across the rebase, so the line anchors in this table still hold; T004 must keep `capture_shard_timings.main` the seam that `run_capture_or_die` (`:186`) calls |
| Stale prose | `scripts/ci/recapture_charter_shard_timings.py:60-68` bullet "Latent selection mismatch"; `.github/workflows/ci-charter-shard-recapture.yml:69-71` "the capture selects `-m "not performance"` … (latent risk)" |

### Import constraints you must respect

- `capture_shard_timings.py` is run as a **bare script** and is loaded **by file path** in tests.
  `tests/ci/test_capture_shard_timings.py::test_script_help_works_without_installed_package`
  runs it with `python -I -S scripts/ci/capture_shard_timings.py --help` from a temp cwd: no site
  packages, no cwd on `sys.path`. So:
  - `shard_select.py` must import **only the standard library at module level** (import `yaml`
    lazily inside functions if you ever need it);
  - `capture_shard_timings.py` must put the repository root on `sys.path` before
    `from scripts.ci.shard_select import MODULE_SELECTION_MARKER_EXPR`, using the guarded pattern
    already in `recapture_charter_shard_timings.py:116-123`
    (`if str(REPO_ROOT) not in sys.path: sys.path.insert(0, str(REPO_ROOT))`).
- `module-tests.yml` invokes the selector with `"$venv_python" -m scripts.ci.shard_select …` from
  the checkout root. Module mode (`-m`) puts cwd on `sys.path`; `scripts/` is a namespace package
  (no `__init__.py`), the same as `ci-fleet-verdict.yml`'s `python3 -m scripts.ci.fleet_main`.
  `tests/ci/test_workflow_script_import_guard.py` only polices bare-script invocations, so `-m` is
  safe.
- Tests import it as `from scripts.ci.shard_select import …` (precedent:
  `tests/architectural/test_gate_selection_authority.py:24`).

## Branch Strategy

- **Strategy**: {{branch_strategy}}
- **Planning base branch**: {{planning_base_branch}}
- **Merge target branch**: {{merge_target_branch}}

> These fields are populated automatically by `spec-kitty agent mission finalize-tasks`.
> Do NOT change them manually unless you are certain the branch topology has changed.

## Subtasks & Detailed Guidance

### Subtask T001 – Red-first: characterization test pinning current module-row shard assignments

- **Purpose**: Prove, before any code moves, that the extracted algorithm assigns every test of
  every registry module row to the same shard as the inline heredoc. This is the WP's only real
  risk (a silent module-row reshuffle), so the guard comes first (ATDD, charter ATDD-First Discipline).
- **Steps**:
  1. Create `tests/ci/test_shard_select.py` with `pytestmark = pytest.mark.fast`.
  2. Embed the legacy algorithm **verbatim** as a private reference function, copied from
     `module-tests.yml` lines 244-262 (the uniform fallback, the `sorted(zip(...), reverse=True)`
     pairing, the `min(range(total), key=...)` loop), with a comment naming its origin and the
     commit it was copied from. It is a frozen oracle; never "tidy" it.
  3. Parametrize over every row of `.github/ci-module-registry.yml` `modules[]` (load with
     `yaml.safe_load` inside the test). For each row, build synthetic node ids
     `[f"{module}::t{i}" for i in range(n)]` where `n == len(module_test_durations[module])`,
     run the reference and `lpt_assign` for every `idx in 1..shard_count`, assert identical
     ordered lists.
  4. Add a mismatch row: synthetic ids of length `n + 7` against the committed durations, so the
     uniform-fallback path is pinned too.
  5. Add a seeded randomized property test (`random.Random(5510)`, 200 cases, 1-400 items,
     1-8 bins, durations drawn with deliberate ties, e.g. from `[0.0, 0.5, 1.0, 1.0, 2.5]`):
     reference == `lpt_assign`. Ties are where a "cleaner" sort would drift.
  6. Add a workflow-shape test: parse `module-tests.yml` with `yaml.safe_load`, find step
     `id: select` in job `test`, and assert its `run` contains `-m scripts.ci.shard_select module`
     and does **not** contain `<<'PY'`. Also assert the "Run pytest for this shard" step's
     literal `-m "…"` value equals `MODULE_SELECTION_MARKER_EXPR` (selector and runner can never
     drift apart again).
  7. Run it: it must fail with `ModuleNotFoundError: No module named 'scripts.ci.shard_select'`
     (and the shape test fails on the heredoc). Commit this red state first.
- **Files**: `tests/ci/test_shard_select.py` (new).
- **Parallel?**: No — it gates T002/T003.
- **Notes**: Do not collect real module trees in this test; committed timings make it
  deterministic and sub-second. The real-collection equivalence check is a one-off in T003.

### Subtask T002 – Extract `scripts/ci/shard_select.py`

- **Purpose**: One importable selector (D-01). Test granularity only in this WP; WP02 adds file
  granularity, loud mismatch reporting and `enumerate_base_files`.
- **Steps**:
  1. Module docstring: what it is, the C-010 single-authority rule, and that `module-tests.yml`,
     `capture_shard_timings.py`, `test_module_length_agreement.py` (WP02) and
     `test_module_shard_registry.py` consume it. Declare `__all__`.
  2. Public API (pure, typed):
     - `MODULE_SELECTION_MARKER_EXPR: Final = "not performance and not stress"`.
     - `lpt_assign(items: Sequence[tuple[str, float]], bins: int) -> list[list[str]]` — stable
       sort by weight descending over the caller's order, least-loaded bin, lowest index on
       ties. `bins < 1` raises `ValueError`.
     - `lpt_loads(weights: Sequence[float], bins: int) -> list[float]` — same placement rule,
       returns loads. It must reproduce `_lpt_bin_pack` exactly (equal weights are
       interchangeable, so the loads match whatever the tie order).
     - `positional_weights(node_ids: Sequence[str], durations: Sequence[float]) -> list[float]`
       — returns `durations` when lengths match, else `[1.0] * len(node_ids)`. In this WP it is
       silent; WP02 makes it return a mismatch record and report it.
     - `resolve_module_test_dirs(module: str, registry_test_dirs_json: str) -> list[str]` —
       the heredoc's lines 192-203, unchanged semantics (empty or missing JSON → `[]`; keep only
       existing dirs; fallback `tests/{module}` if it exists).
  3. CLI: `main(argv: Sequence[str] | None = None) -> int` with `argparse` subcommand `module`:
     `--module`, `--shard i/n`, `--test-dirs` (raw JSON string, may be empty), `--python`
     (interpreter used for the collect-only subprocess), `--timings`
     (default `.github/ci-shard-timings.json`, relative to cwd as today), `--out`
     (default `shard_tests.txt`). Reproduce exactly: the same collect-only argv (built from
     `MODULE_SELECTION_MARKER_EXPR`), the `"::" in line` filter, `check=True`, the two
     `::error::module-tests: …` messages with exit 64, `FileNotFoundError` → empty durations,
     output file content, and the final print line. Keep `main` thin; each phase is a helper.
  4. `if __name__ == "__main__": raise SystemExit(main())`.
  5. `uv run --frozen mypy --strict scripts/ci/shard_select.py` and ruff clean.
- **Files**: `scripts/ci/shard_select.py` (new).
- **Parallel?**: After T001.
- **Notes**: Do not mention `make test-fast`, `ci-quality.yml` or `sonarcloud` in this module's
  text: `scripts/ci/derive_pinning_inventory.py` scans `scripts/` and `tests/` for those
  subjects and would add a rule to `tests/release/pinning_rule_inventory.json`.

### Subtask T003 – Switch `module-tests.yml` to the script; reuse it from `_lpt_bin_pack`

- **Purpose**: Remove the duplicate algorithm (C-010) without changing a single assignment.
- **Steps**:
  1. Replace the body of step `id: select` (keep its `name`, `id`, `shell` and `env` block) with:
     ```bash
     set -euo pipefail
     venv_python="${{ steps.warmup.outputs.venv-path }}/bin/python"
     "$venv_python" -m scripts.ci.shard_select module \
       --module "$MODULE" \
       --shard "${{ steps.shard-info.outputs.idx }}/${{ steps.shard-info.outputs.total }}" \
       --test-dirs "$TEST_DIRS" \
       --python "$venv_python" \
       --out shard_tests.txt
     ```
     Keep the existing comment about why the selection deselects performance and stress, moved
     above the command (shortened, pointing at `shard_select.MODULE_SELECTION_MARKER_EXPR`).
     Do not add `env:` variables in command position: `test_no_duplicate_suite_execution.py`
     refuses a step whose command word is a declared `env:` name. `$venv_python` is a shell
     variable assigned in the script, the same as today.
  2. In `tests/architectural/test_module_shard_registry.py`, keep the name `_lpt_bin_pack`
     (the registry's charter comment cites it) but make its body
     `return lpt_loads(durations, n)` with `from scripts.ci.shard_select import lpt_loads`.
     Update its docstring: it now reuses the shared selector (C-010); the skew gate's
     independence is about not trusting the registry's *claim*, not about retyping the algorithm.
  3. One-off real-collection equivalence (not a committed test; record the result in the Activity
     Log). From the planning base, extract the old heredoc and run old vs new for three small
     modules, then diff:
     ```bash
     base=$(git merge-base HEAD issue-5510-ci-runtime-stabilisation)   # the planning base
     git show "$base":.github/workflows/module-tests.yml \
       | awk "/<<'PY'/{f=1;next}/^ *PY$/{f=0}f" | sed 's/^          //' > /tmp/old_select.py
     for spec in "kernel 1 1" "next 1 2" "next 2 2" "glossary 1 1"; do
       set -- $spec
       dirs=$(uv run --frozen python -c "import yaml,json;r=yaml.safe_load(open('.github/ci-module-registry.yml'));row=[m for m in r['modules'] if m['module']=='$1'][0];print(json.dumps(row.get('test_dirs') or []))")
       uv run --frozen python /tmp/old_select.py "$1" "$2" "$3" "$(uv run --frozen which python)" "$dirs" && mv shard_tests.txt /tmp/old.txt
       uv run --frozen python -m scripts.ci.shard_select module --module "$1" --shard "$2/$3" --test-dirs "$dirs" --python "$(uv run --frozen which python)" --out /tmp/new.txt
       cmp /tmp/old.txt /tmp/new.txt && echo "identical: $spec"
     done
     ```
     These are module collect-only runs, not test runs; they are within C-009. Delete
     `/tmp/old_select.py` and any stray `shard_tests.txt` afterwards (never commit them).
- **Files**: `.github/workflows/module-tests.yml`, `tests/architectural/test_module_shard_registry.py`.
- **Parallel?**: After T002.
- **Notes**: Do not touch the "Run pytest for this shard" step (gate model parses its literal
  `-m`; `test_dual_mode_contract.py:217-240` pins its exit propagation). `module-tests.yml` is a
  reusable workflow, so the change reaches every module row; T001's characterization is what
  makes that safe.

### Subtask T004 – One marker-expression constant; `capture_shard_timings.py` imports it

- **Purpose**: Close the drift research D-18/R3 §3.6 found: the capture selects
  `-m "not performance"` while the consumer selects `-m "not performance and not stress"`. For any
  module with stress tests (status today) the capture records a list the consumer never collects,
  so the positional pairing degrades to uniform weights by construction.
- **Steps**:
  1. In `capture_shard_timings.py`, after the existing `sys.path.insert(0, str(REPO_ROOT / "src"))`,
     add the guarded repo-root insert and
     `from scripts.ci.shard_select import MODULE_SELECTION_MARKER_EXPR  # noqa: E402`
     (the existing `kernel.clock` import already carries the same justified `E402`).
  2. Keep the public name for compatibility (`recapture_charter_shard_timings.py`, the tests and
     the provenance field use it): `SELECTION_MARKER_EXPR = MODULE_SELECTION_MARKER_EXPR`, with a
     comment that the shared constant is the authority.
  3. Rewrite docstring lines 14-25 so they quote the consumer correctly
     (`-m "not performance and not stress"`, via `scripts/ci/shard_select.py`).
  4. Add a test to `tests/ci/test_capture_shard_timings.py`:
     `capture_shard_timings.SELECTION_MARKER_EXPR == MODULE_SELECTION_MARKER_EXPR` and
     `_pytest_argv(("tests/x",))` carries it after `-m`. The existing
     `test_script_help_works_without_installed_package` must stay green (it is the proof that
     the repo-root insert and the stdlib-only rule hold).
- **Files**: `scripts/ci/capture_shard_timings.py`, `tests/ci/test_capture_shard_timings.py`.
- **Parallel?**: Yes, alongside T003 once T002 exists.
- **Notes**: Charter's committed list (6641) is unaffected: no charter/doctrine test is
  `stress`-marked. Do **not** recapture any module here; WP03 recaptures consolidation.

### Subtask T005 – Fix the stale "latent selection mismatch" prose

- **Purpose**: Campsite (D-33). After T004 the documented latent risk no longer exists; leaving
  the warning makes the next reader chase a non-problem.
- **Steps**:
  1. `scripts/ci/recapture_charter_shard_timings.py:60-68`: replace the "Latent selection
     mismatch" bullet with a short statement that capture and the length gate share
     `scripts/ci/shard_select.MODULE_SELECTION_MARKER_EXPR` (#5510), so the recorded length is
     the length the gate collects.
  2. `.github/workflows/ci-charter-shard-recapture.yml:69-71`: same change in the header comment's
     "Known limitations" list (drop the bullet or restate it as resolved).
  3. Leave lines 26 and 41 ("`agent`, the only other non-allowlisted module") alone; WP03 updates
     them when consolidation leaves the allowlist.
  4. Run `tests/ci/test_recapture_charter_shard_timings.py` to confirm no docstring or workflow
     text is pinned (since #5503 the file pins behaviour — rendered substitutions and the
     `--module charter` argv — not wording, so a prose-only edit cannot red it).
- **Files**: `scripts/ci/recapture_charter_shard_timings.py`, `.github/workflows/ci-charter-shard-recapture.yml`.
- **Parallel?**: Yes.
- **Notes**: Comment-only workflow edit; no job, trigger or step changes.

## Test Strategy

Red-first order: T001 commit (red) → T002/T003/T004 (green) → T005.

Local validation (all must pass; record exact commands and pass/fail counts in the PR body):

```bash
uv run --frozen pytest tests/ci/test_shard_select.py tests/ci/test_capture_shard_timings.py \
  tests/ci/test_recapture_charter_shard_timings.py tests/ci/test_workflow_script_import_guard.py -q
uv run --frozen pytest tests/architectural/test_module_shard_registry.py \
  tests/architectural/test_module_tests_matrix.py tests/architectural/test_dual_mode_contract.py \
  tests/architectural/test_no_duplicate_suite_execution.py \
  tests/architectural/test_coverage_artefact_contract.py -q
uv run --frozen pytest tests/architectural/test_module_length_agreement.py -m fast -q
make test-fast
uv run --frozen ruff check scripts/ci tests/ci tests/architectural/test_module_shard_registry.py
uv run --frozen ruff format --check .
uv run --frozen mypy --strict scripts/ci/shard_select.py scripts/ci/capture_shard_timings.py
python3 scripts/ci/derive_pinning_inventory.py --check
```

- `make test-fast` does not cover `tests/ci` (it is not in `FAST_TIER_DIRS`); the explicit
  `tests/ci` run above is mandatory.
- The pinning-inventory `--check` is green on base `bc826fcbcb` (#5523 fixed by `e3794ded2d`, CLOSED; D-37). This WP must keep it green — add **no**
  delta (confirm with `python3 scripts/ci/derive_pinning_inventory.py --check`; on a red, diff
  `--stdout` against the base and record the rules for WP19). **Never regenerate the inventory in
  this WP** (tasks.md Global rules: only the lane-a WPs that edit pinned files regenerate it —
  WP06 first — and WP19 does the final regeneration, D-25).
- `test_module_length_agreement.py`'s slow tests collect every module tree; run only its
  `-m fast` subset here (WP02/WP03 run the full file).

## Risks & Mitigations

- **Silent reshuffle of module rows** — T001 (characterization over every row + ties) and the
  T003 one-off real-collection diff. Any difference blocks the WP.
- **`-I -S` bare-script import breaks** — stdlib-only module scope plus the guarded repo-root
  insert; `test_script_help_works_without_installed_package` proves it.
- **Gate-model blindness** — the selector step only runs `--collect-only`, and the runner step is
  untouched, so the duplicate-suite and dual-mode gates see the same suite executions as before;
  T003 re-runs both.
- **Pinning inventory drift** — new text must not name the inventory's subjects
  (`make test-fast`, `ci-quality.yml`, `sonarcloud`).

## Review Guidance

- **Red on planning base, green on WP tip**: check out the T001 commit alone and run
  `tests/ci/test_shard_select.py` (red: import error and heredoc shape); then the tip (green).
- Read the embedded reference algorithm against `git show <base>:.github/workflows/module-tests.yml`
  lines 244-262: it must be a verbatim copy.
- Confirm the Activity Log records the T003 one-off `cmp` results for kernel, next 1/2, next 2/2,
  glossary.
- Confirm the "Run pytest for this shard" step is byte-identical to the base.
- Confirm `SELECTION_MARKER_EXPR` now equals `"not performance and not stress"` and the
  recapture prose no longer warns about a mismatch.
- Confirm `ruff`, `ruff format --check` and `mypy --strict` were run and are clean.
- FR/C mapping: C-010 (one selector, one marker constant), FR-005 (enabler: the selector WP02
  makes loud).

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

- 2026-10-01T07:30:00Z – system – Prompt generated via /spec-kitty.tasks

---

### Updating Status

Status is managed via `status.events.jsonl`. Use `spec-kitty agent tasks move-task <WPID> --to <status>` to change WP status.
