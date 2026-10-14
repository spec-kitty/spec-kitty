package org.speckitty.missionstatus.adapter.in.http.contract;

import static org.assertj.core.api.Assertions.assertThat;

import java.io.IOException;
import java.nio.charset.StandardCharsets;
import java.nio.file.Files;
import java.nio.file.Path;
import java.util.ArrayList;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;
import java.util.Set;
import java.util.TreeMap;
import java.util.TreeSet;
import java.util.stream.Stream;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.params.ParameterizedTest;
import org.junit.jupiter.params.provider.MethodSource;
import org.speckitty.missionstatus.conformance.golden.ServedRoute;
import org.speckitty.missionstatus.conformance.golden.ServedRoute.Entry;
import org.speckitty.missionstatus.conformance.golden.ServedRoutes;
import org.speckitty.missionstatus.conformance.golden.served.WorkPackageServedRoute;
import org.speckitty.missionstatus.testsupport.CanonicalJson;
import org.yaml.snakeyaml.Yaml;

/**
 * AC-15.1 to AC-15.3: every response of the five detail operations validates against the contract the service bundles. The parameter set is
 * every served pair of the detail golden manifest (all four providers, every request key), answered by the production application over the
 * fixture, so the refusals of the fixtures are in it as Problems; each body is judged by the schema of its operation and, for a Problem, of
 * the status it carries. The contract's own examples for the five operations validate too, and each is either reproduced by a served body or
 * named in {@link #NOT_REPRODUCED} with the reason (a floor on the discovered count stops a glob that matches nothing).
 */
class DetailResponseContractValidationTest {

  private static final ContractValidator VALIDATOR = ContractValidator.fromClasspath();
  private static final Path CONTRACT = Path.of(System.getProperty("user.dir")).resolve("../../contracts/mission-status").normalize();

  static final String MISSION = "/missions/{missionId}";
  static final String WORK_PACKAGE = "/missions/{missionId}/work-packages/{wpId}";
  static final String DETAIL = "/missions/{missionId}/work-packages/{wpId}/detail";
  static final String LISTING = "/missions/{missionId}/artifacts";
  static final String CONTENT = "/missions/{missionId}/artifacts/content";

  /** The operation of each golden file. */
  static final Map<String, String> PATH_OF_GOLDEN =
      Map.of(
          "get-mission.json", MISSION,
          "get-work-package.json", WORK_PACKAGE,
          "get-work-package-prompt.json", WORK_PACKAGE,
          "get-work-package-detail.json", DETAIL,
          "list-artifacts.json", LISTING,
          "get-artifact-content.json", CONTENT);

  /** The floor on the contract examples of the five operations (a glob that matches nothing is red). */
  static final int EXAMPLE_FLOOR = 34;

  /** The floor on the served bodies of the parameter set. */
  static final int BODY_FLOOR = 300;

  /** One served body: where it came from, the operation and the body text. */
  record Served(String name, String path, String body) {
    @Override
    public String toString() {
      return name;
    }
  }

  private static List<Served> served;

  /** Every served pair x request key, answered once for the whole class. */
  @SuppressWarnings("unchecked")
  static synchronized List<Served> allServed() {
    if (served == null) {
      List<Served> out = new ArrayList<>();
      for (ServedRoute provider : ServedRoutes.loaded()) {
        for (Entry entry : provider.served()) {
          for (String key : WorkPackageServedRoute.requestKeys(WorkPackageServedRoute.fixture(entry.fixtureKey()), entry.goldenFile())) {
            byte[] raw = provider.body(entry, key);
            String text = new String(raw, StandardCharsets.UTF_8);
            text = unwrapped(text);
            out.add(new Served(entry.fixtureKey() + " " + entry.goldenFile() + " " + key, PATH_OF_GOLDEN.get(entry.goldenFile()), text));
          }
        }
      }
      served = List.copyOf(out);
    }
    return served;
  }

