# Data Model: Mission Status contract 1.1

"1.1" is the working name of this slice, not a version: the contract is unreleased and `info.version` stays `1.0.0-SNAPSHOT` (operator ruling 2026-10-05). Nothing in this model depends on a new version or a tag.

Phase 1 output of the plan. The spec's field catalogue stays the authority for what each field is; this file records the entities, the derivation and decision rules the reference reader and the contract descriptions must state alike, and the invariants the checks enforce. A rule written here is a rule of the spec, sharpened only where the plan says so (plan section "Departs from the spec"). Code is cited by symbol.

## Entities

| Entity | Identity | Source of truth | Notes |
|---|---|---|---|
| Work package of a Mission | `(missionId, wpId)` | The files `wp_task_files` selects under the Mission's `tasks/`, each keyed by the `work_package_id` of its frontmatter | One work package per distinct valid id. The **authored file** (the one whose frontmatter, titles source and owned files the detail reads) is the first **regular, non-symlink** entry for the id in byte order of the file name: `wp_task_files` selects by name only, so a symlink or a directory named like a work package file is selected and is **skipped like an unparseable file** (never followed, never a 500; an independent scan counts them, 0 at measurement). A file whose frontmatter raises `FrontmatterError` or a pydantic `ValidationError`, or has no valid `work_package_id`, is skipped (never a 500). The authored file is **not** the prompt file by definition: the two coincide for the four duplicate ids at measurement and for every corpus work package that has a prompt file. |
| Work package detail | `(missionId, wpId)` | Sources in the table "Detail field sources" below | Closed, self-contained (AD-3); every array present. |
| Prompt file | `(missionId, wpId)` | A regular, non-symlink `tasks/WP[0-9]{2,}-*.md` whose name starts with the wpId and a hyphen | The first in byte order of the file name when several qualify; `<wp-slug>` is its stem. Keyed by **file name**, not by frontmatter id (spec Terminology, two selectors): it alone feeds `artifactReferences.prompt` and the `tasks/<wp-slug>/` directory of the review cycles. A work package with no prompt file (`WP-notes.md` carrying a valid id, a name/id mismatch, the one corpus case `tasks/WP01.md`) has `prompt: null` and `reviewCycles: []`. |
| Artifact | `(missionId, path)` | An eligible file of the Mission directory on the primary planning surface | Primary surface = `MissionSource.own_dir` (`kitty-specs/<mission>` under the repository root checkout), never `read_dir` (ledger SK-310). |
| Artifact listing | `missionId` | A walk of one Mission directory | Flat, sorted by path in byte order, at most 1000 entries. |
| Artifact content | `(missionId, path)` | One file, read once, at most 262,144 bytes plus one | JSON envelope. |
| Refusal | a `code` | `ArtifactRefusal` and `WorkPackageDetailRefusal` | Problem plus a code whose status is pinned by the code. |
| Host capability | the reader's explicit input | Test code | `HostCapability(git, worktrees)`; never discovered; the corpus passes `NO_WORKTREES`. |

## Eligible file and the malformed-path predicate (one rule, five uses)

A path is **malformed** when it is empty; is longer than 512 characters; begins with `/`, with `~/` or with a drive letter and a colon; contains a backslash or a NUL character; has an empty segment or a trailing `/`; or has a `.` or `..` segment. The **artifact-path rule** is its negation. It is stated once and used by: the request check (400), the eligibility rule, the listing walk, the scanner's artifact-path class and the `ArtifactPath` schema. The schema form is the pattern in `contracts/operations-and-schemas.md` with `minLength: 1` and `maxLength: 512`; it equals the negation of the predicate on 30 cases (research R-8).

A file is **eligible** when it is regular, **no component of its path below the Mission directory is a symlink** (every component is lstat-ed; nothing is resolved), it is not the root-level `status.events.jsonl` or `status.json` (exact names, root only), and its path is not malformed. Eligibility is a rule over one path. It never depends on the listing or its cap. The listing, the content read, `artifactPath` and `artifactReferences` all call the one function.

## Content read: the order of decision

State machine of one content read (the listing runs the same function over every returned entry):

```text
request path
  malformed or missing or repeated            -> 400 invalid_artifact_path
  Mission unknown or id ill-formed            -> 404 not_found
  Mission directory unreadable                -> 500 artifact_unreadable
  not eligible (absent, directory, symlink,
     through a symlink, root status record)   -> 404 not_found
  open read-only; fstat the OPEN handle
  size > 262144                               -> 413 artifact_too_large   (file not read)
  read at most 262145 bytes
  open or read fails                          -> 500 artifact_unreadable
  a 262145th byte arrived                     -> 413 artifact_too_large   (grew during the read)
  NUL byte or invalid UTF-8 (strict decode)   -> 415 artifact_not_text
  a SECRET_PATTERNS match in the decoded text -> 422 artifact_secret      (no content in the body)
  otherwise                                   -> 200 envelope
```

