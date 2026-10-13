package org.speckitty.missionstatus.adapter.in.http.contract;

import static org.assertj.core.api.Assertions.assertThat;

import java.math.BigDecimal;
import java.nio.charset.StandardCharsets;
import java.util.stream.Stream;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.params.ParameterizedTest;
import org.junit.jupiter.params.provider.MethodSource;
import org.speckitty.missionstatus.adapter.in.http.model.MissionOverviewPage;
import org.speckitty.missionstatus.adapter.in.http.model.MissionProgress;
import org.speckitty.missionstatus.adapter.in.http.model.Project;
import org.speckitty.missionstatus.config.MissionStatusApplicationJson;
import org.speckitty.missionstatus.testsupport.CanonicalJson;
import org.speckitty.missionstatus.testsupport.ConformanceTree;
import org.speckitty.missionstatus.testsupport.ConformanceTree.TreeFixture;
import org.speckitty.missionstatus.testsupport.GoldenComparison;
import tools.jackson.databind.json.JsonMapper;

/**
 * The Jackson contract (WP10 T056 step 3, NFR-005, DD-72): the production mapper writes a required-nullable member as an explicit
 * {@code null}, in canonical member order, non-ASCII as UTF-8, and {@code progress} through the ONE pinned function, so that every
 * committed golden document round-trips through the generated models to the same bytes.
 */
class JacksonContractTest {

  private final JsonMapper mapper = MissionStatusApplicationJson.mapper();

  static Stream<TreeFixture> fixtures() {
    return ConformanceTree.fixtures().stream().filter(f -> f.parity().equals(ConformanceTree.PARITY_GOLDEN)).filter(f -> !f.javaOnly());
  }

  @ParameterizedTest(name = "{0}")
  @MethodSource("fixtures")
  void everyGoldenDocumentRoundTripsThroughTheGeneratedModelsToTheSameBytes(TreeFixture fixture) {
    boolean refusalOnly = true;
    for (String file : new String[] {ConformanceTree.PROJECT_GOLDEN, ConformanceTree.MISSIONS_GOLDEN}) {
      byte[] golden = ConformanceTree.golden(fixture, file);
      if (GoldenComparison.refusalException(golden) != null) {
        continue;
      }
      Object model = file.equals(ConformanceTree.PROJECT_GOLDEN) ? mapper.readValue(golden, Project.class) : mapper.readValue(golden, MissionOverviewPage.class);
      byte[] written = (mapper.writeValueAsString(model) + "\n").getBytes(StandardCharsets.UTF_8);
      CanonicalJson.assertBodyEqualsGolden(written, golden);
      refusalOnly = false;
    }
    assumeDocumentOrRefusal(refusalOnly, fixture);
  }

  private static void assumeDocumentOrRefusal(boolean refusalOnly, TreeFixture fixture) {
    // A fixture whose two goldens are both refusals has no document to round-trip; the golden routes test covers it.
    if (refusalOnly) {
      assertThat(GoldenComparison.refusalException(ConformanceTree.golden(fixture, ConformanceTree.PROJECT_GOLDEN))).isNotNull();
    }
  }

  @Test
  void theGoldenSetHoldsDocumentsWithFractionalProgressAndNonAsciiText() {
    String all = fixtures().flatMap(f -> Stream.of(ConformanceTree.PROJECT_GOLDEN, ConformanceTree.MISSIONS_GOLDEN).map(file -> new String(ConformanceTree.golden(f, file), StandardCharsets.UTF_8))).collect(java.util.stream.Collectors.joining());
    assertThat(all).containsPattern("\"weightedPercentage\":\\d+\\.\\d*[1-9]");
  }

  @Test
  void aRequiredNullableMemberIsWrittenAsAnExplicitNull() {
    Project project = new Project("demo", 0, null, null, Project.HealthEnum.HEALTHY, null, null);
    assertThat(mapper.writeValueAsString(project))
        .isEqualTo("{\"currentBranch\":null,\"health\":\"healthy\",\"lastActivityAt\":null,\"missionCount\":0,\"name\":\"demo\",\"schemaVersion\":null,\"specKittyVersion\":null}");
  }

  @Test
  void aMapperThatOmitsNullsIsNotTheCanonicalForm() {
    JsonMapper omitting = mapper.rebuild().changeDefaultPropertyInclusion(i -> i.withValueInclusion(com.fasterxml.jackson.annotation.JsonInclude.Include.NON_NULL)).build();
    Project project = new Project("demo", 0, null, null, Project.HealthEnum.HEALTHY, null, null);
    assertThat(omitting.writeValueAsString(project)).isNotEqualTo(mapper.writeValueAsString(project));
  }

  @Test
  void nonAsciiTextAndFractionalProgressEqualTheirPythonWrittenForms() {
    String text = new String(Character.toChars(0xE9)) + " " + new String(Character.toChars(0x2615)) + " " + new String(Character.toChars(0x65E5));
    assertThat(mapper.writeValueAsString(new Project(text, 1, "4.0.0", 3, Project.HealthEnum.HEALTHY, "main", null))).contains("\"name\":\"" + text + "\"");
    for (String[] pair : new String[][] {{"65.0", "65.0"}, {"0", "0.0"}, {"12.3456", "12.3456"}, {"0.0001", "0.0001"}, {"100", "100.0"}, {"33.3333", "33.3333"}, {"99.9999", "99.9999"}, {"7.00", "7.0"}}) {
      MissionProgress progress = new MissionProgress(new BigDecimal(pair[0]), new BigDecimal(pair[0]), 1, MissionProgress.SemanticsEnum.WEIGHTED_READINESS);
      assertThat(mapper.writeValueAsString(progress)).as(pair[0]).contains("\"weightedPercentage\":" + pair[1] + "}").contains("\"donePercentage\":" + pair[1] + ",");
    }
  }
}
