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

Skeleton: the three extensions that say where a property comes from, how it is
computed, and that it is not yet stable.

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
