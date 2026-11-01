# Tooling friction

## 2026-11-01 — seed
Tooling touched: `spec-kitty` 4.0.0rc8 from this checkout, `scripts/docs/*`, pytest, doc-kitty `fe835cd` via pnpm 10 / Node 22 in `/tmp`.

## 2026-11-01 — packs not synced in a fresh session
`spec-kitty charter context` reported `pack internal: local_path ... does not exist` until `make sync-packs` ran. CLAUDE.md says so; the error points at `charter fetch`, not `make sync-packs`. Minor.

## 2026-11-01 — spec-commit refuses a directory
`spec-kitty spec-commit ... decisions/` refused a directory; listing the files worked. The decision artifacts (`decisions/index.json`) are not mentioned by the specify prompt's commit example.

## 2026-11-01 — baseline
`pytest tests/docs/ tests/specify_cli/docs/ -n 4 --dist loadfile` on `7e2ca9fd`: 1853 passed, 8 skipped (6 min 16 s).

## 2026-11-01 — intermittent 2-minute pytest start
Some single-file pytest runs take ~2 minutes before the first test (cold import of `charter.offering` under `-X importtime`); the same run is 3 s when warm. Environmental; not chased.

## 2026-11-01 — `move-task --to for_review` ran > 5 minutes
It captures baseline tests for the WP before the transition; no progress output while it runs.

## 2026-11-01 — the `spec-kitty` on PATH was a different, stale checkout
`spec-kitty` on PATH was a uv-tool install editable from `/opt/spec-kitty` (257 commits behind `origin/main`, same `4.0.0rc8` version string). The setup check (`spec-kitty --version`) passed only because that shell had activated `.venv`. Mission lifecycle commands from scaffold through WP02's for_review ran the stale code; fixed with `uv tool install --force --editable .` from this checkout before WP02's approval. Suggestion: `spec-kitty --version` could print the import path, so a stale editable install is visible.

## 2026-11-01 — close assessment
- Filed: #7015 (writers still emit the old shapes).
- Worth filing upstream to core (not filed here, operator's call): `spec-kitty --version` hides which checkout an editable install imports; `move-task --to for_review` runs a multi-minute baseline capture with no progress output; spec/plan edits after `analyze` re-block `implement` (correct, but the refusal could name the edited artifact).
