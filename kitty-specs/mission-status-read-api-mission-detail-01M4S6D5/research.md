# Research: contract models and build spike (WP06, P2, FR-015, D-79)

Date: 2026-10-14. Placeholders: `<repo>` is the repository root, `<scratch>` a directory outside it, `S` is `services/mission-status-api`.
This file is the spike record of WP06. WP11 appends its own sections below; nothing here is rewritten later.

## 1. Pre-flight (C-005, D-107)

Commands run from `<repo>` with `LC_ALL=C.UTF-8`:

```bash
python contracts/tools/bundle.py --root contracts --out "<scratch>/bundle-out" --module mission-status --bundle-only
#   bundle sha256 mission-status fadf8a869e9402306be3fc0a9fb8f3470b507a21ebfa645f0400d53fc2d0effd
cd S && ./gradlew --offline test --tests 'org.speckitty.missionstatus.architecture.CoupledSymbolsShapeTest'   # BUILD SUCCESSFUL
git log -1 --format=%H refs/remotes/m5529/lane-b
#   4dc35c7d5d771cca96f83ef5789f115ca8209b61   (the ref that carries #5529)
grep -rnE '"org\.speckitty\.missionstatus\.(application|domain)' S/src/test S/build.gradle.kts
grep -rnE 'application/port|domain/(overview|reducer|projection|paging|cursor)' tests scripts .github
```

The first grep returns only post-re-cut package names (`application.query...`, `domain.readmodel...`); the second returns nothing, so no stale pre-re-cut path is referenced.
The baseline pin `tests/ci/test_mission_status_api_build.py` passed 162 tests on the lane base before the first change.

## 2. The closure of the five operations (T037)

The five operations are `getMission`, `getWorkPackage`, `getWorkPackageDetail`, `listArtifacts`, `getArtifactContent`.
The script follows every `$ref` from their path files (and so from every response they name) through `contracts/`, and collects the stem of every file under a `schemas/` directory.

```python
import pathlib, yaml
root = pathlib.Path("contracts")
seeds = ["mission-status/paths/missions_missionId.yaml",
         "mission-status/paths/missions_missionId_work-packages_wpId.yaml",
         "mission-status/paths/missions_missionId_work-packages_wpId_detail.yaml",
         "mission-status/paths/missions_missionId_artifacts.yaml",
         "mission-status/paths/missions_missionId_artifacts_content.yaml"]
seen, schemas, todo = set(), set(), list(seeds)
def refs(node):
    if isinstance(node, dict):
        for k, v in node.items():
            if k == "$ref" and isinstance(v, str): yield v
            else: yield from refs(v)
    elif isinstance(node, list):
        for v in node: yield from refs(v)
while todo:
    rel = todo.pop()
    if rel in seen: continue
    seen.add(rel)
    doc = yaml.safe_load((root / rel).read_text(encoding="utf-8"))
    base = (root / rel).parent
    for r in refs(doc):
        target = r.split("#")[0]
        if not target: continue
        p = (base / target).resolve().relative_to(root.resolve()).as_posix()
        if "/schemas/" in "/" + p: schemas.add(pathlib.Path(p).stem)
        todo.append(p)
print(len(schemas)); print(",".join(sorted(schemas)))
```

Result (46 schemas):

```
Actor,ActorHandle,ArtifactContent,ArtifactEntry,ArtifactKind,ArtifactListing,ArtifactPath,ArtifactReference,ArtifactReferences,ArtifactRefusal,ArtifactRefusalCode,Assignment,Authored,Cancellation,ChangeState,DependencyRef,HistoryEntry,LifecycleStatus,MissionDetail,MissionHead,MissionId,MissionPhase,MissionProgress,OwnedFile,Problem,Readiness,RelativeReference,Review,ReviewCycle,ReviewOverride,ReviewResult,ReviewVerdict,Staleness,StatusLane,StatusLaneCounts,StreamCursor,Subtask,SubtaskProgress,Topology,WorkPackage,WorkPackageDetail,WorkPackageDetailRefusal,WorkPackageDetailRefusalCode,WorkPackageSummary,Workspace,WpId
```

