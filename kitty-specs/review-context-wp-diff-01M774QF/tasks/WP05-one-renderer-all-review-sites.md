---
work_package_id: WP05
title: One renderer, and the `next` review step (site 1) on it, driven by acceptance tests
dependencies:
- WP02
- WP03
- WP04
requirement_refs:
- FR-008
- NFR-001
- C-001
- C-010
- SC-001
- SC-002
planning_base_branch: feat/7578-review-context
merge_target_branch: feat/7578-review-context
branch_strategy: Planning artifacts for this mission were generated on feat/7578-review-context. During /spec-kitty.implement this WP may branch from a dependency-specific base, but completed changes must merge back into feat/7578-review-context unless the human explicitly redirects the landing branch.
subtasks:
- T022
- T023
- T024
- T025
- T026
history: []
agent_profile: python-pedro
authoritative_surface: src/specify_cli/review/
create_intent:
- src/specify_cli/review/context_block.py
- tests/integration/review/test_review_range_acceptance.py
- tests/integration/review/review_range_fixtures.py
- tests/review/test_context_block.py
execution_mode: code_change
model: ''
owned_files:
- src/specify_cli/review/context_block.py
- src/runtime/next/prompt_builder.py
- tests/review/test_context_block.py
- tests/integration/review/test_review_range_acceptance.py
- tests/integration/review/review_range_fixtures.py
- tests/next/test_prompt_builder_review_base.py
- tests/next/test_prompt_builder_unit.py
- tests/integration/test_prompt_builder_owned_arms.py
- tests/integration/test_owned_lifecycle_acceptance_review.py
- tests/integration/test_owned_lifecycle_acceptance_e2e.py
role: implementer
tags: []
tracker_refs: []
---

# WP05: One renderer, and the `next` review step (site 1) on it, driven by acceptance tests

## ⚡ Do This First: Load Agent Profile

Use the `/spk-charter-profile-load` skill to load the agent profile specified in the frontmatter, and behave according to its guidance before parsing the rest of this prompt.

- **Profile**: `python-pedro`
- **Role**: `implementer`
- **Agent/tool**: `claude`

If no profile is specified, run `spec-kitty agent profile list` and select the best match for this work package's `task_type` and `authoritative_surface`.

---

## Objective

Build the one review-context renderer, `render_review_context`, from WP03's `WpReviewRange` and WP04's cited-requirement texts, and move **render site 1** (the `spec-kitty next` review step, `prompt_builder._review_command_lines`) onto it. The work is ATDD-first: the lane's first commit is a red acceptance test that drives site 1 over four topology fixtures. WP07 moves sites 2 and 3 (`agent action review` and its finalize summary) onto the same renderer and proves cross-site equality.

Implementation command:

```bash
spec-kitty agent action implement WP05 --agent claude --mission review-context-wp-diff-01M774QF
```

## Context

**Why this WP exists.** Today the `next` review step prints the wrong range (research/code-grounding.md §2): `prompt_builder._build_wp_prompt` (~207-271) → `_review_command_lines` (~371-414). Repo-root `single_branch` workspaces get `lane_id="lane-planning"` (truthy), so they always take the **lane arm**: `_lane_review_base` → `<target>..HEAD`. On commit-to-target that range is **empty**. The lane arm carries no pathspec, so lane-mates leak in (US1, US2). The post-plan squad (research.md P2) also found a second pathspec builder, `prompt_builder._review_pathspecs` (~325), that disagrees with the evidence axis's matcher. This WP retires it: `WpReviewRange.owned_pathspecs` is the one pathspec authority.

**Split with WP07.** WP05 owns the renderer and site 1, and builds the shared acceptance fixtures. WP07 (depends on WP05) owns sites 2 and 3, `workflow_cores.build_owned_files_review_pathspecs`, `ReviewPromptMetadata.base_ref` and the cross-site equality test (SC-003, FR-012). WP07 imports this WP's fixtures, so the fixture module must offer every variant both acceptance files need (listed in T022).

