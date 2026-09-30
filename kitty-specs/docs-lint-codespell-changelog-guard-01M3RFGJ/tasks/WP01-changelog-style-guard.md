---
work_package_id: WP01
title: Changelog Unreleased style guard and canonical extractor
dependencies: []
requirement_refs:
- FR-008
- FR-009
- FR-010
- FR-011
- FR-012
- FR-016
- NFR-003
- NFR-004
- C-002
- C-003
- SC-002
- SC-005
- FR-003
planning_base_branch: issue-5426-docs-lint
merge_target_branch: issue-5426-docs-lint
branch_strategy: Planning artifacts for this mission were generated on issue-5426-docs-lint. During /spec-kitty.implement this WP may branch from a dependency-specific base, but completed changes must merge back into issue-5426-docs-lint unless the human explicitly redirects the landing branch.
base_branch: kitty/mission-docs-lint-codespell-changelog-guard-01M3RFGJ
base_commit: 44cd7cc1865edee46464a7ab4e2c3a2d80d9e41a
created_at: '2026-09-30T07:24:56.238140+00:00'
subtasks:
- T001
- T002
- T003
- T004
- T005
- T006
- T007
- T008
phase: Phase 1 - Foundation
history:
- at: '2026-09-30T08:10:00Z'
  actor: system
  action: Prompt generated via /spec-kitty.tasks
agent_profile: python-pedro
authoritative_surface: scripts/docs/
create_intent:
- scripts/docs/check_changelog_style.py
- tests/docs/test_changelog_style.py
- tests/docs/test_unreleased_section.py
- tests/docs/fixtures/changelog_unreleased_pre_rewrite.md
execution_mode: code_change
model: claude-sonnet-5-5
owned_files:
- scripts/release/validate_release.py
- scripts/docs/check_changelog_style.py
- tests/docs/test_changelog_style.py
- tests/docs/test_unreleased_section.py
- tests/docs/fixtures/changelog_unreleased_pre_rewrite.md
- docs/changelog/CHANGELOG.md
role: implementer
tags: []
task_type: implement
tracker_refs: []
---

# Work Package Prompt: WP01 – Changelog Unreleased style guard and canonical extractor

## ⚡ Do This First: Load Agent Profile

Use the `/ad-hoc-profile-load` skill to load the agent profile specified in the frontmatter, and behave according to its guidance before parsing the rest of this prompt. Load it through the CLI (`spec-kitty agent profile show python-pedro`); do not just adopt the persona name.

- **Profile**: `python-pedro`
- **Role**: `implementer`
- **Agent/tool**: `claude`

---

## ⚠️ IMPORTANT: Review Feedback

- **Has review feedback?** Check the `review_ref` field in the event log (`spec-kitty agent tasks status --mission docs-lint-codespell-changelog-guard-01M3RFGJ`) or the Activity Log below.
- Address every feedback item before you mark the work complete.

---

## Markdown Formatting

Wrap HTML/XML tags in backticks and use language identifiers on code blocks.

## Objectives & Success Criteria

