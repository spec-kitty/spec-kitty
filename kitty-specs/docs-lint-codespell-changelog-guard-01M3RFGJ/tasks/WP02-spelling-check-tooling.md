---
work_package_id: WP02
title: Spelling check tooling
dependencies:
- WP01
requirement_refs:
- FR-001
- FR-002
- FR-004
- FR-005
- NFR-001
- NFR-002
- C-001
- C-004
- NFR-003
- NFR-004
planning_base_branch: issue-5426-docs-lint
merge_target_branch: issue-5426-docs-lint
branch_strategy: Planning artifacts for this mission were generated on issue-5426-docs-lint. During /spec-kitty.implement this WP may branch from a dependency-specific base, but completed changes must merge back into issue-5426-docs-lint unless the human explicitly redirects the landing branch.
base_branch: kitty/mission-docs-lint-codespell-changelog-guard-01M3RFGJ
base_commit: dbec2f454b5e7e957727b00cee411b5b21dcda33
created_at: '2026-09-30T07:56:50.706324+00:00'
subtasks:
- T009
- T010
- T011
- T012
- T013
- T014
phase: Phase 2 - Spelling
history:
- at: '2026-09-30T08:10:00Z'
  actor: system
  action: Prompt generated via /spec-kitty.tasks
agent_profile: python-pedro
authoritative_surface: scripts/docs/
create_intent:
- scripts/docs/check_spelling.py
- tests/docs/test_check_spelling.py
execution_mode: code_change
model: claude-sonnet-5-5
owned_files:
- pyproject.toml
- uv.lock
- scripts/docs/check_spelling.py
- tests/docs/test_check_spelling.py
role: implementer
tags: []
task_type: implement
tracker_refs: []
---

# Work Package Prompt: WP02 – Spelling check tooling

## ⚡ Do This First: Load Agent Profile

Use the `/ad-hoc-profile-load` skill to load the agent profile specified in the frontmatter, and behave according to its guidance before parsing the rest of this prompt. Load it through the CLI (`spec-kitty agent profile show python-pedro`); do not just adopt the persona name.

- **Profile**: `python-pedro`
- **Role**: `implementer`
- **Agent/tool**: `claude`

---

## ⚠️ IMPORTANT: Review Feedback

- Check `review_ref` in the event log (`spec-kitty agent tasks status --mission docs-lint-codespell-changelog-guard-01M3RFGJ`) and the Activity Log. Address every item.

---

## Objectives & Success Criteria

Deliver issue #5426 part 1's tooling: a pinned codespell with one entry point, `python -m scripts.docs.check_spelling`, running three passes (research R-1 to R-3). It is done when:

1. `codespell==2.4.3` is in `[dependency-groups].dev`, `[tool.codespell]` holds the skip and ignore lists from research R-3, `uv.lock` is regenerated, `uv lock --check` is clean, and `tests/architectural/test_pyproject_shape.py` is green.
2. `scripts/docs/check_spelling.py` implements `--pass {typo,us,unreleased,all}`, `--repo-root` and `--changelog` exactly as `contracts/check-cli.md` specifies, with exit codes 0/1/2.
3. Fixture-tree tests prove each pass goes red on a planted word, stays green on exempted forms, and honors the skip list. Every "not reported" assertion is paired with a same-fixture "reported" assertion.
4. ruff, ruff format and mypy are clean. Complexity ≤ 15. Coverage of the new module ≥ 90%.

**Out of scope here**: fixing the real tree. WP03 does that, and `--pass typo` on the live tree is expected to report `migrateable` and `re-using` until WP03 lands. Do not add live-tree tests in this WP.

Requirements: FR-001, FR-002, FR-004, FR-005, NFR-001, NFR-002, C-001, C-004.

## Context & Constraints

