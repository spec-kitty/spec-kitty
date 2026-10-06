# Quickstart: verify the fixes by hand

```bash
# #4275 — upgrade without .claude/
cd "$(mktemp -d)" && git init -q && spec-kitty init --ai claude --non-interactive .
rm -rf .claude && spec-kitty upgrade --project --yes   # expect exit 0, .claude/ recreated

# #5801 — doctor reports missing pack skills
spec-kitty charter activate skill <id>                 # with a pack that ships <id>
rm -rf .claude/skills/<ns>-<id>
spec-kitty doctor skills --json                        # expect exit 1, pack_skills[0].kind == "missing"
spec-kitty doctor skills --fix && spec-kitty doctor skills   # expect exit 0

# no tool folder at all
rm -rf .claude && spec-kitty doctor skills --json      # expect exit 1, tool_folders[0].kind == "no_tool_folder"
```
