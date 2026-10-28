# Quickstart: verify typed diagnostics

```bash
spec-kitty init --ai claude --non-interactive /tmp/sk-demo && cd /tmp/sk-demo
spec-kitty charter context --action implement --json | jq '.context_schema_version, .diagnostics'
# expect "1.4.0" and objects like {"code": "CATALOG_DEFAULT_APPLIED", "message": "..."}
spec-kitty charter interview --profile minimal --defaults --json | jq '.narrowed'
```
