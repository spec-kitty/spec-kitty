# Data Model: In-Harness Feedback Survey

**Mission**: `in-harness-feedback-survey-01M3PK9W` | **Bounded context**: `specify_cli.feedback`

All types are immutable value objects unless noted. There is no database; the only persisted state is `SurveyPreferences`.

## Value objects

### SurveyTrigger (enum)

| Value | Raised when | Counts toward weekly throttle? |
|---|---|---|
| `planning_complete` | `finalize-tasks` succeeded | yes |
| `mission_end` | `consolidate` succeeded | yes |
| `op_close` | `profile-invocation complete` with outcome `done` or `failed` | yes |
| `on_demand` | user ran `spec-kitty feedback` | no (ignores throttle and "don't ask again") |

### Rating

An integer from 1 to 5 inclusive. Any other value is rejected at input and re-asked; it can never be constructed.

### SurveyAnswers

| Field | Type | Rule |
|---|---|---|
| `rating` | Rating | required to submit |
| `comment` | str \| None | optional; stripped; longer than 2,000 characters is truncated to 2,000 and the user is told before consent |
| `email` | str \| None | optional; blank means `None`; must match a basic `local@domain.tld` shape or be re-asked or left blank |

### Harness (enum)

`cli`, one value per supported agent key (from `specify_cli.agent_utils.directories`), or `other`. Never free text.

### ContextFields

| Field | Source | Example |
|---|---|---|
| `spec_kitty_version` | installed CLI version | `3.2.7` |
| `distribution` | `DistributionProfile.package_name` | `spec-kitty-cli` |
| `trigger` | SurveyTrigger | `mission_end` |
| `harness` | Harness | `cursor` |
| `os` | `sys.platform` family: `linux` / `darwin` / `windows` / `other` | `darwin` |
| `mission_type` | mission's `mission_type` if the trigger is mission-scoped, else `null` | `software-dev` |

### FeedbackSubmission (wire payload)

`submission_format_version` (int, starts at 1) + SurveyAnswers + ContextFields. **Closed allowlist**: the builder emits exactly these keys and nothing else. Explicitly never included: repository name or path, mission slug or id, branch, username, hostname, git identity, IP-derived data, or any authentication token. See [contracts/feedback-submission.schema.json](./contracts/feedback-submission.schema.json).

### FeedbackEndpoint

The resolved absolute URL, or `None` (dormant). Precedence: `SPEC_KITTY_FEEDBACK_URL` env var > `SurveyPreferences.endpoint_override` > `DistributionProfile.feedback_endpoint` > `None`. It is valid only if the scheme is `https`, or the scheme is `http` with a loopback host; otherwise it resolves to `None`.

### OfferDecision

The output of the pure `decide_offer(...)` function.

| Field | Meaning |
|---|---|
| `action` | `prompt` or `none` |
| `reason` | `eligible`, `no_endpoint`, `prompts_off`, `throttled`, `non_interactive`, `ci`, `preferences_unreadable`, `clock_skew`, `lock_busy`, `trigger_not_eligible` |
| `trigger` | the SurveyTrigger evaluated |

## Persisted entity

### SurveyPreferences (`feedback.json`, per user, per machine)

| Field | Type | Default | Notes |
|---|---|---|---|
| `schema_version` | int | 1 | unknown higher versions are treated as unreadable (no automatic offer) |
| `automatic_prompts` | bool | true | false after "don't ask again" or `--prompts off` |
| `last_shown_at` | ISO-8601 UTC \| null | null | written at offer time (R-07) |
| `endpoint_override` | str \| null | null | validated at resolution time, not at write time |

**Location**: `platformdirs.user_config_dir("spec-kitty")/feedback.json`. File mode 0600, parent directory 0700, symlinks refused, owner must be the current user on POSIX, maximum 64 KiB. Never inside a project repository.

## Invariants

1. **Consent gate**: a FeedbackSubmission is constructed only from a code path that has received an explicit affirmative consent value. `--agent-submit` without `--consent yes` is a usage error and sends nothing.
2. **Allowlist**: `payload.keys() == ALLOWED_KEYS` for every submission, with `email` present only when provided.
3. **Weekly throttle**: for automatic triggers, an offer happens only if `automatic_prompts` is true and (`last_shown_at` is null or `now − last_shown_at ≥ 7 days`). `last_shown_at` in the future means no offer.
4. **Atomic check-and-mark**: the eligibility read and the `last_shown_at` write happen inside one non-blocking `machine_file_lock` critical section; failing to get the lock means no offer.
5. **Fail toward silence**: any preferences read failure means `automatic_prompts` is effectively false for automatic triggers. The on-demand command is unaffected but reports the problem in `--status`.
6. **Outcome first**: a trigger hook runs only after the trigger command's own result has been durably recorded, and exceptions inside the hook are contained and discarded.

## State transitions (automatic prompts)

```
          "don't ask again" / --prompts off
   ON  ─────────────────────────────────────▶  OFF
   ▲                                            │
   └──────────────── --prompts on ──────────────┘
```

The per-offer lifecycle is: `eligible → shown (last_shown_at written) → {skipped | abandoned | declined | submitted}`. None of the terminal states changes the trigger command's outcome.
