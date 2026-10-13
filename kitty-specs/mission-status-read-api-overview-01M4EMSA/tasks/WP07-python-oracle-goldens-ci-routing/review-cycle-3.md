---
affected_files: []
cycle_number: 3
mission_slug: mission-status-read-api-overview-01M4EMSA
reproduction_command:
reviewed_at: '2026-10-12T07:55:25Z'
reviewer_agent: reviewer-renata
wp_id: WP07
---

# WP07 reopened (orchestrator): three manifest/resolver amendments owed by later rulings

WP07 was approved on 2026-10-11. Three later rulings change files WP07 owns, and WP09 consumes these files, so WP07 is reopened before WP09 starts. Every change must come from the generator (`tests/contract/_mission_status_conformance.py`) and live Python, never from hand edits to generated files. The golden-honesty test must stay green.

| id | where | change | source |
|---|---|---|---|
| A1 | `conformance/resolver-cases.json` plus `manifest.json` `resolverCaseIds` (via the generator) | Add resolver cases for a stored `coord` and a stored `lanes_with_coord`, each with no `coordination_branch` (absent, and empty string `""`) while the coordination Mission dir IS present. The oracle `resolve_read_dir` gives `own` for all of them. Generate the expected class from the oracle, for both a registered worktree and a husk, as the existing cases are. | Operator ruling 2026-10-12 (reviews/analyze.ruling.md, "coordination routing needs a coordination_branch"); DD-100 |
| A2 | `manifest.json` `patternDivergences` (via the generator) | The `construct` text "java.util.regex needs UNICODE_CHARACTER_CLASS" is wrong. Replace it with: "Python str-pattern \\w \\s \\d differ from java.util.regex even with UNICODE_CHARACTER_CLASS (Java \\w also matches Mn, Mc, Me, Pc and Join_Control; Java \\s omits U+001C to U+001F). The Java side translates \\w \\W \\s \\S \\d \\D to Python's classes and guards lookbehind against supplementary characters (DD-86, DD-87); \\b and \\B are refused." Keep the per-pattern ids as they are. | DD-86, DD-87, DD-88 (WP17 cycle 2) |
| A3 | `manifest.json` `provisioning.blank-line` (via the generator) | The text says the invariant is "the SHA-256 of the last consumed non-blank terminated line". The oracle `tail_reader` uses the last terminated line of ANY kind, blank included: `validate_resume_cursor` and `poll_once` accept the blank-line digest and reject the non-blank one. Reword it to "the SHA-256 of the last terminated line, a blank line included (tail_reader)". If the generator can produce a fixture whose final terminated line is blank, add it to the malformed-rows class and drop the sentence "A blank line as the final line is not a fixture"; otherwise keep that sentence. | DD-92 (WP06 review), correcting the orchestrator's earlier ruling |

After the change:
- the honesty test (`tests/contract/test_mission_status_conformance.py`) is green;
- the routing and workflow tests WP07 owns are green;
- every regenerated golden that changed is listed with the reason it changed.
