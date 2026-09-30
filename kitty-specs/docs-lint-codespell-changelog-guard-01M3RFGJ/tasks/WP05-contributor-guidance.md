---
work_package_id: WP05
title: Contributor guidance
dependencies:
- WP03
- WP04
requirement_refs:
- FR-015
- SC-004
- C-007
planning_base_branch: issue-5426-docs-lint
merge_target_branch: issue-5426-docs-lint
branch_strategy: Planning artifacts for this mission were generated on issue-5426-docs-lint. During /spec-kitty.implement this WP may branch from a dependency-specific base, but completed changes must merge back into issue-5426-docs-lint unless the human explicitly redirects the landing branch.
base_branch: kitty/mission-docs-lint-codespell-changelog-guard-01M3RFGJ
base_commit: 397eb501c8bf4552d0670d3ef22e1a237cb394b0
created_at: '2026-09-30T08:43:35.891225+00:00'
subtasks:
- T026
- T027
- T028
- T029
phase: Phase 3 - Wiring and docs
history:
- at: '2026-09-30T08:10:00Z'
  actor: system
  action: Prompt generated via /spec-kitty.tasks
agent_profile: scribe-sally
authoritative_surface: docs/development/
create_intent:
- tests/docs/test_docs_lint_guidance.py
execution_mode: code_change
model: claude-sonnet-5-5
owned_files:
- docs/development/how-to/review-gates.md
- docs/development/reference/ci-gate-mechanics.md
- docs/development/3-2-page-inventory.yaml
- docs/development/3-2-docs-retrieval-index.yaml
- tests/docs/test_docs_lint_guidance.py
role: implementer
tags: []
task_type: implement
tracker_refs: []
---

# Work Package Prompt: WP05 – Contributor guidance

## ⚡ Do This First: Load Agent Profile

Use the `/ad-hoc-profile-load` skill to load the agent profile specified in the frontmatter, and behave according to its guidance before parsing the rest of this prompt. Load it through the CLI (`spec-kitty agent profile show scribe-sally`); do not just adopt the persona name.

- **Profile**: `scribe-sally`
- **Role**: `implementer`
- **Agent/tool**: `claude`

---

## ⚠️ IMPORTANT: Review Feedback

- Check `review_ref` in the event log and the Activity Log. Address every item.

---

## Objectives & Success Criteria

Issue #5426's acceptance line reads: "The docs contributor guidance (`docs/development/`) says how to run both locally and how to add a word to the ignore list." It is done when:

1. `docs/development/how-to/review-gates.md`'s "Changelog update and style" section (around line 314) explains:
   - running `make docs-lint` and each module command;
   - what each spelling pass covers;
   - adding an ignore word (lowercase, in `[tool.codespell]` `ignore-words-list` in `pyproject.toml`);
   - exempting a quoted literal (a code span or fence);
   - never running bare `codespell` (it scans the whole repo);
   - what the changelog guard enforces, with the expected entry shape and one short compliant example;
   - reading a failure message.
2. `docs/development/reference/ci-gate-mechanics.md` has a `docs-lint` entry (around line 257): an always-on job, why it is always-on, what it runs, that it is blocking, and that it runs no pytest.
3. The page inventory and retrieval index are regenerated, and `check_docs_freshness.py --ci` reports errors=0 (or only pre-existing errors, classified against the base).
4. Following the documented commands on a clean tree runs green (SC-004).

Requirements: FR-015, SC-004.

## Context & Constraints

- Audience persona: match the pages' frontmatter, **lead-developer / maintainer** contributors to this repo (DIRECTIVE_047). Use plain, direct language (the `plain-language` styleguide), US spelling (the page is not in the US-check scope, but stay consistent), and "Mission", never "feature".
- Source material: `kitty-specs/docs-lint-codespell-changelog-guard-01M3RFGJ/quickstart.md` (seed), `contracts/check-cli.md` (exact flags and exit codes), `research.md` R-3/R-4 (the rule table, summarized for humans), and the real scripts in `scripts/docs/`. Code is the source of truth; if the scripts differ from the contract, document the scripts and flag the drift in the Activity Log.
- Divio discipline: `review-gates.md` is a how-to page and `ci-gate-mechanics.md` is a reference page. Keep each section in its page's quadrant: steps in the how-to, facts in the reference.
- Frontmatter: bump `updated:` to `2026-09-30` on both pages, and keep the `description` within 50–180 characters if you touch it.
- Link, don't duplicate: the how-to links to the reference entry and vice versa.

## Branch Strategy

- **Planning base branch**: `issue-5426-docs-lint` · **Merge target branch**: `issue-5426-docs-lint`
- Run `spec-kitty implement WP05` and work in the lane workspace it prints. It must contain WP03 and WP04.

