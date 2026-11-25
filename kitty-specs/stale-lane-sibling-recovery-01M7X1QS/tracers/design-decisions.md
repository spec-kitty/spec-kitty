# Design decisions

- Option A (diagnose and redirect the remedy) over rollback changes; see plan.md Options.
- The sibling case names `git merge <sibling lane branch>`: amends the FR-091 / #7311 "no git merge" rule, which assumed the Mission branch was a valid source.
- Gate run: `test_no_worktree_name_guess.py` passed with sibling branches composed through `lane_branch_name` (C-002).
- Remedy wording: "earlier in this run" was not provable on a resumed run; the cause sentence now says the rollback *can* remove the sibling change, which is true in every case.
