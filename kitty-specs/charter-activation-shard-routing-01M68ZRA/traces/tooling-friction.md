# Tracer: tooling-friction

One entry per finding: `YYYY-MM-DD · actor · <text>`.

---

2026-10-31 · claude-code/opus · spec-kitty specify defaults to --topology coord, which minted a coordination worktree whose tracer commits landed outside the checkout; re-created the mission with --topology single_branch for a two-WP CI mission (no coordination branch needed). Also: the implement claim commit is created by 'agent action implement', so a WP whose implementation commits were made BEFORE the claim cannot pass move-task's since-claim check; the claim must precede the first implementation commit.

2026-11-01 · claude-code/opus · Delivery friction after the green run: (1) the batch rebase pass force-rebased this branch onto a newer main twice, restarting CI each time; (2) each rebase conflicts only on kitty-ops/lifecycle.jsonl (append-only journal) — resolved by keeping origin/main's bytes verbatim and appending this mission's rows sorted by 'at', which the archive-freeze guard accepts (0 removed lines, prefix preserved); (3) the operator applied pr:pause-ci to the PR, which cancels/skips every job and fails the required gate names by design, so a fresh green head needs the label lifted. First fully green head: 0d835d23 (38 SUCCESS / 9 SKIPPED).
