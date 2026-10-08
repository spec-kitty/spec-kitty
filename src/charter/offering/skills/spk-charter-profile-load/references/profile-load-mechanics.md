# Resolver-Backed Profile Load Mechanics

This reference is the detailed authority for loading a Spec Kitty agent
profile. Profile identity is resolved data, not the contents of one YAML file:
project and organization overlays, `specializes_from` lineage, and
`enhances`/`overrides` semantics can all change the effective profile.

## 1. Resolve The Profile

Inspect the requested profile through the repository resolver:

```bash
spec-kitty agent profile show <profile-id>
```

Use `--all` only when an explicitly requested abstract or non-activated parent
profile must be inspected. Use `--json` when another tool needs structured
output.

When the user has described a role but not selected an ID, discover the
available resolved profiles first:

```bash
spec-kitty agent profile list --json
```

Do not infer a file path from an ID. The resolver owns built-in, organization,
and project precedence and reports lineage diagnostics.

## 2. Load Action-Scoped Governance

After resolving the profile, load the charter context for the work being
performed:

```bash
spec-kitty charter context --action <action> --json
```

Use the actual lifecycle action, such as `specify`, `plan`, `implement`,
`review`, or `merge`. Do not load the whole doctrine catalog when an
action-scoped context is available.

## 3. Apply The Resolved Definition

Before work starts, apply and state the relevant parts of the resolved result:

1. the initialization declaration;
2. the specialization's primary focus and avoidance boundary;
3. directive and tactic references relevant to the action;
4. collaboration handoffs and working relationships;
5. mode defaults that match the requested work.

Naming a persona without applying these fields is not a profile load.

Maintain the boundaries through the session. When requested work falls beyond
the avoidance boundary, hand it to an allowed collaborator rather than silently
expanding the role.

## 4. Read-Only Harness Fallback

Only a read-only harness that cannot invoke the CLI may inspect the shipped
built-in file at
`packs/built-in/agent_profiles/<profile-id>.agent.yaml`.
This is knowingly degraded, read-only fallback behavior. It can diverge from
the resolved profile because organization/project overlays,
`specializes_from` lineage, and `enhances`/`overrides` semantics are not
applied. The delegate must state that limitation in its result. Do not use this
fallback when either resolver-backed command can run, and do not use it to
author or mutate a profile.

## 5. Standalone Governed Invocation

For a one-shot profile-governed request outside a Mission, prefer canonical
dispatch:

```bash
spec-kitty dispatch "<request>" --profile <profile-id>
```

Mission runtime work returns to `spk-run-next`; it must not create a parallel
ad hoc lifecycle.
