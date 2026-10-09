---
title: Migrating from 2.x / Early 3.x Charter Projects
description: What changed when upgrading from Spec Kitty 2.x or early 3.x to current Charter-era 3.x, migration steps, and known failure modes.
doc_status: active
updated: '2026-10-08'
related:
- docs/context/index.md
- docs/changelog/2x/index.md
---
> Migration note: This page documents a migration path or historical transition. It is not the current 3.2 happy path.

# Migrating from 2.x / Early 3.x Charter Projects

This guide covers what changed when upgrading a project from Spec Kitty 2.x (or early 3.x before
the Charter era) to the current Charter-era 3.x.

---

## What changed

| Area | 2.x behavior | 3.x Charter behavior |
|---|---|---|
| Governance file location | `.kittify/charter/charter.md` — same location, but no DRG-backed synthesis | `.kittify/charter/charter.md` — same file, now drives the full synthesis pipeline |
| Governance artifacts | Repository-native doctrine artifacts in `src/doctrine/` (directives, tactics, styleguides) | Project layer in `.kittify/charter-packs/` promoted by `charter synthesize`; the built-in Charter Pack in `packs/built-in/` is the fallback |
| Synthesis command | `charter sync` (sync only — charter.md to YAML config) | `charter synthesize` (full DRG-backed doctrine promotion) + `charter bundle validate` |
| Partial synthesis | Not available | `charter resynthesize --topic <selector>` |
| Bundle validation | Not available | `charter bundle validate` |
| Graph-native decay | Not available | `charter lint` |
| Synthesis status | `charter status` (sync status only) | `charter status` (sync status + synthesis/operator state + optional provenance) |
| CLI structure | `spec-kitty charter <subcommand>` | Same — `spec-kitty charter <subcommand>` |
| Mission execution | Direct workflow commands: `/spec-kitty.specify`, `/spec-kitty.plan`, etc. | `spec-kitty next --agent <name> --mission <slug>` with automatic Charter context injection |
| Retrospective | Not available in 2.x | Default-on in 3.2.0+: `retrospective.yaml` is authored automatically at mission completion. `spec-kitty retrospect create --mission <slug>` authors on demand; `retrospect summary` aggregates (read-only); `agent retrospect synthesize --mission <slug>` previews/applies proposals. See [How to Use Retrospective Learning](../guides/how-to/governance/use-retrospective-learning.md). |
| Profile invocation | Not available in 2.x | `spec-kitty dispatch "<request>"` + `profile-invocation complete` |
| Governance context injection | `charter context --action <action>` (available; used by runtime) | Same command available for debugging; automatic injection via `spec-kitty next` |

**Note on `constitution`**: In early 3.x, the governance command was `spec-kitty constitution`.
As of 3.1.0 (mission 063), `spec-kitty constitution` has been removed. All references must
be updated to `spec-kitty charter`.

**Note on public constitutions**: Some projects have both a public file such as
`spec/constitution.md` and the Spec Kitty runtime file `.kittify/charter/charter.md`. In current
3.x, `.kittify/charter/charter.md` is the runtime doctrine source consumed by `charter sync`,
`charter context`, and governed mission prompts. The public constitution can remain the long-form
human-facing governance document, but it is not automatically synced into the runtime charter.

---

## Migration steps

Follow these steps after upgrading the Spec Kitty CLI to the current Charter-era version:

### Step 1: Update CLI invocations

If any scripts or CI pipelines reference `spec-kitty constitution`, replace every occurrence
with `spec-kitty charter`:

```bash
# Old (no longer works)
spec-kitty constitution interview
spec-kitty constitution generate

# New
uv run spec-kitty charter interview
uv run spec-kitty charter generate
```

### Step 2: Re-run the interview if charter.md format changed

If the charter format changed between your old CLI version and the current one:

```bash
uv run spec-kitty charter interview --profile minimal --defaults
uv run spec-kitty charter generate --from-interview --force
```

### Step 3: Run the full synthesis flow

Run synthesis to populate `.kittify/charter-packs/` for the first time:

```bash
# Check current status
uv run spec-kitty charter status

# Lint for decay
uv run spec-kitty charter lint

# Synthesize (dry-run first)
uv run spec-kitty charter synthesize --dry-run
uv run spec-kitty charter synthesize

# Validate the bundle
uv run spec-kitty charter bundle validate

# Confirm
uv run spec-kitty charter status
```

### Step 4: Verify no drift

