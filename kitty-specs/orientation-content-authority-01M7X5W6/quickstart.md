# Quickstart: verify #5215

```bash
mkdir dirname-differs && cd dirname-differs && git init -q && git commit -q --allow-empty -m init
spec-kitty init --ai claude --yes
sed -i 's/slug: dirname-differs/slug: local-agent-bus/' .kittify/config.yaml
spec-kitty doctor tool-surfaces            # orientation context file reported stale
spec-kitty doctor tool-surfaces --fix
grep "project:" .claude/CLAUDE.md          # project: local-agent-bus (healthy)
spec-kitty session-start | sed -n 2p       # same project name
spec-kitty upgrade --project --yes && git status --short .claude   # nothing further changes
```
