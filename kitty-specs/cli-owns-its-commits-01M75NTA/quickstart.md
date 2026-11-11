# Quickstart: verify the mission by hand

```bash
# 1. #7555 — init commits what it wrote
git init -q demo && cd demo && git commit -q --allow-empty -m root
spec-kitty init --ai claude --non-interactive
git status --short          # expect: nothing
git log --format=%s -1      # expect: the spec-kitty init commit

# 2. #7556 — another Mission's residue no longer blocks record-analysis
mkdir -p kitty-specs/other-01ABCDEF && echo x > kitty-specs/other-01ABCDEF/notes.md
spec-kitty agent mission record-analysis --mission <m> --input-file report.md --json
# expect: success, with a warning naming kitty-specs/other-01ABCDEF/

# 3. #5938 — next leaves the coordination worktree clean
spec-kitty next --agent claude --mission <coord-mission> --result success --json
git -C .worktrees/<coord-mission>-coord status --short   # expect: nothing

# 4. #3933 — setup-plan commits its lifecycle events
spec-kitty agent mission setup-plan --mission <m> --json   # expect commit_hash non-null
git status --short                                         # expect: nothing
```