- Read: `spec.md`, `plan.md` (IC-02), `research.md` (R-1, R-2, R-3 — **follow R-3's config verbatim**), `contracts/check-cli.md` and `data-model.md` (the Finding shape; reuse the same field names as WP01's `Finding`, but define it locally, because the two scripts must not import each other).
- WP01 has landed `unreleased_section()` in `scripts/release/validate_release.py`; import it.
- **Invoke codespell only as a subprocess**: `[sys.executable, "-m", "codespell_lib", "--toml", str(repo_root / "pyproject.toml"), ...]`. codespell is GPL-2.0-only; never `import codespell_lib` in this module (research R-2).
- Stdlib only otherwise. Do not import `specify_cli`.
- Supply chain (DIRECTIVE_051): the plan's Technical Context records the checks. Install through `uv` from the lockfile only; do not `pip install` codespell into `.venv` by hand.

## Branch Strategy

- **Planning base branch**: `issue-5426-docs-lint` · **Merge target branch**: `issue-5426-docs-lint`
- Run `spec-kitty implement WP02` and work in the lane workspace it prints.

## Subtasks & Detailed Guidance

### Subtask T009 – Dependency pin, config, lockfile

- **Steps**:
  1. In `pyproject.toml` `[dependency-groups]`, `dev` list (around lines 2844–2873), add `"codespell==2.4.3"`. The list is not alphabetical; it is comment-grouped, so append a new commented block at the end. The exact pin is deliberate (research R-1: dictionary content is behavior); add a short inline TOML comment saying so.
  2. Add a `[tool.codespell]` table near the other `[tool.*]` tables:
     ```toml
     [tool.codespell]
     # Scope roots and pass-specific flags live in scripts/docs/check_spelling.py;
     # this table owns only the dictionary behavior shared by every pass.
     skip = "*docs/archive,*docs/archive/*,*docs/reports,*docs/reports/*,*docs/plans,*docs/plans/*,*docs/api/cli-commands.md,*.yaml,*.yml,*.json,*.jsonl,*.pdf,*.png,*.webp,*.jpeg,*.jpg,*.svg,*.css,*.js,*.html"
     ignore-words-list = "accreting,disjointness,pre-empt,pre-empts,pre-emptively,re-declared,trough,unparseable"
     ```
     Keep US spelling in comments.
  3. Run `uv lock` (not `uv sync`, which would re-sync the hand-built `.venv`), then `uv lock --check`. Install into the venv from the lock with `uv sync --frozen --inexact` only if needed to run codespell locally, **or** run the tests with `uv run --frozen`. Record which one you used in the Activity Log.
  4. Run `.venv/bin/python -m pytest tests/architectural/test_pyproject_shape.py -q`.
- **Files**: `pyproject.toml`, `uv.lock`.

### Subtask T010 – Runner core and CLI

- **Steps**:
  1. **Red first**: tests for:
     - output-line parsing (`docs/x.md:12: behaviour ==> behavior` → a Finding with path, line, word and fix);
     - a missing `[tool.codespell]` table → exit 2 with a clear message;
     - codespell not importable → exit 2 with "run `uv sync --frozen`".
  2. Structure the module around small, pure functions:
     - `_codespell_cmd(repo_root, extra_args, files) -> list[str]`
     - `_run_codespell(cmd, cwd) -> str`, via `subprocess.run(..., capture_output=True, text=True, check=False)`, **always with `cwd=repo_root`** (codespell also reads `./pyproject.toml` implicitly, so the cwd must be the root whose config you pass via `--toml`). Return codes verified on 2.4.3: 0 means clean and 65 means hits were found; anything else → raise `SpellcheckError`.
     - **Never invoke codespell with zero file arguments.** With no paths it falls back to scanning `.`, the whole tree. If a pass enumerates zero files, return no findings without calling codespell and let the scanned-count floor catch it. Add a unit test that a zero-file pass never calls `subprocess.run` (monkeypatch it).
     - `_parse_output(stdout, rule, path_map) -> list[Finding]`
     - `run_pass(name, repo_root, changelog) -> list[Finding]`
     - `main(argv) -> int`
  3. **Windows command-line length**: pass files in batches of at most 150 paths per codespell invocation.
  4. Paths in findings are repo-relative with forward slashes, sorted `(path, line, rule)`. Pass **relative** file arguments; codespell echoes the argument form. Print `path:line: [typo|us-spelling] word — fix: <suggestion>`, then the summary `N finding(s) across M file(s); scanned: typo=<K> file(s), us=<K> file(s), unreleased=<L> line(s)` (only the passes that ran). Expose the scanned counts in `run_pass`'s return value (e.g. a `PassResult(findings, scanned)` dataclass) so tests can assert floors (anti-vacuity).
  5. Codespell detection: check `importlib.util.find_spec("codespell_lib")` before running. This does not import the GPL code, so it is fine.

