# Mission Specification: Register an org Charter Pack with a project from the CLI

**Mission Branch**: `issue-6267-charter-org-pack-registration`
**Created**: 2026-11-01
**Status**: Draft
**Input**: GitHub issue #6267 — "No CLI command registers an org Charter Pack with a project (only a hand edit of .kittify/config.yaml)"

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Register a local org pack without editing config by hand (Priority: P1)

A governance maintainer has an org Charter Pack on disk (authored with `charter org init`, or
checked out from the org's doctrine repository) and wants the current project to use it. Today
the only way is to open `.kittify/config.yaml` and hand-write a `charter_packs.org.packs[]`
entry — a CLI-managed file the CLI itself tells people not to edit. With this mission the
maintainer runs one command, the pack is validated exactly as `charter org validate` validates
it, and the entry appears in the config in the canonical shape.

**Why this priority**: it is the case the issue names first, it is what the three blocked
acceptance scenarios need (a project arranged with an org pack without writing `.kittify/`
files), and it delivers the whole value of the issue on its own.

**Independent Test**: in a temporary project, run `spec-kitty charter org add acme --local-path <dir>`
against a valid scaffolded pack, then assert `spec-kitty charter pack list` reports the pack and
`spec-kitty charter fetch --pack acme --dry-run` resolves its root — with no `.kittify/` file
written by the test.

**Acceptance Scenarios**:

1. **Given** a project with no org pack configured and a valid pack at `./packs/acme`, **When**
   the operator runs `spec-kitty charter org add acme --local-path ./packs/acme`, **Then** the
   command exits 0 and `.kittify/config.yaml` carries exactly one `charter_packs.org.packs` entry
   `{name: acme, local_path: ./packs/acme}`.
2. **Given** that same project and a directory `./packs/broken` that fails org pack validation,
   **When** the operator runs `charter org add broken --local-path ./packs/broken`, **Then** the
   command exits 1, names the validation errors, and `.kittify/config.yaml` is byte-identical to
   before the command (positive control: the same command on `./packs/acme`, same fixture, exits 0).
3. **Given** a project that already has an `acme` entry, **When** the operator repeats the add
   without `--force`, **Then** the command exits 1 naming `--force`, and the config is unchanged.

---

### User Story 2 - Register a remote pack that `charter fetch` will materialize (Priority: P1)

A maintainer wants the project pointed at the org's published pack repository, not at a copy they
already have on disk. `charter fetch` can already clone/refresh a configured remote pack, but the
entry must exist first — which again means hand-editing config.

**Why this priority**: without it, the one remaining hand-edit case (the documented remote-source
flow) survives, so the command would only half-close the issue.

**Independent Test**: run `charter org add acme --local-path <dest> --url <git-url> --ref v1.0.0`,
assert the written entry carries `source_type`, `url` and `ref`, assert the command did not touch
the network, and assert `charter fetch --pack acme --dry-run` reports the configured repo and
destination.

**Acceptance Scenarios**:

1. **Given** a project and a destination directory that does not exist yet, **When** the operator
   runs `charter org add acme --local-path ./.kittify/org/acme --url https://example.com/acme/doctrine.git --ref v1.0.0`,
   **Then** the command exits 0, writes `{name, local_path, source_type: git, url, ref}`, and
   prints the `charter fetch` follow-up.
2. **Given** the same project, **When** the operator passes `--ref v1.0.0` without `--url`,
   **Then** the command exits 1 naming the missing `--url` and writes nothing.

---

### User Story 3 - Retire an org pack registration (Priority: P2)

A maintainer stops using an org pack and wants the project to stop loading it. Editing the list by
hand is error-prone (wrong indentation silently disables the whole org layer). `remove` deletes
exactly that entry and leaves the rest of the file alone.

**Why this priority**: it is the second half of the issue's proposal. It is P2 because add alone
already removes the hand edit from the primary flow, but a registration command with no way back
is an incomplete lifecycle.

**Independent Test**: add two packs, remove one, assert the other survives with its comments and
its sibling config sections intact, and assert `charter pack list` no longer reports the removed
pack.

**Acceptance Scenarios**:

1. **Given** a project with `acme` and `security` registered, **When** the operator runs
   `charter org remove acme`, **Then** the command exits 0 and only the `security` entry remains.
2. **Given** a project with no `missing` entry, **When** the operator runs `charter org remove missing`,
   **Then** the command exits 1, lists the configured names, and the config is byte-identical.
3. **Given** a config where the operator added comments around the org block, **When** an entry is
   added and then removed, **Then** the file is byte-identical to the original.

---

### Edge Cases

- A `--local-path` that exists but is a regular file, not a directory → refused (exit 1), nothing written.
- An org pack registered with a `${VAR}`/`~` `local_path` → the literal token is stored verbatim
  (never expanded, never frozen to a machine path) and validation resolves it the same way reads do;
  an unset variable is reported as the existing named `OrgPackEnvVarUnsetError` condition, not a crash.
- `charter_packs.org.packs` present but malformed (duplicate names, bad shape) → the command fails
  closed and writes nothing, rather than overwriting a config it could not read.
- No org block at all → created; `charter_packs` absent entirely → created.
- A pack name containing only whitespace, and the reserved names `built-in` and `project` → refused.
- Removing the last registered pack → the empty `charter_packs.org.packs` block is cleaned up so the
  file does not keep an empty scaffold.
- An `--url` value that is not a supported source type / a `--source-type` outside
  `git|https|artifactory|api` → refused before anything is written.
- Running outside a spec-kitty project → exit 1 with the existing "could not locate project root" style message.

## Requirements *(mandatory)*

### Functional Requirements

| ID | Title | User Story | Priority | Status | Delivery | No-op passable? |
|----|-------|------------|----------|--------|----------|-----------------|
| FR-001 | `charter org add` registers a local pack | As a governance maintainer, I want one command to register an on-disk org pack so that I never hand-edit `.kittify/config.yaml`. | High | Open | [build] | no |
| FR-002 | Registration writes the canonical entry shape | As the CLI, I want the entry written with exactly the `OrgPackConfig` fields (`name`, `local_path`, and optionally `source_type`, `url`, `ref`, `subdir`) so that the reader and writer cannot drift. | High | Open | [ratchet] | no |
| FR-003 | Validation precedes the write | As a maintainer, I want an invalid pack refused before the config changes so that a typo cannot silently disable the org layer. | High | Open | [build] | no |
| FR-004 | Duplicate names are refused; `--force` replaces | As a maintainer, I want a repeated add to fail loudly so that I do not overwrite a working registration by accident, and I want an explicit way to update it. | Medium | Open | [build] | no |
| FR-005 | Reserved and malformed inputs are refused | As a maintainer, I want reserved names (`built-in`, `project`), an invalid `--subdir`, and `--ref` without `--url` refused so that the registry cannot be put into a state the reader rejects. | Medium | Open | [build] | no |
| FR-006 | Remote packs register without a local copy | As a maintainer, I want to register a git/https source whose snapshot is not fetched yet so that `charter fetch` has an entry to work from. | High | Open | [build] | no |
| FR-007 | `charter org remove` deletes exactly one entry | As a maintainer, I want to retire a registration without touching the rest of the file so that unrelated configuration survives. | Medium | Open | [build] | no |
| FR-008 | Unreadable or malformed config fails closed | As a maintainer, I want add/remove to refuse when the existing org config cannot be read so that the command never destroys state it could not parse. | Medium | Open | [build] | no |
| FR-009 | Both commands work without a network | As an operator in an air-gapped CI, I want registration to be purely local so that arranging a project needs no credentials or connectivity. | Medium | Open | [ratchet] | no |
| FR-010 | Machine-readable output | As an automation author, I want `--json` on both commands so that a scenario or script can assert the result without parsing prose. | Low | Open | [build] | no |
| FR-011 | Hand-edit guidance points at the command | As a user of `charter fetch` and the org-pack how-to, I want the "no packs configured" message and the docs to name the new command so that the documented path is not the hand edit the issue is about. | Medium | Open | [build] | no |

### Non-Functional Requirements

| ID | Title | Requirement | Category | Priority | Status |
|----|-------|-------------|----------|----------|--------|
| NFR-001 | Atomic config write | A failed write leaves `.kittify/config.yaml` byte-identical to its pre-command content (no partial or truncated file), proven by a test that fails the write. | Reliability | High | Open |
| NFR-002 | Round-trip byte stability | Adding an entry and then removing it restores `.kittify/config.yaml` byte-for-byte, including comments, key order and quoting, so the command is format-preserving, not re-serializing. | Reliability | High | Open |
| NFR-003 | Bounded command cost | `charter org add`/`remove` complete in under 1 second on a pack of 100 artifacts with no network access (measured by the CLI test's wall clock, generous margin over a local validate). | Performance | Medium | Open |
| NFR-004 | Structured failure surface | Every refusal exits 1 and names the offending value (name, path, option) on stderr/stdout; no traceback reaches the user for a bad input. | Usability | Medium | Open |

### Constraints

| ID | Title | Constraint | Category | Priority | Status |
|----|-------|------------|----------|----------|--------|
| C-001 | No new config shape | Only the fields `OrgPackConfig` already declares may be written; no new keys, no second spelling, no legacy key. | Technical | High | Open |
| C-002 | Single canonical reader | The command must read through `load_pack_registry`/`PackRegistry`, validate through `validate_pack_with_org_charter`, and reuse `OrgPackConfig` validation — no second parser or schema. | Technical | High | Open |
| C-003 | No destructive filesystem work | `remove` edits config only; it never deletes the pack directory, and the command prints the path it leaves behind. | Technical | High | Open |
| C-004 | Surface stays under `charter org` | No new top-level command group; no change to `charter fetch`, `charter org validate`, or pack resolution semantics. | Technical | Medium | Open |
| C-005 | Scope boundary | The `#6101` acceptance-scenario migration (#6266 wave 3) and the wider install/update/uninstall lifecycle (#5243) are out of scope. | Business | Medium | Open |

### Key Entities

- **Org pack registration**: one entry in `.kittify/config.yaml` under `charter_packs.org.packs[]`;
  identity is the `name`; carries `local_path` (verbatim, possibly env-templated) plus optional
  `source_type`, `url`, `ref`, `subdir`. Read by `PackRegistry`.
- **Pack root**: `local_path` expanded and resolved against the project root, joined with `subdir`;
  the directory `charter org validate` validates and `charter fetch` writes.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: An operator can take a project from no org configuration to a pack that `charter pack list` reports, with zero hand edits to `.kittify/config.yaml` — proven by a CLI test that never writes a `.kittify/` file itself. — [build] · no-op passable: no
- **SC-002**: `add` followed by `remove` leaves the config file byte-identical (SHA-256 equal before and after) on a config carrying comments and two other packs. — [build] · no-op passable: no
- **SC-003**: An invalid pack is refused with exit 1 and an unchanged config, while the same command on a valid pack in the same fixture exits 0 — the refusal assertion is paired with that positive control. — [build] · no-op passable: no
- **SC-004**: No documented flow requires hand-editing `charter_packs.org.packs` — the org-pack how-to and the `charter fetch` empty-registry message both name the new commands. — [build] · no-op passable: no
