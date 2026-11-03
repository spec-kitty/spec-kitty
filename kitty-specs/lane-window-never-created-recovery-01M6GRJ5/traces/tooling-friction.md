# Tracer: tooling-friction

One entry per finding: `YYYY-MM-DD · actor · <text>`.

---

2026-11-03 · python-pedro · The single_branch for_review gate needs a qualifying commit AFTER the recorded claim base (refs/spec-kitty/wp-base/<slug>/<WP>), so a Mission that writes the code before claiming a work package cannot move it without --force. Resolved by reordering the local history into claim-then-implement (unpushed commits) rather than bypassing the gate; noted in the PR body.
