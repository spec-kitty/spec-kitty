---
name: spk-gate-accept
description: "Run the Spec Kitty accept gate for a completed mission and verify final readiness before merge."
---

# spk-gate-accept

Use this skill when runtime reaches terminal state, the user asks to accept a
mission, or all WPs appear complete.

## Flow

1. Run `/spec-kitty.accept` or the equivalent CLI command.
2. Confirm all required WPs are approved or done.
3. Verify required tests, artifacts, and mission invariants. When the mission
   changed typed sources, run the project's configured compiler/typecheck
   command, matching CI, in addition to the test runner. A failed compiler
   command fails the gate; passing behavioral tests are not a substitute.
4. If accept fails, route to `spk-run-blocked-recovery`.
5. If accept passes, route to `spk-gate-merge`.

## Rule

Accept is not a formality. It is the final pre-merge readiness gate.
