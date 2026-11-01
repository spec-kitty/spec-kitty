# Implementation Plan: Register an org Charter Pack with a project from the CLI

**Branch**: `issue-6267-charter-org-pack-registration` | **Date**: 2026-11-01 | **Spec**: [spec.md](./spec.md)
**Input**: Mission specification from `kitty-specs/charter-org-pack-registration-01M6BTTJ/spec.md`
(GitHub issue #6267)

## Summary

Add `spec-kitty charter org add <name> --local-path <dir> [--url <url> --ref <ref>]
[--source-type <t>] [--subdir <dir>] [--force]` and `spec-kitty charter org remove <name>`, so a
project can be pointed at an org Charter Pack without hand-editing `.kittify/config.yaml`. The
write goes through one seam in the module that already owns the `charter_packs.org.packs` shape
(`charter.offering.drg.org_pack_config`), which serializes with ruamel's comment-preserving
round-trip YAML and writes atomically; the CLI command validates the pack with the same
`validate_pack_with_org_charter` door `charter org validate` uses before anything is written.

## Technical Context

**Language/Version**: Python 3.11 (repo floor; `pyproject.toml` `requires-python`)
**Primary Dependencies**: `typer` (CLI), `pydantic` v2 (`OrgPackConfig`), `ruamel.yaml` (already the
config reader/writer in this module), `kernel.atomic.atomic_write`
**Storage**: `.kittify/config.yaml` (YAML, hand-comment-bearing, CLI-owned)
**Testing**: `pytest` + `typer.testing.CliRunner`; existing owner test file
`tests/cli/test_doctrine_org_commands.py` (markers `unit`, `fast`)
**Target Platform**: Linux/macOS/Windows CLI
**Project Type**: single project — `src/charter/offering/**` (shape authority below the charter
service) + `src/specify_cli/cli/commands/charter/org.py` (CLI door)
**Performance Goals**: command completes under 1 second on a 100-artifact pack (no network)
**Constraints**: offline; no new config keys; never delete pack directories; never write outside
`.kittify/config.yaml`
**Scale/Scope**: two new subcommands, one write seam (~90 lines of production code), one test file

## Charter Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

| Charter rule | How this plan satisfies it |
|---|---|
| Single canonical authority | The shape authority stays `charter/offering/drg/org_pack_config.py`; no second schema, no new key spelling (C-001/C-002). |
| Architectural alignment | Read and write of the registry shape live in the same offering module; the CLI layer only builds the `OrgPackConfig` and renders. `charter ↛ specify_cli` is preserved (`kernel.atomic` is the shared write primitive). |
| ATDD-first | Each acceptance scenario in `spec.md` maps to a `CliRunner` test that exercises the real command; the refusal tests pair with a positive control on the same fixture. |
| Terminology canon | Mission/Charter Pack vocabulary reused verbatim; no new nouns ("registration" is described, not coined as an entity). |
| Standing Order #4 (red-first) | The defect is the missing command: the test file is written first against the pre-existing entry point (`charter org` Typer app) and fails on `Error: No such command 'add'`. |
| Standing Order #8 (mission hygiene) | One issue-matrix row for #6267; review by a distinct role from the implementer. |
| `NO_FULL_HEAVY_SUITES_IN_MISSION` | Only `tests/cli/test_doctrine_org_commands.py`, the new registration test file, and the named architectural gates the diff implicates are run locally. |
| Docs freshness | `docs/api/cli-commands.md` regenerated for the touched command paths only; `docs/changelog/CHANGELOG.md` `[Unreleased]` entry; `scripts.docs.check_docs_freshness --ci` verified. |

No violations; Complexity Tracking stays empty.

## Project Structure

### Documentation (this mission)

```
kitty-specs/charter-org-pack-registration-01M6BTTJ/
├── plan.md           # This file
├── spec.md           # Mission specification
├── tasks.md          # Work packages (/spec-kitty.tasks)
├── tasks/            # Task index + status
└── traces/           # tooling-friction.md, approach.md, design-decisions.md
```

### Source Code (repository root)

```
src/
├── charter/offering/drg/org_pack_config.py   # + register_org_pack / unregister_org_pack (write seam)
├── specify_cli/cli/commands/charter/
│   ├── org.py                                # + `add` / `remove` subcommands
│   └── authoring.py                          # fetch's empty-registry message -> new command
docs/
├── api/cli-commands.md                       # regenerated sections for the two new paths
├── api/charter-commands.md                   # `org` row in the subcommand table
├── guides/how-to/governance/create-an-org-doctrine-pack.md   # Step 8 leads with the command
└── changelog/CHANGELOG.md                    # [Unreleased] entry
tests/cli/
├── test_charter_org_registration.py          # new: accept + refuse + round-trip
└── test_doctrine_org_commands.py             # existing owner file (unchanged behaviour)
```

**Structure Decision**: single project. The write seam belongs in the offering module that already
parses this shape, because a write path anywhere else would be a second authority over
`charter_packs.org.packs`. The CLI module owns option parsing, validation dispatch and rendering.

## Design decisions

1. **Where the write lives.** `charter/offering/drg/org_pack_config.py` gains
   `register_org_pack(repo_root, pack, *, replace=False)` and `unregister_org_pack(repo_root, name)`.
   Both load the whole config with `YAML()` (round-trip, comment/quote/order preserving), mutate only
   the `charter_packs.org.packs` list, and write through `kernel.atomic.atomic_write`. Rejected
   alternative: a new `org_pack_registry_write.py` module — it would split the shape's read and
   write authority for no gain.
2. **Read strictly before writing.** `load_pack_registry(repo_root, strict=True)` runs first, so a
   config that cannot be read is never rewritten (FR-008). The plain read path keeps its lenient
   behaviour untouched.
3. **Validation at the effective root.** A `--local-path` value may be relative, `~`-prefixed or
   `${VAR}`-templated; validation resolves it through `OrgPackConfig.effective_root(repo_root)`,
   the same seam the readers use. A templated path is stored verbatim (never expanded, never frozen).
4. **Existence rule.** Without `--url` the pack root must exist (a local pack that is not there is a
   typo; nothing could ever materialize it) and must validate. With `--url` the root may be absent
   (`charter fetch` materializes it) and validation is skipped with a printed follow-up; if it does
   exist it is validated like the local case.
5. **Source fields.** `--url` implies `source_type` (default `git`, overridable with
   `--source-type git|https|artifactory|api`) and accepts `--ref`; `--ref`/`--source-type` without
   `--url` is refused. Only `OrgPackConfig`'s declared fields are ever written (C-001).
6. **Reserved names.** `built-in` and `project` are tier names the offering resolves by name; an org
   pack may not shadow them.
7. **Duplicate handling.** Refuse unless `--force`; `--force` replaces the entry in place, so the
   declaration order (which sets the org layer index) does not change.
8. **Remove cleans up empty scaffolding.** Remove the entry; if `org.packs` is then empty drop `org`,
   and if `charter_packs` is then empty drop it. Byte-round-trip stability (NFR-002) is asserted by
   the add→remove test on a commented config.
9. **`--json` payloads.** `add`: `{pack: {...}, config: <path>, replaced: bool, validated: bool,
   fetched: <bool>}`. `remove`: `{removed: <name>, config: <path>}`. Refusals keep the existing
   coded-error rendering style used by `charter pack path`.

## Implementation Concern Map

### IC-01 — Registry write seam

- **Purpose**: One owner for mutating `charter_packs.org.packs`, preserving format and writing atomically.
- **Relevant requirements**: FR-002, FR-007, FR-008, NFR-001, NFR-002, C-001, C-002
- **Affected surfaces**: `src/charter/offering/drg/org_pack_config.py`
- **Sequencing/depends-on**: none
- **Risks**: ruamel round-trip must not reformat unrelated blocks (indent/mapping settings match the
  module's existing `_yaml()`); dropping empty parent blocks must not touch sibling keys.

### IC-02 — CLI door: `charter org add` / `charter org remove`

- **Purpose**: Turn the operator's intent into a validated `OrgPackConfig` and report the outcome.
- **Relevant requirements**: FR-001, FR-003, FR-004, FR-005, FR-006, FR-009, FR-010, NFR-003, NFR-004, C-003, C-004
- **Affected surfaces**: `src/specify_cli/cli/commands/charter/org.py`
- **Sequencing/depends-on**: IC-01
- **Risks**: option validation order (all mutual-exclusion and reserved-name checks before any write);
  project-root resolution outside a project; keeping `--help` fast (heavy imports stay lazily inside
  the command bodies, as the module already does).

### IC-03 — Guidance, docs and changelog

- **Purpose**: Stop documenting the hand edit the issue is about, and record the change.
- **Relevant requirements**: FR-011, SC-004
- **Affected surfaces**: `src/specify_cli/cli/commands/charter/authoring.py` (fetch's "no packs
  configured" message and hint), `src/specify_cli/charter_packs/snapshot.py` (`_build_source` error
  text stays factual — no change needed), `docs/api/cli-commands.md`,
  `docs/api/charter-commands.md`, `docs/guides/how-to/governance/create-an-org-doctrine-pack.md`,
  `docs/changelog/CHANGELOG.md`
- **Sequencing/depends-on**: IC-02 (the text names the flags that actually exist)
- **Risks**: `docs/api/cli-commands.md` is a generated file inside a marker envelope — regenerate
  the touched sections from a temp build rather than rebuilding the whole reference (other agents on
  this host rewrite the shared CLI asset cache concurrently).

## Complexity Tracking

*No charter violations to justify.*

| Violation | Why Needed | Simpler Alternative Rejected Because |
|-----------|------------|-------------------------------------|
| — | — | — |
