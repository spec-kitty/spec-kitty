# Quickstart: verify the settled-placement fix

1. Create a default Mission (no `--topology`) with three code work packages and run
   `spec-kitty agent mission finalize-tasks --mission <slug>`; it settles to `lanes_with_coord`,
   moves the repository root checkout back to its starting branch and opens
   `.worktrees/<slug>-coord` on the Mission branch.
2. From the coordination worktree, write `kitty-specs/<slug>/traces/note.md` and run
   `spec-kitty spec-commit kitty-specs/<slug>/traces/note.md -m "tracer" --mission <slug>`.
   Expected: committed on the Mission branch (no `WRONG_SURFACE`).
3. From the repository root checkout (on a protected branch such as `main`), run
   `spec-kitty agent action implement WP01 --mission <slug> --agent <name>`.
   Expected: exit 0; the claim is committed on the Mission branch; `main` does not move.
4. Move WP01 to `for_review` with a configured `review.test_command`.
   Expected: `kitty-specs/<slug>/tasks/WP01-*/baseline-tests.json` is committed on the Mission branch.
5. Run `spec-kitty agent tasks move-task WP01 --to in_progress --note "…" --mission <slug>` from the root.
   Expected: not refused; the banner names the Mission's declared target branch.

The automated version of these steps is the settled-fixture integration test module added by this Mission.