After synthesis, confirm `charter status` reports no drift between `charter.md` and the bundle.
If drift is reported, re-run `charter sync` followed by `charter synthesize`.

### Step 4a: Resolve duplicate constitutions

If an upgraded project now has both a public constitution and `.kittify/charter/charter.md`,
choose an explicit ownership model:

| Model | Use when | Migration step |
|---|---|---|
| Runtime summary with external authority | The public constitution is long-form or public-facing, and agents only need concise binding directives. | Keep `spec/constitution.md`; edit `.kittify/charter/charter.md` to summarize operative rules and reference the public document. Add the containing directory, such as `spec/`, to `authority_paths` if agents should inspect it. |
| Committed mirror | The project deliberately wants the public constitution and runtime charter to match. | Keep an explicit copy/sync process outside `charter sync`, then run `spec-kitty charter sync` after the mirror has been refreshed. |
| Symlink | The project can rely on symlink support in every checkout and wants sync-only extraction from one physical markdown file. Avoid this for Windows or mixed-platform projects unless native Windows CI proves symlink support. | Point `.kittify/charter/charter.md` at the chosen source file. `charter sync` follows the symlink for reads and writes generated YAML into `.kittify/charter/`; `charter generate` refuses to overwrite a symlinked charter before compilation or generated-file writes. |

Do not leave this implicit. Equality checks between `spec/constitution.md` and
`.kittify/charter/charter.md` should exist only for projects that intentionally picked the
committed-mirror model.

### Step 5: Update mission execution patterns

If your scripts run missions using direct command invocations (e.g., calling specific slash
commands in a loop), update them to use `spec-kitty next`:

```bash
# Old pattern (2.x direct invocations)
# /spec-kitty.specify, /spec-kitty.plan, /spec-kitty.implement ...

# New pattern (Charter era)
uv run spec-kitty next --agent claude --mission my-feature-slug --json
uv run spec-kitty next --agent claude --mission my-feature-slug --result success --json
```

---

## Known migration failures and fixes

### 1. "TaskCliError: charter.md must exist"

`charter synthesize` requires `charter.md` to exist. If your project predates the charter
generation step, create it:

```bash
uv run spec-kitty charter interview --profile minimal --defaults
uv run spec-kitty charter generate --from-interview
```

### 2. "No such command: constitution"

You are calling `spec-kitty constitution` which was removed in 3.1.0. Replace all occurrences
with `spec-kitty charter`.

### 3. Bundle validate fails after upgrading

If `charter bundle validate` reports schema errors after upgrading, the bundle was generated by
an older CLI version and may not conform to CharterBundleManifest v1.0.0. Force regenerate:

```bash
uv run spec-kitty charter generate --from-interview --force
uv run spec-kitty charter synthesize
uv run spec-kitty charter bundle validate
```

### 4. Doctrine files missing after migration

On first migration, `.kittify/charter-packs/` may be empty because `charter synthesize` was never run.
Run it once to populate:

```bash
uv run spec-kitty charter synthesize
```

If `.kittify/charter/generated/` is also empty (no agent-generated artifacts), synthesize will
create only the minimal artifact set. The runtime falls back to the built-in Charter Pack until you run
a full synthesis with agent-generated content.

### 5. compact-context warnings in agent prompts

After migrating, agents may receive compact-context mode warnings if your governance layer is
large. This is expected — see [Troubleshooting Charter Failures](../guides/how-to/governance/troubleshoot-charter.md)
for workarounds.

### 6. Duplicate public constitution and runtime charter drift

If governance checks fail because `spec/constitution.md` differs from
`.kittify/charter/charter.md`, first decide whether the project wants a mirror. Current Spec Kitty
does not require duplication. The recommended current model is a concise runtime charter that
references the public constitution and extracts cleanly with `spec-kitty charter sync`.

---

## Getting help

If you encounter issues not covered here, see
[Troubleshooting Charter Failures](../guides/how-to/governance/troubleshoot-charter.md).

---

## See Also

- [How to Set Up Project Governance](../guides/how-to/governance/setup-governance.md)
- [How to Synthesize and Maintain Doctrine](../guides/how-to/governance/synthesize-doctrine.md)
- [Troubleshooting Charter Failures](../guides/how-to/governance/troubleshoot-charter.md)
- [Spec Kitty 3.x — Charter Era](../context/index.md)
- [Spec Kitty 2.x Docs (archived)](../changelog/2x/index.md)
