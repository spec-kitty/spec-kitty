# Quickstart — verifying "rework is not an override"

Run the unforced two-cycle loop on a mission. The implementer (`claude:…`) and the reviewer (`codex:…`) must use different tools.

```bash
spec-kitty agent tasks move-task WP01 --to in_review --agent codex:gpt-5:reviewer-renata:reviewer --mission <m>
spec-kitty agent tasks move-task WP01 --to planned --review-feedback-file fb.md --agent codex:gpt-5:reviewer-renata:reviewer --mission <m>
spec-kitty agent tasks move-task WP01 --to in_progress --agent claude:opus:implementer-ivan:implementer --mission <m>
spec-kitty agent tasks move-task WP01 --to for_review --agent claude:opus:implementer-ivan:implementer --mission <m>
spec-kitty agent tasks move-task WP01 --to approved --agent codex:gpt-5:reviewer-renata:reviewer --mission <m>
spec-kitty agent tasks status --mission <m>   # no "Arbiter Override History"
```

None of these moves needs `--force`. A genuine override is still recorded: forcing a rejected WP from `planned` straight to `approved` with `--note` prints "Arbiter override recorded".

Targeted tests (no heavy suites):

```bash
.venv/bin/python -m pytest tests/specify_cli/cli/commands/agent/test_rework_is_not_an_override.py tests/specify_cli/status/test_review_roles.py tests/specify_cli/review/test_arbiter.py tests/review/test_arbiter.py -q
```
