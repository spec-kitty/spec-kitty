# Contracts

This directory holds machine-readable contracts that other programs build on,
plus the small Python tools that check them. Each contract is a *module*: a
directory with a root `openapi.yaml`. The sections below fix the conventions
every module follows. Each section carries one example.

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
the path. Two paths that would share a file name (`/a/{b}` and `/a/b`) are refused with
`PATH_FILE_COLLISION`. `contract_resolver.path_file_name` is the one definition of the rule.

## Relative $ref rules

A `$ref` is a relative file path, optionally followed by a JSON pointer. A URL,
an absolute path and a `~` pointer escape are refused, and so is a brace in any
spelling (raw, or percent-encoded once or more): path files are named brace-free.
A schema file carries a `title` equal to
its file name without the extension, and each `schemas/`, `parameters/` and
`responses/` directory lists its files in an `_index.yaml` with a `files:` list.

```yaml
# contracts/mission-status/openapi.yaml
paths:
  /missions/{missionId}:
    $ref: paths/missions_missionId.yaml   # plain relative; no brace, no URL
# inside a schema file: a shared piece, one level up
#   $ref: ../../_shared/schemas/Problem.yaml
```

Refusals: `BAD_REF_FORM` (a URL, an absolute path, a `~` escape or a brace) from
`layout_check.py`, and `BRACE_IN_REF` from the resolver.

## _shared admission

Only cross-module pieces live in `_shared/`, and only under `schemas/`,
`parameters/` and `responses/`. A piece is admitted when all of these hold:

1. It is vocabulary, not a resource: an error shape, a paging cursor, a paging
   parameter. A schema that describes one module's resource stays in that module.
2. More than one module refers to it, or it is written so that any module can
   (today `Problem`, `PageInfo` and `PageCursor`, used by `mission-status`).
3. It never refers back into a module. `layout_check.py` fails with `SHARED_MISUSE`
   when it does.

Example: `contracts/_shared/schemas/Problem.yaml` is the error body every module
returns for a refusal, and a module reaches it with
`$ref: ../../_shared/schemas/Problem.yaml`. A shared piece is versioned through the
modules that refer to it: a change to it is a change to each of them, and shows up
in each module's bundle comparison. `_shared/` has no version of its own.

## Module version and the /api/v1 prefix

Each module declares its own `info.version` in its root `openapi.yaml`, and
modules move independently. Every module lists `servers: [{url: /api/v1}]`, so a
path such as `/missions` is served at `/api/v1/missions`; the path keys never carry
the prefix. The module's `CHANGELOG.md` must hold a heading for the current
`info.version`; `structure_check.py` fails without it.

```yaml
info:
  title: Mission Status API
  version: 1.0.0
servers:
  - url: /api/v1
```

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
schema: its siblings first, then the schema root. A path segment that is not a property
of the node it is on steps through that node's array items or its map value schema, up
to three steps per segment, so `workPackages.wpId` resolves through the array's items.
`Schema.property`
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

Three things are called a lane in conversation, and this tree keeps them apart.

- The **status lane** is the display state of a work package (`planned`, `claimed`,
  `in_progress`, `for_review`, `in_review`, `approved`, `done`, `blocked`,
  `canceled`). It is the glossary term `lane`. The contract spells it `statusLane`
  (`statusLaneCounts`, `fromStatusLane`, `toStatusLane`) and the enum is
  `StatusLane`; the bare stem `lane` is not used.
- A **code lane** is a lane that resolves to a `.worktrees/` lane worktree and a lane
  branch. The **repo-root lane** is the single-lane manifest of a `single_branch`
  Mission. Both come from the glossary page `docs/context/topology.md`.
- **Execution lane** is only the umbrella phrase for what a Mission's `lanes.json`
  records across both (`docs/architecture/execution-lanes.md`). It is not a glossary
  term.

Execution-lane data is not part of version 1 of any contract here. Example: a work
package payload carries `"statusLane": "for_review"`, which says nothing about which
worktree the work happens in.

