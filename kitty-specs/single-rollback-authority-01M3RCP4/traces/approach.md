# Tracer: approach

Mission single-rollback-authority-01M3RCP4 (#5385). Seeded at planning 2026-09-30.

- Grounding: two scouts (protection seam, test blast radius) plus a post-spec architect reviewer; findings folded into spec edge cases and residuals.
- Red-first: real-CLI repros in tests/terminus, fault injection only where a real run cannot fail at that point.
- WP01: T001 red on base (18/18), green after the door (18/18); planted break (move `_phase_merge_lanes` out of the door) turns the AST pin and the merge_lanes repro cases red.
- WP01: old-contract tests re-pinned by observing the phase-level strand/marker at phase exit (a wrapper around the real phase), then asserting the door's outcome after the run.
- WP02: T007 (9 real-CLI cases) red on the WP01 head: the protected-`main` and `--target develop` cases squashed onto the target and were then rolled back by the door (no up-front refusal, no remedy text); the `--dry-run --json` case exited 0. Green after the preflight (9/9); controls (develop, hatch, empty protected list, coordination mission, commit_to_target single_branch, all-done) green on both.
- WP02: planted breaks: `refuse_protected_status_target` returning `None` turns the refusal and dry-run cases red; `preflight_refusal` dropping the hatch env turns the real-CLI hatch control and the unit hatch test red. Both restored byte-identical (sha256).
