# Mission status API

A read-only, loopback-only service that reads the Missions of one project directory and serves their status over HTTP: a project header, a page of Mission overviews, a stream of changes and the planning artifacts of one Mission. It serves `GET /api/v1/project`, `GET /api/v1/missions`, `GET /api/v1/events` (a server-sent change stream), the two artifact reads of one Mission (`GET /api/v1/missions/{missionId}/artifacts` and `.../artifacts/content`) and `GET /api/v1/openapi.yaml`, behind a Host and Origin guard that answers only to `127.0.0.1` and `localhost` on its own port. Every other path of the contract answers 404 by design (`OutOfScopeRoutesTest`). For status it reads a Mission's event log and the few files needed to find it; for the artifact reads, the files of that Mission's own primary directory. It never writes to the project, takes no lock, starts no process and reads no git state beyond the one `HEAD` file. It is a detached service: no spec-kitty command starts it, and it is not part of the PyPI package. CI replays a golden request set against the native binary of four targets and compares the response digests, holds the performance budgets of NFR-001, NFR-002 and NFR-004, and can compare the service with the Python reference over the whole repository corpus in a nightly scheduled run (04:37 UTC) or a manually dispatched one (see Tests and Recorded divergences).

## How to run

Start the built jar with `java -jar build/libs/mission-status-api.jar --mission-status.project-root=<project root> --mission-status.port=8787`. The native binary takes the same two properties. The configuration keys are:

- `mission-status.project-root` (required, no default): the project directory to read. The service refuses to start without it, or when it is not a directory.
- `mission-status.port` (default 8787; 0 asks the operating system for a free port).
- `mission-status.stream.queue-capacity` (default 1024): the capacity of each stream subscriber's queue.
- `mission-status.stream.heartbeat-interval` (default `PT30S`, an ISO-8601 duration): the interval of the idle-stream heartbeat comment.
- `mission-status.stream.max-connections` (default 128): the most event streams open at once. Over the bound a request is answered `503` with the Problem code `stream_capacity_reached`, before anything is subscribed, and it takes no place. The default is NFR-004's 100 connections plus headroom; each stream costs a virtual thread and a queue, and an unscoped stream also costs a full listing of the Missions on connect. A place is freed when the stream ends, which for a client that vanished is at the next heartbeat write.

The service binds `127.0.0.1` only (`server.address`, packaged as `127.0.0.1`). BindGuard refuses any other value, `localhost` included. A configured address that is not loopback (`0.0.0.0`, `::`, a LAN address, a hostname) makes it exit non-zero with a message naming the address, and a port already in use does the same; it never falls back to another port or interface. The `spring.aot.processing` switch (set by the build while it runs the application for ahead-of-time processing) skips only the "unset" case of that check; a non-blank address that is not loopback is refused under the switch too.

The configuration is pinned to the packaged `application.properties` (`ConfigPin`). Spring Boot would also read `./config/application.properties` and `./application.properties` from the working directory, and `SPRING_CONFIG_LOCATION`, `SPRING_CONFIG_ADDITIONAL_LOCATION` and `spring.config.import` could name more files; a service started from inside an untrusted project would then let that project reconfigure it (serve any file through the static-resource handler, write a log file anywhere). None of those is read: the pin fixes where configuration FILES are read from, so a file planted in the working directory cannot take effect. The command line and the environment (`SPRING_APPLICATION_JSON` included, which can still set `logging.file.name`) are the operator's own and still apply, as do `--mission-status.*` and `--server.*` keys; static serving stays off regardless. `spring.web.resources.add-mappings` is `false`: there is no static-resource handler, and Spring's and Tomcat's loggers that would echo a request path or Host into the log are raised so that no caller-controlled text reaches the log.

