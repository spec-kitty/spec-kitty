# Tracer: tooling-friction

One entry per finding: `YYYY-MM-DD · actor · <text>`.

---

2026-11-12 · claude · bulk_ref_rewrite.py replays the whole moves ledger over src/tests/docs (minutes per dry run) and rewrites prose in plans/ and archive/, which D-7 treats as immutable; relative_link_fixer.py resolves a broken link from the file's pre-move folder first (sent guides/how-to/monitoring/use-dashboard.md's index.md link to guides/README.md) and heals unrelated dead links by basename. WP01 rewrote links from the ledger's #6939 pairs with a scoped one-off instead.

2026-11-12 · claude · The built-in common-docs styleguide (packs, compiled into .kittify/charter/charter.yaml) still says each directory carries its own index.md; AGENTS.md (CLAUDE.md) line 270 names docs/architecture/index.md. Neither is edited here: packs are upstream (spec-kitty-open-packs) and AGENTS.md needs operator approval.

2026-11-12 · claude · Known gap, upstream follow-up: packs/built-in/assets/docs_structural_lint.py (spec-kitty-open-packs) reads the section landing page as index.md. check_index_completeness skips a section without one and _INDEX_LANDING_BASENAMES keeps index.md as the canonical keeper, so after #6939 the curated-complete check on docs/architecture/ does not run. The open-packs lint needs README.md as the landing basename (via INDEX_BASENAMES). packs/ is not edited here (C-004); the coordinator raises it with the operator; no issue filed from this Mission.

2026-11-13 · claude · Correction (WP01 review cycle 2): base 7e9113ce2 has the same 10 dead relative body links as HEAD, not 12. The two extra targets in a fresh base worktree were packs/ paths that resolve once make sync-packs has run; the earlier comparison ran before the pack tree was in place.

2026-11-13 · claude · WP02 review cycle 1: the review prompt showed the reviewer as claude-reviewer::reviewer-renata, a CLI rendering quirk of the reviewer identity, not a second agent; noted here only.

2026-11-13 · claude · Follow-up (out of scope, not changed): the code gate's RETIRED_CLI_PREFIXES (scripts/retired_surfaces.py, read by tests/architectural/test_no_retired_subsystems.py) lacks the six #6164 commands auth, issue-search, live-work, moments, routes and zeitgeist. The docs gate covers them through DOC_RETIRED_SURFACES; adding them to the code list would make the live-CLI check assert their absence too.

2026-11-13 · claude · WP02 review cycle 3 low follow-ups (not fixed here): (1) the landing-set subset check (refilled vs _LANDING_PAIRS) runs only in pytest, not in the gate script that docs-lint runs; the baseline-equality check does run in both. (2) A page with malformed frontmatter has its title and description scan skipped without a warning (parse_frontmatter returns an empty mapping). (3) The issue-matrix row wording for #7520 can be tightened.
