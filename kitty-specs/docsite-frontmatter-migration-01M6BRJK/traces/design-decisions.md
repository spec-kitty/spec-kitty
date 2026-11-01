# Design decisions

## 2026-11-01 — seed
- One contract module (`scripts/docs/_dockitty_contract.py`) owns slug, publication, excluded folders, persona resolution, immutable set.
- Line-level frontmatter block replacement, not a YAML round-trip, so untouched keys keep their bytes.
- `guidance_text`: persona-derived sentence (DM `01M6BRRS43THXH8SZ861AFG8M3`).
- Unpublished `related` targets → `external_references` (DM `01M6BRRXG0MVX09DH92W1NTEWP`); deviates from the issue's "body link or drop", flagged for the operator.
- Excluded trees migrated too, so readers carry one shape.
- Not classified as a bulk edit (schema transformation, guarded by shape + body tests).
- Body-hash test is in-memory over the real corpus plus a `--verify-against` run, not a permanent git comparison (would fail later legitimate ADR amendments such as #6902).

## 2026-11-01 — WP01 review folds
- Root page slug is `''` (doc-kitty's `slugFromEntryId`; `check-links` skips an empty id). Accepting it fixed a non-idempotent second run (review blocker).
- `related` rule made source-aware and the spec amended (DM `01M6BW2S981SKQWXKCBNQD8RBW`): excluded history keeps slugs, drafts keep draft slugs, published pages name published pages only.
- Fail closed on comments inside an edited block, mixed line endings, unknown `external_references` shapes; `{ref, note}` entries classified like strings; index basenames case-insensitive; `--apply` computes every change before the first write; `verify_against` follows renames.

## 2026-11-01 — WP03 cutover folds
- ADR era `index.md` frontmatter IS migrated: only their table rows are bot-owned (the PR guard refuses new rows, not frontmatter). Found in the WP02 review.
- Excluded folders are NOT migrated (DM 01M6BZ0JPAYWD42A3GB4PYSTNA): a byte-pinned archive evidence bundle tripped `test_archive_root_byte_identical.py`. Readers and the shape test skip excluded folders as doc-kitty's gates do. Diff shrank from 719 to 618 pages.
- Two more readers of the old shape surfaced only by running the suites: `tests/glossary/test_canonical_promotion.py` (T007b diff-shape vs a pinned historical commit; now sanctions exactly this migration by running it over the expected text, mutation-checked) and `tests/docs/test_tracker_egress_upgrade_note_3108.py`.
- NFR-002: the docs retrieval index regenerated from the migrated tree equals the one from the base tree, so `docs query` is unaffected by construction.

## 2026-11-01 — close assessment
Five Decision Moments, all autonomous-run defaults flagged for the operator: guidance_text wording; unpublished related → external_references; source-aware related rule; excluded folders untouched; (plan) not a bulk edit. The excluded-folder decision reversed an earlier assumption and shrank the diff by ~100 files.