  /** Some providers answer {@code {"body":..., "status":...}}: the body is what was on the wire. A Problem or a view never has exactly these two members. */
  @SuppressWarnings("unchecked")
  private static String unwrapped(String text) {
    Object parsed = CanonicalJson.parse(text.getBytes(StandardCharsets.UTF_8));
    if (parsed instanceof Map<?, ?> members && members.keySet().equals(Set.of("body", "status"))) {
      return new String(CanonicalJson.toBytes(((Map<String, Object>) parsed).get("body")), StandardCharsets.UTF_8);
    }
    return text;
  }

  static Stream<Served> servedBodies() {
    return allServed().stream();
  }

  /** The problems of a body: judged as a Problem of the status it carries, or as the 200 body of the operation. */
  @SuppressWarnings("unchecked")
  static List<String> problems(String path, String body) {
    Object parsed = CanonicalJson.parse(body.getBytes(StandardCharsets.UTF_8));
    if (parsed instanceof Map<?, ?> members && members.containsKey("status") && members.containsKey("code")) {
      String status = String.valueOf(((CanonicalJson.Num) members.get("status")).text());
      return VALIDATOR.validate(refusalSchema(path, status), body);
    }
    return VALIDATOR.validate(VALIDATOR.responseSchema(path, "200", "application/json"), body);
  }

  private static tools.jackson.databind.JsonNode refusalSchema(String path, String status) {
    try {
      return VALIDATOR.responseSchema(path, status, "application/problem+json");
    } catch (IllegalArgumentException undeclared) {
      return VALIDATOR.responseSchema(path, "default", "application/problem+json");
    }
  }

  @Test
  void theParameterSetHoldsItsFloorAndEveryDetailRouteIsInIt() {
    assertThat(allServed()).hasSizeGreaterThanOrEqualTo(BODY_FLOOR);
    assertThat(allServed().stream().map(Served::path).collect(java.util.stream.Collectors.toSet())).containsExactlyInAnyOrder(MISSION, WORK_PACKAGE, DETAIL, LISTING, CONTENT);
    assertThat(allServed()).as("the refusals of the fixtures are in the set").anyMatch(entry -> entry.body().contains("\"code\""));
  }

  @ParameterizedTest(name = "{0}")
  @MethodSource("servedBodies")
  void everyServedAnswerValidatesAgainstTheContract(Served answer) {
    assertThat(problems(answer.path(), answer.body())).isEmpty();
  }

  // ---- AC-15.1 control -------------------------------------------------------------------------------------------------------

  @Test
  void controlAnExtraMemberAndAWrongTypeAreRefused() {
    Served ok = allServed().stream().filter(answer -> answer.path().equals(MISSION) && !answer.body().contains("\"code\"")).findFirst().orElseThrow();
    assertThat(problems(ok.path(), ok.body())).isEmpty();

    String extra = ok.body().replaceFirst("\\{", "{\"surprise\":1,");
    assertThat(problems(ok.path(), extra)).isNotEmpty();

    String wrongType = ok.body().replaceFirst("\"wpTotal\":[0-9]+", "\"wpTotal\":\"many\"");
    assertThat(wrongType).isNotEqualTo(ok.body());
    assertThat(problems(ok.path(), wrongType)).isNotEmpty();
  }

  // ---- AC-15.2: the contract's examples --------------------------------------------------------------------------------------

  private static boolean isOfTheFive(String name) {
    return name.startsWith("MissionDetail.")
        || name.startsWith("WorkPackage.")
        || name.startsWith("WorkPackageDetail.")
        || name.startsWith("WorkPackageDetailRefusal.")
        || name.startsWith("ArtifactListing.")
        || name.startsWith("ArtifactContent.")
        || name.startsWith("ArtifactRefusal.");
  }

  /** The example files of the five operations. */
  static List<Path> examples() throws IOException {
    try (Stream<Path> files = Files.list(CONTRACT.resolve("examples"))) {
      return files.filter(file -> file.getFileName().toString().endsWith(".yaml") && isOfTheFive(file.getFileName().toString())).sorted().toList();
    }
  }

  static Stream<Path> exampleFiles() throws IOException {
    return examples().stream();
  }

