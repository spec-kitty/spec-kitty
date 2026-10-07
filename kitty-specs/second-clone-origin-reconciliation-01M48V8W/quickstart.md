# Quickstart: see the fix with two clones

```bash
git init --bare origin.git
git clone origin.git A && (cd A && spec-kitty init --ai claude --non-interactive && ... create, plan, finalize, implement, approve, git push --all)
git clone origin.git B && (cd B && spec-kitty init --ai claude --non-interactive)   # now installs merge.* config (#5759)
git -C B config --get-regexp '^merge\.' | wc -l                                     # 14
# B rejects WP02 and pushes; A, without pulling:
(cd A && spec-kitty consolidate --mission <m>)        # ORIGIN_STATUS_STALE, nothing moved (#5780)
(cd A && SPEC_KITTY_ORIGIN_CHECK=warn spec-kitty consolidate --mission <m> --dry-run)  # warns instead
# Re-review after B pushes a fix to the lane:
(cd A && spec-kitty agent action review WP02 --mission <m> --agent claude)   # "Updated ... from origin/..." (#5758)
```

The full scripted reproductions live in the issue bodies of #5780, #5758 and #5759 and in the mission's regression tests.
