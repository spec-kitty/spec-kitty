---
affected_files: []
cycle_number: 1
mission_slug: readme-rename-and-docs-audit-01M78WZM
reproduction_command:
reviewed_at: '2026-11-12T23:32:04Z'
reviewer_agent: claude-reviewer::reviewer-renata
wp_id: WP01
---

# WP01 review — cycle 1 (reviewer: claude-reviewer::reviewer-renata)

Verdict: **changes requested**. The rename itself is sound. All 59 renames are pure `git mv` (R100) and no `index.md` is left. The ledger has exactly 59 `#6939` entries and they match the renamed set. `INDEX_BASENAMES == ("README",)`. `legacy-redirects.json` is byte-identical. Immutable bodies change only in link targets, and the ADR amendment is append-only. The AGENTS.md commit touches one path, and the generated surfaces are untouched. A fresh build covers 970 of 970 baseline URLs and still emits `dir/index.html`. Three things block approval.

## Required

**Issue 1 (high): a docs-lint guard now passes because it checks nothing, and this is not recorded.**
`packs/built-in/assets/docs_structural_lint.py::check_index_completeness` (around lines 469-472) reads `section_dir / "index.md"` and skips the section with `continue` when that file is missing. `docs/architecture/` is the only `curated_complete_sections` entry (`packs/internal/styleguides/spec-kitty-docs-lint-config.styleguide.yaml:16-20`). Its `index.md` is now `README.md`, so the completeness check that every architecture page is listed on the landing page no longer runs. It passes without checking anything.
- What I measured: the live run returns 0 violations. Renaming `README.md` back to `index.md` in a scratch copy also gives 0 violations, so no omission is hidden today. But the guard is inert from now on.
- The asset's shadow-tree and one-index helpers also still treat `index.md` as the canonical keeper (`_INDEX_LANDING_BASENAMES`, around line 638).
- This reader of the old basename was not updated, and neither the spec, the plan nor the tracers mention it.
- Packs are out of scope here (C-004), and their source is `spec-kitty-open-packs`. So the fix is to record the gap, not to edit `packs/`:
  - append a design-decisions or tooling-friction tracer entry;
  - name it in the PR body;
  - file the upstream gap in spec-kitty-open-packs so the asset reads the section index through `README.md` / `INDEX_BASENAMES`.
- The CLAUDE.md canonical-source rule says to file an upstream gap rather than leave it silent. Charter Standing Order 5 says a gate that checks nothing must not pass silently.

**Issue 2 (medium): five of the six WP01 code commits carry no trailers.**
`f6a4d36f5`, `ae5c15c37`, `a58f59977`, `558b1e308` and `07bc8d702` have no `Co-Authored-By:` and no `Claude-Session:` trailer. Only `5a53f2550` has them. The branch is not published, so reword these commits to add the required trailers. Keep the SSH signatures by re-signing.

**Issue 3 (medium): a model identifier appears in a commit.**
`5a53f2550` carries `Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>`. Commits must not name an AI model. Reword it to a model-free trailer, for example `Co-Authored-By: Claude <noreply@anthropic.com>`, and apply the same form to the trailers added under Issue 2.

## Should fix while you are in here (low)

**Issue 4: rule 3 in `site_redirects._entry` is wider than the index rename.**
The change removes `route not in moved` at `scripts/docs/site_redirects.py:124`. That condition kept a key from being emitted only for an unmoved `dir/index.html` whose resolved target is `dir/`. Now any moved `dir/index.html` whose resolved target is `dir/` gets no key and no refusal. That includes a move to an unpublished page whose rule-4 hub fallback happens to be `dir/`.
- The URL still resolves, because the live page serves it, so this is not a broken redirect today.
- But it silently drops a refusal that used to flag a conflicting move.
- Consider narrowing it to `route not in moved or is_index_rename(...)`, following the chain, and add a test for the hub-fallback case.

**Issue 5: the claim "never written" is inaccurate.**
The ADR amendment's Readers bullet and the `freshen_adr_inventory.py` docstrings at lines 10 and 72-76 say the retired `index.md` is read but never written. This is not true:
- `prune_dangling_rows` (lines 429-445) writes to whatever `_table_era_indexes` returns, and that is a lone retired `index.md` when no `README.md` exists.
- The add-row path (`_era_index_for`) only returns `README.md`, so on such a tree it raises "era index not found" while the prune path accepts the file.

Make the two paths agree: either drop the retired-read fallback, or never write it. Then correct the amendment text before it lands.

**Issue 6: the exemption added to `test_issue_3914_forward_reconcile_clean` is wider than its comment.**
The exemption added at `tests/docs/test_moves_ledger.py:99-100` passes any #3914 route whose old source file exists on disk. The comment says the intent is "a route a later move returned to". Key it on the ledger's returned routes (`moves_ledger._returned_routes`, or a public helper), so an unrelated file that reappears cannot excuse a missing redirect.

**Issue 7: the WP's "`relative_link_fixer --check` clean" criterion does not hold, though the failure is pre-existing.**
At HEAD it reports 10 dead bare-relative links. The same 10 are present at the base `7e9113ce2`, so none are caused by WP01. Say so in the PR body.

**Issue 8: mission bookkeeping is mixed into code commits.**
`a58f59977` and `07bc8d702` also edit `tasks/WP01-rename-section-indexes.md` (`owned_files`). Keep mission-artifact edits in their own commits.

**Issue 9: one behaviour change was not red-first.**
`07bc8d702` adds `_renamed_section_index` together with its test in a single commit, so that change has no red commit of its own. Note it in the tracer, or split it into a red commit and a green commit when you reword.

## Verified (no action)

- 59 renames: R100, no collisions, the set equals every base `docs/**/index.md`; `find docs -name index.md` finds 0.
- Ledger: 59 `#6939` entries matching the renamed folders 1:1. Eight returns are read from #3914 and #6928; `plans/initiatives` and `plans/next-mission-mappings` correctly stay non-returned because they were removed later. No earlier entry was edited (C-005); only the header comment changed.
- Red-first: at `f6a4d36f5` the basename test (2 tests), the redirect test (1 test) and the ledger test module (import of `is_index_rename`) all fail.
- D-7: 60 immutable files differ from the rename commit only in Markdown link targets. The ADR amendment adds 13 lines and removes 0.
- No generated surface was edited, and `check_generated_docs_untouched` returns no violations on this diff with or without rename detection.