  /** The operation and status an example is the answer to. */
  @SuppressWarnings("unchecked")
  static String pathOf(String name, Map<String, Object> body) {
    if (name.startsWith("MissionDetail.")) {
      return MISSION;
    }
    if (name.startsWith("WorkPackageDetail")) {
      return DETAIL;
    }
    if (name.startsWith("WorkPackage.")) {
      return WORK_PACKAGE;
    }
    if (name.startsWith("ArtifactListing.") || "artifact_listing_unreadable".equals(body.get("code"))) {
      return LISTING;
    }
    return CONTENT;
  }

  @Test
  void theExampleSetHoldsItsFloor() throws IOException {
    assertThat(examples()).hasSizeGreaterThanOrEqualTo(EXAMPLE_FLOOR);
  }

  @ParameterizedTest(name = "{0}")
  @MethodSource("exampleFiles")
  void everyContractExampleOfTheFiveOperationsValidates(Path example) throws IOException {
    @SuppressWarnings("unchecked")
    Map<String, Object> body = (Map<String, Object>) new Yaml().load(Files.readString(example, StandardCharsets.UTF_8));
    String json = JSON.writeValueAsString(body);

    assertThat(problems(pathOf(example.getFileName().toString(), body), json)).as(example.getFileName().toString()).isEmpty();
  }

  private static final tools.jackson.databind.json.JsonMapper JSON = tools.jackson.databind.json.JsonMapper.builder().build();

  /** The canonical bytes of a JSON text, so two texts compare equal exactly when they say the same thing. */
  static String canonical(String json) {
    return new String(CanonicalJson.toBytes(CanonicalJson.parse(json.getBytes(StandardCharsets.UTF_8))), StandardCharsets.UTF_8);
  }

  /** The examples that a served body reproduces byte for byte (canonical form). */
  static Set<String> reproduced() throws IOException {
    Set<String> bodies = new TreeSet<>();
    allServed().forEach(answer -> bodies.add(canonical(answer.body())));
    Set<String> names = new TreeSet<>();
    for (Path example : examples()) {
      if (bodies.contains(canonical(jsonOf(example)))) {
        names.add(example.getFileName().toString());
      }
    }
    return names;
  }

  @SuppressWarnings("unchecked")
  static String jsonOf(Path example) throws IOException {
    return JSON.writeValueAsString(new Yaml().load(Files.readString(example, StandardCharsets.UTF_8)));
  }

  /** The examples that no fixture reproduces byte for byte, each with the reason. A name here that a fixture does reproduce is a red. */
  static final Map<String, String> NOT_REPRODUCED = new TreeMap<>();

