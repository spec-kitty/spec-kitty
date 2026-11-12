---
affected_files: []
cycle_number: 1
mission_slug: retire-docfx-01M78FG2
reproduction_command:
reviewed_at: '2026-11-12T19:20:29Z'
reviewer_agent: claude-reviewer::reviewer-renata
wp_id: WP02
---

# WP02 review (claude-reviewer::reviewer-renata) — changes requested

## Blocking

**B1. The new gate is red on its own file.** `tests/architectural/test_legacy_docsite_named_nowhere.py:10` names the legacy tool in its docstring through the Mission slug (`kitty-specs/retire-...-01M78FG2/spec.md`). The file is tracked and not excluded, so `test_no_living_file_names_the_legacy_tool` fails at e5a72d393:

```
FAILED tests/architectural/test_legacy_docsite_named_nowhere.py::test_no_living_file_names_the_legacy_tool
AssertionError: ['tests/architectural/test_legacy_docsite_named_nowhere.py:10'] == []
```

This breaks NFR-001 and SC-001/SC-004. `git grep -il docfx` also lists this file.

Remedy: reword line 10 so that it does not spell the slug. For example, write "the Mission's immutable-history list (its spec, C-001)", or build the path from fragments the way `LEGACY_TOOL` is built. Do NOT add the file to `IMMUTABLE_HISTORY` or `GENERATED`, because NFR-003 forbids growing that list. Then re-run:
`uv run --frozen pytest tests/architectural/test_legacy_docsite_named_nowhere.py -q`

## Low (fold while there)

- **L1.** `docs/api/configuration.md`, "Docsite build (doc-kitty)" section, says "A page is published unless it lies in an excluded folder or has `doc_status: draft`". That rule is incomplete. `_dockitty_contract.py` also never publishes pages in `DRAFT_FOLDERS` (`plans/engineering-notes`, `plans/investigations`, `plans/research`). Add that clause.
- **L2.** ADR amendment, evidence bullet: it says "green on every run since the merge of #7558". The merge-commit run 43095177387 (ba45c46c2) is still `queued` with no conclusion. Every run that completed is green. Say "every completed run", or name the run.
- **Nit.** `site/url-baseline.txt` header has an orphaned wrap: "publishes it). A route is" / "# removed only by ...". Reflow those two lines into one sentence. This is a header comment only, so C-005 allows it.

## Verified OK

- Item 1: the `tests (docs)` job has no jar steps. Both new tests in `test_nightly_tooling_cache.py` pin that, and every `hashFiles()` input exists. Swept workflows, router, registry, scrub JSON and Makefile: no references to deleted files. `ci-shard-timings.json` is generated (`b273a96ff`). Its timings are identity-keyed, and `shard_select` reports stale ids without failing.
- Item 2: the ADR diff from 89217ac83 adds lines only. Run 43027580608 is green: canary-build, canary-deploy and canary-probe. Run 43265541140 is green: pages, build, deploy and smoketest. The `glossary_linker` reason is accurate: it imported `generate_kitty_specs_docs` and walked `docs/_site`. The rollback text and the D-13/#6939 text are accurate, and #6939, #6940 and #3024 are open.
- Item 3: the exclusion set equals spec Context line 16 exactly. The planted self-test is non-vacuous.
- Items 4 to 6: the doc-kitty facts check out (`make docs-site-bump`, `site_contract`, `site_redirects --check`, the 50-180 band, `assert_reports_unpublished`). `site/public/CNAME` is `docs.spec-kitty.ai`, unchanged. The fragment passes style and spelling. Terminology is clean.
- Item 7: `spec-kitty regen --check` is fresh. `docs-retrieval-index.yaml` must not be in a PR (`check_generated_docs_untouched.py`, `docs-index-regen.yml`). Correctly untouched.
