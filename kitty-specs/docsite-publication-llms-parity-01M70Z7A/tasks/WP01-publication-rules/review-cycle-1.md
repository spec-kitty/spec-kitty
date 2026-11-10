---
affected_files: []
cycle_number: 1
mission_slug: docsite-publication-llms-parity-01M70Z7A
reproduction_command:
reviewed_at: '2026-11-10T07:20:05Z'
reviewer_agent: claude-reviewer::reviewer-renata
wp_id: WP01
---

**Issue 1 (HIGH): the link-gate wrapper hides a failing gate when every parsed problem is listed.** `scripts/docs/site_link_gates.py:116` only parses lines that start with `✖`, and `main` (line 164) only fails a non-zero exit when *no* problem was parsed. `dockitty-check-links` also fails with exit 1 on route collisions, which it prints as `[dk-routes] N route collision(s) ...` with no `✖` (`site/node_modules/@spec-kitty/doc-toolkit/scripts/check-links.mjs:705-712`, `lib/vocabulary-core.mjs:1215`). The 59 `check-links` debt entries always occur, so a route collision (two pages served at one address) always passes. Reproduced: a fake gate that prints one listed `✖` line, then a `[dk-routes]` line, and exits 1 makes `python -m scripts.docs.site_link_gates check-links -- <fake>` exit **0**. Fix: when the gate exits non-zero, also fail on any failure-shaped output outside the parsed problems. For example, treat `[dk-routes]` lines as unparsed problems, and/or compare the parsed count with the gate's own summary (`N link problem(s)` / `FAILED — N broken ...`) and fail when they differ. Add a mutant test (listed problem + collision + exit 1 must fail).

**Issue 2 (MEDIUM): moved bodies are not byte-identical, and the ADR amendment says they are.** Seven moved pages had 14 relative links re-pointed: team-kitty-saas, sync-workspaces (2), project-sync-consent (7), internal-hosted-readiness, logged-out-teamspace, sync-daemon-orphan-cleanup and zeitgeist-client-wp01-remaining. The last of these was already immutable (`plans/`) before the move: `docs/archive/plans/zeitgeist-client-wp01-remaining.md:31`. The hand-off said "4 links in 3 pages". Every re-point keeps its target, and I accept them as part of the move's mechanics under C-001. But `docs/adr/4.x/2026-10-31-1-...md:346` says "with their bodies unchanged", which is false. Reword it to say that relative links were re-pointed to the same targets on move and nothing else changed, and correct the history note. `tests/docs/test_immutable_bodies.py` cannot catch this, because it compares only the migration's own output.

**Issue 3 (MEDIUM, C-002): a second hand-written draft-folder list remains.** `scripts/docs/dockitty_frontmatter_migration.py:145` `DRAFT_SECTIONS` repeats `DRAFT_FOLDERS` (`_dockitty_contract.py:110`) by hand. Derive it with `tuple(f"{f}/" for f in DRAFT_FOLDERS)`, so the contract stays the one authority.

**Note (LOW):** `tests/docs/test_relative_link_fixer.py` `_KNOWN_GAPS` ignores a stale `relative-links` entry without reporting it. The wrapper reports stale entries, so consider reporting them here as well.

Verified OK:
- single authority for the unpublished set, and its projection;
- route normalisation against the real `site/dist`: 0 published routes unbuilt, case and dots preserved;
- all seven surfaces have mutants, and the red commits are red on their own;
- all 174 debt entries have immutable sources, and on the real build 169/169 gate entries match (0 stale);
- moves.yaml is append-only and `check-map` is fresh;
- no bot surface was touched, and D-8 is unchanged;
- the out-of-map edits are justified.