`sizeBytes` is the `st_size` of the opened handle (`fstat`), never a content-derived length. A zero-byte file is a 200 with empty `content`. The decode is strict with no signature stripping (a leading byte order mark stays) and never uses replacement characters. The listing sets `readable` to false for exactly the files whose read would end in 413, 415, 422 or `artifact_unreadable`; a file over the cap is decided from `st_size` alone and is not opened; every other returned entry is read whole, so a NUL or an invalid byte at the last byte of a 262,144-byte file gives `readable: false`.

## Redaction

Applied to the decoded text after the checks above, with the patterns of `contracts/tools/leak_patterns.py` (this Mission adds and weakens none): every match of a widened human host-path pattern (the pattern plus the non-space characters that follow) becomes `[path]`, every e-mail match becomes `[email]`. `redacted` is true when at least one substitution changed the text (AD-10, provisional). The cap is measured on raw bytes before redaction. Human text fields (`title` of a subtask or a dependency) follow the same substitution; a title that holds a credential is withheld: a subtask `title` is `null`, a dependency `title` is the work package id.

## Classifier (kind)

One ordered function, first match wins, shared by the listing and the content read:

1. `tasks/<dir>/review-cycle-<N>.md` with `N` matching `[1-9][0-9]*`: `review_cycle`.
2. `tasks/WP[0-9]{2,}-*.md` directly under `tasks/`: `work_package_prompt` (`tasks/WP1-x.md` and `tasks/WP-notes.md` fall through).
3. Root `spec.md`, `plan.md`, `tasks.md`, `data-model.md`, `quickstart.md`, `analysis-report.md`: `spec`, `plan`, `tasks`, `data_model`, `quickstart`, `analysis_report`.
4. Root `research.md` and everything under `research/`: `research`.
5. Everything under `contracts/`: `contract`. 6. Everything under `checklists/`: `checklist`. 7. Everything else: `other`.

`ArtifactKind` therefore has twelve values (the order above). Measured corpus distribution of the classes: 3,196 prompts, 1,322 review cycles, 546 specs, 538 plans, 536 tasks, 370 data models, 341 quickstarts, 333 analysis reports, 709 research, 684 contract, 405 checklist, 6,581 other (research R-2).

## Media type

Fixed table by extension, never sniffed: `md` `text/markdown`, `json` `application/json`, `yaml` and `yml` `application/yaml`, `jsonl` `application/x-ndjson`, `csv` `text/csv`, anything else `text/plain`. `encoding` is the constant `utf-8`.

## `modifiedAt`

RFC 3339 UTC with `Z` and whole seconds, the modification time floored (never rounded): `datetime.fromtimestamp(math.floor(st_mtime), UTC)` formatted `YYYY-MM-DDTHH:MM:SSZ`. Host time, not authorship; not an ordering key (the listing order is the byte order of `path` alone).

## Detail field sources

