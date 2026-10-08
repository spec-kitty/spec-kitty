---
name: spk-charter-profile-load
description: >-
  Load a Spec Kitty agent profile on demand for interactive sessions,
  including identity, governance scope, boundaries, and initialization.
  Triggers: "act as the architect", "load the reviewer profile",
  "switch to researcher", "use the planner role", "adopt a profile".
argument-hint: "<profile-id>"
---

# spk-charter-profile-load

Use this skill when the agent needs a profile outside the runtime loop or the
user asks to adopt a specific role.

## Resolver-Backed Flow

1. Identify the requested profile, action, and active Mission context.
2. Resolve the profile through the CLI:

   ```bash
   spec-kitty agent profile show <profile-id>
   ```

3. Load action-scoped governance:

   ```bash
   spec-kitty charter context --action <action> --json
   ```

4. Apply the resolved initialization declaration, specialization boundaries,
   directive and tactic references, collaboration handoffs, and mode defaults.
5. Return to `spk-run-next` for Mission advancement.

Do not substitute a raw `.agent.yaml` read for resolution. A narrowly scoped
read-only-harness fallback is documented in the reference below.

For a one-shot governed request outside a Mission, use:

```bash
spec-kitty dispatch "<request>" --profile <profile-id>
```

## References

- `references/profile-load-mechanics.md` -- Full resolver flow, application
  checklist, standalone dispatch, and the bounded read-only fallback.
