# WP01 review — cycle 1

- **Reviewer**: `pi:deepseek-v4.1-flash-1017:reviewer-renata:reviewer` (profile `reviewer-renata`)
- **Date**: 2026-10-31T13:28Z
- **Mission**: `orchestrator-contract-version-single-source-01M68ZRJ` (issue #6578)
- **Branch / HEAD**: `kitty/mission-orchestrator-contract-version-single-source-01M68ZRJ` @ `0bdab23949`
- **Diff reviewed**: `c9d4991aa4` (code: `tests/orchestrator_api/test_origin_freshness_envelopes.py`, `tests/specify_cli/orchestrator_api/test_contract_version.py`) and `0156635bba` (spec.md / plan.md / WP01 prompt / mission bookkeeping). Net test diff vs `origin/main` (`dfe9efb0e8..HEAD -- tests/`): 2 files, +91/−9.
- **Governance loaded**: `agent profile show reviewer-renata`; `charter context --action review --include agent-profile:reviewer-renata`; `charter context --include tactic:delete-the-assertion-not-the-test`; charter "ATDD-First Discipline", standing order 5 (DIRECTIVE_043 non-vacuous gates), Code Review Checklist, DIRECTIVE_041.

## What I ran

| # | Command | Result |
|---|---------|--------|
| 1 | `uv run --frozen python -m pytest tests/specify_cli/orchestrator_api/test_contract_version.py -q` | **5 passed in 2.70 s** (guard run inside the module: whole module 2.70 s, not the 2–4 min import cost the implementer reported) |
| 2 | `uv run --frozen python -m pytest tests/orchestrator_api/test_origin_freshness_envelopes.py -q` | **13 passed in 177.49 s** (the re-pointed refusal assertions are green end-to-end) |
| 3 | `uv run --frozen python -m pytest tests/agent/test_envelope_unit.py -q` | **19 passed in 65.59 s** |
| 4 | `uv run --frozen python -m pytest tests/orchestrator_api/test_wp_lifecycle_structured_actor_6400.py -q` | **7 passed in 6.43 s** (5 + 19 + 7 = **31**, matching the implementer's 31-passed claim exactly) |
| 5 | `uv run --frozen ruff check <both touched files>` | **All checks passed** |
| 6 | `uv run --frozen ruff format --check <both touched files>` | **2 files already formatted** |
| 7 | `git diff dfe9efb0e8..HEAD -- src/` | **empty** — `src/` untouched; `CONTRACT_VERSION = "1.21.0"` still at `src/specify_cli/orchestrator_api/envelope.py:176` |
| 8 | RED reproduction: fed `git show dfe9efb0e8:tests/orchestrator_api/test_origin_freshness_envelopes.py` through the guard's own helper `_contract_version_literals_in` | **`[29]`** — the base file's `_CONTRACT_VERSION = "1.21.0"` at line 29; same helper on the HEAD file → **`[]`**. The claimed RED is real and reproducible, not manufactured. |
| 9 | Mutation reproduction (in memory, no file written): HEAD file line 127 `== CONTRACT_VERSION` → `== "1.21.0"` | **`[127]`** — matches the recorded mutation evidence (line 127). |
| 10 | Guard cost + breadth: `_offending_files(_TESTS_DIR)` | **`scanned=4282`, floor 3000, `offending=[]`, walk 0.90 s** (69 MB read once; `pytest.mark.fast` module) |
| 11 | End-to-end positive control of the gate's data path: `_offending_files(REPO_ROOT / "src")` | **`src/specify_cli/orchestrator_api/envelope.py:176`**, `scanned=1402` — the walk/read/format wiring really emits `path:line`, not just the line helper |
| 12 | False-negative / false-positive probes of `_contract_version_literals_in` | planted same-line pin → `[1]`; `payload = {"contract_version": "1.20.0"}` → `[1]` (**FP class**); `_EXPECTED = "1.21.0"` + `== _EXPECTED` → `[]` (**FN**); implicit-concat and two-line JSON blob → `[]` (**FN**); `"api_version": "3.0.0"` → `[]`; `CONTRACT_VERSION_MISMATCH` → `[]`; constant read → `[]` |
| 13 | Historical claim check: distinct `_CONTRACT_VERSION` values in that file's git history | **11** (`1.11.0` … `1.21.0`) — the "re-pinned eleven times" claim in the commit message/comment is accurate |
| 14 | Precedent check: `tests/architectural/test_no_assert_swallowed_by_own_handler.py` (`MIN_SCANNED_FILES`, `slowest durations`) | floor `{"src": 1000, "tests": 3000}` confirmed; that `fast`-marked sibling takes **6.42 s** in one test, so a multi-second `fast` source scan is established practice |
| 15 | `git show c9d4991aa4` grepped for host-absolute path prefixes | no matches — no host-absolute paths, no personal data in the code commit |

## Correctness against #6578

- **Fixed**: `_CONTRACT_VERSION = "1.21.0"` is gone; both refusal tests compare `envelope["contract_version"]` to
  `specify_cli.orchestrator_api.envelope.CONTRACT_VERSION` (`tests/orchestrator_api/test_origin_freshness_envelopes.py:127`,
  `:181`). A contract bump now touches `envelope.py` only (plus the canonical pin, as designed).
- **Nothing lost**: the diff changes exactly two assertion lines plus the docstring and import; `success`, `error_code`,
  `preflight_error_code(s)`, `origin_freshness`, `target_branch` assertions are byte-identical, so C-002 / FR-005 hold and
  the tactic `delete-the-assertion-not-the-test` ("transform in place, keep the setup") is followed.
- **Still meaningful**: the compared constant is read in-process while the envelope comes from the real CLI subprocess, so
  the assertion still fails if the subprocess stamps a hardcoded/omitted version. The exact value remains pinned once, by
  literal, at `test_contract_version.py:109-110` (`"1.21.0"` ×2) — a forgotten bump still cannot pass.
- **No shortcut detected**: no deleted assertion, no tautology, no `xfail`, no try/except swallowing, no manufactured
  green; the recorded RED/GREEN/mutation evidence reproduces (rows 8–9).

## Findings

### Blocking

None.

### Non-blocking

| ID | Severity | Location | Finding | Recommendation |
|----|----------|----------|---------|----------------|
| N1 | non-blocking (false negative) | `tests/specify_cli/orchestrator_api/test_contract_version.py:130-132` (`_contract_version_literals_in`) | The scan only pairs the `contract_version` token with a quoted semver **on the same line**. A re-introduced pin in single-indirection form is invisible: `_EXPECTED = "1.21.0"` + `assert envelope["contract_version"] == _EXPECTED` → `[]` (probed, row 12); implicit string concat and a two-line JSON string are also missed. The historical shape (`_CONTRACT_VERSION = "1.21.0"`) *is* caught because the constant name contains the token. | Either also flag module-level quoted-semver assignments in test modules that import `CONTRACT_VERSION`, or document the blind spot in the guard docstring — the sibling gate documents its blind spots (alias, starred tuple, `self.assert*`), so a documented gap is the repo's own idiom. |
| N2 | non-blocking (false positive vs. spec) | `test_contract_version.py:130-132` vs `kitty-specs/.../spec.md:120-123` (Edge Cases) | The guard cannot tell a *payload* from a *comparison*: `payload = {"contract_version": "1.20.0"}` → `[1]` (probed). spec.md Edge Cases promises the opposite ("A test that legitimately needs a *different* version to exercise `CONTRACT_VERSION_MISMATCH`: it builds a payload … so the guard must not flag it") and only the `"api_version": "3.0.0"` example happens to be unflagged. A future legit version-tolerance test would be false-red with no escape hatch (DIRECTIVE_041 false-red class). | Either narrow the spec sentence to the `api_version`-style payload it actually covers, or add an explicit per-line opt-out marker (e.g. `# contract-version-literal-ok: <reason>`) plus a self-check for it. |
| N3 | non-blocking (non-vacuity coverage gap) | `test_contract_version.py:135-146` (`_offending_files`), self-check at `:167-181` | The DIRECTIVE_043 self-mutation control covers only the **line helper**; the gate's actual data path (walk → read → `offending.extend(f"{path.relative_to(_REPO_ROOT)…}")`) has no automated control. The cited precedent covers exactly that seam with `test_collect_violations_reads_a_planted_file(tmp_path)` ("so a broken text prefilter cannot hide every file", `tests/architectural/test_no_assert_swallowed_by_own_handler.py:158`), and this implementation *cannot* copy it: a `tmp_path` dir makes `path.relative_to(_REPO_ROOT)` raise `ValueError` (reproduced: `ValueError: '<tmp>/wiring/aaaa/test_bad.py' is not in the subpath of '<repo-root>'`). A future no-op in that comprehension would leave every test green while the gate reports "clean" forever. The gate is non-vacuous **today** — I proved it end-to-end (row 11) and the floor works (row 10) — so this is a durability gap, not a live vacuity. | Decouple formatting from scanning (pass a `format_path` callable, or build the `path:line` string in the test) and add the `tmp_path` planted-file test. |
| N4 | non-blocking (spec/plan inaccuracy) | `spec.md:130-131`; `spec.md:150` (NFR-002); `test_contract_version.py:120` (`_CANONICAL_PIN = Path(__file__).resolve()`), `:163` | Two documented claims are false of the implementation: (a) spec.md says that if the canonical pin module is renamed the guard "fails loudly (its allowlist path no longer exists)" — but the allowlist is `__file__`-derived, so it moves with the file and nothing fails (only the hardcoded path in the failure message would go stale); (b) NFR-002 says the scan "reports exactly one file (the canonical pin module)", while the scan *skips* it and reports **zero** files. analysis-report A1 raised (a) and no existence check was added. | Reword both sentences to match: the pin module is exempt, not reported; a rename silently re-homes the allowlist. Or add the `_CANONICAL_PIN.is_file()` assertion A1 asked for. |
| N5 | non-blocking (measurement provenance) | `spec.md:149` (NFR-001), `plan.md:44-45`, `analysis-report.md:50` (P1) | NFR-001 was relaxed from "under 1 second" to "single-digit seconds" **after** measuring, inside the implementation WP; `analysis-report.md:50` then calls it "no requirement weakened", which is inaccurate — the threshold *was* weakened (disclosed and quantified, but weakened). Measured here: 0.90 s walk, 2.70 s module. `pytest.ini:57` defines `fast` as "sub-second per test"; the cited sibling gate (also `fast`) took 6.42 s, so the precedent does hold. | Keep the amendment, but have the PR body record it as a deliberate deviation (§7 Deferred/Notes) and correct the "no requirement weakened" wording rather than editing the analysis report. |
| N6 | non-blocking (ATDD commit shape) | commit `c9d4991aa4` | The guard test and the origin-freshness fix land in a single commit, so the history does not exhibit the separate red-first commit the charter's ATDD-First Discipline asks for. The red→green is nevertheless *reproducible* from the base tree (rows 8–9), which is what the reviewer is asked to verify. | Accept as-is for this test-only WP; note in the PR body that the RED is proven by execution against `dfe9efb0e8`, not by commit order. |

### Verified sound (no action)

- `src/` byte-identical, `CONTRACT_VERSION = "1.21.0"` unchanged (string *and* file unchanged).
- Sibling pattern respected: `tests/agent/test_envelope_unit.py:34`, `tests/agent/test_orchestrator_commands_integration.py:382`,
  `tests/orchestrator_api/test_wp_lifecycle_structured_actor_6400.py:46,174`, `tests/contract/test_orchestrator_api.py:25`
  already read the constant; the changed file now matches them (DIRECTIVE_044).
- The self-check is non-vacuous in the direction it tests: a planted pin yields `[1]`, the constant read, the f-string
  interpolation and `CONTRACT_VERSION_MISMATCH` all yield `[]`.
- `MIN_SCANNED_FILES = 3000` against an actual 4282 is a real floor (~42 % headroom) and is asserted before the
  emptiness assertion, so a broken root goes red rather than passing vacuously.
- Concurrency/path hygiene: the module derives `_REPO_ROOT` from `__file__`, so the scan is cwd-independent and has no
  host-absolute path; `ruff check`/`format` clean; no personal data added.
- Docstring de-claiming (FR-004): the stale "`CONTRACT_VERSION` is currently `"1.3.0"` (envelope.py:28)" sentence is gone,
  and the replacement paragraph names no current value, so it cannot drift again.

## Could not verify

- The implementer's verbatim RED transcript (only the underlying fact, which I reproduced independently from
  `dfe9efb0e8`'s file content).
- Their exact `--durations` numbers (their host was under 20-agent load; I measured 0.90 s for the walk on this host,
  which sits inside their reported 0.4–4.1 s envelope).
- Their "ruff format clean" was reproducible; their 2–4 minute module runtime was **not** (2.70 s here) — harmless, but
  the stated cost is host-dependent.

VERDICT: APPROVED
The change fixes #6578 with the assertion strength retained and a genuinely failing-first, non-vacuous guard (reproduced independently), leaving only documentation-accuracy and gate-durability findings that do not need to block this test-only WP.
