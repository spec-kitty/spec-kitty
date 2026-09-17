# Quickstart — CLI Boundary Robustness

Dev + verification guide for implementers/reviewers of this mission.

## Environment
```bash
uv sync --frozen --all-extras     # never a bare `uv run` (destroys a hand-built .venv)
```

## Reproduce the bugs (pre-fix, red)
```bash
# #4600 (P0) — in a throwaway init'd project:
printf '\xd0\xd0\xd0bad\xff' > .kittify/config.yaml
spec-kitty --version            # RED: UnicodeDecodeError traceback, no version

# #4601 — prose on stdout under --json:
spec-kitty context info --workspace nope --json      # RED: prose, not JSON
spec-kitty mission-type show nope --json             # RED: prose

# #4643 — prose at exit 0 under --json:
spec-kitty agent tasks status --mission <empty-mission> --json   # RED: "No work packages..." prose, exit 0

# #4597 — OptionInfo leak:
spec-kitty context                                   # RED: <OptionInfo object ...> in output

# #4598 — inactive types shown:
spec-kitty mission-type list                         # RED: lists inactive types
```

## Targeted test surface (per charter: run affected packages, not the full suite)
```bash
# WP01
PWHEADLESS=1 .venv/bin/python -m pytest tests/specify_cli/bootstrap/ -q
# WP02–WP05 adoption
PWHEADLESS=1 .venv/bin/python -m pytest tests/specify_cli/cli/ tests/status/ -q
# WP06 gates
PWHEADLESS=1 .venv/bin/python -m pytest tests/architectural/test_cli_console_single_seam.py -q
# shared baseline
make test-fast
```

## Gates before hand-off
```bash
ruff check .
uv run --frozen ruff format --check .          # whole-repo format gate
uv run --frozen mypy -p specify_cli            # package-level (single-file mypy false-yells)
pytest tests/architectural/test_no_legacy_terminology.py   # terminology guard (prose/offering touched)
```

## ATDD discipline
- Each WP: commit the failing-first acceptance test BEFORE implementation.
- #4600 and #4643 carry issue-pinned `@pytest.mark.regression` tests driven through
  the pre-existing entry point; reviewer confirms red-on-base / green-on-final.
