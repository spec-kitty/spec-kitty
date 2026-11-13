# Design decisions — mission-base-window-bound-01M78XB4

- **[2026-11-12][research] Root cause is data shape, not a regression.** The refusal code and its inputs are byte-identical between `bcd2afa03` and `v4.0.0rc8`; the window base (local target tip) need not reach the Mission base on a fork.
- **[2026-11-12][specify] Base source: record + derive (DM 01M78XBQS8NE8PPMSTZHMDJ610).** New `meta.json` `mission_base_sha`; older Missions derive it.
- **[2026-11-12][specify] Derivation: scaffold parent (DM 01M78XBWYTWJ6TZJVF4GWQMCQF).** Corrects my first recommendation (earliest lane base), which the challenger showed unsound: lane bases sit above planning and pre-implement commits.
- **[2026-11-12][specify] All window axes (DM 01M78XC2CJVH9ZXR0WB92NWYG5).** Declared-ref window stays `target..ref` (challenger: `^base` would empty report 2's window).
- **[2026-11-12][specify] Fold #7593 (DM 01M78XC76BMN026BTEH4T1ADFM).** Blocked on PR #7596.
- **[2026-11-12][plan] No resume state.** The base is re-derived deterministically (recorded key or scaffold commit, both stable under consolidation), so no `ConsolidationState` field and no A2 resume surface is touched.
- **[2026-11-12][plan] Approved-bound and canceled-content axes unchanged.** Dispatch non-goal; approval stamps descend from the base, so pre-base commits never enter those checks.
- **[2026-11-12][review] Renamed Mission dir fails closed (WP02 cycle 1).** A `git mv` into `kitty-specs/<slug>/` made the derived base land above Mission work; the derivation now returns UNAVAILABLE on a git-detected rename. Following renames was rejected (more surface, same residuals).
- **[2026-11-12][review] Rename-only probe, no copy detection (WP02 cycle 2).** `-C --find-copies-harder` marked every real Mission UNAVAILABLE (scaffold files resemble older Missions) at seconds per call. Accepted residual: a hand copy that keeps its source, a move edited past 50% similarity, copy-then-delete.
- **[2026-11-12][review] `core` must not import `consolidation` (WP02 cycle 1).** `record_mission_base_sha` lives in `mission_metadata.py`.
- **[2026-11-13][review] Exact-SHA exemption only (WP04 cycle 2).** A re-lettered-copy patch-id exemption was added on WP01's evidence, then dropped: a mutation test showed no reproduced shape needs it, and under `--strategy rebase` it would exempt re-lettered Mission commits. Re-lettered copies stay flagged (fail-closed).
- **[2026-11-13][review] Quiet note when the Mission branch does not resolve; no git stderr in the note (WP04).**
