# Research: Docs lint: codespell and changelog Unreleased guard

Sources:
- Two grounding scouts (researcher-robbie, opus): a CI seam map and codespell measurements.
- The post-spec adversarial squad: reviewer-renata (non-vacuity) and architect-alphonso (authority/CI).

All measurements used codespell 2.4.3 against this branch (PR #5420 changelog text) and against `main`, on 2026-09-30.

## R-1 Tool and pin

- **Decision**: `codespell==2.4.3`, pinned exactly in `[dependency-groups].dev`, with `uv.lock` regenerated.
- **Rationale**: the tool choice is fixed by the operator (issue #5426). An exact pin makes the dictionary reproducible, so a new codespell release cannot turn CI red (NFR-002). The dev group otherwise uses `>=` ranges with the lockfile carrying the exact version. This pin is deliberately stricter because dictionary content is behavior.
- **Alternatives**: `typos` (rejected by the operator: 78 `mis-` false positives); a `>=` range (rejected: dictionary drift).

## R-2 Invoke codespell as a subprocess

- **Decision**: run `[sys.executable, "-m", "codespell_lib", "--toml", "<repo>/pyproject.toml", ...]` via `subprocess.run`, and parse its `path:line: word ==> fix` output.
- **Rationale**:
  - codespell is GPL-2.0-only. A subprocess keeps its code out of our MIT modules' import graph.
  - A subprocess also avoids redirecting codespell's global stdout.
  - An explicit `--toml` path makes the config independent of the working directory.
  - `python -m codespell_lib` works in 2.4.3 (the package ships `__main__.py`).
- **Alternatives**: `codespell_lib.main(*args)` under `redirect_stdout` (prototyped and working, but it imports GPL code into the script and couples to stdout capture).

## R-3 Configuration and scope

- **`[tool.codespell]`** (the only dictionary config):
  - `skip`: `*docs/archive,*docs/archive/*,*docs/reports,*docs/reports/*,*docs/plans,*docs/plans/*,*docs/api/cli-commands.md,*.yaml,*.yml,*.json,*.jsonl,*.pdf,*.png,*.webp,*.jpeg,*.jpg,*.svg,*.css,*.js,*.html`. The `*dir,*dir/*` pair is required: a bare or `./`-prefixed dir only matches in some invocation modes (tested).
  - `ignore-words-list`: `accreting,disjointness,pre-empt,pre-empts,pre-emptively,re-declared,trough,unparseable`. Entries are lowercase: `-L sme` ignores every case, while `-L SME` ignores only that exact case.
- **Scope roots are named constants in `check_spelling.py`**:
  - `TYPO_ROOTS = ("docs", "README.md", "packs/built-in")`, restricted to `*.md`;
  - `US_ROOTS = ("docs/guides", "docs/context")`;
  - the Unreleased section.
- **Pass-specific flags live in the script, not the config**, so they cannot leak into the typo pass:
  - US passes: `--builtin en-GB_to_en-US`;
  - `-L dialogue` (the command-line `-L` adds to the config list; tested);
  - `--ignore-regex` for code spans `` `[^`\n]*` `` and anchor ids `<a id="[^"]*">`;
  - `--ignore-multiline-regex '```.*?```'` for fenced blocks.
  - The typo pass reports typos inside code spans; the US passes exempt them.
- **Symlinks**: `CHANGELOG.md` and `.github/CHANGELOG.md` symlink to `docs/changelog/CHANGELOG.md`. The typo roots never list the root symlink, and `README.md` is a regular file. Each finding is reported once, against the canonical path.

## R-4 Guard rule calibration (measured on 224 entries)

| Rule | Calibrated definition | Current text |
|---|---|---|
| Headings | Level-3 set and order: Breaking, Upgrade Notes, Added, Changed, Fixed, Internal. Each at most once. Empty sections allowed. Level-4 only under Fixed, unique within its parent. | passes (7 `####` under Fixed) |
| Bold headline | Every entry in the first five sections starts `- **…**`. Internal entries are single-line plain bullets without `**Before:**`. | passes (22 Internal, max 328 chars) |
| Refs | Optional. A `#<digits>` inside the bold and outside a code span fails. `owner/repo#N` is accepted. Non-ref parentheticals are allowed. | passes (7 entries have no refs; `WP##` in a code span inside the bold is fine) |
| Contrast (Breaking/Changed/Fixed) | Contains `**Before:**`, or `**Why:**` + `**After:**`, or has a body after the refs of ≤ 2 sentences and ≤ 300 characters. | 2 Changed entries fail and are fixed in text (C-003): "`implement` on a `single_branch` mission refuses unsafe checkouts…" (590 chars) and "Creating a `single_branch` mission on a protected branch now switches…" (853 chars) |
| Length | Unicode code points over the entry's own raw lines (markdown included). Each nested sub-item is measured separately. Fail > 1,200; warn > 900. | max 972 then 948 (warn); naive whole-entry max 1,354 would fail, so the nested rule is load-bearing |
| Requirement IDs | `\b(?:FR\|NFR\|SC\|C\|D)-\d+[a-z]?(?:\.\d+)?\b` outside code spans | 0 hits outside code spans; 9 inside (exemption load-bearing) |
| ULID | `\b[0-7][0-9A-HJKMNP-TV-Z]{25}\b` on raw text | 0 hits, no collisions (underscore error codes break the run) |
| Evidence / planning refs | `.kittify/evidence/` and `planning#` on raw text | 0 |
| All-caps | `\b(?:DEFAULT\|REFUSE\|FAIL)\b` outside code spans (case-sensitive) | 0 (`…_FAILED` unaffected) |
| Boilerplate | literal "Bug-fix; no CLI version bump" | 0 |
| `spec-kitty merge` | Raw text including code spans. Allowed only in a paragraph or entry that also contains `spec-kitty consolidate`. `merge-driver` never matches (`spec-kitty merge-driver-…` is excluded by a `(?![-\w])` lookahead). | 3 paragraphs (preamble, Breaking rename, Upgrade Note "Replace …"), all in the rename context → pass |

