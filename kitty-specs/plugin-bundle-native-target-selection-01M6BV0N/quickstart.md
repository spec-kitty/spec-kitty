# Quickstart — verify #6273 locally

## Reproduction (must be red before the fix, green after)

```bash
D=$(mktemp -d) && cd "$D" && git init -q
spec-kitty init --ai claude,codex,copilot --non-interactive < /dev/null
spec-kitty doctor tool-surfaces --fix < /dev/null; echo "exit=$?"
spec-kitty doctor tool-surfaces --json < /dev/null | jq -c '{ok, summary}'
ls dist/spec-kitty-plugins
```

Before: exit 0, no `dist/`, `missing: 3`. After: exit 0, three staged bundles, `missing: 0`,
`ok: true`, and a second `--fix` is a no-op.

## Focused tests

```bash
uv run pytest tests/specify_cli/tool_surface/bundles tests/specify_cli/tool_surface/providers/test_plugin_bundle.py \
  tests/specify_cli/tool_surface/integration/test_doctor_tool_surfaces_cli.py -q
```

## Force a repair failure

Point `dist/spec-kitty-plugins` at a member that cannot match the prepared batch (e.g. delete the
staged `.claude-plugin/plugin.json` and make `dist` a read-only path, or use the unit fixture that
mutates a prepared member) and run `doctor tool-surfaces --fix`. Expected: exit 1, a
`Failed to repair:` line naming each surface id, and the provider reason printed below it; JSON
carries `repair.failed` and `repair.findings_after`.
