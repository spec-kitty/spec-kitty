# WP01 review — cycle 2 (re-check of `088d147e4d`)

- **Reviewer**: `pi:deepseek-v4.1-flash-1017:reviewer-renata:reviewer` (profile `reviewer-renata`)
- **Date**: 2026-10-31T13:40Z
- **Mission**: `orchestrator-contract-version-single-source-01M68ZRJ` (issue #6578)
- **Branch / HEAD**: `kitty/mission-orchestrator-contract-version-single-source-01M68ZRJ` @ `9798dcaa05`
- **Subject of this re-check**: commit `088d147e4d` ("review-cycle-1 fixes — planted-file control, documented blind spots, truthful spec prose"), which claims N1, N2, N3, N4.
- **Scope**: narrow re-check of the four claimed fixes only. Design, assertion strength, and the N5/N6 findings were settled in cycle 1 and are not re-reviewed. No code edited; the only write is this file. `git status --short` is empty at end of review.
- **Governance loaded**: `agent profile show reviewer-renata`; `charter context --include directive:DIRECTIVE_043` (non-vacuous gate: concrete floor + self-mutation check).

## Verdict on the claim

Four of four claimed fixes are real. N1, N2, N3, N4 → **FIXED**. No new blocking findings. The gate is still non-vacuous, and its data path is now covered by an automated planted-file control rather than by a reviewer's one-off probe.

## What I ran

| # | Command | Result |
|---|---------|--------|
| 1 | `git show 088d147e4d --stat` | 7 files, +146/−13: test module (+50/−8 net), `spec.md`, `review-cycle-1.md`, mission bookkeeping. No `src/` file. |
| 2 | `git show 088d147e4d -- tests/specify_cli/orchestrator_api/test_contract_version.py` | `_offending_files` split into `_contract_version_pins` (walk → `(path, line)`) + `_offending_files` (`relative_to` formatting only); new `test_the_contract_version_scan_reads_a_planted_file(tmp_path)`; documentation block added above `_CANONICAL_PIN`. |
| 3 | `uv run --frozen python -m pytest tests/specify_cli/orchestrator_api/test_contract_version.py -q` | **6 passed in 6.55 s** (5 at cycle 1 → 6, +1 = the planted-file test; nothing removed) |
| 4 | `... -q -k planted -v` | **1 passed, 5 deselected in 1.86 s** |
| 5 | `uv run --frozen ruff check tests/specify_cli/orchestrator_api/test_contract_version.py` | **All checks passed!** |
| 6 | `uv run --frozen ruff format --check` (same file) | **1 file already formatted** |
| 7 | `git diff dfe9efb0e8..HEAD -- src/ \| wc -l` | **0** — `src/` still byte-identical; `CONTRACT_VERSION` untouched |
| 8 | `git diff dfe9efb0e8..HEAD --stat -- tests/` | 2 files, +131/−9 — the same two files as cycle 1; no scope creep |
| 9 | Non-vacuity of the new control (in-process, no file edited): `_contract_version_pins(tmp_path_with_planted_file)` vs. same call with `Path.rglob` monkey-patched to yield nothing | normal → `[('test_planted.py', 1)]`, `scanned=1`; **mutated walk → `[]`, `scanned=0`**, i.e. both assertions in the planted test fail → the control is genuinely non-vacuous |
| 10 | `_contract_version_pins(_TESTS_DIR)` on the real tree | `pins=[]`, `scanned=4282` (floor 3000) — clean, floor holds |
| 11 | `_offending_files(REPO_ROOT/"src")` (end-to-end formatted path, post-refactor) | `['src/specify_cli/orchestrator_api/envelope.py:176']`, `scanned=1402` — the split did not break `path:line` formatting |
| 12 | `grep -n "must not be flagged\|reports exactly one file\|fails loudly" spec.md` | **no matches** — the three false sentences are gone |
| 13 | Literal inventory of the pin module (`_contract_version_literals_in` on its own source) | flagged lines: 91 (canonical pin `"1.21.0"`), 124/125/126 (prose examples in the new comment), 193/217 (the `"9.9.9"` fixtures). Exactly **one** real contract-version pin, at `:91`. |
| 14 | `git status --short` | **empty** — no test file modified by me; nothing to revert |

## N1–N4

### N1 — documented blind spots → **FIXED**
`tests/specify_cli/orchestrator_api/test_contract_version.py:120-128` now states the scan's one-line rule and names all three missed shapes explicitly: single indirection (`_EXPECTED = "1.21.0"` then `== _EXPECTED`), implicit string concatenation across lines, and a version inside a multi-line JSON string. It also says why (a data-flow read of arbitrary test code) and cites the sibling `tests/architectural/test_no_assert_swallowed_by_own_handler.py` as the idiom (evidence: `git show`, row 2; text read in file). This is exactly the recommendation, and matches the sibling gate that documents alias/starred-tuple/`self.assert*` gaps.

### N2 — payload-vs-comparison now documented and spec-consistent → **FIXED**
- Guard comment `:130-133`: "It also cannot tell a payload from a comparison, so a test that must carry a DIFFERENT version … is flagged by design: build that payload from the constant (`f"{CONTRACT_VERSION}-bogus"`) instead of spelling a number."
- `spec.md` Edge Cases (`:120-124`) now says the same: a mismatch fixture builds its version from the constant, "a spelled literal next to `contract_version` is flagged by design", and the `"api_version": "3.0.0"` payload is unscoped because it "names no contract version".
- Behaviour matches the prose (row 13 probe): `{"contract_version": "1.20.0"}` → `[1]` (flagged), `f"{CONTRACT_VERSION}-bogus"` → `[]` (clean), `test_fail_message_preserved.py` → `[]` (untouched, unflagged; its line 67 `"api_version": "3.0.0"` is still there). Old promise "must not be flagged" is gone (row 12).

### N3 — durability gap closed with a real control → **FIXED**
- Structure: walk and formatting are separated as recommended. `_contract_version_pins(tests_dir) -> tuple[list[tuple[Path, int]], int]` owns rglob/read/`(path, lineno)`; `_offending_files` only does `path.relative_to(_REPO_ROOT).as_posix()` (row 2).
- New test `test_the_contract_version_scan_reads_a_planted_file(tmp_path)` writes `assert envelope["contract_version"] == "9.9.9"` and asserts **both** `[(path.name, lineno) for path, lineno in pins] == [("test_planted.py", 1)]` and `scanned == 1` — the tuple proves the walk returned the right file *and* line, `scanned` proves the walk actually visited it (a `scanned` that stayed 0 would fail independently).
- Non-vacuity proven by mutation, not just by reading (row 9): with `rglob` neutered the same call returns `([], 0)` and the test fails on both assertions. It also fails if the `pins.extend(...)` comprehension is dropped or the return tuple is reordered. The `relative_to` `ValueError` that blocked the cycle-1 probe is genuinely gone because `tmp_path` never reaches `_offending_files`.
- Depth is *stronger* than the cited precedent: the sibling test passes explicit paths to `collect_violations` (`test_no_assert_swallowed_by_own_handler.py:152`), while this one exercises the directory walk.

### N4 — spec prose made truthful → **FIXED**
- `spec.md:130-132`: the "fails loudly (its allowlist path no longer exists)" claim is replaced by "The exemption is derived from `__file__`, so renaming the canonical pin module re-homes the exemption with it; nothing fails, and that is accepted".
- `spec.md:152` (NFR-002): now "skips exactly one file (the canonical pin module, **exempt not reported**) and yields 0 offenders", matching the implementation (`pins == []`, skip active — rows 10–11; the pin module's own lines 124/125 are not reported).
- Behavioural truth confirmed: the skip is `path == _CANONICAL_PIN` inside `_contract_version_pins` and applies to exactly one path; the real-tree scan returns no pins while the module does contain flagged lines (rows 10, 13).

## New findings

### Blocking
None.

### Non-blocking
| ID | Severity | Location | Finding | Recommendation |
|----|----------|----------|---------|----------------|
| C2-1 | informational (cosmetic) | `test_contract_version.py:133` | "The canonical pin above is exempt by path, and it is exempt — not reported" is a redundant half-sentence (it states the exemption twice). Harmless, no behavioural implication, does not mislead. | Optionally tighten to one clause on the next touch. Do not block, do not re-cycle for this. |

Carry-over, not raised by this re-check and still open by design: N5 (NFR-001 threshold relaxed after measuring; the analysis-report "no requirement weakened" wording) and N6 (guard and fix in one commit). Neither is affected by `088d147e4d`, and neither blocks a test-only WP.

## Sanity items

- **Exactly one intentional contract-version literal?** Yes. `:91` `assert envelope["contract_version"] == "1.21.0"` is the single real pin; `:90` is `api_version`; `:124-126` are prose; `:193`/`:217` are the `"9.9.9"` fixtures (never the real version). Unchanged in value across the whole mission — `src/` diff is empty (row 7), so the pin and `envelope.CONTRACT_VERSION` cannot have drifted.
- **Guard still skips only its own file?** Yes. `_CANONICAL_PIN = Path(__file__).resolve()` is compared against each rglob result; `_REPO_ROOT` derives from the same resolved path, so the paths are comparable, and the real-tree scan returns zero pins while the file itself carries flagged lines (rows 10, 13). Row 11 shows no collateral suppression: a scan rooted at `src/` still reports `envelope.py:176`.
- **No regression from the refactor.** `_offending_files`' failure message and its `scanned >= MIN_SCANNED_FILES` floor are unchanged, and the formatted `path:line` output is proven end-to-end after the split (row 11).

## Could not verify
Nothing material. The refactor's behaviour is fully exercised by rows 5–11, and the mutation at row 9 was performed in-process, so no scratch file was created and none needed reverting.

VERDICT: APPROVED
All four claims in `088d147e4d` hold: N1 and N2 are documented where the gate lives and the spec no longer promises the opposite; N3's walk/format split plus the `tmp_path` planted-file test closes the durability gap and is non-vacuous under mutation (proven, not assumed); N4's two spec sentences now match the `__file__`-derived exemption. Six tests pass, `src/` is untouched, lint and format are clean, and the only new item is a cosmetic redundancy that does not justify another cycle.
