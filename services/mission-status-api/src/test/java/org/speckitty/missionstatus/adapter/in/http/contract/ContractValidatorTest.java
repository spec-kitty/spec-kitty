package org.speckitty.missionstatus.adapter.in.http.contract;

import static org.assertj.core.api.Assertions.assertThat;
import static org.assertj.core.api.Assertions.assertThatThrownBy;

import java.util.List;
import org.junit.jupiter.api.Test;
import org.speckitty.missionstatus.testsupport.ConformanceTree;
import tools.jackson.databind.JsonNode;
import tools.jackson.databind.json.JsonMapper;
import tools.jackson.databind.node.ObjectNode;

/**
 * AC-11b (and the reusable helper's own tests): the validator really honours {@code unevaluatedProperties}, required members, the
 * nullable type form and the format keywords, against hand-written valid and invalid documents and the contract's own examples.
 */
class ContractValidatorTest {

  private static final JsonMapper JSON = JsonMapper.builder().build();
  private final ContractValidator validator = ContractValidator.fromClasspath();

  private static String golden(String key, String file) {
    var fixture = ConformanceTree.fixtures().stream().filter(f -> f.key().equals(key)).findFirst().orElseThrow();
    return new String(ConformanceTree.golden(fixture, file), java.nio.charset.StandardCharsets.UTF_8);
  }

  @Test
  void aGoldenProjectAndAGoldenPageAreValid() {
    assertThat(validator.validateProject(golden("project-header/healthy", "project.json"))).isEmpty();
    assertThat(validator.validateMissions(golden("interleaved/two-missions", "missions.json"))).isEmpty();
  }

  @Test
  void ac11bOneAddedUnknownPropertyFailsTheProjectAndTheNestedItem() {
    ObjectNode project = (ObjectNode) JSON.readTree(golden("project-header/healthy", "project.json"));
    project.put("surprise", 1);
    assertThat(validator.validateProject(project.toString())).as("unknown member of Project").isNotEmpty();

    ObjectNode page = (ObjectNode) JSON.readTree(golden("interleaved/two-missions", "missions.json"));
    ((ObjectNode) page.get("items").get(0).get("progress")).put("surprise", 1);
    assertThat(validator.validateMissions(page.toString())).as("unknown member nested in an item").isNotEmpty();
  }

  @Test
  void aMissingRequiredMemberAndAWrongTypeFail() {
    ObjectNode project = (ObjectNode) JSON.readTree(golden("project-header/healthy", "project.json"));
    ObjectNode missing = project.deepCopy();
    missing.remove("currentBranch");
    assertThat(validator.validateProject(missing.toString())).isNotEmpty();
    ObjectNode wrong = project.deepCopy();
    wrong.put("missionCount", "three");
    assertThat(validator.validateProject(wrong.toString())).isNotEmpty();
    ObjectNode badDate = project.deepCopy();
    badDate.put("lastActivityAt", "yesterday");
    assertThat(validator.validateProject(badDate.toString())).as("format date-time is asserted").isNotEmpty();
  }

  @Test
  void aRequiredNullableMemberAcceptsNullButNotAbsence() {
    ObjectNode project = (ObjectNode) JSON.readTree(golden("project-header/healthy", "project.json"));
    project.putNull("currentBranch");
    assertThat(validator.validateProject(project.toString())).isEmpty();
  }

  @Test
  void theProblemSchemasAcceptTheirShapesAndRefuseOthers() {
    assertThat(validator.validateProblem("{\"status\":500,\"title\":\"x\",\"code\":\"ledger_unparseable\"}")).isEmpty();
    assertThat(validator.validateProblem("{\"status\":200,\"title\":\"x\"}")).isNotEmpty();
    assertThat(validator.validateProblem("{\"status\":500,\"title\":\"x\",\"nope\":1}")).isNotEmpty();
    assertThat(validator.validatePageCursorRefusal("{\"status\":400,\"title\":\"x\",\"code\":\"invalid_page_cursor\"}")).isEmpty();
    assertThat(validator.validatePageCursorRefusal("{\"status\":400,\"title\":\"x\",\"code\":\"other\"}")).isNotEmpty();
    assertThat(validator.validateStreamRefusal(409, "{\"status\":409,\"title\":\"x\",\"code\":\"out_of_range\",\"detail\":\"d\"}")).isEmpty();
    assertThat(validator.validateStreamRefusal(409, "{\"status\":400,\"title\":\"x\",\"code\":\"out_of_range\",\"detail\":\"d\"}")).isNotEmpty();
  }

  @Test
  void everyEventSchemaAcceptsItsOwnExamplesAndRefusesAnAddedMember() {
    for (var entry : validator.eventSchemas().entrySet()) {
      List<String> examples = validator.examples(entry.getValue());
      assertThat(examples).as(entry.getKey() + " examples").isNotEmpty();
      for (String example : examples) {
        assertThat(validator.validateEventData(entry.getKey(), example)).as(entry.getKey() + " example").isEmpty();
        ObjectNode extra = (ObjectNode) JSON.readTree(example);
        extra.put("surprise", 1);
        assertThat(validator.validateEventData(entry.getKey(), extra.toString())).as(entry.getKey() + " with an unknown member").isNotEmpty();
      }
    }
  }

  @Test
  void anUnknownEventNameIsRefused() {
    assertThatThrownBy(() -> validator.validateEventData("heartbeat", "{}")).isInstanceOf(IllegalArgumentException.class);
  }

  @Test
  void theThreeEventsAreTheOnesTheContractDefines() {
    JsonNode oneOf = validator.responseSchema("/events", "200", "text/event-stream").path("oneOf");
    assertThat(oneOf).hasSize(ContractValidator.EVENT_NAMES.size());
  }
}