The explicit models list of `openApiGenerate` is this closure united with the eleven names the two existing operations already needed
(`MissionOverview`, `MissionOverviewPage`, `PageCursorRefusal`, `PageInfo`, `Problem_1` and the rest of the old list), plus three inline
duplicates the compiler asked for: `Actor_1`, `Readiness_1`, `SubtaskProgress_1` (generated as `Actor1`, `Readiness1`, `SubtaskProgress1`). 55 names.
Names that are plain string schemas (`ArtifactKind`, `StatusLane`, `ChangeState`, ids and the like) generate no class; they are inlined as `String` or as a nested enum. They stay in the list: an extra name is harmless.
Generating once with the candidate list produced 41 model classes; the first compile asked for exactly the three `_1` names above and nothing else. After adding them `openApiGenerate compileJava` is green.
`FILTER`, `apis` (empty) and `interfaceOnly` (true) are unchanged: no `*Api` interface gained a method.

## 3. Spike harness

A throwaway test (replaced by the standing `GeneratedModelsCanonicalFormTest` and `WorkPackageTest`) instantiated every generated model through
its no-argument constructor, serialised it with the canonical mapper (`MissionStatusApplicationJson.mapper()`), and compared the written member
names with the `required` list of the schema file. The checks are the three of D-79: (a) a required-nullable member is written as `null`; (b) member
and map-entry order equal the golden's; (c) `WorkPackage.promptMarkdown` is absent when not requested.

## 4. Decision table (T038)

Checks run through the canonical mapper. `a`, `b`, `c` are the D-79 checks; `n/a` means the model has no member the check is about.
"Evidence" names the standing test that re-runs the check: `GeneratedModelsCanonicalFormTest` (an empty instance of each plain model writes every
`required` member, as `null` when unset, in alphabetical order, and writes no optional member), `WorkPackageTest` (hand record).

| Model | a | b | c | Decision | Hand class | Reason |
|---|---|---|---|---|---|---|
| Actor, ArtifactContent, ArtifactEntry, ArtifactListing, ArtifactReference, ArtifactReferences, Assignment, Authored, Cancellation, DependencyRef, HistoryEntry, MissionPhase, OwnedFile, Readiness, Review, ReviewCycle, ReviewOverride, ReviewResult, Staleness, Subtask, SubtaskProgress, WorkPackageDetail, WorkPackageSummary, Workspace (24 rows) | pass | pass | n/a | generated | none | no optional member and no map: every member is required, an unset one is written as `null`, order is alphabetical (`GeneratedModelsCanonicalFormTest`, 24 cases) |
| MissionDetail | pass | pass | n/a | generated | none | composes `MissionHead` (required members) and adds `phases` and `workPackages`, both required; the empty instance writes all 24 members |
| MissionProgress, StatusLaneCounts, StreamCursor, MissionOverview, MissionOverviewPage, PageInfo, Project | pass | pass | n/a | generated | none | already served by #5529; `JacksonContractTest` round-trips every golden through them |
| ArtifactRefusal, WorkPackageDetailRefusal | pass | pass | see note | generated | none | compile-time drift sensor and schema twin only: a refusal is served through the existing hand `ProblemBody` (NON_NULL), exactly as the 400 and 500 Problems of #5529 are, because the shared `Problem` has optional text members (`type`, `detail`, `instance`, `code`) that the generated class writes as `null`. No route serialises these two classes |
| ActorHandle, ArtifactKind, ArtifactPath, ArtifactRefusalCode, ChangeState, LifecycleStatus, MissionHead, MissionId, RelativeReference, ReviewVerdict, StatusLane, Topology, WorkPackageDetailRefusalCode, WpId (14 rows) | n/a | n/a | n/a | generated (no class) | none | string schemas, enums and the open `MissionHead` piece: the generator inlines them as `String` or as a nested enum of the referencing model; the names stay in the list because an extra name is harmless |
| Problem, Problem_1 | n/a | n/a | n/a | generated | none | unchanged from #5529; the error side uses `ProblemBody` |
| **WorkPackage** | pass | **fail** | **fail** | **hand** | `WorkPackage` | see below |

### WorkPackage: the failing checks (hand row)

