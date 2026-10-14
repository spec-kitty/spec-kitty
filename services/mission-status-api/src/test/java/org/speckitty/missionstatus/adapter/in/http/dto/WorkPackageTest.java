package org.speckitty.missionstatus.adapter.in.http.dto;

import static org.assertj.core.api.Assertions.assertThat;

import java.io.IOException;
import java.lang.reflect.RecordComponent;
import java.nio.charset.StandardCharsets;
import java.nio.file.Files;
import java.nio.file.Path;
import java.util.Arrays;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;
import java.util.Set;
import java.util.TreeSet;
import java.util.stream.Collectors;
import java.util.stream.Stream;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.params.ParameterizedTest;
import org.junit.jupiter.params.provider.MethodSource;
import org.speckitty.missionstatus.adapter.in.http.contract.ContractValidator;
import org.speckitty.missionstatus.config.MissionStatusApplicationJson;
import org.speckitty.missionstatus.testsupport.CanonicalJson;
import org.yaml.snakeyaml.Yaml;
import tools.jackson.databind.json.JsonMapper;

/**
 * The hand record {@link WorkPackage} (D-79 check c, D-111): the generated model of the same schema writes {@code "promptMarkdown":null}
 * when the prompt was not requested, the contract says the member is then absent. The record is written through the production mapper
 * and compared byte for byte with the canonical form of each contract example, validated against the bundled schema, and held to the
 * schema's property names.
 */
class WorkPackageTest {

  private static final JsonMapper MAPPER = MissionStatusApplicationJson.mapper();
  private static final Path CONTRACT = Path.of(System.getProperty("user.dir")).resolve("../../contracts/mission-status").normalize();
  private static final ContractValidator VALIDATOR = ContractValidator.fromClasspath();

  static Stream<Path> examples() throws IOException {
    try (Stream<Path> files = Files.list(CONTRACT.resolve("examples"))) {
      return files.filter(p -> p.getFileName().toString().startsWith("WorkPackage.") && !p.getFileName().toString().startsWith("WorkPackageDetail")).sorted().toList().stream();
    }
  }

  private static Object yamlTree(Path example) throws IOException {
    return new Yaml().load(Files.readString(example, StandardCharsets.UTF_8));
  }

  private static String written(Object record) {
    return MAPPER.writeValueAsString(record);
  }

  @Test
  void theExampleSetIsNotEmptyAndCoversTheWithAndWithoutPromptCases() throws IOException {
    List<String> names = examples().map(p -> p.getFileName().toString()).toList();
    assertThat(names).hasSizeGreaterThanOrEqualTo(10).contains("WorkPackage.with-prompt.yaml", "WorkPackage.populated.yaml");
  }

  @ParameterizedTest(name = "{0}")
  @MethodSource("examples")
  void theRecordWritesTheCanonicalBytesOfEachContractExample(Path example) throws IOException {
    Object tree = yamlTree(example);
    String json = MAPPER.writeValueAsString(tree);
    WorkPackage record = MAPPER.readValue(json, WorkPackage.class);
    byte[] actual = (written(record) + "\n").getBytes(StandardCharsets.UTF_8);
    CanonicalJson.assertBodyEqualsGolden(actual, CanonicalJson.toBytes(tree));
  }

  @ParameterizedTest(name = "{0}")
  @MethodSource("examples")
  void theRecordValidatesAgainstTheBundledSchema(Path example) throws IOException {
    WorkPackage record = MAPPER.readValue(MAPPER.writeValueAsString(yamlTree(example)), WorkPackage.class);
    var schema = VALIDATOR.responseSchema("/missions/{missionId}/work-packages/{wpId}", "200", "application/json");
    assertThat(VALIDATOR.validate(schema, written(record))).isEmpty();
  }

