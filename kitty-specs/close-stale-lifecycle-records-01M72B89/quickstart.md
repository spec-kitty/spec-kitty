# Quickstart: Close stale WP lifecycle records

1. See what is open:

   ```bash
   spec-kitty doctor invocation-pairing --json
   ```

2. Close lifecycle records (and Ops) older than 24 hours:

   ```bash
   spec-kitty doctor ops --close-stale
   ```

   Use `--threshold 0` to close every open one. The closures are committed on the current branch; on a protected branch the commit is refused and reported, and the files stay written for you to commit through a pull request branch.

3. Check:

   ```bash
   spec-kitty doctor invocation-pairing --json   # the closed orphans are gone
   git log -1 --stat                              # the closure commit
   ```

The Mission's status and `meta.json` are not touched.