Check (c). The contract says `promptMarkdown` is "returned only when the request sets `includePrompt` to true; otherwise the property is absent".
The generated class holds `private @Nullable String promptMarkdown = null` and no `@JsonInclude` (`generateJsonIncludeAnnotations` is `false`, and
the pin forbids changing it), so an instance with the prompt unset serialises as

```
{"actor":null,"assignment":null,"authored":null,"cancellation":null,"dependencies":[],"executionMode":null,"forceCount":0,"history":[],"implementerOfRecord":null,"lastEventId":null,"lastTransitionAt":null,"mergeTargetBranch":null,"ownedFiles":[],"phaseLabel":null,"priority":null,"promptMarkdown":null,"readiness":null,"readyToStart":false,"requirementRefs":[],"review":null,"staleness":null,"statusLane":null,"subtaskProgress":null,"subtasks":{"T001":"done","<U+1F600>":"done","<U+FF5E>":"planned"},"taskType":null,"title":null,"trackerRefs":[],"wpId":"WP01"}
```

`"promptMarkdown":null` is written where the contract demands absence (a `null` is valid for the schema type but is not what the contract documents and not
what the golden holds). `GeneratedModelsCanonicalFormTest#theGeneratedWorkPackageWritesAnUnsetPromptAsNullWhichIsWhyTheRecordExists` pins the text.

Check (b). The open `subtasks` map is the one place where member order can differ. In the line above the generated twin writes `<U+1F600>` (U+1F600,
surrogate pair D83D DE00) before `<U+FF5E>` (U+FF5E): that is `String` natural order (UTF-16), set by `ORDER_MAP_ENTRIES_BY_KEYS`. The golden sorts by code
point, which puts U+FF5E first. `WorkPackageTest#theOpenSubtasksMapIsWrittenInCodePointOrderNotUtf16Order` shows the record writing
`{"T001":"done","<U+FF5E>":"planned","<U+1F600>":"done"}` and the twin not doing so. Check (a) passes: every required member is written, a null one as `null`.

Result: the hand record `adapter.in.http.dto.WorkPackage` with `@JsonInclude(NON_NULL)` on `promptMarkdown` only and a code-point-ordered serializer
on `subtasks`. `HAND_DTO_RECORDS` of `tests/ci/test_mission_status_api_build.py` is exactly `{WorkPackage}`; no route phase may add a record (D-111).
All other members of the record are composed of generated models (`Authored`, `Assignment`, `SubtaskProgress`, `Actor`, `Cancellation`, `Readiness`,
`Review`, `HistoryEntry`, `Staleness`). `statusLane` is a `String` because `StatusLane` is inlined as a nested enum of each referencing model.

## 5. Drift sensors for a hand record ("Plan defects found" item 1)

A hand record cannot fail when the contract changes. The mechanism adopted, as the WP prompt proposes:

- the schema `WorkPackage` stays in the explicit models list, so its generated twin exists and is unused at runtime;
- `ContractDriftProbe` references one member of the twin (`new WorkPackage().forceCount(1)`) and reads the same member from the hand record
  (`handWorkPackageForceCount`), so a rename of `forceCount` in a contract copy stops the probe compiling;
- `WorkPackageTest#theRecordComponentsAreExactlyThePropertiesOfTheSchema` compares the record component names with the property names read from
  `schemas/WorkPackage.yaml`;
- the twin and the record cannot clash: they live in `adapter.in.http.model` and `adapter.in.http.dto`.

`ContractDriftNestedBuildTest` renames one member of each of the 28 models in one contract copy (a single nested build; javac reports every missing
symbol of the probe and quotes each probe line) and asserts that every quoted reference is among the errors. Two refusals need an enum argument
(`code(ArtifactRefusal.CodeEnum.NOT_FOUND)`): the shared `Problem` also declares a text `code`, so renaming the own `code` leaves `code(String)` behind
and a `code(null)` reference would still compile.

## 6. Skipped-test report hook, planted-class control, test-run facts

- `build.gradle.kts` `test` task: a `doLast` between the markers `BEGIN/END not-run report hook` appends `build/reports/not-run.txt` to the file named
  by `GITHUB_STEP_SUMMARY`, or prints it. `SkipReportNestedBuildTest` runs three nested builds: with the hook (stdout, and a summary file), without it
  (the control script has the marker region removed: nothing printed, summary unchanged) and a script-shape check. It was red before the hook existed.