| Field | Reader rule | Source |
|---|---|---|
| `missionId`, `wpId` | the Mission's `mission_id`; the id of the work package file | `resolve_mission_identity`; `WPMetadata.work_package_id` |
| `subtasks[].id` | the authored roster in order, as v1 reads it | `AuthoredGroup.subtasks` built from `normalize_authored_subtask_roster` (never `authored_subtask_roster`, which raises) |
| `subtasks[].title` | table row: second cell trimmed; checkbox row: remainder after the id trimmed; a leading `[P]` tag is dropped; one pair of `**` markers is stripped; trimmed again; empty becomes `null`; first row wins for a duplicate id; a credential withholds it | rows of `tasks.md` (x-derived; `iter_wp_section_subtask_rows` yields no title) |
| `subtasks[].statusLane` | the resolved state of the subtask, or `null` when none is recorded (never `planned`) | `ResolvedGroup.subtasks` via `reconstruct_wp_view` |
| `dependencies[]` | `wpId` as authored; `title` is the stripped `display_title` when non-empty, else the id, and the id when it holds a credential; `statusLane` from the snapshot or `null` for a dependency with no events or no work package | `AuthoredGroup.dependencies`; `WPMetadata.display_title`; the snapshot lane |
| `reviewCycles[]` | one entry per `tasks/<wp-slug>/review-cycle-<N>.md` of the primary directory, ascending by `cycleNumber`; an unparseable file is an entry with `null` members and the number from its name | `_REVIEW_CYCLE_FILE_RE` (the name rule), `ReviewCycleArtifact.from_file` |
| `reviewCycles[].reviewedAt` | the stored string only when it is a valid RFC 3339 date-time with an offset, else `null` (a date-only value is `null`, never midnight) | `is_rfc3339_date_time` |
| `reviewCycles[].verdict` | the `review_result.verdict` of the events of this work package whose trimmed `review_result.reference` equals the cycle's full pointer; the last such event wins; else `null` | status events |
| `reviewCycles[].feedbackReference` | `review-cycle://<mission-slug>/<wp-slug>/review-cycle-<N>.md` from the three directory and file names; `null` when the builder refuses a segment; never an event's `feedback_path` | `build_review_cycle_pointer`, `validate_review_cycle_pointer` |
| `reviewCycles[].artifactPath` | non-null exactly when the cycle file is eligible (no symlink component), independent of the listing cap | the eligibility rule |
| `workspace.laneId` | the code lane of the work package (`lane-planning` for a planning-artifact or single-branch one); `null` with no `lanes.json` or no lane | `read_lanes_json`, `LanesManifest.lane_for_wp` |
| `workspace.laneBranch` | `lane_branch_name(slug, lane_id, target_branch=manifest.target_branch)`; `null` for `PLANNING_LANE_ID` and when `laneId` is null; a value failing the strict branch pattern projects to `null` | `lane_branch_name` |
| `workspace.planningBranch` | `planning_base_branch` of the frontmatter, or `null` | `WPMetadata` |
| `workspace.worktreePresent` | `true` only when `runs_in_checkout_root` is false and `exists` is true on a host that has worktrees; otherwise `false` | `ResolvedWorkspace` |
| `ownedFiles[]` | `pattern` as authored; `isGlob` from `is_glob_pattern`; `changeState` below | `AuthoredGroup.owned_files` |
| `artifactReferences.prompt`, `.spec` | `{path, kind}` of the Mission's prompt file and `spec.md` when eligible, else `null`; one `tasks/` directory read plus lstat of each component; no file opened | the eligibility rule |

Exceptions are outcomes, not silence: `MissingLanesError` and the "work package in no lane" `ValueError` give `worktreePresent: false` with null lane members; `CorruptLanesError`, `MissionSelectorAmbiguous`, an undecodable `tasks.md` and an unreadable Mission or work package file give 500 `source_unreadable`; an unknown or ill-formed Mission or work package id, a stem that is no work package of the Mission and an id present only in the status log give 404 `not_found`.

## `changeState` derivation (per work package, once)

