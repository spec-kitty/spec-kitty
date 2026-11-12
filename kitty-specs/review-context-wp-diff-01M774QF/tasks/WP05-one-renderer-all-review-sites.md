---
work_package_id: "WP05"
title: "One renderer for every review render site, driven by acceptance tests"
dependencies: ["WP02", "WP03", "WP04"]
requirement_refs: ["FR-008", "FR-012", "NFR-001", "C-001", "C-002", "C-004", "C-010", "SC-001", "SC-002", "SC-003"]
subtasks: ["T022", "T023", "T024", "T025", "T026", "T027", "T028"]
owned_files: ["src/specify_cli/review/context_block.py", "src/runtime/next/prompt_builder.py", "src/specify_cli/cli/commands/agent/workflow_executor.py", "src/specify_cli/cli/commands/agent/workflow_cores.py", "src/specify_cli/review/prompt_metadata.py", "tests/integration/review/test_review_range_acceptance.py", "tests/integration/review/review_range_fixtures.py", "tests/review/test_context_block.py", "tests/next/test_prompt_builder_review_base.py", "tests/specify_cli/cli/commands/agent/test_workflow_cores.py", "tests/agent/test_workflow_mixed_dependency_review_context.py", "tests/integration/review/test_canonical_review_diff_refs.py", "tests/characterization/test_trio_pure_cores.py", "tests/integration/test_prompt_builder_owned_arms.py"]
authoritative_surface: "src/specify_cli/review/"
execution_mode: "code_change"
agent_profile: "python-pedro"  # filled in Step 4a — profile identifier (e.g., implementer-ivan)
role: "implementer"           # filled in Step 4a — role within the profile (e.g., "implementer")
agent: "claude"          # filled in Step 4a — CLI agent identifier (claude, codex, copilot, etc.)
model: ""          # filled in Step 4a — model identifier (e.g., claude-sonnet-4-6), optional
create_intent:
  - "src/specify_cli/review/context_block.py"
  - "tests/integration/review/test_review_range_acceptance.py"
  - "tests/integration/review/review_range_fixtures.py"
  - "tests/review/test_context_block.py"
---

# WP05: One renderer for every review render site, driven by acceptance tests

## ⚡ Do This First: Load Agent Profile

Use the `/spk-charter-profile-load` skill to load the agent profile specified in the frontmatter, and behave according to its guidance before parsing the rest of this prompt.

- **Profile**: `python-pedro`
- **Role**: `implementer`
- **Agent/tool**: `claude`

If no profile is specified, run `spec-kitty agent profile list` and select the best match for this work package's `task_type` and `authoritative_surface`.

---

## Objective

Make every review surface (the `spec-kitty next` review step, the `agent action review` prompt, and its stdout finalize summary) print one identical REVIEW RANGE block, rendered by a single new function `render_review_context` from WP03's `WpReviewRange` and WP04's cited-requirement texts. The work is driven ATDD-first: a red acceptance test over four topology fixtures is committed before any production change, then turned green.

Implementation command:

```bash
spec-kitty agent action implement WP05 --agent claude --mission review-context-wp-diff-01M774QF
```

## Context

**Why this WP exists.** Two review-prompt builders exist today, and they disagree (research/code-grounding.md §2):

| Path | Today's range | Defect |
|---|---|---|
| `spec-kitty next` → `prompt_builder._build_wp_prompt` (~207-271) → `_review_command_lines` (~371-414) | Repo-root `single_branch` workspaces get `lane_id="lane-planning"` (truthy), so they always take the **lane arm**: `_lane_review_base` → `<target>..HEAD`. Commit-to-target prints an **empty** range. No pathspec on the lane arm, so lane-mates leak in. | US1, US2 |
| `agent action review` → `workflow._resolve_review_context` (~1956) → `workflow_executor.review_context_for_repo_root_workspace` (~2534, `claim_commit..HEAD`, open above) / `review_context_for_worktree_branch` (~2610, lane base / mission branch / scored search) → `build_review_prompt_lines` (~2262) → `_review_context_line` (~2115); plus `_review_print_finalize_summary` (~2473-2510) on stdout | Open-ended `..HEAD`, last-claim lower bound, whole-lane on lanes. | US1, US2, FR-012 |

