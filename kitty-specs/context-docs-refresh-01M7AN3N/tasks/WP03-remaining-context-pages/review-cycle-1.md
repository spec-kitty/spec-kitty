---
affected_files: []
cycle_number: 1
mission_slug: context-docs-refresh-01M7AN3N
reproduction_command:
reviewed_at: '2026-11-16T06:54:35Z'
reviewer_agent: claude-reviewer::reviewer-renata
wp_id: WP03
---

**Issue 1 (medium, FR-009): doc-kitty does not read the `%% title:` / `%% description:` metadata in either new Mermaid diagram.**
In `docs/context/README.md` and `docs/context/contextive-glossaries.md` the metadata lines come after `flowchart LR` / `flowchart TD` and are indented (`  %% title: ...`).

doc-kitty's `parseMeta` (`@spec-kitty/doc-toolkit/lib/remark/diagram-meta.internal.ts`) reads only the leading block, and that block ends at the first line that is neither blank nor `%%`. Its regex is `^%%\s+(title|description|attribution|source):`, with no leading indent allowed. Running that same function on both sources returns `{}` for each. A control with the lines at the top returns `{"title":"T","description":"D"}`.

As committed, the built figure gets no caption from `%% description:`, and the metadata #3891 asks for has no effect. The explicit `accTitle`/`accDescr` lines still give each SVG an accessible name, so accessibility is not lost.

Fix:
- Move `%% title:` and `%% description:` to the top of each block, before the `flowchart` line and without indentation.
- Drop the hand-written `accTitle:`/`accDescr:` lines. `injectAccStatements` writes them from the metadata, and keeping both leaves two copies in the rendered source.
- Re-run `parseMeta`, or the built-site `diagrams` check where Docker is available, to confirm.

Both diagrams parse cleanly with the pinned `mermaid@11.17.1` (`flowchart-v2`; a broken control fails), so only the metadata placement needs changing. This also answers P5: the convention is a leading `%%` block, as `assert-build-artifacts.mjs` and `diagram-meta.ts` describe.

**Issue 2 (low, overloaded `merge` sense): "lane consolidation" is used for the landing on the target branch.**
- `spec-driven.md:226`: "`spec-kitty consolidate` performs lane consolidation: it lands the Mission's execution lanes on the local target branch".
- `ops-vs-missions.md:143`: "lane consolidation into the local target branch".

Per `orchestration.md#lane-consolidation`, lane consolidation is the lane step into the Mission branch. Landing on the target is [Branch Integration](orchestration.md#branch-integration--git-merge). Write it as, for example: "`spec-kitty consolidate` consolidates the execution lanes into the Mission branch and integrates that branch into the local target branch; publishing to origin goes through a pull request."

**Issue 3 (low, citation): `dossier.md:131` and `:144` say the drift detector was deleted in "#274".**
The deleting commit is `e7f777652b` (2026-08-27), "[#116] Wire-or-prune adjudication for orphaned sync-transport collateral", and its body says `Issue: #116`. Nothing found ties #274 to it. Cite the commit, or #116, or verify #274 and add it to the corrections-log evidence (row 73).

**Issue 4 (low, precision): `spec-driven.md`, the `/spec-kitty.implement` section, says `agent action implement` "moves the work package from `planned` to `in_progress`".**
The status log records two transitions, `planned -> claimed -> in_progress`; WP03's own events show this. Say "through `claimed` to `in_progress`".

Verified and fine. Spot-checked against the code:
- Rows 41-62 and 64-120 hold where checked:
  - `REGISTERED_TRIGGERS`, and the test deletion in `177e062694`;
  - `NodeKind` has 17 members; `DenyListChoice` has 5;
  - `BOOTSTRAP_ACTIONS` and `_MIN_EFFECTIVE_DEPTH = 2`;
  - `optional_tracked_files=[ACTIVATION_YAML]`;
  - the `charter.yaml` and `activation.yaml` keys, and the tracked provenance and `graph.yaml`;
  - `ProjectIdentity`: `generate_project_uuid`, `derive_build_id` UUID5, `generate_node_id` sha256[:12], `repo_slug` as an override, `derive_project_slug`;
  - `should_block` behaviour for off/medium/max;
  - dossier `MissionDossier*` names with no caller in `src/`; `build_status_event_payload`;
  - glossary events path; `events tail --log` with seven logs;
  - DR/AR/QR in the requirement grammar; 3-7 subtasks per WP with a maximum of 10;
  - `pytest.ini`: 41 markers, slow >30 s; the page's 30 described plus 11 listed make 41;
  - the 9 CI-routed markers; `CI_INVISIBLE` (13) covers the platform, orchestrator, exploratory and agent markers;
  - `FAST_TIER_MARKERS` excludes `distribution` and `platform_darwin`; `test_pytest_marker_convention.py` is absent;
  - the `analyze` step in the software-dev DAG; the research step titles; `source_documented_count < 3`;
  - the `mission.yaml` copies are byte-identical;
  - `ask`/`advise`/`do` are absent; `dispatch` and `profile-invocation complete` exist; `charter sync` is absent;
  - the Contextive counts (16 pages, 7 mapped, 7 "yes" rows), and no workflow runs `check`;
  - the pre-commit hook does what the page says.
- Anchors from `CLAUDE.md`, `AGENTS.md`, `docs/` and `src/` into the 22 pages all resolve. The two apparent misses point at another `README.md` and at an immutable report, and neither page had those headings on the base. Removed headings have no inbound links.
- All 22 pages name their readers and carry `updated: 2026-11-13`.
- WP01 and WP02 pages, `packs/` and ADRs are untouched; out-of-scope code drift is flagged (O8-O12), not edited.
- The 27 commits are signed, with no model identifier outside the sanctioned trailer.
- All gates are green.
