# Quickstart — accept-path-conventions-name-overrides-01M66F7N

## For an operator blocked on path conventions (the #6633 scenario)

Your repository puts source somewhere other than `src/`, tests somewhere other than `tests/`, or has no `docs/` at all. When `spec-kitty accept --mission <m> --diagnose` (or strict validation) blocks with "Path Convention Errors", the failure text now names the two honest project-level levers instead of only `--lenient` and `mkdir -p`:

1. **Remap to the real layout** — declare it once in `.kittify/config.yaml`:

   ```yaml
   project:
     path_conventions:
       workspace: internal/   # where your source actually lives
       tests: internal/       # where your tests actually live
   ```

   The keys in the printed example are exactly the ones missing in your run (artifact-routed keys like `deliverables` are never suggested — they are governed by the `contracts: none` waiver instead).

2. **Drop a key the project has no directory for** — copy the packaged `mission.yaml` to `.kittify/overrides/missions/<mission-type>/mission.yaml` (e.g. `software-dev`) and remove that key's line.

`accept --lenient` still exists but also skips the per-WP `agent`/`assignee`/`shell_pid` metadata checks, so prefer the routes above.

## Verify the change locally

```bash
uv run pytest tests/agent/test_validators_unit.py -k "path_conventions or format_errors or lenient" -q
```