Deliver the changelog `## [Unreleased]` style guard (issue #5426, part 2) and the single shared Unreleased extractor. It is done when:

1. `scripts/release/validate_release.py` exposes `unreleased_section(text) -> UnreleasedSection | None`, built on the existing `CHANGELOG_HEADING_RE` / `parse_changelog_heading`.
2. `python -m scripts.docs.check_changelog_style` exits 0 on the current `docs/changelog/CHANGELOG.md`, printing warnings for the 948- and 972-code-point entries. It exits 1 on the pre-rewrite Unreleased section (fixture).
3. Every rule in FR-008 to FR-011, and every banned token in FR-010, has a planted-violation test that fails when the rule is violated. Every exemption has its own positive test. Every failure message names the entry (`[section] headline excerpt`) and the exact fix (FR-012).
4. The two Changed entries named in spec C-003 carry a truthful `**Before:**`. The two released-section typos are fixed. One Internal entry for this change is added, and the guard passes on it.
5. ruff, ruff format and mypy are clean on the new and changed files. Complexity ≤ 15 per function. Line coverage of the new module is ≥ 90%.

Requirements: FR-008, FR-009, FR-010, FR-011, FR-012, FR-016, NFR-003, NFR-004, C-002, C-003, SC-002, SC-005.

## Context & Constraints

- Read first: `kitty-specs/docs-lint-codespell-changelog-guard-01M3RFGJ/spec.md`, then `plan.md` (IC-01), `research.md` (**R-4 is the calibration table; follow it exactly**, and R-5 covers the extractor), `data-model.md` and `contracts/check-cli.md`.
- Charter: ATDD red-first (write the failing test before each rule), non-vacuous gates (DIRECTIVE_043), and no full `tests/architectural/` sweep.
- **Stdlib only.** No new dependency in this WP. Do not import `specify_cli` from these scripts.
- **Never modify** `kitty-specs/`, `kitty-ops/` or `docs/archive/`.
- **Released changelog sections are only typo-corrected** (C-002). The guard reads only the Unreleased section.
- Run scripts as modules from the repo root: `python -m scripts.docs.check_changelog_style`. `scripts/docs/` is a package; `scripts/` and `scripts/release/` are namespace packages. Import the extractor with `from scripts.release.validate_release import unreleased_section`, as `tests/docs/test_sync_changelog.py` already does for `scripts.release.extract_changelog`.
- Closest existing test template: `tests/docs/test_tracker_egress_upgrade_note_3108.py`, which feeds text to the checker, runs it once on the real file, and plants mutants. Mark the new test modules with `pytestmark = [pytest.mark.unit, pytest.mark.fast]`.

## Branch Strategy

- **Strategy**: populated by finalize-tasks
- **Planning base branch**: `issue-5426-docs-lint`
- **Merge target branch**: `issue-5426-docs-lint`

> Execution worktrees are allocated per computed lane from `lanes.json`. Run `spec-kitty implement WP01` (or `spec-kitty agent action implement WP01 --agent claude`) and work in the workspace path it prints. Do not reconstruct paths.

## Subtasks & Detailed Guidance

### Subtask T001 – `unreleased_section()` extractor

- **Purpose**: one definition of "the Unreleased section" for both the guard and WP02's spelling pass (FR-016).
- **Steps**:
  1. **Red first:** create `tests/docs/test_unreleased_section.py` with cases for:
     - a bare `## [Unreleased]` heading;
     - `## [Unreleased] - 4.0.0rc5`;
     - a section ending at `## [4.0.0rc4] - 2026-09-20`;
     - a section running to EOF;
     - no Unreleased heading → `None`;
     - a `## [9.9.9]` line inside a fenced block (three backticks) inside the section, which must NOT end it;
     - `start_line` is the 1-based line of the heading;
     - `lines` excludes the heading and the terminating heading.
  2. In `scripts/release/validate_release.py`, next to `parse_changelog_heading`, add:
     ```python
     @dataclass(frozen=True)
     class UnreleasedSection:
         start_line: int          # 1-based line of the "## [Unreleased]..." heading
         lines: tuple[str, ...]   # body lines, heading and terminator excluded

     def unreleased_section(text: str) -> UnreleasedSection | None: ...
     ```
     - Walk the lines, toggling an `in_fence` flag on lines whose stripped form starts with a triple backtick.
     - Outside a fence, a line starting with `## ` counts as a release heading only if `parse_changelog_heading(line)` returns non-None.
     - The first heading with `unreleased=True` starts the section, and the next release heading (any) ends it.
     - The module has no `__all__`; do not add one. **Do not add any `from scripts…` import to `validate_release.py`**: it also runs as a bare script in the release workflows (`release.yml:128`, `release-readiness.yml:96-104`). The new code is stdlib-only.
  3. Keep the function at complexity ≤ 15; extract a small `_is_fence(line)` helper if needed.
- **Files**: `scripts/release/validate_release.py`, `tests/docs/test_unreleased_section.py` (new).
- **Notes**:
  - Do not touch `scripts/release/extract_changelog.py` or `tests/contract/test_terminology_guards.py`. Leaving them is a deliberate locality decision (research R-5).
  - Run the existing tests that import `validate_release` to prove no regression: `grep -rl "validate_release" tests/ --include="*.py"`, then run them.

### Subtask T002 – Guard skeleton, entry parser, CLI

- **Purpose**: parse the section into Entries and render Findings deterministically.
- **Steps**:
  1. **Red first:** in `tests/docs/test_changelog_style.py`, add parser tests:
     - entries are split at top-level `- ` bullets;
     - continuation lines join to their entry;
     - a nested `  - ` item becomes a nested item with its own lines;
     - `section` and `subsection` are tracked from `###` and `####`;
     - `line` is the real file line (section `start_line` + offset);
     - the preamble (text before the first `###`) is captured separately.
  2. Create `scripts/docs/check_changelog_style.py` with the data-model shapes (`Entry`, `Finding`, both frozen dataclasses). Also add:
     - `parse_section(section: UnreleasedSection) -> ParsedSection`, which holds the preamble lines with their line numbers, the headings with levels and lines, and the entries;
     - `check(text: str, path: str = "docs/changelog/CHANGELOG.md") -> list[Finding]`, sorted by `(path, line, rule)`;
     - `main(argv: list[str] | None = None) -> int`, using argparse with `--changelog PATH` (default `docs/changelog/CHANGELOG.md` relative to the repo root; resolve the repo root from `Path(__file__).resolve().parents[2]`).
     - An `if __name__ == "__main__": raise SystemExit(main())` block.
  3. Exit codes follow `contracts/check-cli.md`: 0 means no error findings (warnings may print), 1 means an error finding, 2 means a usage error or unreadable file. With no Unreleased section, print `no [Unreleased] section found; nothing to check` and return 0.
  4. Output format: `path:line: [rule] [<section>] <headline excerpt ≤ 60 chars> — <fix>`. Warnings get a `warning: ` prefix. End with the summary line `N error(s), M warning(s)`.
  5. Code-span handling helper: `_strip_code_spans(text) -> str` replaces `` `...` `` spans with an equal number of spaces, so offsets are preserved. Rules that say "outside code spans" run on the stripped text.
- **Files**: `scripts/docs/check_changelog_style.py` (new), `tests/docs/test_changelog_style.py` (new).

### Subtask T003 – Heading rules (FR-008)

- **Rule id**: `heading-order`, `heading-unknown`, `heading-duplicate`, `subheading-placement`.
- **Definition**:
  - The allowed `###` headings, in order: `Breaking`, `Upgrade Notes`, `Added`, `Changed`, `Fixed`, `Internal`. Each appears at most once, and they appear in that relative order (gaps allowed; empty sections allowed).
  - `####` is allowed only under `### Fixed`, unique within its parent.
  - Any other `###` text is `heading-unknown`.
- **Fix texts** (examples; keep them this concrete):
  - "Merge this `### Changed` into the earlier one at line N."
  - "Move `### Added` above `### Changed`; required order: Breaking, Upgrade Notes, Added, Changed, Fixed, Internal."
  - "Use one of: Breaking, Upgrade Notes, Added, Changed, Fixed, Internal."
- **Tests (red first)**: plant a duplicate `### Fixed`, an out-of-order `### Added`, an unknown `### Security`, a `####` under Changed and a duplicate `####` under Fixed. One test per violation, each asserting the rule id, the line and the fix text. Also a positive test: an empty `### Added` section passes.

### Subtask T004 – Entry-shape rules (FR-009)

Follow research R-4 exactly.

- **`headline-missing`**: in Breaking, Upgrade Notes, Added, Changed and Fixed, an entry must start with `- **` and contain a closing `**`. Fix: "Start the entry with a bold headline: `- **What changed** (#1234).`"
- **`refs-in-bold`**: inside the bold headline, with code spans stripped, a `#\d+` fails. `owner/repo#N` outside the bold is fine. A `WP##` inside a code span inside the bold is fine; the current text has one. Fix: "Move `(#1234)` out of the bold headline: `- **Headline** (#1234).`"
- **`contrast-missing`**: in Breaking, Changed and Fixed, the entry passes if **any** of these holds:
  - (a) it contains `**Before:**`;
  - (b) it contains both `**Why:**` and `**After:**`;
  - (c) the body after the headline and refs is ≤ 2 sentences **and** ≤ 300 characters.

  Count sentences as `.`, `!` or `?` followed by whitespace or end, on code-span-stripped text. Added and Upgrade Notes are exempt. Fix: "Add a `**Before:**` sentence describing the old behavior (or shorten the body to at most 2 sentences / 300 characters)."
- **`internal-shape`**: an Internal entry must be a single physical line with no nested items and no `**Before:**`. Fix: "Keep Internal entries to one line; move user-visible detail to Changed or Fixed."
- **Tests (red first)**:
  - refs inside bold → red, and `WP##` in a code span inside bold → green (same fixture);
  - a 400-character Fixed entry without contrast → red; the same body cut to 2 sentences / 250 characters → green;
  - a Breaking entry with `**Why:**` + `**After:**` → green, with only `**Why:**` → red;
  - an Upgrade Notes entry without contrast → green;
  - a two-line Internal entry → red;
  - an Internal bullet without bold → green;
  - a Changed entry without a bold headline → red;
  - a cross-repo ref `(#4990, spec-kitty/spec-kitty-events#69)` → green.

### Subtask T005 – Banned tokens (FR-010)

Rule id `banned-token`, with the token named in `where`. Apply to preamble lines **and** entries.

| Token | Match on | Regex / literal | Fix text |
|---|---|---|---|
| boilerplate | raw | `Bug-fix\s*[;—–-]\s*no CLI version bump` (the pre-rewrite text has both the `;` and the em-dash forms) | "Delete the boilerplate; the section heading already says it is a fix." |
| requirement id | code-span-stripped | `\b(?:FR\|NFR\|SC\|C\|D)-\d+[a-z]?(?:\.\d+)?\b` | "Describe the behavior instead of citing internal requirement `FR-011`; put an ID in backticks only when quoting CLI output." |
| ULID | raw, code spans included (a backticked `DM-<ULID>` is still maintainer-only noise) | `\b[0-7][0-9A-HJKMNP-TV-Z]{25}\b` | "Remove the mission/event ULID; link the issue instead." |
| evidence path | raw | `.kittify/evidence/` | "Remove the local evidence path; it is not reachable by users." |
| planning ref | raw | `planning#` | "Remove the private planning-repo reference." |
| all-caps | code-span-stripped, case-sensitive | `\b(?:DEFAULT\|REFUSE\|FAIL)\b` | "Write `default`/`refuses`/`fails` in lowercase prose, or put the literal CLI token in backticks." |
| retired command | raw (code spans included) | `spec-kitty merge(?![-\w])` | "Use `spec-kitty consolidate`; `spec-kitty merge` was renamed (only the rename entry may name it)." |

- **Rename-context exemption for `spec-kitty merge`**: allowed only when the same entry, or for the preamble the same paragraph (lines between blank lines), also contains `spec-kitty consolidate`. On the current text this exempts the preamble (line ~22), the Breaking rename entry (~26) and the Upgrade Note "Replace `spec-kitty merge` with…" (~38). Verify with a quick run.
- **Tests (red first)**:
  - one planted violation per row;
  - the `spec-kitty merge` plant is backticked, `` `spec-kitty merge --resume` ``, inside a Fixed entry without `consolidate` → red;
  - `spec-kitty merge-driver-traces` → green;
  - `` `FR-002.3` `` in backticks → green, and bare `FR-002.3` → red (same fixture);
  - `` `FAIL` `` in backticks → green, and `PLAN_SETUP_FAILED` → green;
  - a lowercase `default` → green;
  - **rename-context same-fixture pair**: plant into a *copy of the live Unreleased text* (whose preamble already names `spec-kitty consolidate`). A new Fixed entry saying "`spec-kitty merge --resume` now …" → red. The same entry with "(use `spec-kitty consolidate --resume`)" appended → green. This proves the exemption is entry/paragraph-scoped, not section-scoped;
  - **preamble plant**: add a new preamble paragraph containing `FR-011` and one containing `spec-kitty merge` without `consolidate`. Both → red, with `line` pointing at the preamble line;
  - the em-dash boilerplate variant → red.

### Subtask T006 – Length (FR-011)

- **Rule id**: `length` (error) and `length-warning` (warning).
- **Measure**: `len()` in Unicode code points over the entry's own raw lines joined with `\n`, markdown included, **excluding** nested items. Each nested item is measured separately by the same rule. Fail at > 1,200; warn at > 900.
- **Fix text**: "Entry is N characters (limit 1,200); split it or move detail to the docs." Warning text: "Entry is N characters; aim for 900 or fewer."
- **Tests (red first)**:
  - a 1,201-code-point entry → error;
  - a 901 entry → exactly one finding of severity `warning`, and `main()` returns 0;
  - an entry with 3 nested items of 500 each (total > 1,200) → no error;
  - one nested item of 1,201 → error;
  - multi-byte check: an entry of 1,199 code points containing `✓` passes, proving code points, not bytes.

### Subtask T007 – Changelog text edits (C-002, C-003, FR-003 changelog half)

1. **Changed-entry defects** (the current lines are about 93 and 96 of `docs/changelog/CHANGELOG.md`):
   - "`implement` on a `single_branch` mission refuses unsafe checkouts, with an error code and a fix" (#5100)
   - "Creating a `single_branch` mission on a protected branch now switches your repository root checkout to a new mission branch" (#5100)

   Add a **truthful** `**Before:**` sentence to each. Leads the brownfield scout verified:
   - The "refuses unsafe checkouts" entry: commit `8482d32bf3` introduced the `WRITE_CHECKOUT_*` codes. Before it, `implement` allocated lane worktrees for `single_branch` missions (corroborated by the Before at changelog line ~92).
   - The "switches your repository root checkout" entry: commit `9e73b3cf0e` introduced the minted branch. Read the prior behavior at `git show 9e73b3cf0e^:src/specify_cli/core/mission_creation.py` (the `ProtectedBranchRefused` path around lines 446–461); the Before at line ~71 corroborates it.
   - **Cite the SHA and quote the prior code or message in the Activity Log**; the reviewer verifies both entries against it.
   Source the old behavior from history, never invent it: `unset GITHUB_TOKEN; gh issue view 5100 --repo spec-kitty/spec-kitty`, the PR that closed it, and `git log -S WRITE_CHECKOUT_OCCUPIED --oneline` plus the pre-change code. If the prior behavior cannot be established, stop and report instead of guessing. Keep each entry ≤ 1,200 code points.
2. **Released-section typos** (C-002 allows typo fixes only):
   - line ~3970, "…skip the gate, reding the gate-observability tests" → "turning the gate-observability tests red" (not codespell's "reading");
   - line ~5811, "filesytem" → "filesystem".

   Change nothing else in released sections.
3. **Internal entry**: add one single-line entry under `### Internal`, for example "- Docs prose is now spell-checked in CI (typos, and US spelling in the guides, context pages and this section), and a style guard keeps Unreleased entries in the Breaking…Internal shape (#5426)." It must pass `internal-shape` and the US-spelling expectations (US spelling throughout).
4. Record each edited entry (section + headline) in the Activity Log. They are listed in the PR body per C-003.

### Subtask T008 – Live text, real-world red control, entry point

- **Fixture**: `tests/docs/fixtures/changelog_unreleased_pre_rewrite.md` holds the pre-rewrite changelog **Unreleased section only**, frozen from `git show 294f4c352d:docs/changelog/CHANGELOG.md` (the heading plus section body, up to the next release heading). Add a one-line HTML comment at the top of the fixture naming its source commit. The tests must tolerate that comment: place it before the heading.
- **Tests**:
  - `test_live_changelog_passes`: `check()` on the real `docs/changelog/CHANGELOG.md` yields zero `error` findings and at least one `length-warning`, the positive control that the parser saw real entries. Also assert that the parsed entry count is ≥ 200.
  - `test_pre_rewrite_section_fails`: `check()` on the fixture yields errors for at least `heading-duplicate`, `heading-order`, `banned-token` (boilerplate), `banned-token` (requirement id) and `banned-token` (all-caps). Assert each rule id is present.
  - `test_module_entry_point`: `subprocess.run([sys.executable, "-m", "scripts.docs.check_changelog_style", "--changelog", <tmp copy with one planted violation>], cwd=repo_root)` → returncode 1, stdout names the entry; on a clean tmp copy → returncode 0. This proves the production entry point (non-vacuity rule: exercise the production path).
  - `test_no_unreleased_section`: a changelog without one → 0 plus the message.
  - `test_deterministic`: three runs give identical output (NFR-003).
  - `test_every_failure_message_is_actionable` (FR-012): **one parametrized test over every planted case from T003–T006**. For each case, render the finding line and assert that it contains the `[section]`, a headline excerpt (for entry rules) and the rule's fix text. Keep the planted cases in one module-level table so this test and the per-rule tests share them.
  - In `test_pre_rewrite_section_fails`, also assert the ULID finding: the fixture contains a backticked `DM-01M3EC2FMWKCKGSBX1QHC7GFCJ`, the only real-world ULID case.

## Test Strategy

```bash
.venv/bin/python -m pytest tests/docs/test_unreleased_section.py tests/docs/test_changelog_style.py -q
.venv/bin/python -m pytest $(grep -rl "validate_release" tests/ --include="*.py") -q
.venv/bin/python -m scripts.docs.check_changelog_style            # exit 0, warnings only
.venv/bin/ruff check scripts/docs/check_changelog_style.py scripts/release/validate_release.py tests/docs/test_changelog_style.py tests/docs/test_unreleased_section.py
.venv/bin/ruff format --check scripts/docs/check_changelog_style.py scripts/release/validate_release.py tests/docs/test_changelog_style.py tests/docs/test_unreleased_section.py
.venv/bin/mypy scripts/docs/check_changelog_style.py scripts/release/validate_release.py
.venv/bin/python -m pytest tests/docs/test_changelog_style.py --cov=scripts.docs.check_changelog_style --cov-report=term-missing -q   # >= 90%
.venv/bin/python -m pytest tests/architectural/test_no_legacy_terminology.py tests/contract/test_terminology_guards.py tests/release/test_validate_changelog_entry.py tests/release/test_validate_metadata_yaml_sync.py tests/release/test_validate_release.py -q
```

**Non-vacuity proof (put it in the Activity Log):** for each of T003–T006, temporarily make the rule function return `[]`, run the tests, confirm its planted tests go red, then restore. Record the counts.

Use `.venv/bin/spec-kitty`, never the bare `spec-kitty` shim.

## Risks & Mitigations

- **Over-fitting the rules to today's text.** Every exemption has a paired red case on the same fixture.
- **Inventing a Before for the two Changed entries.** Source it from #5100 history, or stop and report.
- **Fence-unaware extraction.** Covered by the T001 fence test.
- **Complexity creep in `check()`.** Keep one function per rule and a small dispatcher.

## Review Guidance

- Verify red→green: the ATDD tests commit precedes the implementation commit in the lane.
- Re-run the non-vacuity stub proof for at least two rules.
- Confirm that no released section changed except the two typo lines (`git diff` on CHANGELOG.md and inspect the hunks).
- Confirm that every failure message contains the section, a headline excerpt and a concrete fix; the parametrized FR-012 test enforces this.
- **Verify the two `**Before:**` sentences** against the SHAs and quotes in the Activity Log (`8482d32bf3`, `9e73b3cf0e^`). Reject if either is unsourced.

## Activity Log

- 2026-09-30T08:10:00Z – system – Prompt created.
- 2026-09-30T07:48:58Z – claude – shell_pid=3009161 – Profile python-pedro loaded via 'spec-kitty agent profile show python-pedro' + 'charter context --action implement': applied its initialization (TDD, quality gate pytest/ruff/mypy before handoff, no architectural decisions), directives 010/043/044/045/051/024/025/030/034/041 and tactics tdd-red-green-refactor + acceptance-test-first + architectural-gate-non-vacuity; boundary: no changes outside WP01 owned files.
- 2026-09-30T07:49:00Z – claude – shell_pid=3009161 – Before sources (C-003). Entry 'implement on a single_branch mission refuses unsafe checkouts' (#5100): git log -S WRITE_CHECKOUT_OCCUPIED first hit is 8482d32bf3 (WP04); 'git grep WRITE_CHECKOUT 8482d32bf3^ -- src' is empty; in 8482d32bf3^ create_lane_workspace repo-root arm (is_planning_lane) only calls record_claim_base(repo_root, repo_root, mission_slug, wp_id) then returns, no branch/occupancy/dirty check. Before written: when a WP ran in the repo root checkout, implement did not check the branch, another in-progress WP, or uncommitted changes. Entry 'Creating a single_branch mission on a protected branch switches your checkout' (#5100): 9e73b3cf0e introduced _mint_protected_single_branch_mission_branch. In 9e73b3cf0e^:src/specify_cli/core/mission_creation.py: _BOOTSTRAP_META_COMMIT_SKIPS = (ProtectedBranchRefused, SafeCommitDestinationNotFound, SafeCommitHeadMismatch); step 8.5 'except _BOOTSTRAP_META_COMMIT_SKIPS: scaffold_commit_skipped = True ... Skipping bootstrap scaffold commit for %s on planning branch %s'; step 10 'if scaffold_commit_skipped: ... uncommitted_files.extend(skipped_scaffold)'; no branch mint. Before written: on a protected branch such as main it skipped the scaffold commit and left the new mission's files uncommitted.
- 2026-09-30T07:49:01Z – claude – shell_pid=3009161 – Edited changelog entries (C-003): [Changed] 'implement on a single_branch mission refuses unsafe checkouts...' (+Before/After), [Changed] 'Creating a single_branch mission on a protected branch now switches...' (+Before/After, now 991 chars, warns), [Internal] new entry 'Docs prose is now spell-checked in CI ...(#5426)'. Released-section typo lines only: 'reding' -> 'turning the gate-observability tests red' (~L3970), 'filesytem' -> 'filesystem' (~L5811).
- 2026-09-30T07:49:02Z – claude – shell_pid=3009161 – Red-first commits: 4e7e2721be (extractor, ImportError at collection), cf184c9258 (parser/CLI, ModuleNotFoundError), heading tests 13 failed/19 passed, entry-shape 22 failed/43 passed, banned-token 39 failed/69 passed, length 9 failed/109 passed, live-text 2 failed/122 passed. Non-vacuity stubs (rule returns []): check_headings 13 failed/19 passed; check_headline 4F/61P; check_refs_in_bold 3F/62P; check_contrast 9F/56P; check_internal_shape 6F/59P; check_banned_tokens 39F/69P; check_length 9F/109P. Final: 135 passed; coverage of check_changelog_style 99%.
