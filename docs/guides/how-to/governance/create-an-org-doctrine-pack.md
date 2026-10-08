---
title: How to Create an Org Doctrine Pack
description: Author, validate, assemble, publish, and consume a spec-kitty org doctrine pack.
doc_status: active
updated: '2026-10-06'
type: how-to
audience: docs/context/audience/external/tech-lead-evaluator.md
related:
- docs/guides/how-to/governance/setup-governance.md
- docs/guides/how-to/governance/synthesize-doctrine.md
- docs/migrations/doctrine-local-overlay-to-org-layer.md
---
# How to Create an Org Doctrine Pack

This guide walks a governance system maintainer through producing an org doctrine pack,
validating it, optionally assembling several packs into a single distributable, publishing
it, and configuring consumer projects to install it.

You'd build one of these instead of just running [project governance
setup](setup-governance.md) on each repo separately when you have more than one project
that needs the same rules — the same testing standard, the same architectural
conventions, the same review discipline — and you don't want each project's charter to
drift out of sync as you update the rule. An org doctrine pack is versioned and
distributed like any other dependency: you publish once, consumer projects pull a
specific version, and a rule change is a PR to the pack, not a hand-edit repeated N
times.

Not the same thing as Spec Kitty's **built-in** doctrine packs (e.g. SPDD) — see
[Doctrine Packs](../../../architecture/doctrine-kinds.md) for those; this guide is for a pack *you* author
and distribute.

For background on what the org layer is and how it composes with built-in and project
doctrine, see [Understanding the Org Doctrine Layer](../../../architecture/org-doctrine-layer.md).

---

## Before you start

You need:

- Spec Kitty installed and on `PATH` (verify with `uv run spec-kitty --version`).
- A directory you control where you can lay out pack files.
- For publishing: a git remote, an HTTPS bundle location, or a custom HTTP API endpoint —
  whichever your organization prefers.

You do **not** need a spec-kitty project to author a pack. Authoring is independent of any
consumer project.

---

## Step 1: Lay out the pack directory

The canonical layout uses one directory per artifact type. All directories are optional;
a valid pack may contain any non-empty subset.

```
my-pack/
├── directives/                 # *.directive.yaml — project rules
├── tactics/                    # *.tactic.yaml — domain tactics
├── styleguides/                # *.styleguide.yaml — style standards (subdirs allowed)
├── toolguides/                 # *.toolguide.yaml — tool usage rules
├── paradigms/                  # *.paradigm.yaml — paradigm definitions
├── procedures/                 # *.procedure.yaml — operational procedures
├── agent_profiles/             # *.agent.yaml — agent personas
├── mission_step_contracts/     # *.step-contract.yaml — mission step contracts
├── drg/                        # fragment.yaml — a single OrgDRGFragment (nodes/edges)
└── org-charter.yaml            # optional: org governance policy
```

**Important: do not create `pack-manifest.yaml` yourself.** It is written by
`charter fetch` (for non-git sources) and `charter pack assemble`. Authors should leave
it alone; manual edits surface as an advisory in `pack validate`.

---

## Step 2: Author your artifacts

Each artifact file conforms to the same YAML schema used elsewhere in spec-kitty. The
recipe is the same for every artifact type — give it a unique `id`, fill in the required
fields for its schema, and save it in the matching directory.

### Example: a directive

```yaml
# directives/acme-001-secret-handling.directive.yaml
id: ACME_001_SECRET_HANDLING
title: Never commit credentials to the repository
severity: high
description: |
  Secrets must be supplied via environment or secret manager. Pre-commit hooks
  must scan staged content for known credential shapes.
action_scope:
  - implement
  - review
```

### Example: an agent profile

