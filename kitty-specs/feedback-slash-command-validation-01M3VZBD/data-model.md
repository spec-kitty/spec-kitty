# Data Model: Feedback slash command and input hardening

No new persisted data. The existing submission shape and `ALLOWED_KEYS` are unchanged.

## Feedback answers (existing `SurveyAnswers`)

| Field | Rule |
|-------|------|
| rating | Required. Integer 1 to 5 only. Booleans, floats, words, whitespace-padded values and empty are rejected. |
| comment | Optional. Cleaned (NFC; control, format and escape sequences removed). Markup kept. Empty after cleaning means absent. Capped at 2000 characters, truncation flagged. |
| email | Optional. If present, exactly one well-formed address, at most 254 characters. Never altered. |

## Validation outcome (returned by `agent_submit`)

| Condition | Result |
|-----------|--------|
| Rating invalid | `status: invalid_input`, `errors` contains `rating_out_of_range` |
| Email invalid | `status: invalid_input`, `errors` contains `email_malformed` |
| Both invalid | both codes in one response |
| Comment truncated | submission proceeds, `errors` contains `comment_truncated` |
| Any invalid field | nothing is sent |

## Invariants

- One validator serves the command, terminal form, inline hooks and `agent_submit`.
- The comment limit text is derived from `COMMENT_MAX_LENGTH`.
- A validation failure never produces a network request.
