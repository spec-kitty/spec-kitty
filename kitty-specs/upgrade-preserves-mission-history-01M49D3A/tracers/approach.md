# Approach

Starting approach: red-first CLI repros (WP01). Then three fixes:
- the repair round-trips lane rows through `StatusEvent` and keeps their order (WP02);
- one shared is-a-Mission predicate (WP03);
- `upgrade` becomes report-only under drain (WP04).

Record changes of approach and why below.
- WP01 red-on-base evidence (review-cycle-1): 5 tests failed under `SPEC_KITTY_RUN_P0_REPRO=1` for their defects:
  - rewritten `status.events.jsonl` and `meta.json`, including the out-of-order Mission;
  - an audit manifest written;
  - a dirty tree after an auto_commit run;
  - ghost `IDENTITY_MISSING`;
  - `--fix` minting `meta.json`.

  The auto_commit test was strengthened with a post-run `git status` check, because the commit step runs before the repair step.
- The integrated run after consolidation surfaced 4 cross-lane breaks in `test_mission_corpus_recovery.py`. One was a monkeypatch signature break; in the other, the original corpus's two archival directories are now residue, which is legitimate under FR-006. Both were fixed in a test-only commit.