```yaml
# agent_profiles/acme-implementer.agent.yaml
profile-id: acme-implementer
name: ACME Implementer
description: ACME's security-first implementation persona
roles:
  - implementer
purpose: |
  An ACME engineer adopts this profile during implement actions. They prioritise
  security review, follow the change-intent canvas, and refuse to commit secrets.
specialization:
  primary-focus: Feature implementation under ACME's secret-handling rules
  avoidance-boundary: Architectural decisions, release management
directive-references:
  - code: ACME_001_SECRET_HANDLING
    name: Never commit credentials to the repository
```

**Agent-profile keys are closed.** A key the profile schema does not declare is a
load error, not a warning — the profile is skipped and the pack is reported
unhealthy by `spec-kitty doctor charter-packs --json` (look for `skipped_profiles`).
Note in particular that the identifier key is `profile-id` (not `id`), that
`roles` is a list (not a singular `role`), and that most keys are hyphenated.
Copy the field names from a built-in profile under
`packs/built-in/agent_profiles/` if you are unsure.

### Namespace your IDs

IDs in an org pack collide globally with built-in and project IDs. To keep collisions
visible (and to make `doctor charter-packs` output readable), prefix your IDs with an
organisation-specific code:

| Artifact type | File pattern | Recommended ID prefix |
|---|---|---|
| Directives | `*.directive.yaml` | `<ORG>_<SEQ>_<SLUG>` (e.g. `ACME_001_SECRET_HANDLING`) |
| Tactics | `*.tactic.yaml` | `<org>-tac-<seq>` |
| Styleguides | `*.styleguide.yaml` | `<org>-sty-<seq>` |
| Toolguides | `*.toolguide.yaml` | `<org>-tg-<seq>` |
| Paradigms | `*.paradigm.yaml` | `<org>-par-<seq>` |
| Procedures | `*.procedure.yaml` | `<org>-proc-<seq>` |
| Agent profiles | `*.agent.yaml` | `<org>-<role>` |
| Mission step contracts | `*.step-contract.yaml` | `<org>-msc-<seq>` |

Collisions with built-in IDs are **permitted** but produce a full-replace advisory at
resolution time — keep them intentional and rare.

**Note**: the `mission_step_contracts/` surface documented above (`step_contracts.py`, the
`MissionStepContract` model, and this file suffix) is slated for retirement in its entirety
in favor of a unified `MissionStep` model — see ADR `2026-08-13-1`, *Built-in mission
subtree stays nested; retire legacy step contracts* (Accepted). Treat the corrected suffix
above as a bridge, not a durable authoring target.

### DRG extensions

If your pack contributes typed graph relations (for example, a new directive that scopes
to a specific mission action), declare them in a single `drg/fragment.yaml` — the
`OrgDRGFragment` shape that `spec-kitty charter org init` scaffolds. An org pack's DRG
is read only from `drg/fragment.yaml`; a `drg/*.graph.yaml` fragment is **not** consumed
and `charter org validate` now rejects it (`drg_root_graph_missing`):

```yaml
# drg/fragment.yaml
# pydantic_model: charter.drg.OrgDRGFragment
# expect: valid
pack_name: acme-security
source_kind: local_path
source_ref: .
layer_index: 1
provenance_marker: org
nodes: []   # nodes are inferred from the artifact files
edges:
  - source: action:software-dev/implement
    target: directive:ACME_001_SECRET_HANDLING
    relation: scope
```

Nodes are inferred recursively from matching artifact files in `directives/`,
`tactics/`, `styleguides/`, `toolguides/`, `paradigms/`, `procedures/`,
`agent_profiles/`, `glossary_packs/`, `assets/`, and `mission_step_contracts/`.
Discovery uses each kind's standard suffix (for example, `.agent.yaml`,
`.glossary-pack.yaml`, and `.asset.yaml`). Agent profiles use `profile-id`;
other artifacts use `id`. Filenames never supply an identity. Inference preserves
these IDs exactly. Use canonical directive IDs such as
`ACME_001_SECRET_HANDLING` for action-context delivery; node inference does not
normalize directive IDs.

