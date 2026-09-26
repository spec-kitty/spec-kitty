# Quickstart — Validating Terminus Integrity Follow-ups

All validation runs against **this tree's** code via its own venv. Never bare `spec-kitty` (PATH resolves a sibling checkout).

## Environment

```bash
cd /home/stijn/Documents/_code/SDD/fork/SHADOW_CLONES/spec-kitty_TWO
# Tests (this tree's src):
PWHEADLESS=1 .venv/bin/python -m pytest tests/terminus/ -o addopts="" -q
# CLI behavior (this tree's code):
.venv/bin/spec-kitty <args>
```

## Red-first proof (before fixes)

```bash
# Targets that must be RED (xfail-strict) at start:
PWHEADLESS=1 .venv/bin/python -m pytest tests/terminus/test_repro_{4970,4982,4985,4991,4997}.py \
  "tests/terminus/test_terminus_reconciliation_property.py::...[squash]" -o addopts="" -q -rxX
# Expect: xfailed (honest red), 0 xpassed.
```

## Per-workstream validation (after fixes)

- **WS1 (#5013):** `tests/terminus/test_terminus_reconciliation_property.py -k squash` and the default-squash variants of `test_repro_{4945,4977,4981}.py` pass; the removed file is absent from the target after a default `spec-kitty merge`. A clean squash still passes.
- **WS2 (resume):** `test_repro_{4985,4991}.py` (strategy) and `test_repro_{4982,4997}.py` (strategy + lane-tip) pass; an interrupted `--strategy merge` resumes as merge with all pre-interrupt commits reachable.
- **WS3 (#4970):** `test_repro_4970.py` passes; a stale local-head coord branch's committed rows survive a second `issue-verdict`.

## Blast-radius gate (before PR)

```bash
PWHEADLESS=1 .venv/bin/python -m pytest tests/merge tests/coordination tests/git tests/lanes tests/terminus -o addopts="" -q
make test-fast
uv run --frozen ruff check .          # 0 new
uv run --frozen ruff format --check . # 0 new
.venv/bin/python -m mypy src/         # 0 new
```

## Success = all six SC met (spec.md §Success Criteria), honest xfail residuals only.
