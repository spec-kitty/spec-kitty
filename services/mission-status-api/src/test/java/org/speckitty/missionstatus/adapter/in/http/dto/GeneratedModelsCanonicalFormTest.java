package org.speckitty.missionstatus.adapter.in.http.dto;

import static org.assertj.core.api.Assertions.assertThat;

import java.io.IOException;
import java.nio.charset.StandardCharsets;
import java.nio.file.Files;
import java.nio.file.Path;
import java.util.LinkedHashSet;
import java.util.List;
import java.util.Map;
import java.util.Set;
import java.util.TreeSet;
import java.util.stream.Stream;
import org.junit.jupiter.params.ParameterizedTest;
import org.junit.jupiter.params.provider.MethodSource;
import org.speckitty.missionstatus.config.MissionStatusApplicationJson;
import org.yaml.snakeyaml.Yaml;
import tools.jackson.databind.JsonNode;
import tools.jackson.databind.json.JsonMapper;

/**
 * The D-79 go/no-go checks (a) and (b) for the generated models of the five detail operations, kept as a standing test: through the
 * production mapper an empty instance of each closure model writes every {@code required} member of its schema (a required-nullable
 * member as an explicit {@code null}), and the members come out in the canonical alphabetical order. Check (c), the optional
 * {@code promptMarkdown}, is why {@link WorkPackage} is a hand record; check (b) for the open {@code subtasks} map is pinned in
 * {@code WorkPackageTest}.
 */
class GeneratedModelsCanonicalFormTest {

  private static final JsonMapper MAPPER = MissionStatusApplicationJson.mapper();
  private static final Path SCHEMAS = Path.of(System.getProperty("user.dir")).resolve("../../contracts/mission-status/schemas").normalize();

  /** The closure models whose schema is one plain object with its own {@code required} list (the composed ones are covered below). */
  static Stream<String> plainModels() {
    return Stream.of(
        "Actor", "ArtifactContent", "ArtifactEntry", "ArtifactListing", "ArtifactReference", "ArtifactReferences", "Assignment", "Authored", "Cancellation",
        "DependencyRef", "HistoryEntry", "MissionPhase", "OwnedFile", "Readiness", "Review", "ReviewCycle", "ReviewOverride", "ReviewResult", "Staleness",
        "SubtaskProgress", "Subtask", "WorkPackageDetail", "WorkPackageSummary", "Workspace");
  }

  @SuppressWarnings("unchecked")
  @ParameterizedTest(name = "{0}")
  @MethodSource("plainModels")
  void anEmptyInstanceWritesEveryRequiredMemberInAlphabeticalOrder(String name) throws Exception {
    Map<String, Object> schema = (Map<String, Object>) new Yaml().load(Files.readString(SCHEMAS.resolve(name + ".yaml"), StandardCharsets.UTF_8));
    Set<String> required = new TreeSet<>((List<String>) schema.get("required"));
    assertThat(required).as("the schema of %s lists required members", name).isNotEmpty();
    Object instance = Class.forName("org.speckitty.missionstatus.adapter.in.http.model." + name).getDeclaredConstructor().newInstance();
    JsonNode written = MAPPER.readTree(MAPPER.writeValueAsString(instance));
    List<String> keys = new java.util.ArrayList<>();
    written.propertyNames().forEach(keys::add);
    assertThat(keys).as("members written for %s", name).containsAll(required);
    assertThat(keys).as("alphabetical order for %s", name).isSorted();
    Set<String> optionalWritten = new LinkedHashSet<>(keys);
    optionalWritten.removeAll(required);
    assertThat(optionalWritten).as("optional members of %s that would be written as null", name).isEmpty();
  }

  @org.junit.jupiter.api.Test
  void theGeneratedWorkPackageWritesAnUnsetPromptAsNullWhichIsWhyTheRecordExists() throws IOException {
    var twin = new org.speckitty.missionstatus.adapter.in.http.model.WorkPackage();
    assertThat(MAPPER.writeValueAsString(twin)).contains("\"promptMarkdown\":null");
  }
}