Inference supplements an omitted, empty, or partially authored `nodes:` list.
An explicit node with the same kind and ID takes precedence, including its title
and body path. Use `id` and the **plural** node kind for an explicit declaration:

```yaml
nodes:
  - id: ACME_001_SECRET_HANDLING
    kind: directives
    title: Secret handling policy
    body_path: bodies/secret-handling.md
```

Mission types and templates still require explicit nodes; inference does not
create graph-only anti-pattern nodes. Step-contract files infer the plural node
kind `mission_steps`. Malformed or unreadable artifact YAML and missing or
non-string IDs are skipped during discovery; run pack validation to diagnose
artifact schema errors. Non-string optional titles/body paths are ignored.
Explicit node schema errors still fail loading. No nodes are invented for missing
edge endpoints, and artifact discovery does not infer scope or reference edges.

**Write endpoints in full: `<kind>:<id>`.** The kind half must be a real node
kind (`directive`, `tactic`, `styleguide`, `toolguide`, `paradigm`, `procedure`,
`agent_profile`, `mission_step_contract`, `mission_type`, `template`, `asset`,
`action`, `glossary_pack`, `anti_pattern`). A bare id with no kind prefix only
works if the same fragment declares or infers it, or if it matches a
built-in artifact — it will **not** find an artifact contributed by another pack,
because pack-to-pack resolution would make the result depend on the order the
packs are listed in. Anything that cannot be resolved is refused at merge time
with an `unresolved_edge_endpoint` conflict naming the token; there is no
`urn:` prefix form.

DRG fragments are **additive only**. They may add new edges and nodes but must not
remove or modify built-in graph state. An org pack contributes a single
`drg/fragment.yaml`; its edges are appended to the resolved graph in the order the pack
is listed under `organisation_packs:` (the `layer_index` the loader assigns).

---

## Step 3: Optional — author `org-charter.yaml`

If your pack should pre-fill the project charter interview, require specific directives
across all consumers, or surface advisory governance policies, add an `org-charter.yaml`
at the pack root:

```yaml
# org-charter.yaml
schema_version: "1"
org_name: ACME Corporation
interview_defaults:
  language: python
  test_framework: pytest
required_directives:
  - ACME_001_SECRET_HANDLING
  - ACME_002_CODE_REVIEW
governance_policies:
  - field: min_test_coverage
    value: "80"
    enforcement: advisory
```

The `org-charter.yaml` file is **optional**. Packs that ship only doctrine artifacts (no
policy) simply omit it.