## Workflow phase and glossary phase

Three different things use the word phase, and none of them is the glossary term
`phase` (`.kittify/glossaries/spec_kitty_core.yaml`, a grouping container for
mission primitives).

- The **workflow phase** of a Mission is a step of its workflow: `specify`, `plan`,
  `tasks`, `implement`, `review`. The contract field is `phases` (the name is kept
  because the issue that asked for it uses it); each entry has a `status` and a
  `basis`.
- The **phase label** is the optional free-text `phase` key in a work package's
  frontmatter. The contract field is `phaseLabel`.
- The glossary `phase` is neither of these.

Example: `MissionDetail.phases[0]` is `{name: specify, ...}` and describes a workflow
step, while `WorkPackage.phaseLabel` is whatever grouping text the plan's author
wrote, or null.

## Topology enum

The `Topology` enum (`lanes`, `single_branch`, `coord`, `lanes_with_coord`,
`unknown`) is the shape stored in a Mission's `meta.json`. It is unrelated to
`MissionStatus.topology` in the status aggregate, which is a two-value legacy or
coordination vocabulary outside this contract. A Mission with no stored topology, or
a stored value outside the four known shapes, is reported as `unknown`.

Example: a Mission whose `meta.json` stamps `lanes_with_coord` reads
`"topology": "lanes_with_coord"`; a Mission with no stamp reads `"unknown"`.

## The bundle is a build product

A bundle is a module resolved into one `openapi.yaml`. The Python resolver
(`contracts/tools/contract_resolver.py`, written by `bundle.py`) produces it; the
output is byte-deterministic, so the same files always give the same bytes. The
bundle is built in CI and by the local command below, is the file a release
publishes, and is never committed. The layout check fails with `TRACKED_BUNDLE` when
a module holds one.

Example: after the local command below, `<out>/bundle/mission-status/openapi.yaml`
exists under the directory you named; the repository tree is unchanged.

## Validate and bundle locally

The pinned JVM toolchain (the openapi-generator Gradle plugin 7.25.0 under Gradle
8.14.5, with strict dependency verification) validates both the split root and the
bundle, and generates a TypeScript client from the bundle as a consumer check. It
needs a JDK on `PATH` (the workflow uses Temurin 21) and network access to fetch the
pinned tools. Neither Node nor pytest is involved.

```bash
.venv/bin/python contracts/tools/install_tools.py --pins contracts/tools/pins.json --dest "$HOME/.cache/contract-tools" --only gradle
PATH="$HOME/.cache/contract-tools/gradle-8.14.5/bin:$PATH" \
  .venv/bin/python contracts/tools/bundle.py --root contracts --out "$HOME/.cache/contract-out"
```

`install_tools.py` verifies each download against its pinned sha256 before it
unpacks anything. `--out` must lie outside the repository. The last line of
`bundle.py` is a `counts:` line; exit 0 is a pass, 1 a violation, 2 means a tool was
missing. Add `--bundle-only` to write and check only the bundle, with no JDK and no
Gradle.

The other tools run as bare scripts over the same tree, for example
`.venv/bin/python contracts/tools/layout_check.py --root contracts`. Two further
checks run in CI only, because they download prebuilt binaries: `vacuum` 0.30.6
(lint) and `oasdiff` 1.32.1 (breaking-change comparison), each pinned by sha256 in
`contracts/tools/pins.json`.

## Markdown lint is advisory

The repository's markdown lint job (the router's `markdownlint` job) ends in
`|| true`, so it is advisory and cannot fail a change. This README and each module's
`CHANGELOG.md` are checked for required headings by a separate structural check,
`contracts/tools/structure_check.py`, which the Contracts workflow runs:

```bash
.venv/bin/python contracts/tools/structure_check.py --root contracts
```

## Not the CLI contract registry

`src/specify_cli/contracts/` is the CLI's shared-contract registry. It is
unrelated to this top-level `contracts/` tree.