- `PlantedClassCoverageNestedBuildTest`: a small covered `domain` class and `application` class pass `jacocoTestCoverageVerification`; planting one
  untested class in either package fails it with `Rule violated for class ...Planted ... lines covered ratio is 0.00`. With the domain and application
  line floors set to 0.00 in the script, the two planted legs go red (checked once, script restored).
- Nested-build test source must not live under a `build` package: the `test` source set excludes `**/org/speckitty/missionstatus/build/**` (they belong
  to the `kit` source set), so a probe test planted there is compiled by neither. The nested copies use `...missionstatus.probe`.
- `kitTest` declares no input for the files its tests read at run time (`kit.projectDir`, the contract): after editing only a main source file it reports
  UP-TO-DATE and runs nothing. Use `kitTest --rerun` for a mutation check.
- Red-first on the record: with `@JsonInclude(NON_NULL)` removed 11 of 27 `WorkPackageTest` cases fail; with the serializer removed the subtasks case fails.
  With the probe line of `Workspace` replaced, both `ContractDriftNestedBuildTest` cases that cover it fail.

## WP11 (P6): the YAML 1.1 / 1.2 parity spike of the Work Package frontmatter decoder (FR-006, R-3, R-15, S-19)

*Appended by WP11 (named edit, append-only). Ran on lane `lane-j` at commit `8fc59c3a999a14587780fee85298660b5216aa06` (the commit that adds the codecs; the parity numbers below were re-run on the final tree of the WP, whose decoders are byte-identical to that commit). Oracle side: Python 3.11.15, ruamel.yaml 0.19.1 (`YAML()` round-trip loader, YAML 1.2, as `FrontmatterManager` configures it), pydantic 2.13.3, `read_authored_wp_frontmatter` (`model_validate(..., strict=False)`), the lane's own `src/`. Java side: `WpFrontmatterCodec`, snakeyaml as the Spring Boot BOM manages it (no dependency was added: AC-19.4).*

### Policy

snakeyaml's default resolver is YAML 1.1; ruamel's is YAML 1.2. The decoder therefore takes snakeyaml's **parser events** only, which are shared syntax, and never lets snakeyaml resolve or construct a value. A plain scalar is resolved by a port of ruamel's YAML 1.2 implicit resolvers and constructed the way ruamel's `construct_yaml_int` and `construct_yaml_float` do. What the decoder cannot read identically is **refused** (the file is skipped with `wp_file_skipped`, the safe side of R-15), never read differently. E-6 (a dialect case that needs a dependency and cannot be refused without breaking an oracle-parsed fixture) was **not** triggered: every case the corpus `wpm-01..28` needs decodes identically.

### The dialect cases (field value `V` spelled after a key; "str field" is a `str | None` member such as `priority`)