  @Test
  void anUnsetPromptIsAbsentNotNull() throws IOException {
    WorkPackage record = MAPPER.readValue(MAPPER.writeValueAsString(yamlTree(CONTRACT.resolve("examples/WorkPackage.populated.yaml"))), WorkPackage.class);
    assertThat(record.promptMarkdown()).isNull();
    assertThat(written(record)).doesNotContain("promptMarkdown");
  }

  @Test
  void anExplicitNullPromptIsAlsoAbsent() throws IOException {
    Map<String, Object> tree = new LinkedHashMap<>(asMap(yamlTree(CONTRACT.resolve("examples/WorkPackage.populated.yaml"))));
    tree.put("promptMarkdown", null);
    WorkPackage record = MAPPER.readValue(MAPPER.writeValueAsString(tree), WorkPackage.class);
    assertThat(written(record)).doesNotContain("promptMarkdown");
  }

  @Test
  void aSetPromptIsWritten() throws IOException {
    WorkPackage record = MAPPER.readValue(MAPPER.writeValueAsString(yamlTree(CONTRACT.resolve("examples/WorkPackage.with-prompt.yaml"))), WorkPackage.class);
    assertThat(record.promptMarkdown()).startsWith("# Work Package Prompt");
    assertThat(written(record)).contains("\"promptMarkdown\":\"# Work Package Prompt");
  }

  @Test
  void everyOtherNullableMemberKeepsItsExplicitNull() throws IOException {
    WorkPackage record = MAPPER.readValue(MAPPER.writeValueAsString(yamlTree(CONTRACT.resolve("examples/WorkPackage.no-events.yaml"))), WorkPackage.class);
    assertThat(written(record)).contains("\"statusLane\":null").contains("\"lastTransitionAt\":null").contains("\"lastEventId\":null").contains("\"cancellation\":null").contains("\"staleness\":null").contains("\"taskType\":null");
  }

  @Test
  void theOpenSubtasksMapIsWrittenInCodePointOrderNotUtf16Order() throws IOException {
    // U+FF5E (a BMP character above the surrogate range) sorts before U+1F600 by code point and after it by UTF-16 unit.
    String bmp = new String(Character.toChars(0xFF5E));
    String astral = new String(Character.toChars(0x1F600));
    Map<String, Object> tree = new LinkedHashMap<>(asMap(yamlTree(CONTRACT.resolve("examples/WorkPackage.populated.yaml"))));
    Map<String, Object> subtasks = new LinkedHashMap<>();
    subtasks.put(astral, "done");
    subtasks.put(bmp, "planned");
    subtasks.put("T001", "done");
    tree.put("subtasks", subtasks);
    String json = MAPPER.writeValueAsString(tree);
    String ordered = "\"subtasks\":{\"T001\":\"done\",\"" + bmp + "\":\"planned\",\"" + astral + "\":\"done\"}";
    assertThat(written(MAPPER.readValue(json, WorkPackage.class))).contains(ordered);
    // the generated twin, which the record replaces, writes the same map in UTF-16 order: that is why the record owns the order
    var twin = MAPPER.readValue(json, org.speckitty.missionstatus.adapter.in.http.model.WorkPackage.class);
    assertThat(written(twin)).doesNotContain(ordered).contains("\"" + astral + "\":\"done\",\"" + bmp + "\":\"planned\"");
  }

  @Test
  void theRecordComponentsAreExactlyThePropertiesOfTheSchema() throws IOException {
    Map<String, Object> schema = asMap(new Yaml().load(Files.readString(CONTRACT.resolve("schemas/WorkPackage.yaml"), StandardCharsets.UTF_8)));
    Set<String> properties = new TreeSet<>(asMap(schema.get("properties")).keySet());
    Set<String> components = Arrays.stream(WorkPackage.class.getRecordComponents()).map(RecordComponent::getName).collect(Collectors.toCollection(TreeSet::new));
    assertThat(components).isEqualTo(properties);
  }

  @SuppressWarnings("unchecked")
  private static Map<String, Object> asMap(Object value) {
    return (Map<String, Object>) value;
  }
}
