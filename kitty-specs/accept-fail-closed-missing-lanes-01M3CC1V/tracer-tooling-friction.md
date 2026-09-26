# Tracer: Tooling Friction

Mission: `accept-fail-closed-missing-lanes-01M3CC1V` — fix P0 #4891.

Append friction encountered during the mission; assessed at close.

## Observations

- **F-1 (mission create).** `spec-kitty agent mission create --pr-bound --json` fails with
  `BRANCH_STRATEGY_CONFIRMATION_REQUIRED` unless `--branch-strategy already-confirmed` is passed;
  the flag is present but truncated out of the first page of `--help`. Minor: the remediation
  message was clear and self-correcting.
- (append during implement/review)