### Subtask T011 – Typo pass

- **Red first**: commit this pass's T014 cases (1–5, 9, 12) before the pass implementation. The same applies to T012 (cases 6–8) and T013 (case 10): tests before code for each pass.

- **Constants**: `TYPO_ROOTS = ("docs", "packs/built-in")` (directories, `*.md` only, recursive) plus `TYPO_FILES = ("README.md",)`.
- **Enumeration**: `sorted(root.rglob("*.md"))`. Skip symlinks (`Path.is_symlink()`) so that `CHANGELOG.md`-style symlinks never double-report; the canonical `docs/changelog/CHANGELOG.md` is a regular file inside `docs/`. The skip list itself stays in `[tool.codespell]` (single owner). Do **not** re-implement the skip globs in Python: pass the files and let codespell's `skip` (the `*dir/*` form works for explicit file arguments) drop them.
- **Flags**: none beyond `--toml`. No ignore-regex: typos inside code spans are still reported (spec edge case).

### Subtask T012 – US pass over guides and context

- **Constants**: `US_ROOTS = ("docs/guides", "docs/context")`, `*.md` recursive.
- **Flags**:
  ```text
  --builtin en-GB_to_en-US
  -L dialogue
  --ignore-regex (`[^`\n]*`|<a id="[^"]*"></a>)     # ONE combined regex: codespell keeps only the LAST --ignore-regex (verified)
  --ignore-multiline-regex ```.*?```
  ```
  Pass a single combined `--ignore-regex`; with repeated flags only the last one applies (verified on 2.4.3). **Known blind spot (verified):** codespell's word regex includes `-`, so hyphenated UK tokens (`organisation-tier`, `behaviour-driven`) are never flagged, anchor or not. The anchor alternative therefore matters only for single-word ids such as `<a id="behaviour"></a>`. Say so in a code comment. `--builtin en-GB_to_en-US` alone replaces the default dictionaries, which is intended: the typo pass owns typos.
- Keep these flags in one module constant, `US_FLAGS`, so a reader sees the US policy in one place.

### Subtask T013 – US pass over the Unreleased section

- **Steps**:
  1. Read `--changelog` (default `docs/changelog/CHANGELOG.md`) and call `unreleased_section(text)`. If it is `None`, return no findings.
  2. Write the section lines to a temp file (`tempfile.TemporaryDirectory()`; name it `unreleased.md` so the `*.md`-agnostic skip globs do not match). Run the US flags on it.
  3. Map each finding back: `real_line = section.start_line + reported_line`. The section's first body line is `start_line + 1`, so check the off-by-one with a test. Report the path as the canonical changelog path.
- **Test**: a changelog fixture with `behaviour` at a known line in the Unreleased section, and `` `cancelled` `` in a code span there, plus `behaviour` in a released section. Expect exactly one finding, at the exact real line.

### Subtask T014 – Fixture-tree tests

Build a `tmp_path` repo per test, via a pytest fixture helper `make_repo(tmp_path, files: dict[str, str])` that also copies the **real** `pyproject.toml` (so the real `[tool.codespell]` is exercised; non-vacuity). Then call `main(["--repo-root", str(tmp_path), "--pass", ...])` and also, once, the subprocess `python -m scripts.docs.check_spelling --repo-root <tmp>` from the real repo root. Cases:

| # | Fixture | Expect |
|---|---|---|
| 1 | `docs/guide.md` with "the reding tests" | typo red, finding names the file and line 1 |
| 2 | same word in `docs/archive/old.md`, `docs/reports/r.md`, `docs/plans/p.md` **plus** case 1's file | only `docs/guide.md` reported (pairs skip with positive) |
| 3 | `docs/guide.md` with "disjointness" | green (ignore list) |
| 4 | `packs/built-in/x/prompt.md` with a typo; `packs/built-in/x/tool.py` with the same typo | only the `.md` reported |
| 5 | `README.md` with a typo | reported |
| 6 | `docs/guides/g.md`: prose "behaviour", `` `behaviour` `` span, fenced block with "behaviour", `<a id="behaviour"></a>` (single-word id, so the anchor regex is load-bearing) | US: exactly 1 finding (the prose) |
| 7 | `docs/other/o.md` with "behaviour" | US: none; typo: none (proves US scope) |
| 8 | "dialogue" in `docs/context/c.md` | US: none |
| 9 | typo inside a code span in `docs/guide.md` | typo pass still reports it |
| 10 | Unreleased mapping (T013), **parametrized over a bare `## [Unreleased]` and `## [Unreleased] - 4.0.0rc5` heading**. The section also contains a fenced block with a `## [9.9.9]` line, and a UK prose word **after** that fence | exactly one finding, at the exact real line of the post-fence word. That word is reported only if the shared fence-aware `unreleased_section()` is used, which is FR-016's cross-check. Also monkeypatch `scripts.release.validate_release.unreleased_section` with a spy and assert that it was called |
| 11 | determinism | three runs, identical stdout |
| 12 | a symlink **inside the fixture's `docs/`** (`docs/alias.md` → `docs/changelog/CHANGELOG.md`) with a typo in the target | reported once, under `docs/changelog/CHANGELOG.md` (proves the `is_symlink()` skip) |
| 13 | the exact pin | `pyproject.toml` dev group contains `codespell==2.4.3`, and `uv.lock`'s `codespell` package version is `2.4.3` (NFR-002) |
| 14 | scanned floors on the fixture | `PassResult.scanned` equals the number of in-scope fixture files (skipped trees excluded) |

