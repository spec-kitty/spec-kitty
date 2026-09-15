# Feature Specification: Doctrine Org Init From Template

**Mission**: doctrine-org-init-from-template-01KXNA6P
**Mission type**: software-dev
**Status**: Draft

## Overview

Today `spec-kitty doctrine org init <PACK_PATH>` always scaffolds a minimal
three-file org doctrine pack (`org-charter.yaml`, `drg/fragment.yaml`,
`README.md`). This mission **extends that same command** so operators who
create their own doctrine can optionally initialise from an existing template
(local path or git URL): resolve the template as-is, honour `.templateignore`,
validate the organisation name, substitute identity and registration-path
tokens, and write the result to a destination path that is distinct from the
registration path token.

When no template is supplied, behaviour remains the existing minimal scaffold.
Authoring or maintaining the external template is out of scope — the template
is consumed as provided.

## User Scenarios & Testing

### Primary actors

- **Operator** — creates their own doctrine by scaffolding or rendering an org
  pack via `spec-kitty doctrine org init`.

### Primary scenario (happy path — template render)

1. Operator runs `doctrine org init` with a destination **PACK_PATH**, a
   **TEMPLATE** (local directory or git HTTPS/SSH URL that may include a
   branch), an **ORG_NAME**, and optionally a **LOCAL_PATH**.
2. The command validates **ORG_NAME** (and **LOCAL_PATH** if supplied) before
   writing any rendered content.
3. It resolves the template (local copy or clone/fetch of the named branch),
   applies `.templateignore` so ignored paths are not present in the rendered
   output, substitutes every literal `{{ORG_NAME}}` and `{{LOCAL_PATH}}`, and
   writes the **entire** template tree (minus ignores) under **PACK_PATH**.
4. Operator can proceed to use the rendered doctrine project; ignored template
   paths are absent and tokens are filled.

### Alternate scenario (minimal scaffold)

1. Operator runs `doctrine org init <PACK_PATH>` without **TEMPLATE**.
2. The command creates the same minimal three-file skeleton as today under
   **PACK_PATH** (subject to existing `--force` overwrite rules).

### Exception / edge cases

- Invalid **ORG_NAME** or **LOCAL_PATH** → fail with a clear error naming the
  violated rule and the offending value; do not write a partial render; do not
  silently sanitise (no auto-lowercasing / hyphenating).
- **TEMPLATE** path does not exist, or git URL/branch cannot be resolved → fail
  with a clear error before writing the destination.
- Destination **PACK_PATH** already exists without force → refuse (same as
  today’s overwrite guard).
- Template has no `.templateignore` → render all files that would otherwise be
  copied (aside from any built-in ignore of `.templateignore` itself if the
  renderer treats that file as non-deliverable).
- Unfilled tokens after render (`{{ORG_NAME}}` / `{{LOCAL_PATH}}` still present)
  → treat as failure (render incomplete).
- **PACK_PATH** and **LOCAL_PATH** differ: destination on disk vs registration
  token value; using one must not silently overwrite or redefine the other.

### Acceptance scenarios

1. **Given** no TEMPLATE, **when** the operator inits a new PACK_PATH, **then**
   the minimal three-file scaffold is created as today.
2. **Given** a local TEMPLATE with `{{ORG_NAME}}` / `{{LOCAL_PATH}}` and a
   `.templateignore`, **when** the operator supplies valid ORG_NAME, LOCAL_PATH,
   and PACK_PATH, **then** the rendered tree at PACK_PATH has tokens substituted,
   ignored paths absent, and PACK_PATH ≠ LOCAL_PATH when they were supplied as
   different values.
3. **Given** a git TEMPLATE URL with branch, **when** the operator inits with a
   valid ORG_NAME, **then** the pack is rendered from that revision into
   PACK_PATH.
4. **Given** an invalid ORG_NAME (uppercase, reserved `doctrine-org`, literal
   `{{ORG_NAME}}`, too short/long), **when** init runs with TEMPLATE, **then**
   the command exits non-zero with a rule-specific error and does not leave a
   rendered pack.

## Domain Language

| Term | Canonical meaning | Avoid |
|---|---|---|
| PACK_PATH | Destination directory where the scaffold or rendered pack is written | Treating it as the `{{LOCAL_PATH}}` token |
| LOCAL_PATH | Value substituted into `{{LOCAL_PATH}}` (pack registration / `source_ref` path) | Equating it with PACK_PATH |
| TEMPLATE | Local directory path **or** git repo URL (HTTPS or SSH, may include branch) used as the render source | Assuming TEMPLATE is always local |
| ORG_NAME | Validated org/pack identity substituted into `{{ORG_NAME}}` | Free-text display names that violate the slug rules |
| `.templateignore` | Ignore file in the template that lists paths to omit from the rendered output | Ad-hoc post-copy deletion without the ignore file |
| render | Validate → resolve template → copy with ignores → substitute tokens → write to PACK_PATH | "compile" (DRG compile is a separate pack step) |

## Requirements

### Functional Requirements