Reads are capped. `meta.json`, `lanes.json` and the two `.kittify` YAML files are read up to 1 MiB: an oversize `meta.json` is row L7, an oversize `lanes.json` reads as "no lanes", an oversize YAML file as absent. The event log is read up to 64 MiB (the largest of this repository's 594 is under 1 MiB): a larger one is row L2, `ledger_unreadable`, never an out-of-memory failure. There is no read of the project that is not capped.

Every request is checked before anything is read:

- The `Host` header must be exactly `127.0.0.1:<port>` or `localhost:<port>`, with the service's own port. `[::1]` is not accepted: the service never listens on IPv6, so a client that resolves `localhost` to `::1` first is refused the connection and falls back to `127.0.0.1`. A `Forwarded` or `X-Forwarded-Host` header is refused.
- An `Origin` header is optional. When present it must be `http://` plus one of the two accepted host forms; `null`, another scheme or another port is refused. There is no setting that widens the accepted set.
- `Sec-Fetch-Site: cross-site` is refused: a browser sends no `Origin` on a cross-site GET, and could otherwise fill the stream places. `same-origin`, `same-site`, `none` and an absent header (a non-browser client) pass.
- A refusal is `403` with the Problem code `request_refused`, no `detail` and no echo of the request. An error the container itself routes to its error page (a method it refuses, such as `TRACE`, under an accepted Host) is answered with the shared Problem as well: the status and its reason phrase, with no `path` and no timestamp. A few malformed Host values are answered `400` by the web container itself before the check runs: a Host with a character outside host syntax (such as `@`), a duplicate `Host` header, an HTTP/1.1 request without `Host`, and an HTTP/1.1 absolute-form target that names a foreign authority. The check covers every path, unknown paths and error paths included.

## Routes and scope

The service answers exactly these routes and no others:

- `GET /api/v1/project`: the project header.
- `GET /api/v1/missions`: a page of Mission overviews.
- `GET /api/v1/events`: the change stream (`text/event-stream`).
- `GET /api/v1/missions/{missionId}/artifacts` (`listArtifacts`): the eligible files of one Mission's primary directory, in code-point order of the path, at most 1000, with `truncated`.
- `GET /api/v1/missions/{missionId}/artifacts/content?path=` (`getArtifactContent`): the decoded and redacted text of one artifact, or one of the contract's seven refusals (400, 404, 413, 415, 422, 500).
- `GET /api/v1/openapi.yaml`: the contract document, bundled at build time from `contracts/mission-status` and served as it stands.

Any other path is `404` once the Host and Origin check has passed. There is no generated or interactive API documentation. The other detail routes (a single Mission, a Work Package, its detail) are the rest of issue #957, and drift and Ops are out of scope here; `OutOfScopeRoutesTest` keeps all five at 404.

The artifact routes follow the order of decision of the Python reference reader (`tests/contract/_mission_status_artifacts.py`). The `path` parameter is judged as the list of its values, so a missing or repeated one is `400 invalid_artifact_path`, as is a malformed percent-encoding. An unknown or ill-formed `missionId` is `404 not_found`. A Mission directory that is gone, a link or outside the root is `404`, and one that cannot be stat-ed is `500`. Per file, the steps run in this order:

1. Eligibility (the name rule, then an lstat of every component; no link, a regular file, not a root status record): not eligible is `404`, and a fault is `500`. The name rule denies by default (`ArtifactNameRule`, the reference's `is_artifact_name`): the final name ends in `.md`, `.json`, `.jsonl`, `.yaml`, `.yml`, `.csv` or `.txt` (with that case), no segment starts with a dot, and a data file (not `.md`) is not named `credential(s)`, `secret(s)`, `service-account`, `service_account` or `client_secret*` (by case fold). A `.env`, a key, a certificate or any other file is never listed and never opened.
2. A NOFOLLOW open, with the size taken from the open handle: a failure to open is `500`, and more than 262,144 bytes is `413` with nothing read.
3. The bytes: a NUL byte or invalid UTF-8 is `415`, and a credential is `422`.
4. Otherwise `200`, with host paths and e-mail addresses replaced by `[path]` and `[email]`.

A refusal body is the shared Problem with `type: about:blank`, the code, its status and a fixed title and detail; it never names the path, a directory or content.

## Paging

`GET /api/v1/missions` takes `pageSize` and `pageCursor`:

- `pageSize` defaults to 50 and is clamped at both ends: a value above 200 becomes 200 and a value below 1 becomes 1. A value that is not an integer (`abc`, `1.5`) is treated as absent, so the default page is served; there is no `400` for it. Integers beyond 32 bits saturate and are then clamped.
- A `pageCursor` the service did not issue, or an empty one, is refused with `400` and the code `invalid_page_cursor`.

## Stream

`GET /api/v1/events` streams `status-transition`, `mission-lifecycle` and `log-truncated` events, with a `: heartbeat` comment while idle. It can be scoped to one Mission with `missionId`.

- A Tail cursor has the form `<offset>:<sha256 of the last terminated line>`. A scoped event carries it as its `id:`. A client resumes with the `streamCursor` query parameter or with `Last-Event-ID`; `streamCursor` wins when both are sent. A cursor needs `missionId`.
- `HEAD /api/v1/events` is `405` with `Allow: GET`, answered before a stream place is taken: a `HEAD` request never writes a body, so a disconnect would never release its place.
- A cursor whose text does not parse is refused `400` with the code `misaligned`. The other refusals are `400` `negative`, `400` `cursor_without_mission`, `409` `out_of_range` and `409` `content_mismatch`, and an unknown `missionId` is `404` before any event.
- The cursor invariant is the digest of the last terminated line of any kind, a blank line included.
- A scoped client reconnects with the last `id:` it saw. An unscoped event carries no `id:`, so an unscoped client reconnects and sees only later rows. A subscriber whose queue overflows is closed (never silently dropped); it reconnects the same way.
- A log that shrinks under an open stream yields a `log-truncated` event. A fault in a Mission's log is handled per scope: a scoped stream closes after the rows before the fault, and an unscoped stream drops that Mission and keeps the connection.
- Mission ids and event ids in event data are projected strictly, a row's `at` (or a lifecycle row's `timestamp`) must parse as an instant, and the actor handles `tool`, `role` and `profile` are projected strictly and are `null` when they look like a token, a path or an address: an event that cannot be represented (an unusable id or instant) is dropped with one `projection_refused` diagnostic.
- At most `mission-status.stream.max-connections` streams are open at once; a request over the bound is `503` `stream_capacity_reached` (the contract's `default` Problem response), see the configuration keys above.

## Fail-loud reads

The service never answers a fault as a healthy success. Each condition has an observable, and a diagnostic with a stable code and a short Mission id goes to the service log (never a path):

| Condition | Observable |
| --- | --- |
| L1 ledger absent (a new Mission) | 200, zero Work Packages, `draft` (or `discarded`); no diagnostic |
| L2 ledger unreadable (permission, I/O, symbolic link, larger than 64 MiB) | 200 item as `draft`, plus the diagnostic `ledger_unreadable` |
| L3a, L3b ledger not decodable or parseable, in any Mission | 500 Problem on `/project` and on `/missions`, diagnostic `ledger_unparseable` |
| L4, L4b unterminated last line (parseable or not) | the same 500, diagnostic `ledger_torn_tail`; the partial line is never served |
| L5 log shrinks under an open stream | a `log-truncated` event |
| L6 Mission directory vanishes during a read | the Mission is omitted from the page, diagnostic `mission_vanished` |
| L7 `meta.json` unusable (invalid JSON, not an object, empty, not UTF-8, unreadable, larger than 1 MiB) | 500, diagnostic `meta_unparseable` |
| L8 unknown schema version | 200, the recorded integer, the contract's drift health |
| L9 Mission path refused (symbolic link or outside the project root) | the Mission is omitted from the page, diagnostic `path_refused` |
| L10 bad terminated line on a stream | stream rows S4: a scoped stream closes, an unscoped one drops the Mission |
| L11 OS failure listing or stat-ing | 500, diagnostic `mission_dir_unreadable` |

Cases decided beyond the table:

- Two Mission directories that carry the same `mission_id` (a copied or backed-up `kitty-specs/<dir>`) are both listed, each once, ordered by `createdAt`, then `missionId`, then the directory name. The opaque page cursor carries the directory name as well, so a page walk ends. One diagnostic `mission_id_duplicate` is written for each such id in a listing. A Mission-scoped stream resolves such an id to the first readable directory and writes the same diagnostic. The oracle lists them in directory order and has no cursor.
- A Mission-scoped request for an id that matches no readable Mission answers by the first unusable Mission met: L9 gives `404` with `path_refused`, L7 gives `500` `meta_unparseable`, an unreadable directory gives `500` `mission_dir_unreadable`. A plain `404` is given only when no such Mission exists.
- A `meta.json` that parses but cannot populate the Mission is L7 (`meta_unparseable`). A missing or unusable `project.slug` makes `GET /api/v1/project` answer `500` with the diagnostic `mission_dir_unreadable`; the oracle names it `projection_refused`, with the same status and body. A missing `created_at` is refused as L7.
- A `mission_number` beyond 31 bits is L7; a `schema_version` beyond 31 bits is served as null. The contract carries 32-bit integers, so this is a documented limit.
- A Work Package with annotation rows but no transition is held in the `uninitialized` lane; it counts toward `wpTotal` and the progress denominator, but in no Lane count. A well-formed row that is not usable (a missing required key, an unknown Lane or `kind`) is treated as unparseable on a request route and is skipped on a stream.

## Read allowlist

The Mission status reads (the project header, the overview page and the stream) open exactly these paths, read-only, and list exactly these directories. The artifact routes have their own, separate list (see Artifact read allowlist); the event source never opens an artifact. Nothing else is opened by the status reads: never `tasks/*.md`, `spec.md`, `plan.md`, artifacts, WP frontmatter, `status.json`, the content of the coordination copy of `meta.json`, or the personal `config.toml`. `<read-dir>` is the Mission's own primary directory or, when its stored topology routes through coordination and the coordination Mission directory exists, that directory if it holds a `meta.json` or the Mission's own `meta.json` names a non-blank string coordination branch. `<primary-dir>` is always the Mission's own directory under `kitty-specs/`. One path pattern per line; a test compares this list with the `Allowlist` constant in the code, entry for entry and in order.

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
- `.kittify/config.yaml` is read for `project.slug` only; no other key, including any hosted-drain key, is looked at. Both `.kittify` files are read only when their real path is inside the real project root: a `.kittify` that is a link to a directory elsewhere is unusable project configuration (`GET /api/v1/project` answers `500` with `mission_dir_unreadable`).
- `.kittify/metadata.yaml` is read for `spec_kitty.version` and `spec_kitty.schema_version`.
- `.git/HEAD` gives the branch name. When `.git` is a pointer file, the file is read for its `gitdir:` line and the single file `HEAD` of the directory it names is read; that is the one read outside the project root. The directory a pointer names is contained by real path: a pointer that reaches a directory inside the project root through a symbolic link is refused exactly as one that names it directly, and no in-root `HEAD` is read through it. An in-root `.git/**/HEAD`, `.git/worktrees`, `packed-refs` and `refs/` are never read.
- The two directory listings give names only, and the coordination Mission directory and the `meta.json` inside it are stat-ed to see whether they exist; the coordination `meta.json` is never opened.

### Threat note

Every read opens its target without following a symbolic link in the final path component, and a Mission directory must resolve to a real path inside the project root. That guards the final component only. An intermediate directory that is swapped for a link after the containment check has run is not covered: the check and the open are two steps, and the service does not hold a directory handle across them. This residual time-of-check to time-of-use window is accepted for a service that only reads, and it is why the service must run against a project directory whose owner trusts the processes that can write to it.

### Known residuals

Each of these is accepted for a local, read-only service and is recorded here so that nobody assumes otherwise.

- **Stat, then open, on a final component.** A non-regular file is refused on its stat, before any open, so a FIFO placed there is refused without blocking. A local process that swaps a regular file for a FIFO between the stat and the open can make a request thread block, because Java has no `O_NONBLOCK` open for a file.
- **Intermediate path steps are resolved again between the containment check and the read.** Any file of a Mission's directory is reachable that way since the artifact routes (see the artifact residuals below), and only a local process that can write to the project can race it (see the threat note above).
- **The ledger cap is per read.** One read holds at most 64 MiB of ledger bytes and then the decoded lines, so concurrent requests multiply that. Size the heap (`-Xmx`) for the number of concurrent ledger reads the deployment allows, not for one.
- **The event stream is capped, not shaped per connection.** At most 128 streams are open at once (`mission-status.stream.max-connections`); the 129th request is answered 503 with the Problem code `stream_capacity_reached` until a stream ends. A vanished client is noticed at the next heartbeat or event write, which is when its place is freed. There is no per-client limit: any local process can use every place.
- **`pageSize` is clamped, not refused (operator ruling).** A value outside 1 to 200 is served as the nearest bound, a value that is not an integer is treated as absent (the default of 50 applies), and `pageInfo.pageSize` reports the size actually used.
- **Run under a UTF-8 locale.** The JVM decodes file names with `sun.jnu.encoding`, taken from the locale. Under a non-UTF-8 locale (for example `LANG=C` or `POSIX`), a Mission directory whose name holds non-ASCII characters cannot be opened by name and is read as vanished.

## Artifact read allowlist

The two artifact routes (`listArtifacts`, `getArtifactContent`) read through their own source, `FilesystemMissionArtifactSource`, and touch exactly these paths. They find a Mission by reading each `kitty-specs/<mission>/meta.json` for its `mission_id`. They then read only below that Mission's own primary directory, never a coordination copy. Every component of a path is checked with an lstat before anything is opened, the walk never enters or lists a symbolic link, and a file is opened without following a final link, its size taken from the open handle and at most 262,145 bytes read. The two root status records are stat-ed by the walk and never read or served. One path pattern per line; a test compares this list with the `ArtifactAllowlist` constant in the code, entry for entry and in order.

```
kitty-specs/ (names only)
kitty-specs/<mission>/meta.json
kitty-specs/<mission>/ (stat, real path, names)
kitty-specs/<mission>/status.events.jsonl and status.json (stat only)
kitty-specs/<mission>/<path> (stat, names, read)
```

The residuals of the threat note apply here too. The check and the open are two steps, so an intermediate directory swapped for a link, or a file swapped for a FIFO, after the check is not caught. A hard link to a file outside the Mission is a regular file and is served when its name is an artifact name and it holds no credential. The rules are lexical, as the reference's are: on Windows a trailing dot or an 8.3 short name (`status.json.`, `STATUS~1.JSO`) can reach a root status record, and on a case-insensitive file system `SPEC.md` reaches `spec.md` and is classed `other`. A listing walks, stats and checks the whole Mission tree before it keeps the first 1000 entries, and reads each kept file up to the cap to decide `readable`; a Mission directory that holds a very large tree (a `node_modules`, say) makes every listing of it slow.

## Recorded divergences from the Python reference

The service is checked against the Python reducer on a curated golden set and, in the `nightly-corpus` job (a nightly scheduled run, 04:37 UTC, or a manual dispatch), on the whole repository corpus. These differences are known, kept on purpose and recorded in the Mission's decision record, `kitty-specs/mission-status-read-api-overview-01M4EMSA/traces/design-decisions.md` (the DD ids are its entries):

- DD-79: an offset-less timestamp is read as UTC (Python uses the machine's zone); timestamps are stricter than `fromisoformat` (date-only, basic format and more than nine fractional digits are refused); the implementer-of-record projection is not gated on schema version 2.
- Artifact reads (mission `mission-status-artifact-reads-01M57KY3`): a Mission's `meta.json` is read for its `mission_id` through the same 1 MiB cap as the overview reads, without following a final link, where the reference reads it whole and follows a link; a `meta.json` over the cap or behind a link is skipped. The Mission directory must also resolve inside the real project root, which the reference does not check. Real Missions trigger neither. A `kitty-specs/` that is itself a symbolic link out of the root is answered 404 here, where the reference serves it. A `meta.json` that starts with a byte order mark, or is UTF-16 or UTF-32, is skipped here (strict UTF-8, as every other read of the service), where the reference's `json.loads` of the bytes accepts it.
- Artifact reads: a credential scan or redaction that cannot finish is refused `500 artifact_unreadable` (and the listing marks the file `readable: false`), where the reference answers 200. `java.util.regex` recurses once per repetition of a variable-width group, so a few kilobytes of a repeated PEM-header word or address label overflow the stack; the text is then neither known to be free of a credential nor redacted, so it is not served. No real artifact comes near this.
- DD-81: annotation-only Work Packages enter the snapshot in file order, where the oracle sorts them by `(at, event_id)`; no overview field depends on the order.
- DD-85: optional members of the wrong type read as absent. Physical lines end at `\n` bytes only, so a lone `\r`, U+2028 or U+0085 does not split a line; a non-text `event_id`, `at` or `wp_id` is refused.
- DD-89, DD-90: a truthy non-text or over-long slug, and a lone CR, U+0085 or U+2028 inside a row, differ from Python's failures. Each occurs zero times in the 959 ledgers checked.
- DD-95, DD-97: an actor handle must match `^[A-Za-z0-9._:-]{1,128}$` and excludes the four resolver sentinels; a value that is neither text nor a record gives three nulls.
- DD-100 to DD-106: the read-directory resolver follows the oracle's coordination rule, with only a stat (never a read) of the coordination `meta.json`; a Mission name that is not a safe single segment is refused; `meta.json` nested more than 500 levels is unusable here; for a directory, an empty file or corrupt JSON at the coordination `meta.json` path Java never reads the content.
- DD-86 to DD-88, DD-104: leak patterns are translated to Python `re` classes (`\w`, `\s`, `\d` and their negations), lookbehind is guarded for supplementary characters, and `\b` and `\B` are refused; the stream blank-line cursor uses the last terminated line of any kind.
- DD-95 (C2-2): an actor `"claude\n"` gives a null tool, which differs from the oracle.
- DD-99 (Q-3): the service reads no git, so whether a coordination directory exists decides the read directory; a husk folder is not told apart from a registered worktree.
- DD-101, DD-102: the diagnostic codes of unusable `meta.json` contents and of a missing project slug differ from the oracle's `projection_refused` (the status and body are the same); the stamp that detects a changed log is the size, mtime, file key, terminated length and last-line digest, so a middle-line rewrite with the mtime restored is served stale.
- DD-107: `/project` follows the specification (a strict field that cannot be represented refuses the whole read, as on `/missions`), where the oracle serves it; a git pointer file whose target lies inside the project root is refused.
- DD-109: a stream closes after the rows before a bad line, where Python's `poll_once` refuses all of them.
- Reducer version: the reduction ports `spec-kitty-events` 10.4.6 (`reduce_parsed`: `from_lane` continuity for every setter, the reconstruction-seed exemptions with the rollback-seed lane authority of #6061, the canonical-minimum dedup of same-id seeds, a real `approved -> X` ordered after its same-`at` approval). The seed payload fold of 10.4.3 writes claim slots and a verdict that this service does not serve, so it is not ported. The conformance goldens and `manifest.json` are generated under the locked version; `tests/contract/test_mission_status_conformance.py` goes red when the locked version moves.
- A1 (landing fold): `Project.name` is a strict field, so a `project.slug` shaped like a path, an address or a secret refuses `/project` with `projection_refused`, and a clean one is served. The oracle (`read_project_name`) serves the slug as stored. Real slugs are plain names, so no real data is affected.
- R-7 (landing fold): a served date-time (`acceptedAt`, `mergedAt`, `discardedAt`, `lastActivityAt`, and the `at` of a stream event) needs an offset, as the contract's `format: date-time` does. A Mission date or `lastActivityAt` without one is `null`, and a stream event whose `at` has none is dropped, each with one `projection_refused` diagnostic; a Mission date that is junk (J7) writes the same diagnostic now. Comparison keeps DD-79 (an offset-less timestamp is UTC). The oracle serves the text as stored. `createdAt` is stricter: a `created_at` without an offset is `META_UNPARSEABLE`, as a missing one is (landing ruling of 2026-10-13, after FR-004). The oracle serves an offset-less `created_at` as stored; no conformance fixture carries one, so no golden diverges.
- A5 (landing fold): an `eventId` or `wpId` of a stream event longer than 64 characters, the contract's bound, drops the event with one `projection_refused` diagnostic. The oracle forwards the id as stored. Real ids are ULIDs and `WP` plus digits.
- DD-110: `lastEventId` is projected strictly on `/project` and `/missions`, as `eventId` is on the stream; the oracle never projects it. Real ledgers carry ULID event ids, so no real data is affected.
- Pre-merge squad rulings of 2026-10-13 (`kitty-specs/mission-status-read-api-overview-01M4EMSA/reviews/analyze.ruling.md`), each a deliberate divergence from the oracle that real data does not trigger:
  - Ruling 1 (J7): `acceptedAt`, `mergedAt` and `discardedAt` of `/missions` are projected strictly and are nullable. A value that is not an instant, or that is shaped like a path, an address or a secret, is `null`, and the lifecycle status is derived from the projected value, so a junk date cannot make a Mission `done` or `discarded`. The oracle serves the text as stored.
  - Ruling 2 (J8): the actor handles `tool`, `role` and `profile` of a stream event are projected strictly and are nullable, so a token-, path- or address-shaped handle is `null`. The oracle serves a handle that matches the handle pattern.
  - Ruling 3 (J4): `.kittify` must resolve inside the project root by real path; the oracle follows a link out of the root.
  - Single-remedy rulings (J6): an `at` or a `timestamp` that is not an instant drops the stream event with one `projection_refused` diagnostic; the oracle forwards the text.

## Release and binaries

Native binaries for Linux x64, Linux arm64, macOS arm64 and Windows x64 are built by CI and attached to a GitHub release together with a `.sha256` file each. The maintainer cuts a release by pushing a tag of the form `mission-status-api-v<semver>`; nothing is published from a pull request, and this service is not on PyPI, not in the wheel and has no auto-update.

- The release job attests build provenance for the four binaries (`actions/attest-build-provenance`). Verify a download with `gh attestation verify <binary> --repo spec-kitty/spec-kitty`.
- Each binary has a `.sha256` file: it shows that a download matches what the build job produced, not where it was built; the attestation does that.
- The binaries are unsigned: macOS Gatekeeper and Windows SmartScreen warn on first run. Verify a download against its `.sha256` file.
- A release asset carries no Unix file mode. On Linux and macOS run `chmod +x <binary>` before the first start.

## Package layout

Root package `org.speckitty.missionstatus`. The service is a read-only query side; the command side is reserved and does not exist.

- `application.query`: `MissionStatusQueryService`, `ProjectionCache`, and `stream` (`ChangeFeed`, `StreamSubscriber`, `Resume`, `StreamSettings`).
- `application.query.port.in` and `application.query.port.out` hold interfaces only (`MissionStatusQuery`, `Subscription`; `MissionEventSource`). Their value types are in `dto`, their failures in `exceptions`.
- `application.command`: reserved. Nothing in `application.query` may depend on it (an architecture rule).
- `domain.model`, `domain.readmodel` (`overview`, `reducer`, `paging`, `cursor`) and `domain.redaction`.
- `adapter.in.http`, `adapter.out.filesystem` and `config`.

## Tests

From this directory, with placeholders for what is yours:

- `./gradlew check` runs the JVM tests, the architecture rules, the coverage floors and the replay of the native request set against the JVM service. The build needs the contract document as `-PcontractBundle=<file> -PcontractBundleSha256=<digest>`.
- `./gradlew nativeCompile nativeTest` builds the native binary and runs the tests tagged for it.
- `./gradlew nativeSmoke -PnativeBinary=<path of the built binary>` starts the binary and replays `src/test/resources/nativesmoke/requests.json` byte for byte against its goldens, in two stages: `base` (the golden set, every refusal code and an append-while-open stream round trip) and `hostOrigin` (the Host and Origin refusals and their accepted controls). It writes a digest of the response bodies; the four CI legs must write the same digest.
  The replay also counts the service's child processes before and after the requests and requires the count not to move; a child the binary already had when it became ready (on Windows, the console host) is not a process the replay started.
- Performance budgets live in `src/test/java/org/speckitty/missionstatus/perf/PerfBudgets.java` (ADR 2026-10-05-2): the primary assertion is a ratio to a same-run floor; the absolute ceiling only stops a test from waiting unbounded and is amended by measurement, never by a retry. The NFR-001 warm p95 ceiling is 400 ms, amended from the initial 200 ms after two hosted 4-cpu runner measurements of 212 ms and 235 ms (load about 3.9, same-run ratio 27.75 against its limit of 40, so no regression).
- `ArtifactConformanceTest` serves every case of `src/test/resources/artifact-conformance/cases.json` (project trees described as data) and requires the status and body of `golden.json`, which the Python reference writes: `.venv/bin/python -m tests.contract._mission_status_artifact_goldens --write` (or `--check`; `tests/contract/test_mission_status_artifact_goldens.py` runs the check). Run the Gradle tests under a UTF-8 locale (`LC_ALL=C.UTF-8`); under a POSIX locale the JVM cannot represent non-ASCII file names.
- `.venv/bin/python -m pytest tests/ci/test_mission_status_api_build.py tests/ci/test_mission_status_gate_checks.py tests/ci/test_mission_status_routing.py tests/ci/test_mission_status_corpus_compare.py -q` from the repository root runs the Python pins on the build and the workflow.

## Terms

Mission, Work Package, Lane, Tail cursor and `log_truncated` are the product's own terms and are defined in its glossary. The rest of this list names identifiers of this code, defined here so that they are not mistaken for glossary terms.

- **BindGuard**: the start-up check in `config` that exits non-zero unless the effective `server.address` is the literal `127.0.0.1` before the web server starts, and unless the connector is bound to a loopback address after it starts.
- **ConfigPin**: the start-up listener in `config` that fixes the places a configuration file is read from to the packaged `application.properties`.
- **reducer**: the code that folds a Mission's status events into one snapshot of Work Package lanes.
- **status event**: one row of a Mission's event log that moves a Work Package between Lanes.
- **`Diagnostic`**: the record written to the service log when a read hits a fault. It carries a stable code and a short Mission id and never a path.
- **overview read model**: the per-Mission summary the service derives from `meta.json` and the reduced event log.
- **conformance golden**: a stored expected response that the service must reproduce byte for byte.
