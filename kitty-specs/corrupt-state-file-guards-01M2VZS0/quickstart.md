# Quickstart: reproduce & verify #4642

## Reproduce (RED, before fix)
```bash
# Instance 1 — next on corrupt meta.json
printf '{ this is not valid json\n' > kitty-specs/<slug>/meta.json
spec-kitty next --mission <slug>            # today: uncaught MissionMetaReadError traceback

# Instance 2 — decision cmds on corrupt index.json
printf '{bad json\n' > kitty-specs/<slug>/decisions/index.json
spec-kitty agent decision verify --mission <slug>   # today: raw JSONDecodeError
printf 'ok\xd0\xff'  > kitty-specs/<slug>/decisions/index.json
spec-kitty agent decision verify --mission <slug>   # today: raw UnicodeDecodeError
```

## Verify (GREEN, after fix) — for each corruption class × entry point
- exit code == 1
- no `Traceback (most recent call last)` in output
- message names the corrupt file + `run: spec-kitty doctor`
- with `--json`: error payload parses as JSON

## Run the tests
```bash
PWHEADLESS=1 .venv/bin/python -m pytest tests/specify_cli/next/ tests/specify_cli/cli/commands/test_decision.py tests/specify_cli/decisions/test_store.py -q
```