**Real-world red control**: the pre-rewrite Unreleased section (`git show 294f4c352d:docs/changelog/CHANGELOG.md`, frozen as a test fixture) fails on duplicate/out-of-order headings, the boilerplate (13× with `;` plus 3× with an em-dash), all-caps tokens, requirement IDs, `planning#`, `.kittify/evidence/`, and one ULID inside a backticked `DM-01M3EC2FMWKCKGSBX1QHC7GFCJ`. The post-tasks brownfield scout corrected the earlier "no ULID" claim. The ULID rule therefore matches raw text, code spans included.

## R-5 Canonical extractor

- **Decision**: add `unreleased_section(text: str) -> UnreleasedSection | None` to `scripts/release/validate_release.py`. It uses `parse_changelog_heading`/`CHANGELOG_HEADING_RE`, which already recognize both `## [Unreleased]` and `## [Unreleased] - 4.0.0rc5`. It returns the 1-based start line and the section lines, and skips fenced blocks when looking for the next `##` heading.
- **Rationale**: this is the only complete heading grammar in the repo. The other two extractors are either preamble-inclusive (`tests/contract/test_terminology_guards.py:127-133`) or cannot match a version-less heading (`scripts/release/extract_changelog.py:14-20`).
- **Not done (locality)**: the terminology guard keeps its own extractor, because migrating it would shrink its scan and drop the preamble. The duplicate regex in `extract_changelog.py` is left alone; both are noted in the PR body.

## R-6 CI placement

- **Decision**: a new always-on `docs-lint` job in `.github/workflows/ci-router.yml`, next to `terminology`. It runs `uv sync --frozen`, then `uv run --frozen python -m scripts.docs.check_spelling` and `uv run --frozen python -m scripts.docs.check_changelog_style`, with no `|| true`. The job is added to router-gate `needs` and to `_ALWAYS_ON_JOB_NAMES`. `gate_selection.py` needs no change, because it derives always-on jobs from the absence of an `if:`.
- **Rationale**: the check inputs are `docs/**`, `README.md`, `packs/built-in/**/*.md`, `pyproject.toml`, `uv.lock`, `scripts/release/validate_release.py` and `scripts/docs/*`. No single path group covers that set. `README.md`, `pyproject.toml` and `scripts/release/` fire no docs job at all. Widening the `docs` group would also widen the prose-only globs (`ci-router.yml:367`) and could skip code shards, which is a safety regression.
- **Constraint**: the job must not reach pytest (`test_no_duplicate_suite_execution.py`) and must not call `make`. The planted-violation tests run in the existing `tests-docs` job.

## R-7 Glossary renames

- "Organisation Tier" → "Organization Tier". `docs/context/charter.md:612`; add `<a id="organisation-tier"></a>` and move the 7 in-page links to `#organization-tier`.
- "communication artefact" → "communication artifact". `docs/context/execution.md:242`; this is a ratified term (DIRECTIVE_032 naming note, ADR 2026-06-03-3), so the UK form is recorded as an alias in the entry. Regenerate `src/specify_cli/.contextive/execution.yml` via `scripts/generate_contextive_glossaries.py`.
- "Trail Behaviour" → "Trail Behavior". `docs/guides/gstack-glossary-observations.md:90`, with a legacy anchor.
- Canonical identifiers spelled the UK way (`behaviour-driven-development` paradigm id, pack surface `behaviour-driven development`) are written in code spans, not respelled.

## R-7b Verified codespell behavior (brownfield scout, 2026-09-30)

- Exit codes: 0 when clean, 65 when hits are found.
- Only the last `--ignore-regex` applies, so the script passes one combined regex.
- `./pyproject.toml` is read implicitly from the cwd, so the script always runs with `cwd=repo_root` and an explicit `--toml`.
- With no path arguments codespell scans `.`, so a zero-file pass must never invoke it.
- **Blind spot**: the word regex includes `-`, so hyphenated UK tokens are never flagged. This is documented, not worked around.

## R-8 Deferred (pre-existing, noted in the PR body, not ticketed in-mission)

- `docs/api/cli-commands.md` truncation (`[single_branch|lanes|coo`) comes from the CLI reference generator; the file is skipped.
- The `scripts/docs/sync_changelog.py --check` docstring cites a `docs-freshness.yml` that no longer exists, so nothing in CI enforces the CHANGELOG symlinks.
- Duplicate changelog heading regex in `scripts/release/extract_changelog.py`.
- `scripts/release/**` is in no ci-router path group, so a PR that edits only the extractor skips `tests/docs/test_unreleased_section.py`. The always-on `docs-lint` job still exercises it on the live changelog. This is a residual, noted in the PR body.
- The contextive glossaries are already stale on the base (`governance.yml`, `orchestration.yml`, missing `merge/.contextive.yml`). This is pre-existing and not committed by this mission.
- `generate_contextive_glossaries.py` hard-codes `aliases=[]`, so glossary aliases never reach the contextive YAML.
