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
`info.version`; `structure_check.py` fails without it. A version that is not yet
released carries the `-SNAPSHOT` suffix (see [Versioning rule](#versioning-rule)), and
its CHANGELOG heading carries it too.

```yaml
info:
  title: Mission Status API
  version: 1.0.0-SNAPSHOT
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

**Consumer note: generating a client with stable type names.** The released bundle is
fully dereferenced by design: every `$ref` is inlined, so one file is enough and a
consumer needs no resolver. A generator then has no schema names to reuse and
invents its own (an inline schema becomes `InlineObject3`, and a name can move when
the contract grows). A consumer that wants stable type names generates from the split
`contracts/mission-status/openapi.yaml` instead, which keeps its `$ref`s, so each
named schema file stays one named type. Pin a commit or a release tag, and read the
split tree from there. This is advice, not something CI checks: the Contracts workflow
generates its TypeScript client from the bundle only, so generating from the split root
is a path CI does not exercise.

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

`verify_pins.py` refuses a run that hashed nothing (`CHECKSUMS_UNVERIFIED`, exit 2), so
the workflow's `verify-pins` job calls it as `verify_pins.py --fetch`, which downloads
each pinned artefact over https and checks it against its sha256. A job that has
already downloaded the tools passes the directory instead, `--artifacts DIR`; a bare
call would hash nothing and fail. `--pins-only` checks the pins without hashing and is
not what CI runs.

`gradle_pin_check.py` closes the other half of that pin: `verify_pins.py` never reads the
build, so the generator plugin version in `contracts/build.gradle`, in
`contracts/gradle/verification-metadata.xml` and in any wrapper or `gradle-version`
input must equal the version `pins.json` pins (`GRADLE_PIN_MISMATCH`, exit 1; a file it
cannot read or parse is exit 2). It runs in the same `verify-pins` job and needs no
download.

The other tools run as bare scripts over the same tree, for example
`.venv/bin/python contracts/tools/layout_check.py --root contracts`. Two further
checks run in CI only, because they download prebuilt binaries: `vacuum` 0.30.6
(lint) and `oasdiff` 1.32.1 (breaking-change comparison), each pinned by sha256 in
`contracts/tools/pins.json`.

Every lint plant under `contracts/tools/fixtures/vacuum/` declares the rule it must
fail with on its first line, `# rule: <rule id>`, so a variant plant may be named
`<rule id>-<variant>.yaml`. The `lint` job derives the expected rule from that header,
not from the file name, and fails a plant with no header. `run_negative_cases.py`
accepts only an UPPER_SNAKE code or a rule id of the ruleset as the code a plant
expects; a generic word such as `error` is refused because it matches almost any
output. `install_tools.py` reports a Python without tarfile extraction filters as
`UNSUPPORTED_INTERPRETER` (an environment problem), never as `UNSAFE_ARCHIVE`.

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

**Response schemas are closed.** Every response object schema declares
`additionalProperties: false` (or `unevaluatedProperties: false` where it is
composed), so a consumer may rely on the set of properties. A change to the shape of
a response therefore ships as a new schema version and a new published release.
`breaking_check.py` enforces this: `oasdiff` reports a property added to a response at
level INFO, which would let it through, so the check raises those change ids
(`response-optional-property-added`, `response-required-property-added` and their
write-only forms) to breaking, and an added response property needs a major move like
a removal does. The same holds for the other ways a response grows: a property added
through a new `allOf` branch (`response-body-all-of-added`,
`response-property-all-of-added`; a new `oneOf` or `anyOf` branch is already an error
in `oasdiff`), a new response status code (`response-success-status-added`,
`response-non-success-status-added`), a new response media type
(`response-media-type-added`) and a new response header (`response-header-added`).
Three more rules close the remaining ways a response grows. A new `default` or range
(`4XX`/`5XX`) response is breaking (`response-key-added`); `oasdiff` does not report it,
so `breaking_check.py` finds it by comparing each operation's response keys itself. A
write-only property that becomes readable is breaking
(`response-optional-property-became-not-write-only`,
`response-required-property-became-not-write-only`), because the response now carries
it. Added `patternProperties` on a response schema are breaking, because they admit
properties the schema did not name. A request-side optional addition, such as a new
optional query parameter, stays additive.

**Unreleased versions carry `-SNAPSHOT`.** A version that has no release tag yet is
written `1.0.0-SNAPSHOT`, as in Maven and Gradle: the work in progress of `1.0.0`, which
sorts below `1.0.0`. `breaking_check.py` reads `X-SNAPSHOT` as the work in progress of
`X`, so a snapshot of a later major excuses a breaking change and a snapshot of the
released version itself fails with `VERSION_DECREASED` once the bundle changed. The
CHANGELOG heading carries the suffix too (`## 1.0.0-SNAPSHOT`). The release commit
drops the suffix from `info.version` and from the heading. `release_check.py` refuses
a `-SNAPSHOT` tag with `SNAPSHOT_RELEASE_REFUSED` before it builds or checksums that
module (the release workflow has already installed Gradle and bundled the modules by
then, and no publish step is reachable after the refusal), so a snapshot is never
published.

The breaking-change job writes the bundle of the baseline and of the candidate and
compares them with `oasdiff`. The baseline is the latest release tag reachable from the
commit under test, ordered by semver 2.0 precedence, so a higher tag on a side branch
is never the baseline and `1.0.0-rc.2` sorts below `1.0.0-rc.10` and below `1.0.0`. It fails with `BREAKING_WITHOUT_MAJOR`
when a breaking change leaves the major where it was, and with
`BUNDLE_CHANGED_VERSION_SAME` when the bundle changed and `info.version` did not
move at all. Elements marked `x-provisional` are removed from both sides first;
a difference that exists only because of them never fails and is reported in its own
section.

Until a release tag exists there is no baseline. The one allowed state is
`info.version: 1.0.0-SNAPSHOT` (or `1.0.0` in the release commit) together with a
heading of the same version in the module's `CHANGELOG.md`; the job prints
`NO_BASELINE_INITIAL_VERSION` and counts it, so the state is never silent.

**What a release is.** A release is a tag `contract-<module>-v<semver>` (no leading
`v` on the module part; for example `contract-mission-status-v1.0.0`), pushed by a
maintainer to trigger the Contracts Release workflow. It publishes two assets:
`openapi.yaml` and `openapi.yaml.sha256`. Only a tag push publishes; a pull request
cannot, because the Contracts workflow runs the same steps there as a dry run.

**What the gate checks before it publishes.** The Contracts Release workflow has two
jobs. The `build` job has a read-only token. It runs every check and builds the
assets:

- It refuses a tagged commit that is not an ancestor of `origin/main`.
- It runs `breaking_check.py --release-tag <tag>` against the previous release, so a
  release never skips the comparison.
- It refuses a tag for which the Contracts workflow has not passed. Contracts runs on
  a push to `main` only when one of its trigger paths changed, so the workflow finds
  the most recent commit at or before the tagged one that touched those paths (the
  list is read from `on.push.paths` of `contracts.yml`, never copied) and requires a
  Contracts run with conclusion `success`, event `push`, branch `main` and that commit
  as its head. A run for a pull request does not count, and no commit, no run or an
  unreadable answer (queried through the workflow's own token) means refused. A tag on
  a later `main` commit that changed none of those paths is therefore accepted once
  the earlier commit's run passed.

The `publish` job runs only after `build` succeeds. It is the only job with a write
token. Before it publishes, it confirms that the tag still resolves to the commit that
`build` checked, because a tag is a mutable ref until it is published.

## Residual risk: handle-shaped strings

A handle-shaped string can still be a person's account name: the status domain has
recorded an operating-system or git user name in actor-like fields before. The
contract cannot prove that a handle is not a person's name. The shape rule on
`ActorHandle` and the leak scan over the examples and over every payload the reality
check projects reduce that risk and do not remove it. Do not read a clean scan as a
guarantee.

Example: the shape rule accepts the handle `claude` and, equally, a string such as
`jdoe`; only a person can say which of them is an account name.

## Pattern matching is ECMA 262

Every `pattern` in the schemas (`WpId`, `ActorHandle`, `MissionId`, `StreamCursor` and the
other `$`-anchored ones) is an ECMA 262 regular expression, as OpenAPI and JSON Schema
define. In ECMA 262 a non-multiline `$` matches only at the very end of the input, so
`WP01` followed by a line feed does not match `^WP[0-9]{2,}$`. Python `re.search` and
Java `Matcher.find` treat `$` as also matching before a final line feed, so a validator
built on them accepts that value. A consumer that validates inbound values must use ECMA
262 semantics, or full-string matching (`re.fullmatch`, `Matcher.matches`), or reject a
value with a trailing line feed first. No producer of this contract ships yet. The
projection that the reality check validates matches with `fullmatch`, so it never emits
such a value, and a future producer must do the same. The patterns are not changed.

## Reader-author warning

The reality check projects every Mission in the repository (546 Missions, 3,193 work
package payloads and 24,419 events when slice 5 landed) through the status readers and
validates each projection against the contract. If you edit a status reader, run it
locally first:

```bash
PWHEADLESS=1 .venv/bin/python -m pytest -q tests/contract/test_mission_status_reality.py
```

CI will not run it for you on the pull request. These changes select no job that runs
the reality check: an edit under `src/specify_cli/status/**` (the readers the check
imports), an edit to the reality check's own test files or its fixture, and an edit to a
Mission's `meta.json` or `status.events.jsonl`. The reality check runs in the router job
`tests (corpus-blocking)`, and the router's `corpus` filter matches `contracts/**`
rather than any of those paths. An edit under `tests/contract/**` selects the router job
`tests (contract tools)`, which runs the unit tests of the contract tools and not the
reality check. The Packs run on a push to `main` does not cover the gap either: it
deselects these modules, which run once, in the router jobs. This is an accepted risk,
tracked in issue #5623. The safety net is the nightly run
(`ci-nightly.yml`, shard 4, scheduled daily at 03:17 UTC), which runs `tests/contract`
on its full-mode cadence, so a reader that drifts from the contract is caught the
next night, not on the pull request. To catch it sooner, dispatch the router in full
mode on your branch:

```bash
gh workflow run ci-router.yml -f mode=full --ref <branch>
```

The check is read-only and never writes Mission state. It lets the status snapshot
and the work package files disagree for the Missions named in a shrink-only list (a
ratchet, `header.disagreeing_missions` in
`tests/contract/fixtures/mission_status_expected.json`, tracked in #5579, to drain by
2026-12-31); a Mission that is not on the list and disagrees fails it, and the stored
ceiling must equal the length of the list.

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