## Subtasks & Detailed Guidance

### Subtask T026 (first) – Red-first guidance test

- Create `tests/docs/test_docs_lint_guidance.py` (fast/unit) **before** writing prose, and confirm it is red. It asserts:
  - `review-gates.md` contains `make docs-lint`, `ignore-words-list`, `pyproject.toml` and each of `--pass typo`, `--pass us` and `--pass unreleased`;
  - `ci-gate-mechanics.md` contains a `docs-lint` heading.
- It also extracts the compliant example entry from `review-gates.md` (a fenced block marked with an HTML comment such as `<!-- docs-lint-example -->`), wraps it in a minimal changelog, runs `scripts.docs.check_changelog_style.check()` on it, and asserts zero error findings. That makes FR-015 non-vacuous.

### Subtask T026 – How-to section

- Extend the existing "Changelog update and style" section rather than creating a new page. A new page would need registration in `how-to/index.md`, `toc.yml` and both inventories.
- Suggested structure (sub-headings under the existing section):
  1. **Run the docs checks locally**: `make docs-lint`, plus the three `--pass` variants and the changelog guard command.
  2. **What gets checked**:
     - the typo pass scope (`docs/**/*.md` except archive/reports/plans and the generated CLI reference, `README.md`, `packs/built-in/**/*.md`);
     - the US scope (`docs/guides/`, `docs/context/`, and the changelog Unreleased section);
     - the guard rules as a compact table: headings/order, entry shape, banned tokens, length.
  3. **Fix a finding**: how to read `path:line: [rule] … — fix`.
  4. **Allow a legitimate word**: the one-line `ignore-words-list` edit, lowercase, with a note that it covers all cases.
  5. **Exempt a quoted literal**: a code span, or a fence for multi-line content; anchors via `<a id>` are already exempt.
  6. **Pitfall**: bare `codespell` scans everything, including frozen trees; use the module or the make target.
- Include one compliant entry example that the guard itself would pass: a headline, then refs outside the bold, then **Before:**/**After:**, under 900 characters, marked for the red-first guidance test.
- Note the known blind spot: hyphenated UK tokens (e.g. `behaviour-driven`) are not flagged by codespell.
- **Campsite, same file**: the example at `review-gates.md:~318` names "sync", which is a dead transport (see CLAUDE.md "Team Kitty is Zeitgeist"). Replace it with a live example.

### Subtask T027 – Reference entry

- `ci-gate-mechanics.md` is grouped by symptom, not by job; it has no always-on job listing. Add a `### docs-lint` subsection under the `## Docs-freshness and registration gates` section (~line 257), or a new `##` if that reads better. **Its `description` is 178 characters (cap 180), so do not lengthen it.** The entry covers:
  - the job name;
  - the trigger (always-on, no path filter), and why;
  - the commands;
  - that it is blocking;
  - that it runs no pytest (and that the planted-violation tests run in `tests-docs`);
  - the owning files (`scripts/docs/check_spelling.py`, `scripts/docs/check_changelog_style.py`, `[tool.codespell]`).

### Subtask T028 – Regenerate and verify

```bash
PYTHONPATH=. .venv/bin/python scripts/docs/inventory_lockfile.py --write docs/development/3-2-page-inventory.yaml
PYTHONPATH=. .venv/bin/python scripts/docs/docs_index.py --write
PYTHONPATH=. .venv/bin/python scripts/docs/check_docs_freshness.py --ci
```

The commands come from `docs/development/index.md:52-60`; note that the two `--write` flags have different shapes. Classify any error against the base.

### Subtask T029 – Walk-through and guards

- Follow your own section's commands verbatim in the lane workspace: `make docs-lint` must exit 0. Plant a typo in a scratch copy of the tree, and confirm that the documented command reports it the way the doc says.
- Run `.venv/bin/python -m pytest tests/docs/test_docs_lint_guidance.py tests/architectural/test_no_legacy_terminology.py tests/docs/test_docs_index_freshness.py -q`, plus any docs test that covers these two pages (`grep -rl "review-gates\|ci-gate-mechanics" tests/`).
- Run `python -m scripts.docs.check_spelling --pass typo` to confirm your new prose adds no typos.

## Risks & Mitigations

- **Doc drift from the code.** Take commands and flags from the scripts' `--help`, not from memory.
- **Freshness gate errors.** Regenerate, then classify.

## Review Guidance

- A new contributor can do all three tasks (run, allow a word, exempt a literal) from the page alone.
- Confirm the Divio quadrants were respected, the `updated:` dates bumped, and both generated files regenerated.

## Activity Log

- 2026-09-30T08:10:00Z – system – Prompt created.
