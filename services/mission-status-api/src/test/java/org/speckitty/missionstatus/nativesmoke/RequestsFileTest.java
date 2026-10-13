package org.speckitty.missionstatus.nativesmoke;

import static org.assertj.core.api.Assertions.assertThat;

import java.nio.charset.StandardCharsets;
import java.util.HashSet;
import java.util.List;
import java.util.Set;
import org.junit.jupiter.api.Test;

/** The shape of {@code requests.json} (T064): schema, unique ids, existing goldens and trees, floors tied to the file, literal expectations. */
class RequestsFileTest {

  private final SmokeRequests requests = SmokeRequests.load();

  @Test
  void theFileHasNoProblems() {
    assertThat(requests.problems()).isEmpty();
  }

  @Test
  void everyIdIsUniqueAndAPlainAsciiSlug() {
    Set<String> seen = new HashSet<>();
    for (SmokeRequests.Request request : requests.allRequests()) {
      assertThat(request.id()).matches("[a-z0-9][a-z0-9-]*");
      assertThat(seen.add(request.id())).as("id " + request.id() + " is unique").isTrue();
    }
  }

  @Test
  void theBaseFloorIsTheNumberOfBaseRequestsAndTheSumOfFloorsIsWhatTheGateGets() {
    assertThat(requests.stageNames()).contains("base", "hostOrigin");
    assertThat(requests.floor("base")).isPositive().isEqualTo(requests.requestCount("base"));
    assertThat(requests.floorSum()).isEqualTo(requests.stageNames().stream().mapToInt(requests::floor).sum());
  }

  @Test
  void theHostOriginFloorIsExactlyTheNumberOfItsRequests() {
    assertThat(requests.floor("hostOrigin")).isPositive().isEqualTo(requests.requestCount("hostOrigin"));
    assertThat(requests.floorSum()).isEqualTo(requests.floor("base") + requests.floor("hostOrigin"));
  }

  @Test
  void theHostOriginStageHoldsEachRefusalClassAndItsAcceptedControls() {
    List<SmokeRequests.Request> stage =
        requests.groups().stream().filter(group -> group.stage().equals("hostOrigin")).flatMap(group -> group.requests().stream()).toList();
    // a foreign Host, a foreign Origin with an accepted Host, and a TRACE with a foreign Host (the ERROR dispatch): 403 request_refused, each with a golden
    assertThat(stage).anySatisfy(r -> assertThat(r.headers().get("Host")).startsWith("evil.example:").isNotNull());
    assertThat(stage).anySatisfy(r -> assertThat(r.headers().get("Origin")).isEqualTo("https://evil.example"));
    assertThat(stage).anySatisfy(r -> assertThat(r.method()).isEqualTo("TRACE"));
    assertThat(stage.stream().filter(r -> "request_refused".equals(r.expectedProblemCode()))).isNotEmpty().allSatisfy(r -> {
      assertThat(r.expectedStatus()).isEqualTo(403);
      assertThat(r.expectedGolden()).isEqualTo("smoke:host-origin-refused.json");
    });
    // the container-decided Host keeps its 400 (status only); the controls are accepted
    assertThat(stage).anySatisfy(r -> {
      assertThat(r.headers().get("Host")).startsWith("evil.example@127.0.0.1:");
      assertThat(r.expectedStatus()).isEqualTo(400);
    });
    assertThat(stage.stream().filter(r -> r.expectedStatus() == 200)).hasSizeGreaterThanOrEqualTo(2).allSatisfy(r -> assertThat(r.expectedGolden()).isNotNull());
  }

  @Test
  void theBaseStageHoldsEveryRefusalCodeTheContractNamesAndTheRowsOfTheFailureTable() {
    List<String> codes = requests.allRequests().stream().map(SmokeRequests.Request::expectedProblemCode).filter(c -> c != null).toList();
    assertThat(codes)
        .contains("invalid_page_cursor", "negative", "misaligned", "cursor_without_mission", "out_of_range", "content_mismatch")
        .contains("ledger_unparseable", "ledger_torn_tail");
    assertThat(requests.allRequests()).anySatisfy(r -> assertThat(r.expectedStatus()).isEqualTo(404));
    assertThat(requests.allRequests()).anySatisfy(r -> assertThat(r.path()).isEqualTo("/api/v1/openapi.yaml"));
    assertThat(requests.allRequests()).anySatisfy(r -> assertThat(r.stream()).isNotNull());
  }

  @Test
  void theCuratedGoldenSetIncludesTheCrlfListingAndCanaryTrees() {
    List<String> trees = requests.groups().stream().map(SmokeRequests.Group::tree).toList();
    assertThat(trees).contains("crlf-and-listing/crlf-and-lf-twin", "crlf-and-listing/listing-order", "secret-canaries/planted-canaries");
  }

  @Test
  void everyExpectationIsALiteralAndNoPathOfTheMachineIsInTheFile() {
    String text = new String(SmokeRequests.rawBytes(), StandardCharsets.UTF_8);
    assertThat(text).doesNotContain("/" + "home/").doesNotContain("/" + "Users/").doesNotContain("\\" + "Users");
    for (SmokeRequests.Request request : requests.allRequests()) {
      assertThat(request.expectedStatus()).as(request.id()).isBetween(200, 599);
      assertThat(request.path()).as(request.id()).startsWith("/api/v1/").doesNotContain("hello");
    }
  }

  @Test
  void anEmptyOrBrokenFileReportsProblemsInsteadOfPassing() {
    assertThat(SmokeRequests.parse("{}".getBytes(StandardCharsets.UTF_8)).problems()).isNotEmpty();
    assertThat(SmokeRequests.parse("{\"stages\":{\"base\":{\"requestCountFloor\":1}},\"groups\":[]}".getBytes(StandardCharsets.UTF_8)).problems()).isNotEmpty();
    String unknownTree = "{\"stages\":{\"base\":{\"requestCountFloor\":1}},\"groups\":[{\"stage\":\"base\",\"tree\":\"nope/none\",\"requests\":[{\"id\":\"a\",\"method\":\"GET\",\"path\":\"/api/v1/project\",\"expectedStatus\":200}]}]}";
    assertThat(SmokeRequests.parse(unknownTree.getBytes(StandardCharsets.UTF_8)).problems()).anyMatch(p -> p.contains("nope/none"));
    String missingGolden = unknownTree.replace("nope/none", "project-header/healthy").replace("\"expectedStatus\":200", "\"expectedStatus\":200,\"expectedGolden\":\"tree:absent.json\"");
    assertThat(SmokeRequests.parse(missingGolden.getBytes(StandardCharsets.UTF_8)).problems()).anyMatch(p -> p.contains("absent.json"));
    String duplicate = unknownTree.replace("nope/none", "project-header/healthy").replace("}]}]}", "},{\"id\":\"a\",\"method\":\"GET\",\"path\":\"/api/v1/project\",\"expectedStatus\":200}]}]}");
    assertThat(SmokeRequests.parse(duplicate.getBytes(StandardCharsets.UTF_8)).problems()).anyMatch(p -> p.contains("duplicate"));
  }
}
