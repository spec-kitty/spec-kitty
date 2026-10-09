## DIRECTIVE_terminus_retrospective_always_on

The runtime terminus retrospective lifecycle MUST be always-on by
default. Opt-out is permitted only via an explicit charter clause
(e.g., `retrospective: disabled` or equivalent doctrine-defined
marker), not via an environment variable or implicit project default.

### Background

The current default is opt-in via `SPEC_KITTY_ENABLE_SAAS_SYNC` env
var / charter `mode:` clause. Most missions therefore reach
`mark-done` without authoring a `retrospective.yaml`; the
cross-mission learning loop has no input on those missions; and
`spec-kitty retrospect summary` underreports.

### Mitigations built into the directive

To soften the blast radius of inverting the default:

1. **Charter opt-out clause is well-documented**. The charter
   template scaffolded by `spec-kitty charter init` ships the
   opt-out clause commented-out with explanation of when to use it.
2. **Autonomous mode produces minimal records**. When
   `mode: autonomous` is resolved (no HiC present), the runtime
   writes a record with empty `helped/not_helpful/gaps` and
   `mode.source_signal.evidence = "autonomous; no facilitator invoked"`.
   This satisfies the always-on rule without forcing HiC-quality
   content.
3. **`spec-kitty retrospect summary` flags autonomous-empty
   records** as a separate category so the dashboard distinguishes
   "no learning captured" from "learning captured but no findings".
4. **Migration deprecation flag**: a CLI flag
   `--allow-no-retrospective` is available for the first N
   releases with a deprecation warning that points at the charter
   opt-out as the long-term path.

### Reference cases

- spec-kitty PR #1160 — completed without an authored retrospective
  at terminus. Retrospective was authored post-hoc via direct
  `RetrospectiveRecord` + `write_record` calls in a one-shot
  script, then promoted to a public gist
  (https://gist.github.com/robertDouglass/fc4d0511335f8e6150bcdccce2d43417).
- Filed as spec-kitty#1164 (engineering implementation tracker).
