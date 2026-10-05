---
description: Send feedback about Spec Kitty on demand
---
## User Input

```text
$ARGUMENTS
```

You **MUST** consider the user input before proceeding (if not empty).

**This command works without a mission. If you run any other spec-kitty command in a repo with multiple missions, always pass `--mission <handle>`.**

## Goal

Let the human send a short feedback note about Spec Kitty right now. This is an on-demand request: it is not limited by the weekly offer and it does not use up or change that offer.

Never answer any question on the human's behalf and never pre-fill answers.

## Step 1: Check availability

Replace `<your-agent-key>` with your harness key (for example `claude`, `codex`, `cursor`, `gemini`, `opencode`):

```bash
spec-kitty feedback --agent-check --trigger on_demand --agent <your-agent-key> --json
```

If JSON `action` is `none`, tell the human in plain words why feedback cannot be sent right now (use the `reason` value: for example no feedback endpoint is configured, a CI environment was detected, or no human is available to answer). Send nothing and stop here.

If `action` is `prompt`, continue with Step 2.

## Step 2: Ask the questions

Ask each question with your host-native question UI, one at a time, using the exact wording from the JSON `survey` object. There is no plain-text terminal fallback: if your harness has no question UI, tell the human that this command needs one and stop without sending anything.

1. Rating, from 1 to 5: use `survey.rating_question`.
2. Comment, optional: use `survey.comment_question` exactly as given, because it states the length limit. Never write a limit from memory.
3. Email, optional: use `survey.email_question`.
4. Consent: ask the question with the text "Send feedback" and let the human confirm or decline. If the human declines, tell them nothing was sent and stop.

## Step 3: Submit

Pass `<text>` and `<address>` as single-quoted shell arguments, writing each `'` inside them as `'\''`, and collapse newlines to spaces. Never put the human's words in double quotes (`$(...)` and backticks would run). Leave out `--comment` or `--email` when the human skipped them.

```bash
spec-kitty feedback --agent-submit --trigger on_demand --agent <your-agent-key> --rating <1-5> [--comment '<text>'] [--email '<address>'] --consent yes --json
```

## Step 4: Handle the result

Read JSON `status`:

- `handed_off`: thank the human and show the returned `message`. If `errors` contains `comment_truncated`, tell the human their comment was shortened to the limit.
- `invalid_input`: `errors` lists the failing fields. For `rating_out_of_range`, tell the human the rating must be 1 to 5 and re-ask only the rating. For `email_malformed`, tell the human the address looks invalid and re-ask only the email (they may leave it empty). Do not re-ask answered questions, and never submit again until the failing fields are valid.
- `no_endpoint`: tell the human there is nowhere to send feedback in this installation and that nothing was sent.
- `not_sent`: tell the human nothing was sent.

Never report delivery problems beyond these results; sending is fire-and-forget.

## Rules

- Run the check first; never ask a question before `action` is `prompt`.
- Ask one question at a time and wait for the answer.
- Use the question wording from the check response, never wording from memory.
- Never invent, guess, or fill in an answer for the human.
- Only submit after the human gave consent; use `--consent yes` only then.
- Never repeat the human's answers back in logs, files, or issue text.
- Never edit repository files in this command.