## Board columns are a consumer convention

The contract reports the nine status lanes and their raw counts, with no
grouping. Which lanes a screen puts in which board column is a convention of that
consumer, not part of any contract here. The dashboard this contract replaces, for
instance, showed `claimed` and `in_progress` together as "doing", `for_review` and
`in_review` together as "for review", and `blocked` under "planned". Another
consumer may group them differently and is still reading the same contract.

## Versioning rule

A module's `info.version` is semantic.

- A **breaking** change moves the major version: removing a path, a response
  property or an enum value, making a parameter required, narrowing a type.
  Making a response property optional or nullable counts too, because a generated
  client changes its type.
- An **additive** change moves the minor version.
- A **documentation-only** change moves the patch version.

The breaking-change job writes the bundle of the last release tag and of the
candidate and compares them with `oasdiff`. It fails with `BREAKING_WITHOUT_MAJOR`
when a breaking change leaves the major where it was, and with
`BUNDLE_CHANGED_VERSION_SAME` when the bundle changed and `info.version` did not
move at all. Elements marked `x-provisional` are removed from both sides first;
a difference that exists only because of them never fails and is reported in its own
section.

Until a release tag exists there is no baseline. The one allowed state is
`info.version: 1.0.0` together with a `## 1.0.0` heading in the module's
`CHANGELOG.md`; the job prints `NO_BASELINE_INITIAL_VERSION` and counts it, so the
state is never silent. A release is a tag `contract-<module>-v<semver>` (no leading
`v` on the module part; for example `contract-mission-status-v1.0.0`), pushed to
trigger the Contracts Release workflow. It publishes `openapi.yaml` and
`openapi.yaml.sha256` as release assets, and only a tag push publishes: the
Contracts workflow runs the same steps as a dry run on a pull request and cannot
publish.

## Residual risk: handle-shaped strings

A handle-shaped string can still be a person's account name: the status domain has
recorded an operating-system or git user name in actor-like fields before. The
contract cannot prove that a handle is not a person's name. The shape rule on
`ActorHandle` and the leak scan over the examples and over every payload the reality
check projects reduce that risk and do not remove it. Do not read a clean scan as a
guarantee.

Example: the shape rule accepts the handle `claude` and, equally, a string such as
`jdoe`; only a person can say which of them is an account name.

## Reader-author warning

The reality check projects every Mission in the repository (at delivery 541
Missions, 3156 work package payloads and 23594 events) through the status readers and
validates each projection against the contract. If you edit a status reader, run it
locally first:

```bash
PWHEADLESS=1 .venv/bin/python -m pytest -q tests/contract/test_mission_status_reality.py
```

CI will not always run it for you. A reader edit selects no job that runs the reality
check, and a change confined to `tests/contract/**` selects no corpus job either
(accepted risks, seen on a real pull request, which needed a manual run). The safety
nets are the push-to-`main` run and a manual full-mode run of the router on your
branch: `gh workflow run ci-router.yml -f mode=full --ref <branch>`.

The check is read-only and never writes Mission state. It lets the status snapshot
and the work package files disagree for a counted number of Missions (a ratchet,
ceiling 52, tracked in #5579, to drain by 2026-12-31); a new disagreement fails it.

## Preview tags

Before a release exists, three lightweight tags in the namespace
`preview/mission-status/p<N>` were prepared as stable references for a consumer, but
have not been published; until a maintainer pushes them, a consumer pins a commit.
`p0` is the unvalidated shape, a preview with no stability promise; `p1` marks the
first commit whose Contracts workflow run is green, when generating a client for
development is reasonable; `p2` is the pin-grade point, with the reality check green
too. The namespace is outside `contract-<module>-v<semver>` and the CLI's `v*.*.*`, so
no release workflow reacts to it. Every shape change after `p0` and before the first
release is listed in the module's `CHANGELOG.md` under a `Pre-release shape change`
line.
