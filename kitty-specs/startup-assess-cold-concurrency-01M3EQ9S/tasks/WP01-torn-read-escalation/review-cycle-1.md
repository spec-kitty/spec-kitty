---
affected_files: []
cycle_number: 1
mission_slug: startup-assess-cold-concurrency-01M3EQ9S
reproduction_command:
reviewed_at: '2026-09-26T13:19:38Z'
reviewer_agent: reviewer-renata
wp_id: WP01
---

# WP01 review cycle 1: REJECT (reviewer-renata, opus)

The production code is correct: the design matches contract P1-P6 and folds 1-10, and no product bug was found. The rejection is for missing or weakened BINDING test folds and for new suppressions.

Verified: red→green (a20797b6da is RED for all 3 owners, and HEAD passes 28). 96eb2a01b2 is behaviour-preserving (1005 passed). tests/runtime plus tests/specify_cli/runtime give 1151 passed and 2 skipped. The architectural trio passes 179, and the gates are clean on src. The `_APP` reset is correct test isolation.

Blocking:
1. The US3.3 / fold 6 T008.4 test is missing: `{}` inventory gives StartupAssetError with code global_assets_unavailable, and the lock spy records [].
2. Fold 5 step-4 is not strengthened at test_startup_torn_read_escalation.py:186. Add two assertions: the inventory is observed exactly 2x before the first lock, and the first lock is `_cold_install_sentinel(anchor)`. A mutation probe (an extra unlocked retry) left the entry-point tests green.
3. C-008 is tautological at test_build_serialized.py:257-304. Replace it with concrete lists: cold gives [sentinel], and after touching lock_path it gives [lock_path].
4. test_build_serialized.py:159 asserts `>= 1`. Assert the concrete [sentinel] list instead.
5. T007.13 uses the runtime batch rather than the skills startup path `assess_global_assets(runtime=False, commands=False)`. It must also assert that escalation fired.
6. Remove the 8 new suppressions (:177 noqa; :98, :236/:237/:241, :272/:291, :556 type-ignores). mypy --strict on the 2 test files reports 12 errors, which should be fixed.

Non-blocking (folded at the orchestrator's direction): an entry-point INFO-line assertion on the owner logger; a code-dependent next-step hint (no "another process" hint for source_drift or unavailable); the JSON-mode test asserting stderr is empty.
