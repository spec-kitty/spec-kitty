# Quickstart

From the repository root (the installed `spec-kitty` may be stale; use the editable checkout):

```bash
# On-demand check (bypasses the weekly throttle); needs a feedback endpoint, e.g. a loopback test server
SPEC_KITTY_FEEDBACK_URL=http://127.0.0.1:8099/feedback \
  uv run --frozen spec-kitty feedback --agent-check --trigger on_demand --agent cursor --json

# Invalid rating is refused, nothing is sent
uv run --frozen spec-kitty feedback --agent-submit --trigger on_demand --agent cursor \
  --rating 6 --consent yes --json

# Targeted tests
uv run --frozen pytest tests/specify_cli/feedback -q
```

In a supported harness, type `/spec-kitty.feedback` after installing the generated command with `spec-kitty upgrade`.
