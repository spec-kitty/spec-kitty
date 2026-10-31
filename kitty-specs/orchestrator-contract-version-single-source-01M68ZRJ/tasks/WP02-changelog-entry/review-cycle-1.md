# WP02 review — cycle 1

- **Reviewer**: `pi:deepseek-v4.1-flash-1017:reviewer-renata:reviewer` (profile `reviewer-renata`)
- **Date**: 2026-10-31T13:58Z
- **Mission**: `orchestrator-contract-version-single-source-01M68ZRJ` (issue #6578)
- **Branch / HEAD**: `kitty/mission-orchestrator-contract-version-single-source-01M68ZRJ` @ `a6c7fde7df` (commit under review: `605c28dcee`)
- **Diff reviewed**: `605c28dcee` — one line under `docs/changelog/CHANGELOG.md` `## [Unreleased]` → `### Fixed`, plus mission bookkeeping (`kitty-ops/lifecycle.jsonl`, `mission-events.jsonl`, `status.events.jsonl`, `status.json`, `tasks/WP01-.../review-cycle-3.md`). No `src/`, no test files.
- **Governance loaded**: `agent profile show reviewer-renata`; `charter context --include directive:DIRECTIVE_037` (Living Documentation Sync, enforcement `required`); `docs/development/how-to/review-gates.md` § "Changelog update and style".

## Claims checked, one by one

| # | Changelog claim | Evidence | Verdict |
|---|-----------------|----------|---------|
| 1 | The code it records is CI/test-only; two test files | `git diff dfe9efb0e8..HEAD -- src/` → **empty**. `git diff dfe9efb0e8..HEAD --name-only` outside `kitty-specs/`/`kitty-ops/` → exactly `docs/changelog/CHANGELOG.md`, `tests/orchestrator_api/test_origin_freshness_envelopes.py`, `tests/specify_cli/orchestrator_api/test_contract_version.py` | TRUE |
| 2 | The old file "compared the emitted envelope to its own `_CONTRACT_VERSION` literal" | `git diff` of that file: `_CONTRACT_VERSION = "1.21.0"` deleted from line 29; the two assertions at old lines 122/176 rewritten | TRUE |
| 3 | "both refusal tests read the exported `envelope.CONTRACT_VERSION`" | `tests/orchestrator_api/test_origin_freshness_envelopes.py:26` imports `from specify_cli.orchestrator_api.envelope import CONTRACT_VERSION`; `:127` (`test_accept_mission_refuses_stale_status_evidence`) and `:181` (`test_consolidate_mission_refuses_stale_status_evidence`) both assert `envelope["contract_version"] == CONTRACT_VERSION`. Both assertion names checked, not just one | TRUE |
| 4 | "a fast test in `tests/specify_cli/orchestrator_api/test_contract_version.py`" | File exists at that path; `pytestmark = [pytest.mark.fast]` (line 54); guard is `test_only_this_module_spells_a_contract_version` (line 172) | TRUE |
| 5 | It "fails, naming every `path:line`" when another module spells a version | Guard message joins every offending entry as `f"{path.relative_to(_REPO_ROOT).as_posix()}:{lineno}"` (lines 166-188). Probe: helper detects both historical shapes — `_CONTRACT_VERSION = "1.21.0"` → `[1]`, `assert envelope["contract_version"] == "1.21.0"` → `[1]`. Live tree: `_offending_files(_TESTS_DIR)` → `offending=[]` | TRUE |
| 6 | "a scanned-file floor so a scan that reads nothing cannot pass" | `MIN_SCANNED_FILES = 3000` (line 141) with `assert scanned >= MIN_SCANNED_FILES` before the emptiness assert (line 182); measured `scanned=4282`. A planted-file control (`test_..._reads_a_planted_file`) proves the walk/read path end-to-end | TRUE |
| 7 | "No product behavior changes" | `src/` diff empty; `envelope.CONTRACT_VERSION` still `"1.21.0"` at `src/specify_cli/orchestrator_api/envelope.py:176`; only tests + docs changed | TRUE |
| 8 | "hand-re-pinned eleven times (1.11.0 to 1.21.0)" | `git log -G'_CONTRACT_VERSION = "[0-9]'` on that file → **11** commits touching the one line: `9ed59d9c5c` (create, 1.11.0) `4c8253b9a9` 1.12.0, `3c2bdae4df` 1.13.0, `fc38aacf5c` 1.14.0, `c2ea5bd65d` 1.15.0, `ae0a1c2cbb` 1.16.0, `c0db3bbd0c` 1.17.0, `71e4eddba2` 1.18.0, `79724a4101` 1.19.0, `d45ec106e3` 1.20.0, `c678037c8b` 1.21.0 — 11 distinct values, span `1.11.0..1.21.0` exactly as quoted | TRUE (see F2 for a wording nuance) |
| 9 | "#6578 was filed when it had been left **two** bumps stale" | `gh issue view 6578`: title "… pin contract_version **1.14.0** while the envelope emits **1.15.0**"; body "Cause: … `_CONTRACT_VERSION = "1.14.0"`, while … `CONTRACT_VERSION = "1.15.0"`". That is **one** bump stale, not two | **INACCURATE** — F1 (Low) |
| 10 | "and its two refusal tests were red" | Issue body: `2 failed, 11 passed`, naming `test_accept_mission_refuses_stale_status_evidence` and `test_consolidate_mission_refuses_stale_status_evidence` with `assert '1.15.0' == '1.14.0'` | TRUE |

## Style

- Bold impact-first lead: **"The orchestrator-api contract version has one source of truth in the test suite"** — consumer-visible statement first, then detail. PASS.
- Reference `(#6578, CI)` after the bold, outside it (`refs-in-bold` rule). PASS.
- `**Before:**` / `**After:**` / `**What to do:**` shape present, in that order, with `**Before:**` giving the old behaviour. PASS (`contrast-missing` satisfied by the contrast markers).
- Length 811 characters (< 1,200); one physical line at `docs/changelog/CHANGELOG.md:213`, no continuation lines (`Internal`-style multi-line shape not used). PASS.
- Placement: single line under `### Fixed` (heading at line 107), immediately after the last Fixed entry, before `### Internal` (line 215). Section order `… Fixed, Internal` is respected; `Fixed` is the home the sweep of neighbouring `(#N, CI)` entries uses (lines 160, 161, 168, 169 also under `Fixed`), and `Internal` forbids `**Before:**` by rule (`internal-shape`), so `Fixed` is the correct heading for this shape. PASS.
- Wording notes: "What to do: nothing; a version-tolerance fixture builds its version from the constant" reads as "nothing to do, except in that one case" — acceptable, matches the guard's documented design decision.

## Gates run

| # | Command | Result |
|---|---------|--------|
| 1 | `uv run --frozen python -m pytest tests/docs/test_changelog_style.py tests/docs/test_unreleased_section.py tests/docs/test_check_spelling.py -q` | **217 passed in 8.78 s** |
| 2 | `uv run --frozen python -m scripts.docs.check_docs_freshness --ci` | **`exit=0 findings=… errors=0`**, two runs: 7 warnings (first run) and 5 warnings (second run). Unique findings are 4 `HELP-DRIFT` (`charter activate`, `migrate activation-ledger`, `migrate ledger`, `service status` — each printed twice by the reporter) plus `LINK-HEALTH-FAILED` on unrelated pages (`docs/architecture/divio-documentation.md`, `docs/architecture/git-worktrees.md`, `docs/archive/plans/reviews/code-review-2026-03-25.md`, `docs/migrations/shared-package-boundary-cutover.md` — HTTP 403 / connection refused, i.e. network-dependent). **No finding names `docs/changelog/`, and the rule ids in play (`HELP-DRIFT`, `LINK-HEALTH-FAILED`) are derived from CLI help text and external URLs, so this entry cannot produce one.** No new warning attributable to the entry. The task brief's "6 pre-existing warnings" is a moving target: link-health findings vary per run with the network. |
| 3 | `uv run --frozen python -m pytest tests/specify_cli/orchestrator_api/test_contract_version.py -q` | **6 passed in 2.55 s** (the guard is genuinely fast and green on HEAD) |
| 4 | Guard probe (read-only, no file written): `_contract_version_literals_in(...)` on the two historical shapes; `_offending_files(_TESTS_DIR)` | `[1]` / `[1]`; `offending=[]`, `scanned=4282`, floor 3000 — non-vacuous |

## Churn

`git show 605c28dcee --name-only` → the changelog line, `kitty-ops/lifecycle.jsonl` (+2 events), the mission's `mission-events.jsonl` (+1), `status.events.jsonl` (+3, incl. the `T005: done` annotation and the implementer note), `status.json` (+`notes`, +`subtasks`), and `tasks/WP01-.../review-cycle-3.md` (the WP01 approval record). No product, test or unrelated docs file. Consistent with the mission's bookkeeping pattern (a review record lands with the following transition), and no stray reformatting or whitespace churn.

## Findings

**F1 — Low (accuracy, non-blocking).** "#6578 was filed when it had been left **two** bumps stale" is off by one. Issue #6578 says the pin read `1.14.0` while `envelope.py` declared `1.15.0` — a single bump. The one-word fix is "one bump stale". `kitty-specs/.../spec.md:19` carries the identical error ("two bumps stale (`_CONTRACT_VERSION` was `"1.14.0"` while the envelope emitted `1.15.0"`), so fix both or neither; the entry itself does not misdescribe the shipped change, which is why this does not block.

**F2 — Info (wording nuance).** "hand-re-pinned eleven times" is true of *commits that wrote that line* (11) and of *distinct values* (11, `1.11.0`–`1.21.0`), but one of the eleven is the line's creation at `1.11.0`, i.e. 10 strict re-pins. `research.md` Decision 1 lists exactly these 11 commits, so the phrasing is defensible and needs no change.

**F3 — Info (no action).** The commit bundles WP01's `review-cycle-3.md` approval record with WP02's changelog line. It is mission bookkeeping produced by the previous review cycle, not unrelated product churn.

## Not verified

- The full test suite and the `origin-freshness` integration module (2–3 min of real git work) were not re-run here — out of scope for a one-line changelog WP, and already exercised by WP01's cycles. What matters for this WP (that the entry describes the tree) was verified directly against the source.
- "Two bumps stale" could not be reconciled to any reading of the evidence; see F1. Everything else in the entry is checkable and checks out.

## Verdict

The entry states what the tree actually does, sits under the heading the repo's guard and its neighbours require, is 811 characters on one line, and both docs gates are green (`217 passed`, `errors=0`, no new warning). The only defect is a historical aside off by one bump, inherited from `spec.md`, that does not change what the changelog tells a reader about the shipped suite.

VERDICT: APPROVED