**What this WP consumes (do not reimplement):**

- **WP03**: `specify_cli.review.wp_range.resolve_wp_review_range(repo_root, mission_slug, wp_id, *, owned_files, owned=None) -> WpReviewRange` (see data-model.md). Fields: `wp_id`, `base`, `tip` (full SHAs or `None`), `base_source`, `tip_source` (`RangeSource`), `gap`, `status` (`RangeStatus.RECORDED | DERIVED | UNAVAILABLE`), `moved_past`, `commits: tuple[RangeCommit(sha, subject)]` (oldest first, bookkeeping excluded), `out_of_map_only_commits`, `files: tuple[FileChange(path, added, removed)]`, `out_of_map: tuple[str, ...]`, `owned_pathspecs: tuple[str, ...]`. If WP03 named a field differently, use its name; never recompute anything with git here.
- **WP04**: `specify_cli.requirement_mapping.text.resolve_requirement_texts(spec_text, refs, *, mission_type) -> tuple[CitedRequirement, ...]` with `CitedRequirement(ref, resolution: Resolution.DECLARED | NOT_DECLARED | OTHER_MISSION | AMBIGUOUS, text)`. `spec.md` is read through the placement seam, never a reconstructed path; `refs` come from the WP frontmatter `requirement_refs`.
- **WP02**: commit-to-target `single_branch` now records `lane_head` / `wp_window` stamps, so the commit-to-target fixture yields a `RECORDED` range.

**Layering.** `prompt_builder` already imports `specify_cli` directly (for example `from specify_cli.review.antipattern_checklist import render_wp_review_antipattern_checklist`), and `specify_cli.review` and `specify_cli.requirement_mapping` are on the runtime ledger (`_RUNTIME_ALLOWED_SPECIFY_CLI`). Import the new names at module level the same way; the ledger count stays 22.

**Golden format.** `contracts/review-context-block.md` is the binding contract. Reproduce it byte-for-byte:

