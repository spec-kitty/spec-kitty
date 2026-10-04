---
title: Create and activate a pack skill
description: Author a pack skill, set its namespace, activate it into each configured tool's project skill root, and keep it healthy with doctor skills and upgrade.
doc_status: active
updated: '2026-10-04'
audience: docs/context/audience/internal/lead-developer.md
type: how-to
related:
- docs/development/how-to/create-a-doctrine-artifact.md
- docs/architecture/doctrine-kinds.md
- docs/context/execution.md
- docs/adr/3.x/2026-09-27-1-pack-skills-share-commands-through-charter-packs.md
---
# Create and activate a pack skill

A **pack skill** is a short entry point your team shares through a pack, such as "draft release
notes". Before: each person kept a private copy in their own tool. After: one reviewed
`<id>.skill.yaml` file, and every configured tool in the project gets the same skill.

A pack skill is one of three things the codebase calls a "skill". The
[Pack skill glossary entry](../../context/execution.md#pack-skill) separates it from the doctrine
skills that ship with Spec Kitty and from the generated `spec-kitty.<command>` command skills.

This page covers a **project-tier** pack skill: it lives in your repository and needs no org
pack. [Org packs](#share-the-skill-through-an-org-pack) differ in two places, listed at the end.
For the other doctrine kinds, see [Create a doctrine artifact](create-a-doctrine-artifact.md).

## Prerequisites

- A Spec Kitty project (`spec-kitty init` has run) with at least one tool configured.
- The `spec-kitty` CLI on your `PATH`.

## Step 1: Set the skill namespace

Spec Kitty renders your skill as `<skill_namespace>-<id>`. The namespace keeps your skills apart
from the ones Spec Kitty ships. You must set it. There is no default, and Spec Kitty never
derives one from the repository name.

Add this to `.kittify/config.yaml`:

```yaml
charter_packs:
  project:
    skill_namespace: acme
```

Rules for the namespace:

- Lowercase ASCII only. It starts with a letter. Letters and digits form segments, and single
  `-` characters join the segments (`acme`, `acme-platform`, `team2`).
- At most 32 characters.
- Spec Kitty refuses an invalid value. It never "fixes" it for you, and it writes nothing.
- The prefixes `spk-`, `spec-kitty-` and `spec-kitty.` are reserved for built-in skills.

If the namespace is missing, activation fails with `project-tier skill '<id>' has no skill
namespace to render under` and names the config key to set.

## Step 2: Write the skill

Create two files in `.kittify/doctrine/skills/`.

`.kittify/doctrine/skills/release-notes.skill.yaml`:

```yaml
schema_version: "1.0"
id: release-notes
title: Draft release notes
description: Draft release notes for a release from its merged pull requests.
triggers: ["draft release notes", "write release notes"]
form: prompt
body_path: release-notes.skill.md
parameters:
  - name: version
    required: true
    description: Release version, for example 1.4.0
version: 1.0.0
maintainers: ["@acme/platform"]
```

`.kittify/doctrine/skills/release-notes.skill.md`:

```markdown
Draft release notes for the version the user names.

1. List the pull requests merged since the previous release tag.
2. Group them under Added, Changed and Fixed.
3. Write one plain sentence per pull request. Lead with what changes for the user.
```

This example matches `src/charter/offering/schemas/skill.schema.yaml`: it has every required
field (`schema_version`, `id`, `title`, `description`, `form`) and `body_path`, which a `prompt`
skill requires.

### The fields

| Field | Required | What it does |
| --- | --- | --- |
| `schema_version` | yes | Always `"1.0"`. |
| `id` | yes | Lowercase ASCII kebab-case: it starts with a letter and has at most 64 characters. It is the name you pass to `charter activate`. |
| `title`, `description` | yes | The heading and the description in the rendered `SKILL.md`. |
| `form` | yes | `prompt` or `wrapper` (see below). |
| `body_path` | `prompt` only | The body file, relative to the `.skill.yaml` file. It must stay inside that directory. |
| `expands_to` | `wrapper` only | `target`, and optional `args`. |
| `triggers` | no | Phrases that Spec Kitty appends to the rendered description as `Triggers: ...`. |
| `parameters` | no | A list of `name`, `required`, `description`, `default`. Spec Kitty renders them as a Parameters list. |
| `invocation` | no | `user_invocable` and `model_invocable` (both default to true) and `side_effects`. A non-empty `side_effects` list forces `model_invocable` to false. |
| `version`, `maintainers` | no | Metadata for co-maintenance. |
| `overrides`, `enhances` | no | Replace or narrow a skill from a lower tier. Not covered here. |

The schema also accepts `tools`. Spec Kitty stores it but does not use it to choose which tools
receive the skill. Every configured tool that has a project skill root receives every active
pack skill.

### The two forms

- **`prompt`** carries a Markdown body. Spec Kitty copies the body into `SKILL.md` unchanged.
  It does not rewrite argument placeholders for each tool.
- **`wrapper`** is a shorthand for an existing command. `expands_to.target` is either
  `builtin:spec-kitty.<command>` (one of the built-in command skills) or
  `cli:spec-kitty <arguments>`. For example:

  ```yaml
  form: wrapper
  expands_to:
    target: "builtin:spec-kitty.status"
  ```

  An unknown `builtin:` command is refused when the skill is projected, and the error lists the
  known commands.

### What `requires` does

A pack skill carries no doctrine of its own. In an org pack, you declare `requires` as an edge in
the pack's DRG fragment (`drg/fragment.yaml`):

```yaml
edges:
  - source: "skill:land-pr"
    target: "procedure:landing-contributor-prs"
    relation: requires
```

The rendered `SKILL.md` then gets a "Governing context" section. It tells the agent to run
`spec-kitty charter context --include <urn>` for each `requires` target. Spec Kitty never copies
the procedure text into the skill. Only `requires` edges appear there. The example above has no
edges, so its `SKILL.md` has no such section.

### What Spec Kitty refuses

For project and org skills, Spec Kitty skips the skill file with a warning (and `doctor doctrine`
reports it) when:

- the id or its rendered name starts with `spk-`, `spec-kitty-` or `spec-kitty.`;
- a `scripts/` directory sits beside the skill file;
- the body frontmatter has an `allowed-tools` (or `allowed_tools`) key;
- the body file is missing, or `body_path` points outside the skill's directory;
- a `cli:` target, or its `args`, contains a shell metacharacter (`;` `&` `|` `<` `>` `$`
  `` ` `` or a line break), or the target does not start with `spec-kitty`. Because `$` is on that
  list, a `cli:` wrapper cannot pass `$ARGUMENTS`.

Projection refuses, and writes no skill file, when:

- two active skills render to the same name;
- a skill renders under the name of a built-in skill;
- the namespace is invalid or missing.

To see the skipped files, run `spec-kitty doctor doctrine --json` and read
`profile_health.skills.invalid_skills`.

A skipped file is harmless while nothing activates it. If a skill that is **already in force**
stops loading (for example, you add an unknown key to its record), Spec Kitty refuses instead of
dropping it. `charter activate`, `spec-kitty upgrade` and the skill migrations report
`activated skill '<id>' is not available in any pack tier`, followed by what the loader said, and
they delete nothing. Fix the record and run the command again.

## Step 3: Activate it

```bash
spec-kitty charter activate skill release-notes
```

Output (abridged):

```text
Activated: release-notes
Skill file synced: .claude/skills/acme-release-notes/SKILL.md
```

On disk, you now have `<primary skill root>/acme-release-notes/SKILL.md` for each configured
tool:

| Tools | Skill root |
| --- | --- |
| Claude Code | `.claude/skills/` |
| Qwen Code | `.qwen/skills/` |
| Kilocode | `.kilocode/skills/` |
| Codex, Copilot, Gemini, Cursor, OpenCode, Windsurf, Vibe, Pi, Letta, Auggie, Kiro, Antigravity, LLxprt | `.agents/skills/` |
| Amazon Q | none (Spec Kitty skips it) |

Spec Kitty also records every file in `.kittify/skills-manifest.json`. That record is how it
later knows which files it owns. It never writes a pack skill to a user-global skill root.

Things to know:

- **Activation and projection are two steps.** Spec Kitty records the activation first. If
  projection then refuses (a missing namespace, say), the command exits with an error that says
  `The activation change is recorded`. Fix the cause and run the same command again.
- **The first `activate skill` writes `activated_skills`.** While that key is absent, only the
  org packs' `required_skills` are in force. Your project-tier skill is not.
- **Spec Kitty keeps what it does not own.** A same-name directory that is not in the manifest is
  left alone and reported as `Skill file preserved`. An empty one is projected into.

## Step 4: Check the result

```bash
spec-kitty doctor skills
```

`doctor skills` exits 1 when it finds a problem with a pack skill. It reports three findings.
Each one names the pack source file. With `--json`, the same findings appear in a `pack_skills`
list. That key is additive: existing keys are unchanged.

| Finding | What it means | What to do |
| --- | --- | --- |
| `drift` | Someone edited the rendered `SKILL.md`. Spec Kitty keeps the edited copy. | Make the change in the pack source file instead. To drop the local edit, delete the copied file and run `spec-kitty upgrade`. |
| `stale` | The pack source changed after the copy was written. | Run `spec-kitty upgrade`. It refreshes the copy. |
| `orphaned` | The manifest lists a copy that the current pack no longer provides: the skill was removed or deactivated, or the namespace changed so the skill renders under a new name. | Run `spec-kitty upgrade` to retire the old copy, or activate the skill again. |

The rendered file is read-only by default. Edit the pack source, not the copy.

If Spec Kitty cannot resolve the pack skills at all (see the last section), `doctor skills`
reports no pack finding. The error shows up on `charter activate` and `spec-kitty upgrade`
instead.

## Step 5: Deactivate it

```bash
spec-kitty charter deactivate skill release-notes
```

This retires the files that Spec Kitty wrote, and nothing else. It never deletes your pack
source files, a directory it does not own, or a copy you edited. It lists a kept copy as
`Skill file preserved`.

After the last deactivation, `activated_skills` is an empty list, and an empty list means no
pack skill is in force. That includes any skill an org pack requires. To get the default back,
activate the skills you want, or remove the `activated_skills` key from the file that holds it
(`.kittify/config.yaml` unless your charter configuration lives in a separate `charter.yaml`).

## What `spec-kitty upgrade` does with pack skills

`spec-kitty upgrade` treats pack skills as part of the project's skill inventory:

- It keeps the pack skills that are in force. It does not prune them.
- It refreshes a stale copy and retires an orphaned one.
- It keeps a copy you edited and reports it as `drift`.
- It writes again a copy that you deleted.

If Spec Kitty cannot resolve the pack skills in force, the skill migrations that run report a
failure and change nothing. The error reads `Pack skills could not be resolved: <reason>`. This applies only
to a project that has a pack skill in force. A project with none is not affected, even when an
org pack's DRG fragment is damaged. Typical causes are a missing or invalid namespace, two skills
with the same rendered name, a skill record that no longer loads, an unreadable pack file, or a
damaged org pack DRG fragment. Fix the cause named in the reason, then run `spec-kitty upgrade`
again.

## Share the skill through an org pack

An org pack works the same way, with two differences:

- Put the files in the pack's `skills/` directory (`<pack>/skills/<id>.skill.yaml`). Set
  `skill_namespace` in the pack's `org-charter.yaml` instead of the project config. When several
  packs set it, the last non-empty value wins.
- List the ids in `required_skills` in `org-charter.yaml` to put a skill in force for every
  project that registers the pack, without a `charter activate` step. Two sibling org packs must
  not declare the same skill id.

See [Understanding the Org Doctrine Layer](../../architecture/org-doctrine-layer.md) for how a
project registers a pack.

## See also

- [Doctrine artifact kinds: Skill](../../architecture/doctrine-kinds.md#skill) — what the kind is for.
- [ADR 2026-09-27-1](../../adr/3.x/2026-09-27-1-pack-skills-share-commands-through-charter-packs.md)
  — the decision, and the ownership proof for the files Spec Kitty writes.
- [Create a doctrine artifact](create-a-doctrine-artifact.md) — the walkthrough for the other kinds.
