---
affected_files: []
cycle_number: 2
mission_slug: local-write-safety-01M2ZPZD
reproduction_command:
reviewed_at: '2026-09-20T19:05:08Z'
reviewer_agent: claude
wp_id: WP02
---

# WP02 cycle-2 — cover (or remove) the `_write_asset` FileExistsError branch (operator-directed)

WP02 was approved. The operator directed folding in the residual the reviewer flagged. Confined to
`src/specify_cli/runtime/asset_preparation.py` + its owned test (no owned_files change).

## The residual
The production hardening added to `_write_asset` — the `FileExistsError` tolerance
(asset_preparation.py ~lines 990-1003, INCLUDING the `if path.is_symlink() or not path.is_dir(): raise`
symlink-refusal guard) — is **uncovered by any test**, and its sentinel-driven reachability is unproven
(the sentinel creates only paths outside the managed root, so the reviewer could not construct the live
collision it claims to fix). Per CLAUDE.md "every new branch needs a test" + avoid gold-plating.

## Required fold — pick ONE, justified:
- **(preferred) Cover it**: add a red-first test that drives the `_write_asset` FileExistsError branch —
  construct the concurrent "target dir already exists as an ordinary directory" precondition and assert
  (a) it is tolerated (no raise, the existing dir is used) AND (b) a symlink at that path is STILL
  REFUSED (the `is_symlink()` guard re-raises — no symlink-follow reintroduced). This proves the branch
  is both reachable and security-preserving.
- **OR remove it** if you determine the branch is genuinely unreachable given the sentinel is a sibling
  outside the managed root (i.e. no live call path can hit it), and document why in the commit.

Prefer covering it (it is defense-in-depth against a general concurrent-installer race, not only the
sentinel scenario). Keep the `check_assets` sentinel-materialization tolerance and everything else
unregressed. Re-run the runtime blast radius the WP touches + `ruff format --check` (keep green).
