# Contracts

This directory holds machine-readable contracts that other programs build on,
plus the small Python tools that check them. Each contract is a *module*: a
directory with a root `openapi.yaml`. The sections below fix the conventions
every module follows. Sections marked "skeleton" are completed with the
documentation work of the Mission that introduced this tree.

## Layout

```text
contracts/
  README.md
  _shared/                 pieces shared by more than one module
    schemas/  parameters/  responses/   (each with an _index.yaml)
  <module>/
    openapi.yaml           info, servers, tags and the path-to-file map only
    CHANGELOG.md
    paths/  schemas/  parameters/  responses/  examples/
  tools/                   Python checks and libraries; not a module
```

A module is a direct subdirectory holding a root `openapi.yaml`. `_shared`,
`fixtures`, `gradle` and `tools` are never modules. `contracts/fixtures/` holds
older hand-written hand-off fixtures and is not touched by this tree's tooling.

## Path file naming

One file per path item under `paths/`. The file name is the path with its leading
slash dropped, each `/` turned into `_` and each `{param}` turned into `param`
(braces dropped, the parameter name kept), plus `.yaml`: the path
`/missions/{missionId}/events` lives in `paths/missions_missionId_events.yaml`.
The path key inside the root `openapi.yaml` keeps the real template, and the root
maps each path to its file with a plain relative `$ref` and holds nothing else about
the path. Two paths that would share a file name (`/a/{b}` and `/a/b`) are refused.

## Relative $ref rules

A `$ref` is a relative file path, optionally followed by a JSON pointer. A URL,
an absolute path and a `~` pointer escape are refused, and so is a brace in any
spelling (raw, or percent-encoded once or more): path files are named brace-free.
A schema file carries a `title` equal to
its file name without the extension, and each `schemas/`, `parameters/` and
`responses/` directory lists its files in an `_index.yaml` with a `files:` list.

## _shared admission

Only cross-module pieces live in `_shared/`, and only under `schemas/`,
`parameters/` and `responses/`. A shared piece never refers back into a module.
Skeleton: the full admission criteria are written with the documentation work.

## Module version and the /api/v1 prefix

Skeleton: each module declares its own `info.version`, and its paths are served
under `/api/v1`.

## x-source, x-derived and x-provisional

Three extensions say where a property comes from, how it is computed, and that it
is not yet stable. `citation_check.py` and `provisional_check.py` enforce the
grammar below.

**x-source** is `{path, symbol}` (an optional `line` is allowed and never checked).
`path` is a repository-relative file that git tracks. `symbol` resolves by defined
name, never by text. In a Python file it is a `class`, a `def` or an assignment
target at module or class level, found in the syntax tree, including an annotated
target without a value (`content_invariant: str`); write it bare
(`content_invariant`) or dotted (`TailCursor.content_invariant`). A name that occurs
only in a comment, a string, a function body or as a substring of another name does
not resolve. In a YAML or JSON file it is a dotted key path that must exist, for
example `{path: .kittify/config.yaml, symbol: project.slug}`.

**x-derived** is `{rule, inputs}`. `rule` is non-empty prose. `inputs` is a non-empty
list whose items are either contract-field property paths (strings) or code inputs
`{path, symbol}` resolved exactly like an `x-source`; a list may mix both. A bare
property path (`statusLaneCounts.blocked`, `items`) is relative to the property's own
schema: its siblings first, then the schema root. `Schema.property`
(`MissionHead.createdAt`) names a property of another schema of the same module.
Free text, an empty rule, empty or missing inputs and an input that does not resolve
are each a failure.

**One citation per property.** Every property of every resource schema carries
exactly one of `x-source` and `x-derived`, at any depth: nested objects, array
`items`, map values, `allOf`/`oneOf`/`anyOf` branches and properties reached only
through a `$ref`. A citation written on the root of a referenced schema file is
inherited by every property that refers to it, unless the property states the other
kind itself. A property that an `allOf` branch redeclares only to narrow it (a
`const` or `enum` refinement of a property declared earlier) is a refinement, not a
new property, and needs no citation of its own. The pieces under `_shared/`
(`Problem`, `PageInfo`, the cursors) are cross-module vocabulary, not resource
schemas of the module that uses them: they are not counted and need no citations.
The check reports, without failing, any single citation shared by more than five
properties, so reuse stays visible.

**x-provisional** is `{open_decision: <text>}` on a property, a schema, a parameter or
an operation, and the text names what is undecided (at least four words). The
properties `staleness` and `nextAction` must carry it and must be nullable. Every
`x-provisional` element is also named in the `Provisional` section of the module's
`CHANGELOG.md`: its own name (the property name, schema title, parameter name or
operation path) appears there as a whole word.

## Lane terminology

Skeleton: status lane, code lane and repo-root lane are different things; the
umbrella phrase for the code-bearing ones is execution lane.

## Workflow phase and glossary phase

Skeleton: the workflow phase of a Mission and the glossary term `phase` are
different concepts.

## Topology enum

Skeleton: the `Topology` enum is the shape stored in a Mission's `meta.json` and
is unrelated to the `topology` field of the status aggregate.

## The bundle is a build product

A bundled document, a module resolved into one file, is built in CI and by the
local command below. It is never committed, and the layout check fails when one
is tracked.

## Validate and bundle locally

Skeleton: the one local command that validates and bundles a module. It needs a
JDK and network access to fetch the pinned tools.

## Markdown lint is advisory

The repository's markdown lint job is advisory and cannot fail a change. This
README and each module's `CHANGELOG.md` are checked for required headings by a
separate structural check instead.

## Not the CLI contract registry

`src/specify_cli/contracts/` is the CLI's shared-contract registry. It is
unrelated to this top-level `contracts/` tree.

## Board columns are a consumer convention

Skeleton: the grouping of status lanes into board columns is a convention of a
consumer, not part of any contract here.

## Versioning rule

Skeleton: how a module's `info.version` changes with each kind of edit, and what
counts as a breaking change.

## Residual risk: handle-shaped strings

Skeleton: a handle-shaped string can still be a person's account name. The shape
rules and the value scan reduce that risk and cannot remove it.

## Reader-author warning

Skeleton: what an author of a reader of a contract must know, and the local
command that checks a reader against the contract.

## Preview tags

Skeleton: the tag namespace used to mark an early, unreleased state of a module.