The post-plan squad (research.md P1) found a **third** render site, `_review_print_finalize_summary`, and (P2) **two** pathspec builders (`prompt_builder._review_pathspecs` ~325 and `workflow_cores.build_owned_files_review_pathspecs` ~540) that also disagree with the evidence axis's matcher. IC-05 folds both: one renderer, three call sites; one pathspec authority, `WpReviewRange.owned_pathspecs`.

**What this WP consumes (do not reimplement):**

- **WP03**: `specify_cli.review.wp_range.resolve_wp_review_range(repo_root, mission_slug, wp_id, *, owned_files, owned=None) -> WpReviewRange` (see data-model.md). Fields: `wp_id`, `base`, `tip` (full SHAs or `None`), `base_source`, `tip_source` (`RangeSource`), `gap`, `status` (`RangeStatus.RECORDED | DERIVED | UNAVAILABLE`), `moved_past`, `commits: tuple[RangeCommit(sha, subject)]` (oldest first, bookkeeping excluded), `bookkeeping_commits`, `files: tuple[FileChange(path, added, removed)]`, `out_of_map: tuple[str, ...]`, `owned_pathspecs: tuple[str, ...]`. Also expect an out-of-map commit count (the "<q> commit(s) touching only those paths" figure); if WP03 exposes it under a different name, use that name, do not recompute with git.
- **WP04**: `specify_cli.requirement_mapping.text.resolve_requirement_texts(spec_text, refs, *, mission_type) -> tuple[CitedRequirement, ...]` with `CitedRequirement(ref, resolution: Resolution.DECLARED | NOT_DECLARED | OTHER_MISSION | AMBIGUOUS, text)`. `spec.md` is read through the placement seam (`placement_seam(...).read_dir(...)`), never a reconstructed path; `refs` come from the WP frontmatter `requirement_refs`.
- **WP02**: commit-to-target `single_branch` now records `lane_head` / `wp_window` stamps, so the commit-to-target fixture yields a `RECORDED` range.

**Golden format.** `contracts/review-context-block.md` is the binding contract. Reproduce it byte-for-byte (shape below):

```
REVIEW RANGE (WP02): <base12>..<tip12>  [recorded | derived | unavailable]
  base: <base12> (<window open | opener lane_head stamp | claim base ref | claim event commit>)
? note: recorded window not used: <gap reason>
  tip:  <tip12> (<for_review submission | for_review event commit>)
? note: <branch> has moved <N> commit(s) past the submitted tip
IMPLEMENTATION COMMITS (<n>; = output of the git log command below):
  <sha12> <subject>
? … <k> more (see git log command)
CHANGED FILES (owned files, +added -removed):
  +<a> -<r>  <path>
? … <k> more files
? OUTSIDE OWNED FILES (<p> path(s) in <q> commit(s) touching only those paths; review rationale required): <path>, …
REVIEW COMMANDS:
  git log --oneline <base>..<tip> [-- <owned pathspecs>]
  git diff <base>..<tip> [-- <owned pathspecs>]
CITED REQUIREMENTS:
  FR-003 — <title>: <statement>
? C-009 — not declared in this Mission's spec
? other-mission#FR-002 — cites another Mission (not resolved here)
```

Unavailable form:

```
REVIEW RANGE (WP02): unavailable — <reason>
REVIEW COMMANDS:
  (no deterministic range; inspect `spec-kitty agent tasks status` and the WP's commits)
```

**Binding constraints.**

