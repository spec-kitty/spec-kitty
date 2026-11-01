---
affected_files: []
cycle_number: 1
mission_slug: issue-6917-sentinel-scoped-profile-read-01M6BV17
reproduction_command:
reviewed_at: '2026-11-01T18:18:14Z'
reviewer_agent: pi:glm-5.3:reviewer-renata
wp_id: WP03
---

# WP03 review feedback — REJECT (one defect, everything else verified)

Reviewer: pi:glm-5.3:reviewer-renata · mission `issue-6917-sentinel-scoped-profile-read-01M6BV17`

## Defect (blocking): `docs/development/docs-retrieval-index.yaml` regenerated with unrelated churn

Commit `2121e60274` adds the correct §4.5 anchor row for
`docs/architecture/profile-load-reliability.md`, but the same file also lands **five
unrelated hunks** from a full regeneration:

1. anchor `amendment-2026-10-31-6565-the-project-intent-rename-carries-an-exclusion`
   (docs/adr/4.x page);
2. anchor `amendment-2026-10-31-accepted-the-optional-companion-services-wheel`;
3. anchor `project-local-command-files-stay-retired` — the **exact row commit
   `b65b1a1137` (#6993) removed** when the generated surfaces moved to the post-merge
   regen bot;
4. anchor `if-a-mission-s-meta-json-is-missing` (upgrade page);
5. a full new page entry for
   `docs/plans/events-domain-move/companion-wheel-research.md` (#6904 research note).

Why this is a defect:

- **Repo policy (#6993 / `b65b1a1137`)**: the retrieval index, page inventory and ADR
  era tables are regenerated on `main` by the `ci/regen-docs-index` bot, **never in a
  pull request** — the header this very commit adds says so, as do
  `scripts/docs/check_docs_freshness.py` (`_REGEN_BOT_ACTION`) and
  `tests/docs/test_docs_index_regenerates_cleanly.py`. The re-added
  `project-local-command-files-stay-retired` row reintroduces exactly the cross-PR
  conflict churn #6993 was created to stop.
- **Regeneration was not needed for the gate**: `DOCS-INDEX-DRIFT` is warnings-only
  (verified: `check_docs_freshness --ci` → exit=0, errors=0 with or without the regen),
  and the actual staleness for `companion-wheel-research.md` is its absence from
  `page-inventory.yaml`, a file this WP did not touch — so the regen fixed nothing the
  gate checks.
- **WP03's own constraint**: "regenerate nothing globally; check freshness only"
  (Context & Constraints, Risk "Full-doc regeneration churn").
- **WP03 owned_files** does not include `docs/development/docs-retrieval-index.yaml`.
- The commit message claims "regenerates the docs index row for that page" — six
  hunks landed.

### Required fix

In `docs/development/docs-retrieval-index.yaml`, drop the five unrelated hunks listed
above. Keep at most the single §4.5 anchor row
(`4-5-a-read-only-render-reads-only-the-profiles-it-names-6917`) — or, cleanest per
#6993, revert the file to its `b65b1a1137` state entirely and leave regeneration to the
bot on main. The header policy lines you added are correct and may stay. Then re-run
`uv run python -m scripts.docs.check_docs_freshness --ci` (expect exit=0, errors=0; the
DOCS-INDEX-DRIFT warnings that return are the bot's business, not yours).

## Note (non-blocking, no change required)

The changelog's "(0.31 s)" for the scoped read has no recorded measurement anywhere in
the mission trail (which consistently says "≤ 0.5 s warm"). I measured the delivered
`build_agent_profile_sentinels(repo_root, ['human-in-charge','python-pedro'])` at
0.247–0.25 s warm, so the figure is plausible and under the NFR-002 bound — but if you
touch the entry anyway, prefer the recorded "≤ 0.5 s" or cite where 0.31 s was measured.

## Verified clean (for the record)

- Changelog entry: `## [Unreleased] - 4.0.0rc8` → `### Fixed`, bold impact-first lead
  with `(#6917)`, Before/After + What to do, 1,094 chars (< 1,200), matches bullet shape.
- Technical claims vs merged code: 26 shipped profile documents (counted), 358-node DRG
  (`load_built_in_graph()` run), ~2.1 s baseline (research.md: 1.136 s + 0.935 s),
  two-profile board parses exactly two documents and empty board parses none
  (`tests/charter/test_tasks_status_sentinel_scope_6917.py:153,177` with positive
  control at :165), lazy `_graph()` restored from #6462
  (`agent_profiles/repository.py:329`), `agent_profile_sentinels` /
  `build_agent_profile_sentinels` / `only_ids` exist and skip `PackContext`,
  marker/overlay/activation parity guarded (`test_agent_profile_scoped_load.py`).
- Architecture §4.5: delivered behaviour ("Two current facts replace that cost"), names
  the accessor and `_graph()`, links the existing contract
  (`contracts/agent-profile-sentinels.md`), consistent with the page's sections and
  frontmatter; index anchor matches the heading.
- Tracers (approach, design-decisions, tooling-friction) present with dated entries;
  issue-matrix #6917 = `fixed` with evidence refs to real commits and real test files.
- `check_docs_freshness --ci`: exit=0, errors=0, 12 warnings, all pre-existing and
  unrelated (HELP-DRIFT; events-domain-move inventory staleness).
- `tests/cross_cutting/packaging -k "changelog or docs"`: no such marker exists
  (150 deselected, 0 run) — per the WP's "only if such a marker exists".
