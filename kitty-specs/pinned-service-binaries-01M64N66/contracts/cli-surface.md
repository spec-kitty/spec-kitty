# Contract: operator surfaces

| Surface | Behaviour | Exit codes |
|---|---|---|
| `spec-kitty service fetch [--service <s>\|--all] [--offline] [--json]` | fetches and verifies the host target's assets (and the jar when no native target exists) into the cache | 0 ok; 1 refusal (code in output) |
| `spec-kitty service vendor --service <s> --tag <t> [--repository <url>] [--check]` | bumps the lockfile from a release; `--check` verifies the lockfile offline against the shape rules and, online, against the release's SHA256SUMS | 0 ok; 1 refusal; 2 usage |
| `spec-kitty service status [--service <s>] [--json]` | shows the pin, the cache state and the running instance (healthy or stale or absent); starts nothing | 0 |
| `spec-kitty service stop [--service <s>]` | stops this clone's instance per the launch contract | 0 stopped or none running; 1 refusal |
| `scripts/sync_services.py --service all\|<s> [--offline] [--check]` | dev/CI fetch-and-verify; `--check` verifies without fetching | 0 ok; 1 refusal |
| `make sync-services` | `uv run --frozen python scripts/sync_services.py --service all` | as the script |
| `.github/actions/sync-services` | restores the cache keyed on `hashFiles('pins/*.source.yaml')`, then runs the script | fails the job on refusal |

Environment variables:
- `SPEC_KITTY_<SERVICE>_BINARY`: an explicit path (`WRITE_SERVICE`, `CHARTER_SERVICE`), still digest-checked.
- `SPEC_KITTY_SERVICE_UNPINNED=1`: honoured only together with an explicit path; warns on every start.
- `SPEC_KITTY_SERVICE_ASSET_DIR`: an offline asset directory; its files are digest-checked.
- `SPEC_KITTY_SERVICE_START_TIMEOUT`: seconds; default 15.

When no lockfile exists for a service, every resolve refuses with `SERVICE_PIN_INVALID`. The remedy says the service is not yet pinned in this core version.
