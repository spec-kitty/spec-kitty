# Test-Quality Triage

## Overview

`test-quality-scan.py` is the static first pass of the
`test-suite-quality-assessment` procedure. It lives in this pack as an asset
(`packs/internal/assets/test-quality-scan.py`, standard library only), so a
run never has to rebuild it. The file name does not match `test_*.py`, so
pytest never collects it.

It **runs no tests**. It parses each test module with `ast`, flags the patterns
listed below per test function, and ranks files so review squads read the worst
first. The whole corpus (over 3,000 modules, about 36,000 tests) scans in about
20 seconds.

## Kick off a run

From the repository root:

```bash
make test-quality-scan
```

This scans all of `tests/` into `work/test-quality/<today>/`, which is
gitignored. Pass extra flags through `SCAN_ARGS`:

```bash
make test-quality-scan SCAN_ARGS="--paths tests/status tests/consolidation"
make test-quality-scan SCAN_ARGS="--since $(git rev-list -1 --before='48 hours ago' origin/main)"
```

Or call the asset directly through the doctrine resolver, which is the same
file:

```bash
python "$(spec-kitty doctrine asset path test-quality-scan)" \
    --out work/test-quality/$(date +%F) [--paths tests/<domain>] [--since <rev>] [--top 25] [--no-git]
```

Then hand the ranked ledgers to the review squads:

```bash
spec-kitty dispatch "Run the test-suite-quality-assessment procedure over work/test-quality/$(date +%F)/ledger/<domain>.md"
```

## Options

| Flag | Default | Meaning |
| --- | --- | --- |
| `--paths` | `tests` | Test roots or single files to scan |
| `--since REV` | off | Score only tests added or changed since `REV` (window mode) |
| `--out DIR` | `work/test-quality` | Output folder |
| `--top N` | `25` | Files per domain ledger and in the summary |
| `--no-git` | off | Skip git provenance: faster, and works outside a git checkout |

## Outputs

| File | Content |
| --- | --- |
| `summary.md` | One row per domain (files, tests, flagged tests, score, top flags) and the top files overall |
| `files.json` | One row per module: domain, score, flag counts, `added`, `added_by`, `last_touched` |
| `tests.json` | One row per flagged test: file, line, qualified name, flags, score |
| `ledger/<domain>.md` | A review checklist of the domain's top-ranked files, with a `Verdict:` line each |

A domain is `tests/<dir>`, except `tests/specify_cli`, which is split one level
deeper because it is too large for one squad. An existing ledger is **never
overwritten**, so a stopped review resumes where it left off. To start a
domain again, delete its ledger.

## Flag codes

The review codes (R1 to R9) come from the 2026-09-29 test review.

| Code | Weight | Pattern | Rubric |
| --- | ---: | --- | --- |
| `no-assertion` | 5 | No `assert`, no `raises`, no assert-like call | R1 vacuous |
| `weak-only-assert` | 4 | The only assert is `True` or `x is not None` | R1 vacuous |
| `type-only-assert` | 3 | The only assert is `isinstance`, `callable` or `hasattr` | R1 vacuous |
| `broad-raises` | 3 | `pytest.raises(Exception)` | R1 vacuous |
| `literal-source-scan` | 3 | Reads source text and asserts a substring | R4 literal scan |
| `line-number-pin` | 3 | Asserts a `file.py:NN` location | R6 line pin |
| `over-mocking` | 2 | Four or more patches or mocks in one test | R2 over-mock |
| `private-attr` | 2 | Three or more private attributes read | R3 implementation-coupled |
| `fake-short-ulid` | 2 | A `mission_id` that is not a 26-character ULID | R7 fabricated data |
| `sleep`, `wallclock` | 2 | A real sleep, or an unfrozen clock | R9 non-deterministic |
| `interaction-assert` | 1 | Asserts on mock calls | R3 implementation-coupled |
| `skip-or-xfail` | 1 | A skip or xfail that is not a platform or tool guard | masked defect candidate |
| `long-test`, `many-asserts` | 1 | More than 80 lines, or 15 or more asserts | R8 multi-behaviour |
| `vague-name` | 1 | The name promises nothing (`test_basic`, `test_1`) | R8 unclear |
| `provenance-tokens` | 1 | WP, FR or T ids, or issue numbers, in the name or docstring | development-assist lens |

## Known false positives

Every flag is a candidate, not a verdict:

- `no-assertion` fires on a test that delegates to a helper whose name does not look like an assertion.
- `weak-only-assert` fires on "passes strict validation" tests, where the call under test raises on failure. The assert is then only a formality.
- `provenance-tokens` fires on legitimate issue-pinned regression tests. It only feeds the development-assist lens, and it weighs the least.

The opposite also holds: an unflagged test is not proven good. The scanner
cannot see a self-constructed oracle or a new gate stubbed out of an old
harness. Those need a read and a planted break, as the procedure describes.

## Shallow clones

Provenance comes from one `git log` pass over the top-level directory of each
scanned root. Renames are followed, including a move in from a sibling
directory, so `added` names the commit that created the file, not the one that
last renamed it; a move in from outside that top-level directory still reads as
an add. On a shallow
clone, the graft point stands in for the `added` date of older files. Deepen
the clone (`git fetch --deepen=<n>` or `--unshallow`) when the
development-assist lens matters.
