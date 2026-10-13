# Mission status API

A read-only service that reads the Missions of one project directory and serves their status over HTTP: a project header, a page of Mission overviews and a stream of changes. It reads a Mission's event log and the few files needed to find it, never writes to the project, starts no process and reads no git state beyond the one `HEAD` file.

## Read allowlist

The service opens exactly these paths, read-only, and lists exactly these directories. Nothing else is opened: never `tasks/*.md`, `spec.md`, `plan.md`, artifacts, WP frontmatter, `status.json`, the content of the coordination copy of `meta.json`, or the personal `config.toml`. `<read-dir>` is the Mission's own primary directory or, when its stored topology routes through coordination and the coordination Mission directory exists, that directory if it holds a `meta.json` or the Mission's own `meta.json` names a non-blank string coordination branch. `<primary-dir>` is always the Mission's own directory under `kitty-specs/`. One path pattern per line; a test compares this list with the `Allowlist` constant in the code, entry for entry and in order.

```
<read-dir>/status.events.jsonl
<primary-dir>/meta.json
<primary-dir>/lanes.json
.kittify/config.yaml
.kittify/metadata.yaml
.git/HEAD
.git (pointer file) and <gitdir>/HEAD
kitty-specs/ (names only)
.worktrees/ (names only)
.worktrees/<slug>-<mid8>-coord/kitty-specs/<slug>-<mid8>/ (stat only)
.worktrees/<slug>-<mid8>-coord/kitty-specs/<slug>-<mid8>/meta.json (stat only)
```

What each line is read for:

- `status.events.jsonl` is the Mission's event log of the resolved read directory.
- `meta.json` holds identity, dates and the stored topology, and is read from the Mission's own primary directory only.
- `lanes.json` is read only when the topology is absent from `meta.json` and has to be classified.
- `.kittify/config.yaml` is read for `project.slug` only; no other key, including any hosted-drain key, is looked at.
- `.kittify/metadata.yaml` is read for `spec_kitty.version` and `spec_kitty.schema_version`.
- `.git/HEAD` gives the branch name. When `.git` is a pointer file, the file is read for its `gitdir:` line and the single file `HEAD` of the directory it names is read; that is the one read outside the project root. The directory a pointer names is contained by real path: a pointer that reaches a directory inside the project root through a symbolic link is refused exactly as one that names it directly, and no in-root `HEAD` is read through it. An in-root `.git/**/HEAD`, `.git/worktrees`, `packed-refs` and `refs/` are never read.
- The two directory listings give names only, and the coordination Mission directory and the `meta.json` inside it are stat-ed to see whether they exist; the coordination `meta.json` is never opened.

### Threat note

Every read opens its target without following a symbolic link in the final path component, and a Mission directory must resolve to a real path inside the project root. That guards the final component only. An intermediate directory that is swapped for a link after the containment check has run is not covered: the check and the open are two steps, and the service does not hold a directory handle across them. This residual time-of-check to time-of-use window is accepted for a service that only reads, and it is why the service must run against a project directory whose owner trusts the processes that can write to it.

## Terms

Mission, Work Package, Lane, Tail cursor and `log_truncated` are the product's own terms and are defined in its glossary. The rest of this list names identifiers of this code, defined here so that they are not mistaken for glossary terms.

- **reducer**: the code that folds a Mission's status events into one snapshot of Work Package lanes.
- **status event**: one row of a Mission's event log that moves a Work Package between Lanes.
- **`Diagnostic`**: the record written to the service log when a read hits a fault. It carries a stable code and a short Mission id and never a path.
- **overview read model**: the per-Mission summary the service derives from `meta.json` and the reduced event log.
- **conformance golden**: a stored expected response that the service must reproduce byte for byte.
