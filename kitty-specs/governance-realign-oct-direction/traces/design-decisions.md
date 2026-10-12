# Design Decisions

- 2026-10-12: **Run the loop as artifacts on one branch, not lane worktrees.** The delivery
  target is a plain topic branch + draft PR (brief step 0). A `single_branch` `mission create`
  on a non-primary branch would mint a `kitty/mission-<slug>-<mid8>` branch and move delivery
  off `governance-realign-oct-direction`. For a single-branch prose change the governance
  value is the spec/plan/tasks + tracer artifacts and the phased charter context, which are
  produced here without driving the worktree state machine. Flagged in the PR.
- 2026-10-12: **ADR `2026-10-01-2` — append an amendment, do not rewrite the body.** The ADR
  is currently Proposed, so flipping it to Accepted is a legitimate transition (not an edit to
  an immutable accepted record). The new open-core framing is recorded as a dated amendment
  (mirroring the existing "Amendment 2026-10-03"), leaving D-1..D-8 and that amendment intact.
- 2026-10-12: **ADR `2026-10-06-1` — append-only amendment.** The brief is explicit: do not
  delete its content; append a dated amendment recording the scoped lift. The ADR's
  Decision block and Consequences are preserved byte-for-byte.
- 2026-10-12: **Mark direction vs shipped state.** `services/mission-status-api/` (Java) and
  the charter's own repository are *direction*; the shipped state is in-repo (contracts +
  Python reducer present today, the amended ADR `2026-10-01-2` D-7 Java service as its own
  in-repo build). The open-packs *internal* source move is direction; the shipped no-bundle
  invariant is unchanged. Prose says so explicitly.
- 2026-10-12: **Decision 6 is a source-location move, not an ADR `2026-08-16-3` reversal.**
  The Pack Tiers wording names the `spec-kitty-open-packs` home for both tiers and restates
  that `packs/internal/` stays excluded from the wheel/sdist and built-in content stays
  present in the consumer install; no packaging code or gate is touched.
- 2026-10-12: **GA gate framing.** GA stops being date-gated (done-when-done); the gate's
  contents expand from local-integrity-only to also include charter modular extraction (#645
  precondition) and the mission-status API backend. RCs keep shipping to early adopters off
  `main`; red-CI-no-release (Standing Order 9) still holds per RC.