```
REVIEW RANGE (WP02): <base12>..<tip12>  [recorded | derived | unavailable]
  base: <base12> (<window open | opener lane_head stamp | claim base ref | claim event commit>)
? note: recorded window not used: <gap reason>
? scope: unscoped (no owned_files declared)
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
- **C-002 / FR-013 and operator ruling Q7**: no new gate, refusal code or exit code. `OWNED_REVIEW_BASE_UNAVAILABLE` keeps its code and its message. It fires only when the owned checkout's scoped review range is unavailable, or the WP declares no `owned_files`. A non-owned review with an unavailable range proceeds with the notice.
- **C-004**: the pre-review gate, its changed-file authority and the for_review gate predicate are not touched.
- **C-010 (per work package)**: the lane's first commit is the failing acceptance test (T022), alone.
- **NFR-001**: block ≤ 4,096 bytes excluding CITED REQUIREMENTS.
- Do **not** edit `tests/integration/test_single_branch_write_checkout_e2e.py` (PR #7562 overlap) or anything under `packs/built-in/` (C-003).

**Downstream.** WP07 (sites 2 and 3) depends on this WP; WP06 depends on WP07.

---

### Subtask T022: ATDD acceptance test for site 1 and the shared fixtures, committed RED first

**Purpose**: the executable contract for SC-001, SC-002, FR-008 and C-001 on site 1, committed red before any production change (C-010). The fixture module is shared with WP07's acceptance test.

**Steps**:

1. Create `tests/integration/review/review_range_fixtures.py`. Each builder returns a small frozen dataclass: repo root, mission slug, reviewed WP id, the expected implementation SHAs (oldest first), the expected `CHANGED FILES` lines (`+<a> -<r>  <path>`, exact), the expected out-of-map path, the lane-mate / later-WP SHAs that must be excluded, and the expected provenance (`status`, `base_source` label, `tip_source` label).
   - **Review-ready, not approved.** The reviewed WP must end at `for_review` (or `in_review`). Neither existing builder ends there: `single_branch_window_support.build_template` defines only WP01/WP02 (`_MODULE`), and `characterization_support.build_two_wp_lane` ends with both WPs approved. Extend them **in `review_range_fixtures.py`** (both support modules are other WPs' or nobody's; do not edit them): compose the lane steps from the support modules' lower-level helpers (`move`, `emit`, `commit_file`, `claim`, `implement`, `submit` on `single_branch`; the step helpers `characterization_support` uses on lanes), add a WP03 task file and `owned_files` in the fixture when you need a third WP, and stop the reviewed WP at `for_review`.
   - `single_branch_commit_to_target`: `build_template(base, commit_to_target=True)`. WP01 implemented and submitted; WP02 with **two** implementation commits, then submitted; WP03 committed **after** WP02's submission (the branch moves past the tip, and WP03 must be excluded).
   - `single_branch_minted`: the same with `commit_to_target=False`.
   - `lanes`: WP01 and WP02 on one lane, WP02 reviewed. A small topology adapter in the fixture module rewrites `meta.json` `topology` (and whatever lane manifest key the builder needs).
   - `lanes_with_coord`: the same through the adapter; the review is opened from the repository root checkout (US2-AS3).
   - **Lane-mate on owned paths (only the base can exclude it).** In every fixture, the earlier lane-mate (WP01, or on `single_branch` the earlier WP in sequence) makes one commit that touches a path **inside WP02's `owned_files`**, before WP02's window opens. The owned-file pathspec cannot drop it; only a correct base can. Record its SHA as excluded.
   - In WP02's window, also commit one path **outside** WP02's `owned_files` (US2-AS2), and one commit that touches only that out-of-map path.
   - Give WP02 `requirement_refs` with one declared FR, one declared NFR, one ID absent from the fixture spec and one `other-mission#FR-002` (SC-002, US3).
   - **Stamp-stripped lanes variant** (`lanes_stamp_stripped`): the `lanes` fixture with every `lane_head` and `wp_window` key removed from WP02's events (`characterization_support.rewrite_events`), so the range is genuinely unavailable (lanes never use event commits). Expected: `UNAVAILABLE` with its reason.
   - **Owned-checkout stamp-stripped variant** for the operator ruling Q7 cells (T025): an owned checkout whose WP's stamps are stripped, so its scoped range is genuinely unavailable.
   - Build each template once per module (`scope="module"` / session cache) and copy it per test. Use `monkeypatch.delenv` for `SPEC_KITTY_NO_NAG`, `SPEC_KITTY_NO_UPGRADE_CHECK`, `SPEC_KITTY_NON_INTERACTIVE` where the code under test reads them (CLAUDE.md gotcha 5).
   - Put the shared helpers WP07 needs here, public and documented: `review_block(text) -> str` (from the `REVIEW RANGE` line through the last cited-requirement line), `run_printed_command(repo, line) -> str` (runs one printed command with `bash -c` in the repo, `check=True`), `assert_no_patch_text(text)` (the C-001 detector) and `snapshot_tree(path) -> dict[str, bytes]`.