  static {
    String fault = "a refusal for a fault (an unreadable listing or file) that the fixtures cannot provoke under every host";
    String ids = "its identifiers and instants are hand-picked (a 26-character Mission id, 2026-09-2x instants), where every fixture serves the zero-padded ids and 2026-09-01 instants";
    // The artifact content examples: the nearest served body differs in path, content and sizeBytes (the closest fixture file is another one).
    NOT_REPRODUCED.put("ArtifactContent.empty.yaml", "serves notes/empty.txt with sizeBytes 0; no fixture holds a zero-byte file at that path (the closest served body is extra.txt, 11 bytes)");
    NOT_REPRODUCED.put("ArtifactContent.json.yaml", "serves contracts/schema.json as application/json, 28 bytes; the fixtures serve contracts/api.yaml (application/yaml, 15 bytes), no JSON file");
    NOT_REPRODUCED.put("ArtifactContent.markdown.yaml", "serves a 64-byte spec.md ('# Example Mission' and a sentence); the fixtures' spec.md is the 16-byte '# planning file'");
    NOT_REPRODUCED.put("ArtifactContent.redacted.yaml", "serves notes/handoff.md with a [path] and an [email] redaction, 81 bytes; the redaction fixture serves only-mail.md with [email] alone, 38 bytes");
    NOT_REPRODUCED.put("ArtifactListing.populated.yaml", "lists 12 entries with sizes of thousands of bytes and 2026-09-22 instants; the artifacts-populated fixture lists 14 entries of 11 to 16 bytes at one 2026-09-21 instant");
    NOT_REPRODUCED.put("ArtifactListing.truncated.yaml", "a stand-in: the example itself says a real truncated listing holds exactly 1000 entries, so a served truncated body has 1000 entries where this one has 3 (no fixture lists 1000 files)");
    NOT_REPRODUCED.put("MissionDetail.early.yaml", "a Mission with a null missionType, created 2026-09-21T09:00:00+02:00 (a non-UTC offset) with an in-progress lifecycle_event phase; the detail-early fixture is software-dev, UTC, all phases pending");
    NOT_REPRODUCED.put("MissionDetail.populated.yaml", "a Mission with displayNumber 12, 41 events and 2026-09-2x instants; the nearest served body, phases-matrix/lc-mix, has a null display number, 14 events and 2026-09-01 instants, and differs in 91 members");
    NOT_REPRODUCED.put("WorkPackage.actor-handle.yaml", ids + "; a finalize-tasks tool actor on WP02 titled 'Define the data model', where the fixtures name the actor claude on WP01");
    NOT_REPRODUCED.put("WorkPackage.actor-redacted.yaml", ids + "; an actor whose tool is redacted to null on WP03; no fixture redacts the tool of an actor");
    NOT_REPRODUCED.put("WorkPackage.actor-structured.yaml", ids + "; a structured actor with a role and a profile (implementer, implementer-ivan); the fixtures' actors carry a tool only");
    NOT_REPRODUCED.put("WorkPackage.canceled.yaml", "a canceled WP (reason 'Superseded by WP09.', source operator) with the structured actor implementer-ivan; the nearest served body, the two-selectors WP08, differs in 17 members, among them a null cancellation and a null actor profile and role");
    NOT_REPRODUCED.put("WorkPackage.no-events.yaml", "WP07 titled 'Prepare the release notes' depending on WP06; the nearest served body, the planning-only fixture's WP02, differs in exactly four members: wpId, title, the dependency and the unsatisfied readiness entry (WP01 there)");
    NOT_REPRODUCED.put("WorkPackage.override-partial.yaml", "a populated assignment (agent claude, profile implementer-ivan, model sonnet) with a partial review override; the nearest served body, projection-nulls/override-partial-junk-at, has a null assignment and actor profile, and differs in 57 members");
    NOT_REPRODUCED.put("WorkPackage.override.yaml", "a populated assignment with a complete review override; the nearest served body, projection-nulls/override-partial-junk-at, has a null assignment and actor profile, and differs in 59 members");
    NOT_REPRODUCED.put("WorkPackage.populated.yaml", "a WP with a populated assignment, a structured actor (implementer-ivan) and a full authored plan; the nearest served body, resolved-state/review-result-sticky WP03, differs in 79 members");
    NOT_REPRODUCED.put("WorkPackage.provisional.yaml", "a provisional WP with a populated assignment and authored members; the nearest served body, resolved-state/model-absent-sentinel, has a null assignment profile, model and provider and agent-one as its agent, and differs in 55 members");
    NOT_REPRODUCED.put("WorkPackage.with-prompt.yaml", "WorkPackage.populated plus its promptMarkdown member (the includePrompt answer); it inherits the populated example's 80 differing members, and no fixture serves a populated plan with a prompt");
    NOT_REPRODUCED.put("WorkPackageDetail.cycle-without-path.yaml", ids + "; a review cycle 2 with a null artifactPath and a null feedbackReference, on a lane-a workspace; the unparseable-cycle fixture has a cycle 1 with both set and a null workspace");
    NOT_REPRODUCED.put("WorkPackageDetail.no-cycles.yaml", ids + "; WP05's detail with T005 subtasks and one literal owned file (isGlob false); the populated fixture's WP02 has a glob and T003");
    NOT_REPRODUCED.put("WorkPackageDetail.null-workspace.yaml", "a detail whose artifactReferences.prompt is null (the prompt file is absent) with the example's own ids; the nearest served body, detail-populated/bad-sibling-after WP01, has the prompt reference set (tasks/WP01-fixture.md) and the zero-padded Mission id");
    NOT_REPRODUCED.put("WorkPackageDetail.planning-lane.yaml", "a planning-lane WP06 with a spec reference and one unknown-state owned file; the nearest null-workspace fixture has no spec reference and no owned files");
    NOT_REPRODUCED.put("WorkPackageDetail.populated.yaml", "WP04 depending on an approved WP03 with three owned files in changed state; the populated fixture's WP01 has no dependencies and two owned files in unknown state");
    NOT_REPRODUCED.put("WorkPackageDetail.unknown-change-state.yaml", "three owned files with an {alpha,beta} brace pattern and a spec reference; the unknown-change-state fixture has two owned files (src/a.py, docs/**) and no spec reference");
    NOT_REPRODUCED.put("WorkPackageDetail.unparseable-cycle.yaml", ids + "; cycle 3 of WP03 on a lane-a workspace with a feedbackReference naming the example Mission; the cycles fixture has cycle 1 and a null workspace");
    NOT_REPRODUCED.put("ArtifactRefusal.artifact-listing-unreadable.yaml", fault);
    NOT_REPRODUCED.put("ArtifactRefusal.artifact-unreadable.yaml", fault);
  }

