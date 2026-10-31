# Issue matrix — issue-6693-red-main-refs-to-directive-01M66YZX

One row per issue referenced in `spec.md`. The verdict is recorded through
`spec-kitty agent issue-verdict` and must reach a terminal state before the mission
is `done`.

| Issue | Title | Verdict | Evidence ref |
|-------|-------|---------|--------------|
| #6693 | Repoint red-main-release-discipline procedure references to the RED_MAIN_RELEASE_DISCIPLINE directive on the next open-packs pin bump | fixed | spec.md FR-001–FR-006 — WP01 (pin + curated edge), WP02 (five tests + fixture), WP03 (ledger, guard, changelog); verdict recorded via `agent issue-verdict` after consolidate |
| #4253 | (context) the 4.0.0rc5 activation regression `tests/charter/test_activation_preserves_effective_4253.py` guards | not-applicable | cited as history; that test stays green untouched and this mission owes it no work |
| #74 | (context) `spec-kitty/spec-kitty-open-packs#74`, the upstream PR that moved the rule to a directive | not-applicable | upstream authoring; this mission vendors it at pin `72cb7dbc` and owes no work in this repository |

Valid `Verdict` values: `fixed`, `verified-already-fixed`, `deferred-with-followup`,
`in-mission` (being fixed by a later WP in this mission; must reach a terminal verdict
before mission `done`).
