# Quickstart: see an org-required rule in force

1. Reproduce the scenario fixture (team pack requiring `team-rule`, the rule provided at
   `directives/team-rule.directive.yaml`):

   ```bash
   bash kitty-specs/charter-list-org-required-research-01M5WZQH/research/repro.sh /tmp/repro fixed
   ```

2. In `/tmp/repro`, run `spec-kitty charter list`. The directive row reads
   `(All built-ins — no explicit activation)` followed by `team-rule (required by 'team-pack')`.
3. `spec-kitty charter list --json` shows `"schema_version": "2"`, and the directive row
   `"activated": ["team-rule"], "allow_list_present": false`.
4. Validate: `uv run --frozen pytest tests/specify_cli/cli/commands/charter/test_charter_list_commands.py -q`.