| ID | Requirement | Status |
|---|---|---|
| FR-001 | When TEMPLATE is omitted, `doctrine org init` continues to scaffold the existing minimal org pack under PACK_PATH (same three files and overwrite/`--force` semantics as today). | Planned |
| FR-002 | When TEMPLATE is provided, `doctrine org init` accepts TEMPLATE, ORG_NAME, and optional LOCAL_PATH in addition to PACK_PATH, and performs a template render into PACK_PATH instead of the minimal scaffold. | Planned |
| FR-003 | TEMPLATE may be a local filesystem directory **or** a git repository URL over HTTPS or SSH; the TEMPLATE value may identify a branch; the command resolves that revision before rendering. | Planned |
| FR-004 | Before writing a rendered pack, validate ORG_NAME against the doctrine-template downstream contract: lowercase kebab-case `^[a-z][a-z0-9]*(-[a-z0-9]+)*$`, length 2–64, not equal to reserved base pack name `doctrine-org` (case-insensitive), and not the literal `ORG_NAME`, `{{ORG_NAME}}`, or any value containing `TODO`; on failure abort with a clear error naming the rule and value (no silent sanitising). | Planned |
| FR-005 | LOCAL_PATH is distinct from PACK_PATH: PACK_PATH is the write destination; LOCAL_PATH is the string substituted for every literal `{{LOCAL_PATH}}`. When LOCAL_PATH is omitted during a template render, default it to the render target's pack directory path convention (e.g. `pack`) per the doctrine-template contract. | Planned |
| FR-006 | Validate LOCAL_PATH as a non-empty path string; reject the literal `LOCAL_PATH`, `{{LOCAL_PATH}}`, or any value containing `TODO`; on failure abort with a clear error (no silent sanitising). | Planned |
| FR-007 | During render, honour the template's `.templateignore` so matching paths are excluded from the content written under PACK_PATH. | Planned |
| FR-008 | During render, substitute every literal `{{ORG_NAME}}` with the validated ORG_NAME and every literal `{{LOCAL_PATH}}` with the resolved LOCAL_PATH across the copied file contents. | Planned |
| FR-009 | A template render must not leave unfilled `{{ORG_NAME}}` or `{{LOCAL_PATH}}` tokens in the written PACK_PATH tree; if substitution would leave such tokens, fail without presenting a successful render. | Planned |
| FR-010 | On template resolve failure (missing local path, unreachable git URL, or unresolvable branch) or validation failure, do not leave a partially rendered destination presented as success. | Planned |

### Non-Functional Requirements

| ID | Requirement | Measurable threshold | Status |
|---|---|---|---|
| NFR-001 | Validation and resolve errors are actionable for operators. | Every failure path names the violated rule or resolve step and the offending input value in the command output. | Planned |
| NFR-002 | Minimal-scaffold path remains behaviourally compatible. | Existing init-without-TEMPLATE scenarios (including `--force` refuse/overwrite) continue to pass their current acceptance coverage. | Planned |
| NFR-003 | Template render completes in interactive operator time for a typical local template. | Local TEMPLATE render of a pack-sized tree (on the order of the reference doctrine-template `pack/` plus small repo metadata) finishes in under 30 seconds on a developer machine, excluding network time for git TEMPLATE fetches. | Planned |

### Constraints

| ID | Constraint | Status |
|---|---|---|
| C-001 | ORG_NAME validation rules are those documented by the reference doctrine-template downstream CLI contract; do not invent a divergent slug alphabet. | Active |
| C-002 | PACK_PATH and LOCAL_PATH remain separate parameters/concepts; the command must not treat them as aliases. | Active |
| C-003 | Substitution is plain-text token replace for `{{ORG_NAME}}` and `{{LOCAL_PATH}}` only (no general-purpose templating engine requirement). | Active |
| C-004 | When TEMPLATE is omitted, do not require ORG_NAME or LOCAL_PATH. | Active |

## Key Entities

- **Org pack destination (PACK_PATH)** — directory receiving scaffold or render output.
- **Template source (TEMPLATE)** — local directory or git URL (+ optional branch).
- **Org identity (ORG_NAME)** — validated slug used for `{{ORG_NAME}}`.
- **Registration path (LOCAL_PATH)** — path string used for `{{LOCAL_PATH}}`.
- **Ignore manifest (`.templateignore`)** — template-side list of paths excluded from render output.

## Success Criteria

- **SC-001**: An operator without a template can still initialise a minimal org pack with the same files and overwrite rules as before.
- **SC-002**: An operator with a local or git template can produce a rendered pack at PACK_PATH where ORG_NAME and LOCAL_PATH are applied, ignored paths are absent, and invalid names are rejected before a successful write.
- **SC-003**: Reviewers can confirm PACK_PATH (destination) and LOCAL_PATH (token) were supplied or defaulted independently in documented examples and acceptance checks.
- **SC-004**: At least 95% of invalid ORG_NAME fixtures covering format, length, reserved name, and placeholder cases produce a non-zero exit with a rule-specific message and no successful rendered tree.

## Assumptions

- An existing renderable template (e.g. a local clone or git URL of a doctrine-template-style repo) already provides `{{ORG_NAME}}` / `{{LOCAL_PATH}}` tokens and may ship `.templateignore`; this mission consumes it as-is.
- Git branch may be passed via a dedicated `--branch` option and/or encoded in the TEMPLATE value; conflicting values fail clearly.
- Built-in treatment of the `.templateignore` file itself (whether copied into the output) may follow the template's stated convention that the ignore file is not a deliverable.
- Optional post-render pack validation is not required for init success in this mission.

## Out of Scope

- Authoring, publishing, or changing external doctrine template repositories (including “template maintainer” workflows).
- Implementing a general multi-token templating language beyond `{{ORG_NAME}}` and `{{LOCAL_PATH}}`.
- Changing `doctrine org validate` semantics except as needed to remain compatible with rendered packs.