- **C-001**: never inline patch text, never write a diff file. Only command strings, commit subjects and numstat counts.
- **C-002 / FR-013**: no new gate, refusal code or exit code. `OWNED_REVIEW_BASE_UNAVAILABLE` keeps its code and fires on the same condition (an owned checkout whose scoped base cannot be proven: now "range unavailable" or "no owned files"). A non-owned review with an unavailable range proceeds with the notice.
- **C-004**: the pre-review gate, its changed-file authority and the for_review gate predicate are not touched.
- **C-010**: the acceptance test is committed red, as its own first commit, before any implementation.
- **NFR-001**: block ≤ 4,096 bytes excluding CITED REQUIREMENTS.
- Do **not** edit `tests/integration/test_single_branch_write_checkout_e2e.py` (PR #7562 overlap) or anything under `packs/built-in/` (C-003).

**Downstream.** WP06 (changelog + CLAUDE.md close-out) depends on this WP.

---

### Subtask T022: ATDD acceptance tests, committed RED first

**Purpose**: the executable contract for SC-001..SC-003, driving the production entry points, committed and red on the lane base before any production change (C-010).

**Steps**:

1. Create `tests/integration/review/review_range_fixtures.py` with four fixture builders, each returning a small dataclass (repo root, mission slug, the reviewed WP id, the expected implementation SHAs, the expected owned paths, an out-of-map path, the lane-mate SHAs that must be excluded):
   - `single_branch_commit_to_target`: reuse `tests/integration/single_branch_window_support.build_template(base, commit_to_target=True)` plus `claim` / `implement` / `submit`. Three WPs in sequence: WP01 implemented and submitted, WP02 with **two** implementation commits then submitted, WP03 committed **after** WP02's submission (so the branch moves past the tip and WP03 must be excluded).
   - `single_branch_minted`: same helper with `commit_to_target=False`.
   - `lanes`: reuse `tests/consolidation/characterization_support.build_two_wp_lane` (two WPs on one lane). Add a small topology meta adapter in the fixture module that rewrites `meta.json` `topology` (and whatever lane manifest key the helper needs) so the same builder yields a `lanes` Mission and, in the next item, a `lanes_with_coord` Mission. Keep the adapter in `review_range_fixtures.py`; do not edit `characterization_support.py` (not owned).
   - `lanes_with_coord`: the same builder through the adapter; the review is opened from the repository root checkout (US2-AS3).
   - In WP02's window, also commit one path **outside** WP02's `owned_files` (to drive the OUTSIDE OWNED FILES line, US2-AS2).
   - Give WP02 `requirement_refs` that include one declared FR, one declared NFR, one ID absent from the fixture spec, and one `other-mission#FR-002` citation (SC-002, US3).
   - Build each template once per module (`scope="module"` / session cache) and copy it per test (fixture-cost risk in IC-06). Use `monkeypatch.delenv` for `SPEC_KITTY_NO_NAG`, `SPEC_KITTY_NO_UPGRADE_CHECK`, `SPEC_KITTY_NON_INTERACTIVE` where the code under test reads them (CLAUDE.md gotcha 5).
2. Create `tests/integration/review/test_review_range_acceptance.py`, parametrized over the four fixtures. Drive the **production** entry points only:
   - **Site 1** (`next` review step): `runtime.next.prompt_builder.build_prompt("review", feature_dir, mission_slug, "WP02", agent, repo_root, mission_type)`; read the returned prompt text.
   - **Site 2** (`agent action review` prompt): invoke the review command through its Typer app (the same way `tests/integration/review/test_canonical_review_diff_refs.py` does), then read the written prompt file; also read the `ReviewPromptMetadata` written beside it.
   - **Site 3** (finalize summary): capture the same invocation's stdout.
3. Assertions per fixture:
   - The prompt contains a `REVIEW RANGE (WP02):` header with a provenance label (`[recorded]` or `[derived]`) and `base:` / `tip:` lines.
   - The IMPLEMENTATION COMMITS list equals WP02's implementation commits exactly; no WP01 / WP03 / lane-mate SHA appears (SC-001).
   - Extract the printed `git log` and `git diff` command lines; run them with `subprocess` in the repo (`shlex.split`); assert the output is non-empty and that `git log`'s SHAs equal the listed commits (FR-008).
   - The out-of-map path appears on the `OUTSIDE OWNED FILES` line.
   - `CITED REQUIREMENTS` shows the declared text for declared IDs, `not declared in this Mission's spec` for the missing ID, and `cites another Mission` for the cross-Mission ID (SC-002).
   - The block extracted from site 1 equals the block extracted from site 2, and the range `<base>..<tip>` printed on site 3 equals both (SC-003). `ReviewPromptMetadata.base_ref` equals the range base (FR-012).
   - A plain submission fixture (the WP whose tip is the live head) shows **no** `has moved` note; the commit-to-target fixture with WP03 committed after submission shows `has moved 1 commit(s)` (count non-bookkeeping commits only).
   - No patch text inlined: assert no line starts with `diff --git`, `@@ `, `+++ ` or `--- a/` (C-001).
   - The block, cut at `CITED REQUIREMENTS:`, encodes to ≤ 4,096 bytes (NFR-001).
4. Write a small shared extractor `_review_block(text) -> str` (from the `REVIEW RANGE` line through the last cited requirement line) in the test module so all three comparisons use the same slice.
5. Run the file on the lane base and confirm it is **red for the right reason** (the header is missing / commands are empty), not because of an import or fixture error. Commit only these two files as the first commit, e.g. `test(review): red acceptance for the WP review range on four topologies (C-010)`.

**Files**: `tests/integration/review/review_range_fixtures.py` (~200 lines), `tests/integration/review/test_review_range_acceptance.py` (~220 lines).

**Validation**: `uv run --frozen pytest tests/integration/review/test_review_range_acceptance.py -q` fails with assertion errors (not collection errors) on every fixture; `git log -1 --stat` shows only the two test files.

---

### Subtask T023: NEW `src/specify_cli/review/context_block.py`

**Purpose**: the one renderer, pure and deterministic, implementing `contracts/review-context-block.md`.

**Steps**:

1. Create `src/specify_cli/review/context_block.py` exposing `render_review_context(review_range: WpReviewRange, cited: Sequence[CitedRequirement]) -> list[str]`. No git, no filesystem, no clock: input objects in, lines out.
2. Module constants (S1192): `BYTE_BUDGET = 4096`, `LABEL_LEN = 12`, the provenance label maps (`RangeSource` → `window open` / `opener lane_head stamp` / `claim base ref` / `claim event commit`; tip → `for_review submission` / `for_review event commit`), status labels (`recorded` / `derived`), and the unavailable command line. Coordinate the exact `RangeSource` member names with WP03's `wp_range.py`; if WP03 distinguishes "opener lane_head stamp" from "window open", map each member to its own label.
3. Helpers (keep each ≤ 15 complexity, each unit-tested):
   - `_header_lines(range)`: header, `base:`, optional `note: recorded window not used: <gap>`, `tip:`, optional `note: <branch> has moved <N> commit(s) past the submitted tip` (only when `moved_past > 0`).
   - `_command_lines(range)`: `git log --oneline <base>..<tip>` and `git diff <base>..<tip>`, each suffixed ` -- <pathspecs>` when `owned_pathspecs` is non-empty. **Full** SHAs here; labels elsewhere use `sha[:12]`. Quote pathspecs that contain shell metacharacters (`*`, spaces, `:(exclude)`) with `shlex.quote` so the printed command runs as written.
   - `_fill_list(heading, items, more_fmt, remaining_budget)`: appends item lines while they fit, then one `… <k> more …` line. Commits first, then files, then the out-of-map line; header, provenance and commands are reserved first and always kept.
   - `_requirement_lines(cited)`: `<ref> — <text>` for `DECLARED`; `<ref> — not declared in this Mission's spec`; `<ref> — cites another Mission (not resolved here)`; for `AMBIGUOUS` use the wording WP04 defines (e.g. `<ref> — declared more than once; see spec.md`). Never drop an ID. Requirement text is outside the byte budget (already capped at 600 chars by WP04).
   - `_unavailable_lines(range)`: the two-line unavailable form plus the CITED REQUIREMENTS section (requirements still render when the range is unavailable).
4. Binary files (`added is None`) render as `-` counts, e.g. `+- --  path`; pin the exact form in the golden test.
5. The out-of-map line is omitted when `out_of_map` is empty (also the no-owned-files case, per the spec edge case). When `owned_pathspecs` is empty the commands are printed without `-- <pathspecs>` (unscoped). Do not invent lines the contract does not show; if the spec's "labelled as unscoped" edge case needs a line, raise it with the reviewer as a contract amendment rather than adding one silently.
6. Export `render_review_context` from `specify_cli.review.__init__` only if that package already re-exports peers; otherwise import by module path (avoid an `__init__.py` change, which would require a version bump).
7. Create `tests/review/test_context_block.py`:
   - Golden strings for: a recorded range; a derived range with a gap note; a moved-past range; the unavailable form; a no-owned-files range; cited requirements of all four resolutions.
   - Budget: 500 synthetic commits and 500 files → the block (minus requirements) ≤ 4,096 bytes, header/provenance/command lines present, `… <k> more` counts exact.
   - Ordering: commits in input order (oldest first), files and out-of-map paths sorted.
   - Determinism: two calls with equal inputs return equal lists.
   - Commands contain full 40-char SHAs; labels contain 12-char SHAs.

**Files**: `src/specify_cli/review/context_block.py` (~160 lines), `tests/review/test_context_block.py` (~200 lines).

**Validation**: `uv run --frozen pytest tests/review/test_context_block.py -q` green; `uv run --frozen ruff check src/specify_cli/review/context_block.py`; `uv run --frozen mypy src/specify_cli/review/context_block.py` zero issues.

---

### Subtask T024: Rewire `prompt_builder._review_command_lines`

**Purpose**: site 1 renders through the new renderer; the old base arms go.

**Steps**:

1. In `src/runtime/next/prompt_builder.py`, replace the body of `_review_command_lines(repo_root, feature_dir, mission_slug, wp_id, wp_meta, workspace, owned)`:
   1. `review_range = resolve_wp_review_range(repo_root, mission_slug, wp_id, owned_files=list(wp_meta.owned_files), owned=owned)`.
   2. `cited = resolve_requirement_texts(spec_text, list(wp_meta.requirement_refs or []), mission_type=...)`; read `spec.md` through the placement seam (the same kind-aware read the prompt builder already uses for planning artifacts; never `feature_dir / "spec.md"` if that is a coord husk). If `spec.md` cannot be read, pass `""` so every ID renders as not declared (no new refusal).
   3. Owned refusal (unchanged code and condition): if `owned is not None` and (`not wp_meta.owned_files` or `review_range.status is RangeStatus.UNAVAILABLE`), raise `_review_base_unavailable(wp_id, <why>)` with the existing two reasons ("the work package declares no owned_files" / the range's gap reason).
   4. `lines = render_review_context(review_range, cited)`, then the existing blank line, `render_wp_review_antipattern_checklist()`, blank line.
2. Delete `_review_pathspecs`, `_claim_commit_or_none` and `_lane_review_base`, and their now-unused imports (`claim_commit_for_wp`, `ClaimCommitUnresolved`, `get_feature_target_branch` if no other caller). Grep before deleting: `rg -n "_lane_review_base|_claim_commit_or_none|_review_pathspecs" src tests`.
3. Fix the docstring (it currently claims the repo root uses the claim commit, which the code contradicts): describe the single range authority.
4. Layering check: `runtime` may import `specify_cli`? It may **not** (`kernel <- charter <- {runtime, ...} <- specify_cli`). Check how `prompt_builder` currently reaches `specify_cli` symbols (e.g. through `mission_runtime` or an injected port). If a direct import from `runtime.next` into `specify_cli.review` violates `test_layer_rules.py` or the runtime outbound ledger, route through the existing seam the module already uses for `specify_cli` calls (lazy import inside the function, if that is the module's established pattern and the ledger permits it). Do not grow the shrink-only ledger without an explicit note to the reviewer.
5. Keep `_review_command_lines` and new helpers ≤ 15 complexity.

**Files**: `src/runtime/next/prompt_builder.py` (net shrink, ~-40/+25 lines).

**Validation**: `uv run --frozen pytest tests/next/ tests/runtime/ -q`; `tests/architectural/test_layer_rules.py`; `tests/integration/test_prompt_builder_owned_arms.py` (not owned; if it pins the retired `_lane_review_base` behaviour, report it to the reviewer as stale rather than editing it).

---

### Subtask T025: Rewire `workflow_executor` (sites 2 and 3) and retire the second pathspec builder

**Purpose**: `agent action review` and its stdout summary show the identical range; one pathspec authority remains.

**Steps**:

1. In `src/specify_cli/cli/commands/agent/workflow_executor.py`:
   - `review_context_for_repo_root_workspace` (~2534) and `review_context_for_worktree_branch` (~2610): resolve `WpReviewRange` once and fill the existing dict keys from it: `base_branch` = `base_ref` = range base (full SHA), `branch_name` = `lane_branch` = range tip (or the checked-out branch name for display, as long as the commands use the tip SHA), `commit_count` = `len(range.commits)`. Store the range object itself under one new key (e.g. `ctx["review_range"]`) so render sites never re-resolve. When the range is unavailable, leave `base_branch` at `"unknown"` exactly as today, so downstream truthiness checks keep working.
   - Keep `review_context_search_unknown_base` only if something else still uses it; if the worktree builder was its only caller, remove it and its `pick_best_base_branch` dependency only when `test_no_dead_symbols.py` demands it (otherwise leave for a follow-up and note it).
   - `_review_context_line` (~2115): render `render_review_context(ctx["review_range"], cited)` inside the existing `─── GIT REVIEW CONTEXT` frame, prefixed by `cd {workspace_path}`. Drop the old `Branch:` / `Base branch:` / `..HEAD` command lines. Unavailable range → the renderer's unavailable form (no refusal).
   - `build_review_prompt_lines` (~2262): resolve the cited requirements once (same WP04 call, spec through the placement seam) and pass them to `_review_context_line`.
   - `ReviewPromptMetadata`: `base_ref` must be the range base. The call at ~2454 already reads `review_ctx["base_ref"]`; confirm, and only touch `src/specify_cli/review/prompt_metadata.py` if validation rejects a full SHA or needs the tip recorded (no schema change unless required; if one is required, keep it backward compatible and say so in the PR).
   - `_review_print_finalize_summary` (~2473-2510): replace the `Review diff: git log {base}..{branch}` lines with one line built from the same range: `   Review range: <base12>..<tip12> [<status>] — git log --oneline <base>..<tip> -- <pathspecs>` (reuse a small public helper from `context_block.py`, e.g. `review_range_summary_line(range)`, so the text has one source). Unavailable → `🔀 Review range unavailable — <reason>`.
2. In `src/specify_cli/cli/commands/agent/workflow_cores.py`, delete `build_owned_files_review_pathspecs` (~540) and its import in `workflow_executor.py` (line ~54). `WpReviewRange.owned_pathspecs` is now the single pathspec authority. Confirm `rg -n build_owned_files_review_pathspecs src tests` is empty afterwards (the test re-pin is T026).
3. Keep edits minimal: these are hot files. Extract helpers rather than growing functions; keep every touched function ≤ 15 complexity (`uv run --frozen ruff check --select C901`).
4. `workflow*.py` are on the ruff format ratchet: check with `uv run --frozen ruff format --check --force-exclude <files>` (never a bare per-file `ruff format`, which reformats the whole file).
5. Do not change `workflow.py::_resolve_review_context` beyond what is strictly needed (it is not owned). If it must pass `wp` metadata through, prefer reading `owned_files` inside the executor builders from data they already receive.

**Files**: `workflow_executor.py` (~-50/+45), `workflow_cores.py` (~-30), possibly `prompt_metadata.py` (0-10).

**Validation**: `uv run --frozen pytest tests/agent/ tests/integration/review/ -q`; `tests/architectural/test_execution_context_parity.py`; `make format-check-files FILES="src/specify_cli/cli/commands/agent/workflow_executor.py src/specify_cli/cli/commands/agent/workflow_cores.py"`.

---

### Subtask T026: Re-pin stale old-range tests (DIRECTIVE_041)

**Purpose**: tests that pin the retired `<base>..HEAD` / `claim..HEAD` text are stale, not wrong in intent; re-pin them to the new block. Never delete a valid test.

**Steps**:

1. `tests/next/test_prompt_builder_review_base.py`: imports `_review_pathspecs` (deleted). Re-pin the pathspec test onto `WpReviewRange.owned_pathspecs` (or move its intent to WP03's tests if already covered there; then replace with an assertion that the prompt's commands carry the range's pathspecs). Re-pin the claim-base / lane-base assertions to the REVIEW RANGE header and `<base>..<tip>` commands. Note the `lane_id=None` stand-ins (code-grounding §2): keep them, and add one case with `lane_id="lane-planning"` (the production single_branch arm).
2. `tests/specify_cli/cli/commands/agent/test_workflow_cores.py`: the `build_owned_files_review_pathspecs` class (~105-140) goes stale with the function. Move its behavioural intent (mission-dir bookkeeping excluded only when the mission dir is owned) to an assertion against `WpReviewRange.owned_pathspecs` if WP03's tests do not already cover it; otherwise delete the class with a rationale citing the covering test. Update the module docstring (line ~8).
3. `tests/agent/test_workflow_mixed_dependency_review_context.py`: re-pin the expected `base_ref` / command text to the range.
4. `tests/integration/review/test_canonical_review_diff_refs.py`: re-pin the canonical-manifest assertion to the new block (the slug-prefixed manifest must still resolve the right branch/tip).
5. `tests/characterization/test_trio_pure_cores.py`: re-pin any pinned old summary or pathspec text.
6. One commit per file (or one commit with one rationale line per file) whose message carries a one-line rationale each, e.g. `re-pin: claim..HEAD text replaced by the WP review range (IC-05, DIRECTIVE_041)`.

**Files**: the five test files above.

**Validation**: each file green; `git diff --stat` shows no test function removed without a named replacement.

---

### Subtask T027: Turn T022 green; confirm the owned-checkout refusal

**Purpose**: prove red → green and that FR-013 / C-002 hold.

**Steps**:

1. Run `uv run --frozen pytest tests/integration/review/test_review_range_acceptance.py -q`; iterate on T023-T025 (not on the test's assertions) until all four fixtures pass. If an assertion is genuinely wrong against the contract, fix it in a separate commit with the reason.
2. Run `uv run --frozen pytest tests/integration/test_owned_lifecycle_acceptance_review.py -q`. It must still pass unmodified: `OWNED_REVIEW_BASE_UNAVAILABLE` keeps its code and condition. Edit it only if it is stale (pins retired text, not the refusal) and say so in the commit.
3. Confirm no new refusal: `rg -n "OwnedRefusalCode\.|ActionContextError\(" src/runtime/next/prompt_builder.py` shows only the existing code.

**Validation**: both files green. Record the T022 red run output (from the first commit) and the final green run in the PR's *Tests run* section.

---

### Subtask T028: Validation sweep

**Purpose**: the blast-radius run required by the charter test policy.

**Steps** (record each command and its pass/fail counts for the PR):

```bash
make test-fast
uv run --frozen pytest tests/review/ tests/next/ tests/runtime/ tests/agent/ tests/integration/review/ -q
uv run --frozen pytest tests/integration/test_owned_lifecycle_acceptance_review.py tests/integration/test_prompt_builder_owned_arms.py -q
uv run --frozen pytest tests/specify_cli/cli/commands/agent/test_workflow_cores.py -q   # out-of-matrix, run explicitly
uv run --frozen pytest tests/characterization/test_trio_pure_cores.py -q
uv run --frozen pytest tests/architectural/test_execution_context_parity.py tests/architectural/test_git_path_listing_owner.py tests/architectural/test_layer_rules.py tests/architectural/test_no_dead_symbols.py tests/architectural/test_status_read_single_door.py tests/architectural/test_cold_import_status_boundary.py tests/architectural/test_no_legacy_terminology.py -q
uv run --frozen ruff check src/specify_cli/review/context_block.py src/runtime/next/prompt_builder.py src/specify_cli/cli/commands/agent/workflow_executor.py src/specify_cli/cli/commands/agent/workflow_cores.py src/specify_cli/review/prompt_metadata.py
uv run --frozen ruff format --check --force-exclude <every touched file>
uv run --frozen mypy src/specify_cli/review/context_block.py src/runtime/next/prompt_builder.py src/specify_cli/cli/commands/agent/workflow_executor.py src/specify_cli/cli/commands/agent/workflow_cores.py
```

Do **not** run `make test-full` or the whole `tests/architectural/` directory. Classify any red you did not cause using the CLAUDE.md baseline-red gotcha (stale venv → `uv sync --frozen --all-extras`; harness env leaks → test-local `monkeypatch.delenv`).

---

## Definition of Done

- [ ] T022's two test files land as the **first** commit of the lane and were red on the lane base for an assertion reason (red output recorded in the PR).
- [ ] `src/specify_cli/review/context_block.py` exists; `render_review_context` reproduces `contracts/review-context-block.md` (golden tests), including the unavailable form, 12-char labels, full SHAs in commands, ordered/truncated lists, block ≤ 4,096 bytes without requirements.
- [ ] All three render sites (`prompt_builder._review_command_lines`, `workflow_executor._review_context_line`, `_review_print_finalize_summary`) render from one `WpReviewRange`; the acceptance test proves identical blocks/ranges (SC-003) and `ReviewPromptMetadata.base_ref` = range base (FR-012).
- [ ] `_lane_review_base`, `_claim_commit_or_none`, `_review_pathspecs` and `build_owned_files_review_pathspecs` are gone; `rg` finds no caller; `WpReviewRange.owned_pathspecs` is the only pathspec builder.
- [ ] `OWNED_REVIEW_BASE_UNAVAILABLE` keeps its code and condition; `tests/integration/test_owned_lifecycle_acceptance_review.py` passes; no new refusal/exit code (C-002); pre-review gate untouched (C-004); no patch text in any prompt (C-001).
- [ ] Stale tests re-pinned with one-line rationales; no valid test deleted.
- [ ] T028 commands pass; ruff, ruff format (`--force-exclude`) and mypy clean on touched files; touched functions ≤ 15 complexity.
- [ ] Each subtask recorded with `spec-kitty agent tasks mark-status <Txxx> --status done --mission review-context-wp-diff-01M774QF` (event-sourced; not a ticked box).

## Risks

- **Layering (runtime → specify_cli).** `prompt_builder` lives in `src/runtime/`; importing `specify_cli.review` may break `test_layer_rules.py` or the shrink-only runtime outbound ledger. Mitigation: follow the module's existing pattern for reaching `specify_cli`; if none fits, stop and escalate rather than widen the ledger silently.
- **Hot files / format ratchet.** `workflow*.py` are large and on the formatter-debt ratchet. Mitigation: minimal diffs, `--force-exclude` checks, no whole-file reformat.
- **Fixture cost.** Four topology fixtures driving the real CLI are slow. Mitigation: build each template once per module and copy per test.
- **`lanes_with_coord` from the repository root checkout.** The status surface is on the coord branch while code is on the lane; WP03 must not use event commits on lanes (research P3). If the fixture shows a coord-branch range, the bug is in WP03 — report it, do not patch around it here.
- **Shell quoting of glob pathspecs.** Unquoted `**` / `:(exclude)` in printed commands can expand in the reviewer's shell and change the result. Mitigation: `shlex.quote`, and the acceptance test executes the printed commands via `shlex.split`.
- **Not-owned tests pinning old behaviour** (`tests/integration/test_prompt_builder_owned_arms.py`). Mitigation: run them; report stale ones to the reviewer/orchestrator instead of editing outside `owned_files`.
- **Dead symbols.** Removing builders may leave `review_context_search_unknown_base` / `pick_best_base_branch` unused; `test_no_dead_symbols.py` will say so.

## Reviewer Guidance

- **Red → green**: verify the first lane commit contains only the T022 files and that the PR records its red run; then verify green on the final tip.
- **Three sites identical**: read the acceptance test's site-1 / site-2 / site-3 comparison and run it; the finalize summary must print the same `<base>..<tip>`.
- **No inline diff** (C-001): grep the rendered prompts in the acceptance fixtures for `diff --git` / `@@`.
- **No new refusal** (C-002, FR-013): the only refusal in `_review_command_lines` is `OWNED_REVIEW_BASE_UNAVAILABLE`, same condition; an unavailable non-owned range proceeds with the notice.
- **One pathspec builder**: `rg -n "build_owned_files_review_pathspecs|_review_pathspecs" src tests` is empty.
- **Contract fidelity**: compare `tests/review/test_context_block.py` goldens line by line with `contracts/review-context-block.md`.
- **Re-pins**: each stale test re-pinned, not deleted, with a rationale in the commit message.
- **Layering**: `test_layer_rules.py` green without ledger growth (or the growth explicitly justified).
