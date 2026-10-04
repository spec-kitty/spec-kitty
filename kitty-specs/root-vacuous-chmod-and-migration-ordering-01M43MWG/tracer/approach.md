# approach

Red-first for every site, run as uid 0: plant a break in product code, watch the test fail, revert (with `cp` backup and `diff -q`), and watch it pass. The proofs are recorded in the PR "Tests run" section.