2. Create `tests/integration/review/test_review_range_acceptance.py`, parametrized over the four review-ready fixtures. Drive **site 1** only, through the production entry point: `runtime.next.prompt_builder.build_prompt("review", feature_dir, mission_slug, "WP02", agent, repo_root, mission_type)`, and read the returned prompt text.
3. Assertions per fixture:
   - **Exact provenance.** With WP02's stamps present, every fixture (commit-to-target, minted, `lanes`, `lanes_with_coord`) prints `[recorded]` on the header and `base: <base12> (window open)` and `tip:  <tip12> (for_review submission)`. Assert the exact label. Never accept "recorded or derived".
   - **Commit list (SC-001).** IMPLEMENTATION COMMITS equals WP02's implementation commits exactly, oldest first. No WP01 / WP03 / lane-mate SHA appears, including the lane-mate commit on WP02's owned path.
   - **Per-file summary (FR-006).** The CHANGED FILES section equals the fixture's expected `+<a> -<r>  <path>` lines exactly, line for line.
   - **Printed commands run as written (FR-008).** Extract the `git log` and `git diff` command lines and run each through `run_printed_command` (`bash -c`, so quoting and glob pathspecs are exercised as a reviewer's shell would). Assert both outputs are non-empty, the `git log` SHAs equal the listed commits, and neither output names the excluded SHAs or paths.
   - The out-of-map path appears on the `OUTSIDE OWNED FILES` line with the exact path and commit counts.
   - **Cited requirements (SC-002).** Declared text for the declared IDs, `not declared in this Mission's spec` for the missing ID, `cites another Mission (not resolved here)` for the cross-Mission ID.
   - **Moved-past (FR-009).** Commit-to-target, where WP03 committed after the submission: `has moved 1 commit(s)`. A plain submission (the tip is the live head, only status commits after it): no `has moved` line.
   - **No patch text, no diff file (C-001).** `assert_no_patch_text(prompt)`: no line starts with `diff --git`, `@@ `, `+++ ` or `--- a/`. Positive control in the same test module: feed the detector the real output of `git diff <base>..<tip>` from the fixture and assert it **fails** on it, so the detector is proven to see a real patch. Snapshot the prompt directory and the test's tmp root with `snapshot_tree` before and after the render, and assert no new file other than the prompt itself appeared and no file content contains patch text.
   - **Budget (NFR-001).** The block cut at `CITED REQUIREMENTS:` encodes to ≤ 4,096 bytes.
   - **Determinism (NFR-005).** Render site 1 twice in fresh interpreters with `PYTHONHASHSEED=0` and `PYTHONHASHSEED=1` (a `subprocess.run([sys.executable, "-c", ...])` that calls `build_prompt` and prints the block), and assert the two blocks are byte-identical.
4. **Unavailable notice (FR-013, NFR-004).** On `lanes_stamp_stripped`, drive `spec-kitty next` for the review step (through `CliRunner` over `next_cmd.next_step`, as `tests/integration/test_owned_lifecycle_acceptance_review.py` does) and assert exit code 0, a `step` decision, and a prompt containing `REVIEW RANGE (WP02): unavailable — <reason>` with the expected reason and the unavailable command line.
5. Run the file on the lane base and confirm it is **red for the right reason** (the header is missing, the commands are empty), not because of an import or fixture error. Commit only these two files as the lane's first commit, e.g. `test(review): red acceptance for the WP review range on site 1 (C-010)`.

**Files**: `tests/integration/review/review_range_fixtures.py` (~300 lines), `tests/integration/review/test_review_range_acceptance.py` (~250 lines).

**Validation**: `uv run --frozen pytest tests/integration/review/test_review_range_acceptance.py -q` fails with assertion errors (not collection errors) on every fixture, except the C-001 positive control, which passes; `git log -1 --stat` shows only the two test files.

---

### Subtask T023: NEW `src/specify_cli/review/context_block.py`

**Purpose**: the one renderer, pure and deterministic, implementing `contracts/review-context-block.md`.

**Steps**:

1. Create `src/specify_cli/review/context_block.py` exposing `render_review_context(review_range: WpReviewRange, cited: Sequence[CitedRequirement]) -> list[str]`. No git, no filesystem, no clock: input objects in, lines out.
2. Module constants (S1192): `BYTE_BUDGET = 4096`, `LABEL_LEN = 12`, the provenance label maps (`RangeSource` → `window open` / `opener lane_head stamp` / `claim base ref` / `claim event commit`; tip → `for_review submission` / `for_review event commit`), status labels (`recorded` / `derived`), the unscoped line `scope: unscoped (no owned_files declared)` and the unavailable command line. Map each `RangeSource` member WP03 defines to its own label.
3. Helpers (keep each ≤ 15 complexity, each unit-tested):
   - `_header_lines(range)`: header, `base:`, optional `note: recorded window not used: <gap>`, optional `scope: unscoped (no owned_files declared)` (exactly when `owned_pathspecs` is empty), `tip:`, optional `note: <branch> has moved <N> commit(s) past the submitted tip` (only when `moved_past > 0`).
   - `_command_lines(range)`: `git log --oneline <base>..<tip>` and `git diff <base>..<tip>`, each suffixed ` -- <pathspecs>` when `owned_pathspecs` is non-empty. **Full** SHAs here; labels elsewhere use `sha[:12]`. Quote every pathspec with `shlex.quote` so the printed command runs as written in `bash` (globs like `**`, `:(glob)` / `:(exclude)` magic, spaces).
   - `_fill_list(heading, items, more_fmt, remaining_budget)`: appends item lines while they fit, then one `… <k> more …` line. Commits first, then files, then the out-of-map line; header, provenance and commands are reserved first and always kept.
   - `_requirement_lines(cited)`: `<ref> — <text-after-prefix>` for `DECLARED` (WP04's text already starts with the ID: do not print it twice); `<ref> — not declared in this Mission's spec`; `<ref> — cites another Mission (not resolved here)`; for `AMBIGUOUS` the wording WP04 defines (for example `<ref> — declared more than once; see spec.md`). Never drop an ID. Requirement text is outside the byte budget (capped at 600 characters by WP04).
   - `_unavailable_lines(range)`: the two-line unavailable form plus the CITED REQUIREMENTS section (requirements still render when the range is unavailable).
4. Binary files (`added is None`) render as `-` counts, e.g. `+- --  path`; pin the exact form in the golden test.
5. The out-of-map line is omitted when `out_of_map` is empty (also the no-owned-files case). When `owned_pathspecs` is empty the commands are printed without `-- <pathspecs>` and the header carries the contract's `scope: unscoped (no owned_files declared)` line.
6. Do not edit `specify_cli/review/__init__.py`; callers import `specify_cli.review.context_block` by module path (an `__init__.py` change would need a version bump).
7. Create `tests/review/test_context_block.py`:
   - Golden strings for: a recorded range; a derived range with a gap note; a moved-past range; the unavailable form; a no-owned-files range (with the `scope: unscoped` line and no OUTSIDE OWNED FILES line); cited requirements of all four resolutions; a binary file.
   - Budget: 500 synthetic commits and 500 files → the block (minus requirements) ≤ 4,096 bytes, header/provenance/command lines present, `… <k> more` counts exact.
   - Ordering: commits in input order (oldest first), files and out-of-map paths sorted.
   - Determinism: two calls with equal inputs return equal lists.
   - Commands contain full 40-character SHAs; labels contain 12-character SHAs.
   - Quoting: a pathspec with `**`, a space and `:(exclude)` survives `shlex.split` of the printed command unchanged.

**Files**: `src/specify_cli/review/context_block.py` (~170 lines), `tests/review/test_context_block.py` (~220 lines).

**Validation**: `uv run --frozen pytest tests/review/test_context_block.py -q` green; `uv run --frozen ruff check src/specify_cli/review/context_block.py`; `uv run --frozen mypy --strict src/specify_cli/review/context_block.py` zero issues.

---

### Subtask T024: Rewire site 1, `prompt_builder._review_command_lines`

**Purpose**: the `next` review step renders through the new renderer; the old base arms and the second pathspec builder go.

**Steps**:

1. In `src/runtime/next/prompt_builder.py`, replace the body of `_review_command_lines(repo_root, feature_dir, mission_slug, wp_id, wp_meta, workspace, owned)`:
   1. `review_range = resolve_wp_review_range(repo_root, mission_slug, wp_id, owned_files=list(wp_meta.owned_files or []), owned=owned)`.
   2. `cited = resolve_requirement_texts(spec_text, list(wp_meta.requirement_refs or []), mission_type=...)`; read `spec.md` through the placement seam (the same kind-aware read the prompt builder already uses for planning artifacts; never `feature_dir / "spec.md"` if that is a coordination husk). If `spec.md` cannot be read, pass `""` so every ID renders as not declared (no new refusal, NFR-004).
   3. Owned refusal (operator ruling Q7, FR-013): if `owned is not None` and (`not wp_meta.owned_files` or `review_range.status is RangeStatus.UNAVAILABLE`), raise `_review_base_unavailable(wp_id, <why>)` with the existing code and message, and the reason "the work package declares no owned_files" or the range's gap reason. It fires on nothing else.
   4. `lines = render_review_context(review_range, cited)`, then the existing blank line, `render_wp_review_antipattern_checklist()`, blank line.
2. Delete `_review_pathspecs`, `_claim_commit_or_none` and `_lane_review_base`, and their now-unused imports (`claim_commit_for_wp`, `ClaimCommitUnresolved`, `get_feature_target_branch` if no other caller). Grep before deleting: `rg -n "_lane_review_base|_claim_commit_or_none|_review_pathspecs" src tests`.
3. Fix the docstring (it currently claims the repo root uses the claim commit, which the code contradicts): describe the single range authority.
4. Import `resolve_wp_review_range`, `RangeStatus`, `render_review_context` and `resolve_requirement_texts` at module level, beside the existing `specify_cli.review.antipattern_checklist` import (see Context, Layering).
5. Keep `_review_command_lines` and new helpers ≤ 15 complexity.

**Files**: `src/runtime/next/prompt_builder.py` (net shrink, ~-40/+25 lines).

**Validation**: `uv run --frozen pytest tests/next/ tests/runtime/ -q`; `tests/architectural/test_layer_rules.py` green with the ledger at 22.

---

### Subtask T025: Re-pin the site-1 tests (DIRECTIVE_041; re-pin, never delete)

**Purpose**: tests that pin the retired `<base>..HEAD` / `claim..HEAD` text on site 1 are stale in their expected text, not wrong in intent. Re-pin each to the new block. No test function is deleted.

**Steps**:

1. `tests/next/test_prompt_builder_review_base.py`: it imports `_review_pathspecs` (deleted). Re-pin the pathspec test to assert that the prompt's commands carry the range's `owned_pathspecs` (quoted). Re-pin the claim-base / lane-base assertions to the REVIEW RANGE header and the `<base>..<tip>` commands. Keep the `lane_id=None` stand-ins (code-grounding §2) and add one case with `lane_id="lane-planning"` (the production `single_branch` arm).
2. `tests/next/test_prompt_builder_unit.py`: re-pin every assertion on the old review command text or the retired helpers to the new block.
3. `tests/integration/test_prompt_builder_owned_arms.py`: re-pin the owned-arm assertions to the scoped range block; keep each arm's intent.
4. `tests/integration/test_owned_lifecycle_acceptance_review.py` (site 1 through `next`, except the `TestFr025RepositoryRootReviewBase` class, see step 6) and `tests/integration/test_owned_lifecycle_acceptance_e2e.py` (site 1: its review step goes through `next`, and its `agent action review` call only checks the owned-checkout refusal, which happens before any render):
   - `claim..HEAD` text (`git diff {claim}..HEAD --stat -- wp01.py`, `..HEAD`): re-pin to the range block. Assert the scoped `git diff <base>..<tip> -- 'wp01.py'` command and that running it (through `bash -c`) names `wp01.py` and never `wp02.py`.
   - `OWNED_REVIEW_BASE_UNAVAILABLE` cells, per **operator ruling Q7 (FR-013)**: `OWNED_REVIEW_BASE_UNAVAILABLE` keeps its code and message. It fires only when the owned checkout's scoped review range is unavailable, or the WP declares no `owned_files`. The no-owned-files cell stays as it is. Cells that relied on an unresolvable claim commit (`test_claim_on_no_commit_is_blocked`, `test_ambiguous_claim_commit_is_blocked`) are re-pinned to the owned-checkout stamp-stripped fixture (T022), where the scoped range is genuinely unavailable, and keep asserting the blocked decision, the code and that no `..HEAD` / unscoped diff is printed. Never delete them. Rename them to say what they now prove and cite "operator ruling Q7" and FR-013 in their docstrings.
5. Each re-pin carries a one-line rationale in the commit message, e.g. `re-pin: claim..HEAD text replaced by the WP review range (IC-05, DIRECTIVE_041)`.
6. `TestFr025RepositoryRootReviewBase::test_agent_action_review_context_names_the_claim_commit` in `test_owned_lifecycle_acceptance_review.py` drives **site 2** (`agent action review`), which this WP does not change, so it stays green here: leave it untouched. WP07 changes site 2 and will make this one cell stale; the orchestrator hands this file's ownership to WP07 for that re-pin once this WP is approved. Say so in your completion note.

**Files**: the five test files above.

**Validation**: each file green; `git diff --stat` and the diff itself show no test function removed.

---

### Subtask T026: Green, and the validation sweep

**Purpose**: prove red → green on site 1 and run the blast radius required by the charter test policy.

**Steps**:

1. Run `uv run --frozen pytest tests/integration/review/test_review_range_acceptance.py -q`; iterate on T023-T024 (not on the test's assertions) until every cell passes. If an assertion is genuinely wrong against the contract, fix it in a separate commit with the reason.
2. Confirm no new refusal: `rg -n "OwnedRefusalCode\.|ActionContextError\(" src/runtime/next/prompt_builder.py` shows only the existing code.
3. Dead-code gates: `test_no_dead_symbols.py` and `test_no_dead_modules.py` must now be green for WP03's `resolve_wp_review_range` / `specify_cli.review.wp_range` and WP04's `resolve_requirement_texts` / `TEXT_LIMIT` / `TRUNCATION_MARKER` / `specify_cli.requirement_mapping.text` (site 1 is their first `src/` caller). Any remaining red is a real finding; no allowlist entry, no fake caller.
4. Record each command and its pass/fail counts for the PR:

```bash
make test-fast
uv run --frozen pytest tests/review/ tests/next/ tests/runtime/ tests/integration/review/ -q
uv run --frozen pytest tests/integration/test_owned_lifecycle_acceptance_review.py tests/integration/test_owned_lifecycle_acceptance_e2e.py tests/integration/test_prompt_builder_owned_arms.py -q
uv run --frozen pytest tests/architectural/test_execution_context_parity.py tests/architectural/test_git_path_listing_owner.py tests/architectural/test_layer_rules.py tests/architectural/test_no_dead_symbols.py tests/architectural/test_no_dead_modules.py tests/architectural/test_status_read_single_door.py tests/architectural/test_cold_import_status_boundary.py tests/architectural/test_no_legacy_terminology.py -q
uv run --frozen ruff check src/specify_cli/review/context_block.py src/runtime/next/prompt_builder.py
uv run --frozen ruff format --check --force-exclude <every touched file>
uv run --frozen mypy --strict src/specify_cli/review/context_block.py src/runtime/next/prompt_builder.py
```

Do **not** run `make test-full` or the whole `tests/architectural/` directory. Classify any red you did not cause using the CLAUDE.md baseline-red gotcha (stale venv → `uv sync --frozen --all-extras`; harness env leaks → test-local `monkeypatch.delenv`).

---

## Definition of Done

- [ ] C-010 (per work package): T022's two test files are the lane's **first** commit and were red on the lane base for an assertion reason (red output recorded in the PR).
- [ ] `src/specify_cli/review/context_block.py` exists; `render_review_context` reproduces `contracts/review-context-block.md` (golden tests), including the unavailable form, the `scope: unscoped` line, 12-character labels, full SHAs and quoted pathspecs in commands, ordered and truncated lists, and a block ≤ 4,096 bytes without requirements (NFR-001).
- [ ] Site 1 renders from one `WpReviewRange`; the acceptance test proves, per fixture, the exact provenance (`[recorded]`, `window open`), the exact commit list and CHANGED FILES lines, the exclusion of the lane-mate commit on an owned path, printed commands that run through `bash -c` with non-empty output (FR-008), cited requirement text (SC-002), the moved-past note, byte-identical output under two `PYTHONHASHSEED` values, and the unavailable notice with exit 0 on the stamp-stripped lanes cell (FR-013, NFR-004).
- [ ] C-001: no patch text in any prompt and no diff file written, with the detector's positive control on a real `git diff` and the before/after tree snapshot.
- [ ] `_lane_review_base`, `_claim_commit_or_none` and `_review_pathspecs` are gone; `rg` finds no caller.
- [ ] `OWNED_REVIEW_BASE_UNAVAILABLE` keeps its code and message and fires only as operator ruling Q7 states; its unresolvable-claim cells are re-pinned to stamp-stripped fixtures, not deleted.
- [ ] Stale site-1 tests re-pinned with one-line rationales; no test function deleted; `TestFr025RepositoryRootReviewBase` left for WP07.
- [ ] `test_no_dead_symbols.py` and `test_no_dead_modules.py` green, clearing WP03's and WP04's expected reds.
- [ ] NFR-006: ruff, ruff format (`--force-exclude`) and `mypy --strict` clean on touched files, no new suppressions, touched functions ≤ 15 complexity; T026 commands pass with counts recorded.
- [ ] No `tracer-*.md` edited from the lane; anything to record goes in the completion note for the orchestrator.
- [ ] Each subtask recorded with `spec-kitty agent tasks mark-status <Txxx> --status done --mission review-context-wp-diff-01M774QF` (event-sourced; not a ticked box).

## Risks

- **Fixture cost.** Four topology fixtures driving the real CLI are slow. Mitigation: build each template once per module and copy per test.
- **Fixtures must serve WP07 too.** WP07 cannot edit `review_range_fixtures.py`. Mitigation: build every variant listed in T022 (including the stamp-stripped ones) and the public helpers now, documented.
- **`lanes_with_coord` from the repository root checkout.** The status surface is on the coordination branch while code is on the lane; WP03 must not use event commits on lanes (research P3). If the fixture shows a coordination-branch range, the bug is in WP03: report it with the failing cell, do not patch around it here.
- **Shell quoting of glob pathspecs.** Unquoted `**` / `:(exclude)` in printed commands can expand in the reviewer's shell. Mitigation: `shlex.quote` in the renderer, and the acceptance test runs the printed commands through `bash -c`.
- **Stamp stripping must make the range genuinely unavailable.** On lanes there is no event-commit fallback, but the opener's `lane_head` is a fallback: strip both keys on every WP02 event, and assert `UNAVAILABLE` on the range itself before asserting the prompt.
- **Hot file.** `prompt_builder.py` is large. Mitigation: minimal diff, `--force-exclude` format checks.

## Reviewer Guidance

- **Red → green**: the first lane commit contains only the T022 files and the PR records its red run; the final tip is green.
- **Exact provenance**: every fixture cell asserts one exact label; no "recorded or derived" alternatives.
- **Base, not pathspec, excludes the lane-mate**: find the lane-mate commit on WP02's owned path in the fixture and confirm the test asserts its absence.
- **No inline diff** (C-001): the detector's positive control runs on a real `git diff`, and the tree snapshot is compared.
- **Operator ruling Q7**: the only refusal in `_review_command_lines` is `OWNED_REVIEW_BASE_UNAVAILABLE`, on exactly the two conditions; the re-pinned cells use stamp-stripped fixtures and were not deleted.
- **Contract fidelity**: compare `tests/review/test_context_block.py` goldens line by line with `contracts/review-context-block.md`.
- **Re-pins**: each stale test re-pinned, not deleted, with a rationale in the commit message.
- **Layering**: `test_layer_rules.py` green with the ledger at 22.
