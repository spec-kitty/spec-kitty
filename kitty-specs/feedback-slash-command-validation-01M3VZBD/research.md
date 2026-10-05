# Research: Feedback slash command and input hardening

## R1 — Throttle bypass for an explicit request

- **Decision**: Use the existing `SurveyTrigger.ON_DEMAND` (`on_demand`) with `--agent-check`/`--agent-submit`. No new flag or modifier.
- **Rationale**: `models.py` already defines `on_demand` and marks which triggers are throttled. An explicit request is simply an unthrottled trigger. This keeps the command surface lean (C-005).
- **Alternatives considered**: A new on-demand modifier on `--agent-check` (extra surface for no gain); skipping the check and hardcoding wording in the prompt (wording could drift from `wording.py`).
- **Verification item for implementation**: confirm `--trigger on_demand` is accepted by the hidden CLI and that `claim_offer` does not claim the weekly offer for it.

## R2 — Where the 2000-character limit is shown

- **Decision**: Put it in the comment question text in `wording.py`, built from `COMMENT_MAX_LENGTH`. The agent reads it from the check response; the terminal form and inline hooks import the same string.
- **Rationale**: One source, shown before input everywhere. The limit is per comment, unrelated to the weekly throttle.
- **Alternatives considered**: Hardcoding the number in the pack prompt (drift risk).

## R3 — Comment sanitization

- **Decision**: Normalize to NFC, remove Unicode categories Cc (except newline and tab, which are converted to normal whitespace handling), Cf and ANSI/OSC escape sequences, collapse trailing whitespace, then strip and cap at 2000 characters without splitting a character. Markup is untouched.
- **Rationale**: The data is JSON and never rendered by Spec Kitty, so escaping markup would corrupt valid text without adding safety.
- **Alternatives considered**: Escaping or stripping markup (alters legitimate text); rejecting dirty input (blocks users over a stray paste).

## R4 — Email validation

- **Decision**: One address only: a local part and a dotted domain, no whitespace or control characters, no second `@`, no comma or semicolon lists, at most 254 characters. Invalid values return the existing `email_malformed` code; nothing is auto-corrected.
- **Rationale**: Replaces the loose shape regex and keeps the shipped contract code stable.
- **Alternatives considered**: A full RFC 5322 parser (large, still accepts surprising forms); a new error code (changes a published schema).

## R5 — Rating

- **Decision**: Keep strict integer-only behavior (booleans, floats, `" 5 "` and words rejected). Add table tests for it; behavior is mostly already correct.

## R6 — Command registration

- **Decision**: Register `feedback` as a prompt-driven consumer skill, authored once in the pack source, generated for all agents. The exact pack path and generation touchpoints are confirmed during implementation from `shims/registry.py`, `skills/command_installer.py` and `runtime/agent_commands.py`.
- **Rationale**: The workflow is a multi-question interactive exchange, so it needs a full prompt, not a thin shim.
