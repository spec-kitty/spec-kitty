# Bounded Reproduction and Validation

Audience: software-engineer. Updated: 2026-10-11.

Use temporary fixture Missions, never damage this Mission's own status history. Prior investigator reproduction is in [research.md](research.md), E1.

1. In a TemporaryDirectory, write `{not json\n` to status.events.jsonl. Call existing run_doctor for that directory. On baseline without snapshot it falsely reports healthy.
2. Add a valid status.json with empty work_packages; rerun. Baseline raises StoreError during drift replay. Both are bugs, not expected final results.
3. New failing-first acceptance tests must demand ERROR/unhealthy without exception for both; run explicitly and commit before production edits. If transitional regression marker is used, it must not hide RED evidence and must be removed on the fix.
4. Extend five-class/two-snapshot matrix, truthful physical lines, CLI text/JSON, byte preservation and repaired-history controls. No writes beyond temporary fixtures.
5. After fix, run commands in [plan.md](plan.md#validation-and-evidence-handoff), every changed test file and status owning-module fast tier, plus the shared make test-fast baseline once. No duplicate concurrent runs or heavy full suites.
6. Independent reviewer checks red→green commit order and actual complete diff. Parent opens PR targeting main. Leave mission approved/accepted pending PR integration; never merge/consolidate or push main.
