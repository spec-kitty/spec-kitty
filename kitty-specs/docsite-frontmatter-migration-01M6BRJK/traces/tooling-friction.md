# Tooling friction

## 2026-11-01 — seed
Tooling touched: `spec-kitty` 4.0.0rc8 from this checkout, `scripts/docs/*`, pytest, doc-kitty `fe835cd` via pnpm 10 / Node 22 in `/tmp`.

## 2026-11-01 — packs not synced in a fresh session
`spec-kitty charter context` reported `pack internal: local_path ... does not exist` until `make sync-packs` ran. CLAUDE.md says so; the error points at `charter fetch`, not `make sync-packs`. Minor.

## 2026-11-01 — spec-commit refuses a directory
`spec-kitty spec-commit ... decisions/` refused a directory; listing the files worked. The decision artifacts (`decisions/index.json`) are not mentioned by the specify prompt's commit example.

## 2026-11-01 — baseline
`pytest tests/docs/ tests/specify_cli/docs/ -n 4 --dist loadfile` on `7e2ca9fd`: 1853 passed, 8 skipped (6 min 16 s).
