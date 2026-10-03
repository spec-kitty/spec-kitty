# Contract: on-demand agent handshake

Uses the existing hidden CLI surface and the existing schemas `agent-check` and `agent-submit` from the in-harness feedback survey mission. No new flags.

## Check

```
spec-kitty feedback --agent-check --trigger on_demand --agent <harness> --json
```

- `trigger: on_demand` is not subject to the weekly throttle or "don't ask again".
- Prompt case: `action: prompt`, with `survey` wording that includes the comment question stating the 2000-character limit.
- Unavailable case: `action: none` with a `reason` such as `no_endpoint`, `ci` or `non_interactive`. The agent tells the user and sends nothing.

## Submit

```
spec-kitty feedback --agent-submit --trigger on_demand --agent <harness> \
  --rating <1-5> [--comment "<text>"] [--email "<address>"] --consent yes
```

Responses (unchanged shape):

| status | meaning | agent action |
|--------|---------|--------------|
| `handed_off` | accepted | thank the user (a `comment_truncated` entry in `errors` means tell the user it was shortened) |
| `invalid_input` | `errors` lists `rating_out_of_range` and/or `email_malformed` | re-ask only the failing question(s) |
| `no_endpoint` | nowhere to send | tell the user |
| `not_sent` | no consent or failure | tell the user nothing was sent |

Answer text never appears in responses.