For more on how `org-charter.yaml` composes when multiple packs are configured, see
[the org charter composition section of the explanation doc](../../../architecture/org-doctrine-layer.md#org-charter-composition).

## Step 3b: Sanction the built-ins your pack replaces

If an artifact in your pack has the same ID as a built-in artifact, it replaces that built-in in place. A consumer's `spec-kitty doctor charter-packs` accepts the replacement only when something sanctions it; otherwise it exits 1 and names the URN. You list the built-ins you replace on purpose in a file at the **pack root**. This also covers the case where upstream later promotes one of your artifacts into the built-in set: your same-ID artifact then becomes an override, and the sanction is already in your pack.

Create `replaceable-builtins.yaml` next to `org-charter.yaml`. The pack root is the resolved root of the pack, including any `subdir` the consumer configures:

```yaml
# <pack root>/replaceable-builtins.yaml
replaceable_builtins:
  - urn: directive:MINUTES_STAND_ALONE
    reason: We replace this directive because our minutes template differs.
  - urn: agent_profile:minutes-mahad
```

Rules:

- Each entry is `{urn, reason}`. The `urn` is `<kind>:<id>`.
- A `directive:` entry **must** carry a non-empty `reason`. For other kinds the reason is optional but recommended.
- The sanction covers only overrides your own pack contributes. A consumer matches it by the pack's name in the consumer's configuration, so it cannot sanction an override from another pack.
- The file has one key, `replaceable_builtins`. `revoked_pack_sanctions` belongs to the consumer file only and is an error here. Other unknown keys are ignored.
- An entry for a URN that is not a built-in, or that your pack does not override, does nothing.
- A file that is malformed, unreadable, not a regular file, or a symlink that leaves the pack root makes the consumer's `doctor charter-packs` unhealthy, with an error that names your pack and the file. The file is checked for every configured pack, whether or not that pack overrides anything.

Validate it with the rest of the pack (Step 5). `spec-kitty charter pack validate` parses the file with the same parser the consumer uses. It reports an error for a malformed file or a directive entry without a reason, and an advisory for an entry your pack does not override.

When you assemble packs (Step 6), the assembled pack root carries the union of the input packs' `replaceable-builtins.yaml` files. If two inputs list the same URN with different reasons, assembly reports a conflict; `--force` keeps the last pack's reason.

### Migrating from the setup template

Earlier guidance had packs ship `templates/setup/replaceable-builtins.yaml` for consumers to copy. Nothing reads that template, and the copies drift. Move the file instead, once, in your pack repository:

```bash
git mv templates/setup/replaceable-builtins.yaml replaceable-builtins.yaml
```

If the pack is consumed through a `subdir`, move it to the root of that subdirectory. Consumers then delete their hand-copied entries, or leave them: a consumer file that lists the same URN keeps working.

A pack fetched through an API source (Option C in Step 7) does not carry root files, so it delivers no sanction and the consumer's own file still governs.

---

## Step 4: Wrap an existing governance system

If your organization already documents its rules — typically as Markdown policy pages,
internal wikis, or a YAML config in a different format — you can migrate that content
into a pack without rewriting it from scratch.

The recipe:

1. **Identify the artifact type.** A Markdown policy doc usually maps to one or more
   directives. An "engineering principles" page often maps to paradigms. A "best practices"
   page often maps to tactics. A "how do we do X" runbook maps to a procedure.
2. **Extract one rule per file.** Resist the urge to dump a whole policy page into a
   single directive — split it so each rule has its own `id` and can be cited
   individually in lint advisories and review feedback.
3. **Validate.** Run `pack validate` after each batch (see Step 5 below) so you catch
   schema mistakes early.

**Before** (`security-policy.md`, existing Markdown wiki page):

```markdown
## Secret handling

Credentials, API tokens, and TLS private keys must never be committed to the repository.
Use the secret manager. Pre-commit hooks must scan staged content.
```

**After** (`directives/acme-001-secret-handling.directive.yaml`):

```yaml
id: ACME_001_SECRET_HANDLING
title: Never commit credentials to the repository
severity: high
description: |
  Credentials, API tokens, and TLS private keys must never be committed to the
  repository. Use the secret manager. Pre-commit hooks must scan staged content.
action_scope:
  - implement
  - review
```

The wiki page can keep existing — link to it from the directive's description if you
want to preserve narrative context. The directive is the structured rule the runtime
will see.

---

## Step 5: Validate the pack

Before publishing, validate against schema and DRG constraints:

```bash
uv run spec-kitty charter pack validate ./my-pack
```

Exit codes:

- `0` — pack passes. Advisories are printed but do not affect exit.
- `1` — pack has at least one error. Fix and re-validate.

For machine-readable output (CI integration, scripts):

```bash
uv run spec-kitty charter pack validate ./my-pack --json
```

### Reading the output

The validator distinguishes errors from advisories:

| Condition | Class |
|---|---|
| Artifact YAML fails schema validation | Error |
| Duplicate `id` within the pack | Error |
| Dangling DRG edge (target URN not in merged artifact set) | Error |
| DRG extension tries to modify or remove a built-in node | Error |
| `org-charter.yaml` schema violation | Error |
| `replaceable-builtins.yaml` malformed, or a directive entry without a reason | Error |
| `replaceable-builtins.yaml` entry for a URN your pack does not override | Advisory |
| Artifact ID collides with a built-in ID | Advisory |
| `pack-manifest.yaml` exists and was author-edited | Advisory |
| `enforcement` value other than `"advisory"` | Advisory |

If validation reports `Dangling DRG edge`, the named URN does not resolve in your pack's
artifact set. Either add the missing artifact, fix the URN, or remove the edge.

---

## Step 6 (optional): Assemble multiple packs into a distributable

If your organization prefers a single distributable artifact over multiple independent
pack repositories, you can merge several packs into one with `charter pack assemble`:

```bash
uv run spec-kitty charter pack assemble \
  ./distributable-out \
  ./security-pack ./architecture-pack ./compliance-pack
```

The first positional argument is the output directory. All remaining positional arguments
are input pack directories. The command produces a single merged pack at the output
path and validates the result before exiting.

If two input packs ship the same artifact ID or define conflicting DRG edges, the
default behavior is to **fail** with a conflict report. You have two options:

```bash
# Write the conflict report to a file for inspection
uv run spec-kitty charter pack assemble \
  ./out ./security ./architecture \
  --conflicts-out conflicts.json

# Resolve conflicts by last-pack-wins (and drop duplicate edges silently)
uv run spec-kitty charter pack assemble \
  ./out ./security ./architecture --force
```

Exit codes: `0` on success; `1` if conflicts block the merge or the assembled output
fails validation.

Adding `--json` switches the assemble summary to machine-readable output.

---

## Step 7: Publish the pack

The org layer supports three transport mechanisms. Pick one based on your distribution
model.

### Option A: Git repository (recommended)

Push the pack to a git remote your developers can reach. Tag releases.

```bash
cd my-pack
git init
git add .
git commit -m "Initial pack"
git tag v1.0.0
git remote add origin git@example.com:acme/security-doctrine.git
git push origin main v1.0.0
```

Consumers point at the git remote and pin to a tag.

### Option B: HTTPS bundle

Upload a tarball or zip to an HTTPS-served location (object storage, releases page).
Consumers download and extract.

```bash
tar czf security-doctrine-v1.0.0.tar.gz -C my-pack .
# upload to https://releases.example.com/doctrine/security-doctrine-v1.0.0.tar.gz
```

### Option C: Custom HTTP API

For organizations with an existing governance API server, expose pack contents under a
base URL. The contract for that API is in
[contracts/org-doctrine-source-api-contract.md](https://github.com/spec-kitty/spec-kitty/blob/main/kitty-specs/layered-doctrine-org-layer-01KRNPEE/contracts/org-doctrine-source-api-contract.md)
(in the mission's planning artifacts).

### Versioning strategy

Whichever transport you choose, **pin versions** in consumer config. For git, use a tag
name or commit SHA. Branch names are accepted but discouraged for reproducibility — a
moving target on `main` will silently change behavior for every consumer on every
fetch.

---

## Step 8: Configure consumers

A consumer project enables the org layer by adding a `doctrine.org` block to its
`.kittify/config.yaml`:

```yaml
# .kittify/config.yaml
doctrine:
  org:
    packs:
      - name: security
        local_path: "~/.kittify/org/security/"
        source_type: git
        url: "git@example.com:acme/security-doctrine.git"
        ref: "v1.0.0"
      - name: architecture
        local_path: "~/.kittify/org/architecture/"
        source_type: git
        url: "git@example.com:acme/architecture-doctrine.git"
        ref: "v0.3.0"
```

Field reference:

| Field | Required | Purpose |
|---|---|---|
| `name` | yes | Unique pack name (used by `--pack` flag, displayed in `doctor charter-packs`) |
| `local_path` | yes | Filesystem path where the snapshot lives (`~` and `${VAR}`/`$VAR` env-var indirection expanded at resolution time — see below) |
| `source_type` | no | One of `git`, `https`, `artifactory`, `api`; omit if pre-provisioned |
| `url` | required if `source_type` set | Remote URL |
| `ref` | no | Version pin (git tag/SHA; non-Artifactory HTTPS advisory; API query param) |

Existing `source_type: https` JFrog item URLs are recognized by the path
`/artifactory/<repository>/<item>` (never by hostname). You may instead use
`source_type: artifactory` to declare that intent explicitly and fail before
network access when the URL is not a valid item path. After buffering a
successful download, Spec Kitty sends one exact-item AQL query that returns the
item's `version` property and SHA-256 together. Both are required, and that
co-attested checksum must match the downloaded bytes before extraction or
snapshot promotion. Because Artifactory AQL requires authenticated read access,
set `SPEC_KITTY_ORG_TOKEN` (sent as a bearer token) or
`SPEC_KITTY_ORG_AUTH_HEADER` (sent verbatim) to credentials authorized to
download the item and query AQL. A conditional HTTP 304 performs no AQL query
and preserves the prior snapshot and manifest byte-for-byte, including its
previously sampled version.

Use `source_type: artifactory` explicitly for a JFrog item; Artifactory is not
inferred from the hostname. Its HTTPS URL must contain
`/artifactory/<repository>/<item>`. After staging the download, Spec Kitty
queries the item's `version` property and File Info SHA-256. Both are required,
and the checksum must match the downloaded bytes before extraction or snapshot
promotion.

### Env-var indirection in `local_path`

`local_path` supports `${VAR}` and bare `$VAR` env-var tokens, composed with
`~` tilde-expansion, so a shared `.kittify/config.yaml` can be checked in
without hard-coding a machine-local absolute path:

```yaml
doctrine:
  org:
    packs:
      - name: security
        local_path: "${SPEC_KITTY_PACK_HOME}/security-doctrine"
```

```bash
export SPEC_KITTY_PACK_HOME=/opt/acme-doctrine
```

Expansion happens only when the path is resolved (e.g. `charter fetch`,
`doctor charter-packs`) — the literal `${SPEC_KITTY_PACK_HOME}/security-doctrine`
string is what stays written in `.kittify/config.yaml`, so the config remains
portable across machines/CI. If the referenced variable is unset or empty,
resolution fails closed with a named error identifying the variable and the
pack, rather than silently falling back to a literal-token path or disabling
the org layer.

Then the consumer runs:

```bash
# Fetch all configured packs
uv run spec-kitty charter fetch

# Or fetch a single pack
uv run spec-kitty charter fetch --pack security

# Preview without contacting any remote
uv run spec-kitty charter fetch --dry-run
```

Verify the install:

```bash
uv run spec-kitty doctor charter-packs
```

The output enumerates each configured pack, its on-disk version, per-artifact counts,
and `org-charter.yaml` status. Add `--json` for scripting.

### Built-in overrides: see what is sanctioned, and withdraw it

Consumers no longer copy the pack's allowlist. `spec-kitty doctor charter-packs` reads each pack's root `replaceable-builtins.yaml` in place and unions it with the consumer's own `.kittify/doctrine/replaceable-builtins.yaml`, which keeps its schema and is checked first. A pack's sanction applies only to overrides that same pack contributes.

The report lists every sanctioned built-in override with its source and reason, including on a passing run, under `Sanctioned built-in override(s)`. With `--json` they appear as `sanctioned_overrides` under `profile_health.org_drg`, each with `source` set to `consumer` or `pack`.

To withdraw what a pack delivered without unconfiguring the pack, add `revoked_pack_sanctions` to the consumer file. Each entry names either a URN or a configured pack, with an optional reason:

```yaml
# .kittify/doctrine/replaceable-builtins.yaml
revoked_pack_sanctions:
  - urn: directive:MINUTES_STAND_ALONE
    reason: We want to review this replacement ourselves.
  - pack: acme-doctrine   # every sanction this pack delivers
```

A revoked override is reported as unsanctioned and `doctor charter-packs` exits 1 until you list the URN under `replaceable_builtins` in your own file. Revocation withdraws only pack-delivered sanctions. A `pack` value must match a configured pack name exactly (case-sensitive); one that does not is an error, so a typo cannot leave a sanction in force. Revoking a whole pack also catches overrides the pack starts sanctioning on a later refresh.

A malformed consumer file is now reported as an error that names the file, and is treated as empty. Older CLIs ignore `revoked_pack_sanctions`.

Confirm the org layer is participating in actual context resolution:

```bash
uv run spec-kitty charter context --action implement --json
```

Resolved artifacts will have a `source` field of `builtin`, `org`, or `project`.

---

## Troubleshooting

### Advisory: "org layer overrides built-in artifact"

You wrote an artifact whose `id` collides with a built-in id. The override applies as
intended (full-replace), but `charter lint` and `pack validate` warn because the
collision is usually unintentional. Either rename the artifact (recommended — namespace
your IDs as in Step 2) or accept the override if you genuinely meant to replace the
built-in version.

### Error: "Unsanctioned built-in override(s)"

`doctor charter-packs` found a built-in override that nothing sanctions. The `why` text on the finding says which case applies. Fix it in this order:

1. **Pack root.** If the overriding pack should own the replacement, add the URN to the pack's `replaceable-builtins.yaml` (Step 3b) and refresh the pack with `spec-kitty charter fetch`. A directive needs a non-empty `reason`. The entry counts only for the pack that contributes the override.
2. **Consumer entry.** If you accept the replacement yourself, append `{urn, reason}` under `replaceable_builtins` in `.kittify/doctrine/replaceable-builtins.yaml`. Append the one entry; do not copy a whole file over yours.
3. **Revoked.** If the finding says the pack sanction was revoked by the consumer file, remove the matching `revoked_pack_sanctions` entry, or use step 2.

If the pack still ships only `templates/setup/replaceable-builtins.yaml`, a template is not a sanction and the run still exits 1. The finding then prints where the pack author should move the file and the exact entry to append to your file for step 2. If the template entry is a directive with no reason, it says a reason is required instead of printing an entry; add one yourself.

### Error: "Override sanction file error(s)"

A pack's root `replaceable-builtins.yaml`, or your consumer file, could not be used. The message names the pack and file. Common causes are invalid YAML, an entry without a `urn`, `revoked_pack_sanctions` inside a pack file, a symlink that leaves the pack root, and a `revoked_pack_sanctions` pack name that is not configured. The broken file contributes no sanction; fix it and re-run.

While your consumer file is malformed it is treated as empty, so its `revoked_pack_sanctions` are not applied either: a pack-sanctioned override you meant to revoke may still be listed as sanctioned. Fix the file first; `doctor charter-packs` stays unhealthy until then.

### Error: "No artifact directories found in fetched snapshot"

The fetched pack contains no recognized artifact directories. Check that the pack root
is correct (the pack directory itself, not a parent folder) and that at least one of
the canonical subdirectories exists with valid YAML files.

### Error: "Dangling DRG edge"

A DRG fragment references a URN that does not resolve in the merged artifact set.
Either:

- Add the missing artifact to your pack.
- Fix the URN in the fragment.
- Remove the offending edge.

The validator prints the URN and the fragment file, so locate the offender by grepping
for the URN.

### Error: "DRG extension attempts to modify a built-in node"

A DRG fragment tries to remove or modify a node that originates in the built-in layer.
This is forbidden — extensions are additive only. Refactor the fragment to add new
edges or nodes instead.

---

## See also

- [Understanding the Org Doctrine Layer](../../../architecture/org-doctrine-layer.md)
- [Migrating shared doctrine to the org layer](../../../migrations/doctrine-local-overlay-to-org-layer.md)
- [How to set up project governance](setup-governance.md)
- [How to synthesize and maintain doctrine](synthesize-doctrine.md)
