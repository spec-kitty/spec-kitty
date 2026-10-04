# Quickstart: verify the mission

Use an isolated home so user-global surfaces do not count as drift.

```bash
export HOME=$(mktemp -d) XDG_CONFIG_HOME=$HOME/.config
mkdir demo && cd demo && git init -q
spec-kitty init --ai claude --non-interactive && git add -A && git commit -qm init
spec-kitty upgrade --yes </dev/null; echo "exit=$?"        # Project is already up to date!  exit=0

echo "local edit" >> .claude/agents/<any-profile>.md && git commit -qam edit
spec-kitty upgrade --yes </dev/null; echo "exit=$?"
#   ✗ Unresolved tool-surface drift in 1 file(s); run 'spec-kitty doctor tool-surfaces' to review.
#   Upgrade finished with unresolved tool-surface drift.      exit=1
spec-kitty upgrade --yes --json </dev/null | python -m json.tool | grep -E '"(status|outcome|success)"'
#   "status": "failed", "success": false, "outcome": "drift_unresolved"
```

Targeted tests:

```bash
PWHEADLESS=1 .venv/bin/python -m pytest -q \
  tests/upgrade/test_upgrade_outcome_kind.py tests/upgrade/test_upgrade_outcome_rendering.py \
  tests/upgrade/test_finalizer.py tests/upgrade/test_upgrade_integration.py \
  tests/specify_cli/tool_surface/test_drift_policy.py tests/specify_cli/tool_surface/test_surface_repair_wiring.py \
  tests/specify_cli/cli/commands/test_upgrade_command_skill_drift.py \
  tests/architectural/test_upgrade_outcome_single_rendering.py
```
