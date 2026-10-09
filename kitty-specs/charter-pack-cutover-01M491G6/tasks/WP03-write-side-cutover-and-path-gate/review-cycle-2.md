---
affected_files: []
cycle_number: 2
mission_slug: charter-pack-cutover-01M491G6
reproduction_command:
reviewed_at: '2026-10-07T04:42:51Z'
reviewer_agent: claude
wp_id: WP03
---

# WP03 review feedback (round 2)

Reviewer: reviewer-renata (claude). Reviewed cycle-2 commits 814f4ad8, cb697aee, 7a0894c1, 0114957b, 1b745fc5.

## Verdict: changes requested (one blocker)

Cycle-1 fixes 1 and 3 are done. Fix 2 was resolved by the orchestrator's ruling (owner WP14 under T070), and cb697aee cites T070 correctly. The only problem is new in cycle 2.

## Required change

1. **`ci-router.yml` `tests-corpus-blocking`: the seven new lines end in `\\`, not `\`. This breaks the shell command.**
   In commit 0114957b, `.github/workflows/ci-router.yml` lines 971-977 (the `tests/acceptance/charter_pack_cutover/*.py` selections) end in a double backslash inside the `run: |` block scalar. YAML keeps both characters. Bash reads `\\` as an escaped literal backslash, so the newline after it ends the command. The resulting `pytest` call is `-m "corpus and not windows_ci" tests/acceptance/charter_pack_cutover/test_cli_surface.py '\'`. pytest exits 4 with "file or directory not found: \", and the step fails under `bash -eo pipefail`. Each later line would run as a command of its own.

   Reproduced by extracting the step's `run` text with `yaml.safe_load` and running it under `bash -eo pipefail` with pytest stubbed: argv stops at `test_cli_surface.py`, `\`, then `test_gates_latency_messaging.py: No such file or directory` (exit 127).

   Impact:
   - The required, blocking `tests (corpus-blocking)` job goes red on every PR that matches the `corpus` group.
   - None of its thirteen selections run, including the six it already ran before this change.
   - packs.yml now deselects those seven modules, so in practice they would have no home at all.

   `tests/ci/` (1914 passed) does not catch this, because the selection parser tokenizes paths and never runs the shell. Fix: change each `\\` to `\`.

   Optional: add a `tests/ci` assertion that each continuation line in that `run` block ends with exactly one backslash, or run `bash -n` over the step, so the shape cannot regress.

## Verified green (no change required)

- Fix 1: whole-repo `uv run --frozen ruff check .` passes. `ruff format --check --force-exclude` on the 26 changed .py files is clean.
- Fix 3: the loop-then-join gate is not vacuous. I planted four functions in a real src file (`src/charter/activation/__init__.py`, reverted afterwards):
  - a module-alias comprehension `root / c for c in _PLANT` was flagged;
  - an inline `for` with `root.joinpath(s)` was flagged;
  - `k.upper() for k in ("doctrine", ...)` was not flagged;
  - `for k in ("doctrine",): d[k] = 1` was not flagged.
- Allowlist accounting: exactly 27 entries (WP04 6, WP05 1, WP14 13, WP25 7), matching the baseline of 27. The accounting test passes.
- The VESTIGIAL_FILTER_GLOBS row for `.kittify/charter-packs/**` is earned: `test_vestigial_glob_rows_stay_earned` is green, and the row goes red once WP11 makes the glob live. The row's reason tells WP11 to delete it together with the `.kittify/doctrine/**` glob, and WP11 T-step 6 already drops that glob. WP11's step 6 does not name the ledger row, but the self-reddening test enforces the deletion.
- Corpus tests run once: packs.yml deselects the seven modules, and the router selects them; 25 corpus node-ids. They run only once the router command is fixed.
- `tests/ci`: 1914 passed. Seven architectural gate files (path authority, path literal authority, no stale literals, layer rules, gitignore contract, legacy terminology, workflow coherence): 253 passed.
- Acceptance suite `-n 4 --dist loadfile`: 87 passed, 1 skipped, 265 xfailed, 0 failed, 0 xpassed.
- mypy on the 21 touched src files: 4 errors, the same as on base 3ee1c97a. None are new.
