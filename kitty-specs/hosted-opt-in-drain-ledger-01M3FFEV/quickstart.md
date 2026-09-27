# Quickstart: hosted posture

Default (frozen server): do nothing. No drain, no endpoint, and the local projection is refreshed.

Opt in to live drain (both required):
```bash
spec-kitty moments drain on --repo     # writes hosted.drain: true to .kittify/config.yaml (commit it)
spec-kitty moments drain on            # writes [hosted] drain = true to your runtime-root config.toml
export SPEC_KITTY_SAAS_URL=https://team.spec-kitty.ai   # or [sync].server_url in the same config.toml
spec-kitty auth login
spec-kitty moments drain status        # effective state + which file decided each scope
```

Turn off the automatic local projection:
```yaml
# .kittify/config.yaml
ledger:
  projection: false
```
`spec-kitty materialize` still rebuilds it on demand.