1. **Determined** only when all hold: `host.git` and `host.worktrees` are true; the work package has a code lane (`laneId` non-null and not `lane-planning`); `worktreePresent` is true; `get_current_branch(worktree)` equals `laneBranch` (a detached HEAD gives `None`, another branch another name: not determined; **an `OSError`, `subprocess.SubprocessError` or `ValueError` raised by the call, for example `NotADirectoryError` or `PermissionError` from a worktree directory that vanished or was replaced after the existence check, is caught by the reader and means not determined**: `get_current_branch` itself catches only `CalledProcessError` and `FileNotFoundError`); the manifest's `target_branch` **passes the same strict branch pattern as `laneBranch` and does not start with `-`** (it is a bare string read from `lanes.json`, and `git_merge_base` builds its argv with no end-of-options marker, so an option-like value must never reach git: it makes every entry `unknown` and git is not invoked); `git_merge_base(worktree, "HEAD", target_branch)` is not `None` **and raised nothing** (the function maps a non-zero exit to `None` but lets `FileNotFoundError`, `NotADirectoryError` and other `OSError` escape, and it has no timeout; the reader catches `OSError`, `subprocess.SubprocessError` and `ValueError` around it). Otherwise every entry is `unknown`. **Accepted residual:** neither of these two calls has a timeout, and the reader cannot add one without a `src/` change; a wedged git hangs the read inside them (plan D-P4 states the reason).
2. **Change set**: `changed_paths(worktree, merge_base, "HEAD", renames=False, timeout=<fixed constant, 30 s>)` (committed changes only: uncommitted, staged and untracked paths never appear; a deletion is listed; a rename is a delete plus an add, so **both names** are listed). The result is a tuple of `GitPath` objects, not strings: the reader converts each with `path.as_posix()` before step 3 (the matcher uses `fnmatch` and `startswith`). **A `GitCommandError` (timeout or OS error wrapped by the runner) and a `ValueError` (the parse of git's output refuses a path: an empty, `.` or `..` component or an absolute path) each make every entry `unknown`**, never `unchanged` and never an escaping exception (a read service would otherwise answer 500 with no code).
3. **Matching** per path against each pattern, the reader's `matches_owned_file(path, pattern)`: normalise the path (`\` to `/`, remove a leading `./`); true when `fnmatch.fnmatch(path, pattern)` is true (see the note below); or when the pattern with every `/**` and then every `/*` removed and a trailing `/` stripped is a non-empty prefix `P` and the path starts with `P/`. The pattern is used as authored. A pattern holding `{` is not matchable: `unknown`.
4. `changed` when determined, matchable and some changed path matches; `unchanged` when determined, matchable and none does.

Note on `fnmatch`: the repository's two copies call `fnmatch.fnmatch`, which applies `os.path.normcase` and so is case-insensitive on a case-insensitive platform; the reference reader calls the same `fnmatch.fnmatch` (not `fnmatchcase`) so the parity with the two copies is exact on every platform the tests run on (spec: "case-sensitive on POSIX, the repository's own behaviour").

Invariants asserted on every detail built: `changeState` is `changed` or `unchanged` only when `worktreePresent` is true; `worktreePresent` is true only when the workspace does not run in the repository root checkout; in the corpus every `changeState` is `unknown` and every `worktreePresent` is `false` (a host without worktrees, by construction).

## Listing walk

Visit every name under the Mission directory with `lstat` (no symlink is followed or entered, directories are not entries), keep the eligible files, sort by `path` in byte order of the UTF-8 encoding, keep the first 1000 and set `truncated` when more existed; stat and read only the returned entries. A file that vanishes between the walk and its stat is omitted; any other stat failure, or an unreadable Mission directory, is a 500 `artifact_listing_unreadable`, never a shortened 200.

## Host capability and the file-system seam

`HostCapability` carries two booleans and nothing else. The reader opens, scans and stats through one injectable `FileSystem` value (`scandir`, `lstat`, `open_binary`); the real value is the default. Fault injection replaces one call with one that raises a chosen `OSError` and counts how often it fired; a test fails, not skips, when the count is zero. A counting wrapper records bytes read per open for the bounded-read and no-listing-in-detail assertions; no test uses `chmod`.

## Status and refusal pairing

| Operation | Status | `code` |
|---|---|---|
| `getArtifactContent` | 400 | `invalid_artifact_path` |
| all three | 404 | `not_found` |
| `getArtifactContent` | 413 | `artifact_too_large` |
| `getArtifactContent` | 415 | `artifact_not_text` |
| `getArtifactContent` | 422 | `artifact_secret` |
| `getArtifactContent` | 500 | `artifact_unreadable` |
| `listArtifacts` | 500 | `artifact_listing_unreadable` |
| `getWorkPackageDetail` | 500 | `source_unreadable` |

`ArtifactRefusal` and `WorkPackageDetailRefusal` state the pairing as schema rules (an `if`/`then` per code, the form `StreamRefusal` uses), so an example or a payload with a code and a mismatched status fails validation.

## Closed vocabularies (pinned in `contracts/tools/enum_pins.json` under `mission-status`)

`ChangeState` = `changed`, `unchanged`, `unknown`. `ArtifactKind` = the twelve kinds above. `ArtifactRefusalCode` = the seven codes above (without `source_unreadable`). `WorkPackageDetailRefusalCode` = `not_found`, `source_unreadable`. `encoding` is a `const`, not pinned; `mediaType` is a plain string field with the table above, not an enum.

## Floors and the independent counts (what the reality check compares against)

Every examined count is compared with a count taken by a path that does not use the reader under test: Missions (a scan of `kitty-specs/*/meta.json`); work packages (distinct valid `work_package_id` of the files `wp_task_files` selects, parsed with a plain YAML read; ids present only in the status log counted separately, 404 and not examined); eligible files (a separate `os.walk`); owned-file entries (a count of the frontmatter lists); `tasks.md` rows (two regular expressions); review-cycle files (a directory scan); cycles with a verdict (a scan of the logs for an event reference equal to the pointer); work package files that are symlinks or directories (a scan of the `tasks/` entries); and, for the content read, **the expected status and `readable` of every eligible file from its raw bytes** (size, NUL, strict UTF-8 decode, the credential patterns), computed by the reality module without the reader, so that the reader's own `readable == (content read answers 200)` equality, which holds by construction, is not the oracle (plan D-P8). The proposed numeric floors are the second guard and are in research R-5.