  @Test
  void everyExampleIsReproducedByAServedBodyOrNamedWithItsReason() throws IOException {
    Set<String> all = new TreeSet<>();
    examples().forEach(file -> all.add(file.getFileName().toString()));
    Set<String> reproduced = reproduced();

    assertThat(reproduced).as("some examples are reproduced by the fixtures").isNotEmpty();
    Set<String> unaccounted = new TreeSet<>(all);
    unaccounted.removeAll(reproduced);
    unaccounted.removeAll(NOT_REPRODUCED.keySet());
    assertThat(unaccounted).as("an example neither reproduced nor named").isEmpty();
    assertThat(NOT_REPRODUCED.keySet()).as("a named example that a fixture does reproduce, or that does not exist").doesNotContainAnyElementsOf(reproduced).isSubsetOf(all);
  }

  // ---- AC-15.3: the drift probe covers every model of the five operations --------------------------------------------------------

  /** The generated models the probe does not name, each with the reason it is not a drift target of the five operations. */
  static final Map<String, String> UNPROBED = new TreeMap<>();

  static {
    String twin = "a generator twin of the model of the same name with a numeral (a name collision of two schemas of one title)";
    for (String name : List.of("Actor1", "Problem1", "Readiness1", "SubtaskProgress1")) {
      UNPROBED.put(name, twin);
    }
    for (String name : List.of("MissionOverviewPage", "PageCursorRefusal", "PageInfo")) {
      UNPROBED.put(name, "a model of listMissions, a route of PR A, not one of the five detail operations");
    }
    UNPROBED.put("Problem", "the shared Problem; every refusal model of the five operations extends it and is probed by its own code enum");
  }

  @Test
  void theDriftProbeNamesEveryGeneratedModelExceptTheOnesListedWithTheirReason() throws IOException {
    Set<String> generated = new TreeSet<>();
    for (com.tngtech.archunit.core.domain.JavaClass type : new com.tngtech.archunit.core.importer.ClassFileImporter().importPackages("org.speckitty.missionstatus.adapter.in.http.model")) {
      if (type.getEnclosingClass().isEmpty() && type.getPackageName().equals("org.speckitty.missionstatus.adapter.in.http.model")) {
        generated.add(type.getSimpleName());
      }
    }
    String probe =
        Files.readString(Path.of(System.getProperty("user.dir")).resolve("src/main/java/org/speckitty/missionstatus/adapter/in/http/ContractDriftProbe.java"), StandardCharsets.UTF_8);
    Set<String> probed = new TreeSet<>();
    java.util.regex.Matcher imports = java.util.regex.Pattern.compile("import org\\.speckitty\\.missionstatus\\.adapter\\.in\\.http\\.model\\.(\\w+);").matcher(probe);
    while (imports.find()) {
      probed.add(imports.group(1));
    }

    assertThat(generated).as("a scan that matches nothing must fail").hasSizeGreaterThanOrEqualTo(40);
    Set<String> unprobed = new TreeSet<>(generated);
    unprobed.removeAll(probed);
    assertThat(unprobed).as("a generated model that the probe does not name and that is not listed").isEqualTo(UNPROBED.keySet());
    assertThat(probed).as("the five operations' models").contains("MissionDetail", "WorkPackage", "WorkPackageDetail", "ArtifactListing", "ArtifactContent", "ArtifactRefusal", "WorkPackageDetailRefusal");
  }
}