Mark the module `pytestmark = [pytest.mark.unit, pytest.mark.fast]`. If codespell is missing in the environment, fail with the actionable message rather than skip. The dependency is declared, so a skip would hide a stale venv.

## Test Strategy

```bash
uv lock --check
.venv/bin/python -m pytest tests/architectural/test_pyproject_shape.py tests/docs/test_check_spelling.py -q
.venv/bin/python -m pytest tests/docs/test_check_spelling.py --cov=scripts.docs.check_spelling --cov-report=term-missing -q
.venv/bin/python -m scripts.docs.check_spelling --pass typo   # expect exactly migrateable + re-using on the live tree (WP03 fixes them)
.venv/bin/ruff check scripts/docs/check_spelling.py tests/docs/test_check_spelling.py && .venv/bin/ruff format --check scripts/docs/check_spelling.py tests/docs/test_check_spelling.py
.venv/bin/mypy scripts/docs/check_spelling.py
```

Record the timings of the three passes on the live tree (NFR-001, < 5 s total) in the Activity Log.

**Non-vacuity proof**: temporarily drop `--builtin en-GB_to_en-US` from `US_FLAGS` and confirm case 6 goes red. Temporarily drop the ignore-regex and confirm case 6 reports 3+ findings. Restore both and record the results.

## Risks & Mitigations

- **Skip globs not applying to explicit file arguments.** Case 2 guards it; use the exact `*dir,*dir/*` pair.
- **The US regex leaking into the typo pass.** Case 9 guards it.
- **codespell exit codes.** Verify the value against 2.4.3 rather than assuming it.
- **uv re-syncing the hand-built venv.** Use `uv lock` and `uv run --frozen`, never a bare `uv sync`.

## Review Guidance

- Confirm that codespell is only ever invoked as a subprocess, with an explicit `--toml`.
- Confirm that every negative case has its same-fixture positive.
- Confirm that `uv.lock` changed only in the codespell entry (and its hashes).

## Activity Log

- 2026-09-30T08:10:00Z – system – Prompt created.
