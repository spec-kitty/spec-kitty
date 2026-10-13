package org.speckitty.missionstatus.config;

import static org.assertj.core.api.Assertions.assertThat;

import java.util.ArrayList;
import java.util.List;
import org.junit.jupiter.api.Test;
import org.speckitty.missionstatus.adapter.in.http.model.Project;
import tools.jackson.databind.JsonNode;
import tools.jackson.databind.json.JsonMapper;

/**
 * The production mapper emits generated models in the canonical member order (sorted, not creator-first) with required-nullable
 * members as an explicit null (research.md, spike record T005 criteria 2 and 3).
 */
class MissionStatusApplicationJsonTest {

  private final JsonMapper mapper = MissionStatusApplicationJson.mapper();

  @Test
  void writesMembersSortedAlphabeticallyWithExplicitNulls() throws Exception {
    Project project = new Project("demo", 3, null, null, Project.HealthEnum.fromValue("healthy"), null, null);

    String json = mapper.writeValueAsString(project);

    JsonNode tree = mapper.readTree(json);
    List<String> names = new ArrayList<>();
    tree.propertyNames().forEach(names::add);
    assertThat(names).isSorted().hasSizeGreaterThanOrEqualTo(7);
    assertThat(tree.get("currentBranch").isNull()).isTrue();
    assertThat(tree.get("specKittyVersion").isNull()).isTrue();
    assertThat(json).doesNotContain(" ").doesNotContain("\n");
  }

  @Test
  void writesNonAsciiTextAsUtf8WithoutEscaping() throws Exception {
    // Built from code points so the source file stays ASCII (javac's source encoding is platform dependent on some runners).
    String text = new String(Character.toChars(0xE9)) + " " + new String(Character.toChars(0x2615));
    Project project = new Project(text, 1, "4.0.0", 3, Project.HealthEnum.fromValue("healthy"), "main", null);

    assertThat(mapper.writeValueAsString(project)).contains(text);
  }
}
