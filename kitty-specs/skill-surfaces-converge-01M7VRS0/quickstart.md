# Quickstart: verify the Mission by hand

```bash
export HOME=$(mktemp -d)                     # never your real home
spec-kitty init /tmp/p --ai claude --non-interactive && cd /tmp/p
# 1) stale shipped global skill gets refreshed
git -C <spec-kitty checkout> show dd83e5b6f:src/doctrine/skills/spk-run-implement-review/SKILL.md > ~/.claude/skills/spk-run-implement-review/SKILL.md
rm ~/.kittify/cache/global_skills-assets.json
spec-kitty doctor command-files   # startup sync
diff ~/.claude/skills/spk-run-implement-review/SKILL.md <installed package>/charter/offering/skills/spk-run-implement-review/SKILL.md   # identical
# 2) an edited file is kept and reported, lock not stamped
echo edit >> ~/.claude/skills/spk-run-next/SKILL.md
spec-kitty doctor tool-surfaces --json | jq '.findings[] | select(.code=="global-skill-kept-stale")'
# 3) old-root leftovers
export CLAUDE_CONFIG_DIR=$(mktemp -d)
spec-kitty doctor skills; spec-kitty doctor command-files   # lists ~/.claude copies, deletes nothing
```
