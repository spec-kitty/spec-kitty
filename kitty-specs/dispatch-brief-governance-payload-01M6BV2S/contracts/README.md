# Contracts — none changed

This mission adds no versioned contract file. The `--brief` envelope is an
additive, opt-in extension of the existing dispatch payload (`cli-do-output.md`,
owned by mission `do-dispatch-open-op-lifecycle-01KTSJ2H`), and `charter context
--profile` is an added option on an existing command. Both surfaces are pinned
by tests and documented in:

- `docs/api/cli-commands.md` (regenerated `dispatch` and `charter context` help)
- `docs/architecture/governed-profile-invocation.md` ("Re-dispatching without
  re-embedding the payload")
- `src/charter/offering/skills/spec-kitty/SKILL.md`

The plan's "Contracts" section records the same decision; the directory exists
so the acceptance path-convention check passes for this software-dev mission.