| Case | Oracle (YAML 1.2) | snakeyaml default (YAML 1.1) | Java decoder |
|---|---|---|---|
| `yes`, `Yes`, `YES`, `no`, `on`, `On`, `ON`, `off`, `y`, `n` | string | boolean | string: identical (`wpm-14`, `wpm-15` parse) |
| `true`, `True`, `TRUE`, `false` | boolean | boolean | boolean: a str field refuses it, `phase` is `"True"`; identical |
| `~`, `null`, `Null`, `NULL`, empty | null | null | null: identical |
| `010` | integer 10 | octal 8 | integer 10 (a str field refuses it: `wpm-16`; `shell_pid` accepts it); identical |
| `0777` | integer 777 | octal 511 | integer 777; identical |
| `0o17`, `0x1F`, `0b101`, `1_000`, `+5` | integers 15, 31, 5, 1000, 5 | differs for `0o17` | same integers; identical |
| `1:30` | string | sexagesimal integer | string; identical |
| `1.5`, `.5`, `1e3`, `1.`, `1_0.5`, `.inf`, `-.inf`, `.nan` | float | mostly float | float; `phase` prints as Python does (`1.5`, `0.5`, `1000.0`, `1.0`, `10.5`, `inf`, `-inf`, `nan`) in the range where Java and Python print alike, refused outside it (`1e20`, `0.00001`) |
| `2026-09-01` | date | date | date: a str field refuses it (`wpm-17`), `phase` is `2026-09-01`; identical |
| `2026-09-01T10:00:00Z`, `2026-9-1 1:02:03 +5` | datetime | datetime | datetime: a str field refuses it, identical; `phase` and a subtask entry whose `str()` is a datetime are refused (not reproduced) |
| `2026-13-01`, `2026-02-30`, `0000-01-01`, hour 25, minute 61, second 61, offset +24:00 | ruamel raises: file skipped | n/a | refused: identical |
| `-_`, `0b_`, `0o_`, `0x_` | ruamel raises (empty digits): file skipped | n/a | refused: identical |
| `<<` or `=` as a value | merge and value tags: a str field refuses it, `phase` is the text | n/a | same |
| `<<: {...}` as a key (merge) | merges the keys | n/a | **refused** (merge keys) |
| `&anchor`, `*alias`, `!!tag`, `!custom` | read | read | **refused** |
| U+0085, U+2028, U+2029 inside the YAML text | kept as characters | folded as line breaks | **refused** |
| `phase`/subtask entry that is a mapping or sequence | `str()` of the container | n/a | `phase`: refused; `subtasks`: the file parses and `WpMetadata.subtasksRefused` is true (SK-353, D-97, V20) |
| duplicate key (top level, nested, flow, quoted/plain spellings) | `DuplicateKeyError`: skipped | last wins | refused: identical |
| second YAML document | error: skipped | n/a | refused: identical |
| non-printable character, tab indentation, syntax error | error: skipped | error | refused: identical |
| `shell_pid` that `int()` cannot convert (a list, a mapping, a date, `.inf`, an explicit tag) | an **escaping** `TypeError` or `OverflowError` that the oracle's index does not catch | n/a | skipped (the safe side) |
| framing: BOM (one is dropped), CRLF and lone CR, closing `---` with trailing or Unicode spaces, `---abc` opening line, no frontmatter, no closing delimiter, bytes that are not strict UTF-8 | as in `FrontmatterManager.read` | n/a | identical |

### Results

- **All 3550 `kitty-specs/*/tasks/WP*.md` files of the lane** (every Mission of the repository): 3550 of 3550 give the same outcome class and the same kept fields (id, title, phase, task type, priority, execution mode, merge target and planning base branch, role, agent profile, model, dependencies, requirement refs, tracker refs, owned files, subtasks, body) as the oracle. None is refused.
- **690 synthetic dialect cases** (every table row above, each spelled after seven string-field keys and the list, subtask, agent, reviewer, history, base-commit and lane members): 657 identical (278 parsed, 379 skipped); 12 where the oracle raises an escaping exception on `shell_pid` and the Java side skips; 21 refused by policy (anchors, aliases, tags, the merge key, the three line-break characters, and `str()` of a datetime or a container in `phase`).
- **Review-cycle files** (`ReviewCycleCodec` against `ReviewCycleArtifact.from_file` plus the contract's `is_rfc3339_date_time`): 1744 files (every real `review-cycle-*.md` of the repository, 1708, and 36 synthetic cases), 1743 identical, 1 refused by policy (an anchor). An **unquoted** timestamp in `reviewed_at` is a timestamp under YAML 1.2, not a string, so the whole file is unparsed (null members) in both.
- **`lanes.json`** (`LanesCodec` against `read_lanes_json`): 572 files (every real one, 537, and 35 synthetic), 567 identical, 4 where Java is stricter on a shape the oracle misuses (a `wp_ids` that is a string, which Python splits into characters; a non-string lane id, Work Package id or slug), 1 where the oracle raises an escaping `AttributeError` (`collapse_report: null`) and Java answers `Corrupt`. Every one of the five is a refusal (500 `source_unreadable`), the safe side.

### Decision

Refuse-what-you-cannot-decode-identically stays the default (R-15). The nightly all-file comparison (AC-6.4, WP17/WP18) is the standing form of the 3550-file comparison above and must keep the refused list empty for Work Package files. The decoder's `UNSUPPORTED_YAML` rejection class is the counter to watch.
