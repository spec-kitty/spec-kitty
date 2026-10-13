package org.speckitty.missionstatus.adapter.in.http.contract;

import static org.assertj.core.api.Assertions.assertThat;

import java.util.stream.Stream;
import org.junit.jupiter.params.ParameterizedTest;
import org.junit.jupiter.params.provider.MethodSource;
import org.speckitty.missionstatus.adapter.in.http.rest.ContractRoutes;
import org.speckitty.missionstatus.testsupport.ConformanceTree;
import org.speckitty.missionstatus.testsupport.ConformanceTree.TreeFixture;
import org.speckitty.missionstatus.testsupport.FilesystemFixtureFactory;
import org.speckitty.missionstatus.testsupport.http.HttpHarness;

/**
 * AC-11a, JSON routes only (post-analyze ruling ANL-001: the data of the SSE events is validated by WP20 through the same
 * {@link ContractValidator}): every response of /project and /missions over the fixtures validates against the contract, and so do the
 * refusals (the 400 page-cursor Problem and the 500 Problems).
 */
class ResponseContractValidationTest {

  private static final java.util.Set<String> JAVA_ONLY_VALIDATED = java.util.Set.of("secret-canaries", "symlink");

  private final ContractValidator validator = ContractValidator.fromClasspath();

  static Stream<TreeFixture> fixtures() {
    // The Python-golden fixtures, plus the Java-only trees where the leak and refusal paths live (pre-merge fold J9)
    return ConformanceTree.fixtures().stream().filter(f -> (f.parity().equals(ConformanceTree.PARITY_GOLDEN) && !f.javaOnly()) || JAVA_ONLY_VALIDATED.contains(f.tag()));
  }

  @ParameterizedTest(name = "{0}")
  @MethodSource("fixtures")
  void everyServedAnswerValidatesAgainstTheContract(TreeFixture fixture) {
    FilesystemFixtureFactory.Built built = FilesystemFixtureFactory.fromTreeRecording(fixture.dir());
    try (HttpHarness server = HttpHarness.start(built)) {
      HttpHarness.Response project = server.get("/api/v1/project");
      HttpHarness.Response missions = server.get("/api/v1/missions?pageSize=50");
      check(project, true);
      check(missions, false);
    }
  }

  private void check(HttpHarness.Response response, boolean project) {
    if (response.status() == 200) {
      assertThat(project ? validator.validateProject(response.text()) : validator.validateMissions(response.text())).isEmpty();
    } else {
      assertThat(response.status()).isEqualTo(500);
      assertThat(validator.validateProblem(response.text())).isEmpty();
    }
  }

  @org.junit.jupiter.api.Test
  void theJavaOnlyTreesAreInTheParameterSet() {
    assertThat(fixtures().map(TreeFixture::tag).distinct()).contains("secret-canaries", "symlink");
  }

  @org.junit.jupiter.api.Test
  void theRefusalsValidate() {
    try (HttpHarness server = HttpHarness.start(ContractRoutes.anyFixture())) {
      HttpHarness.Response forged = server.get("/api/v1/missions?pageCursor=forged");
      assertThat(forged.status()).isEqualTo(400);
      assertThat(validator.validatePageCursorRefusal(forged.text())).isEmpty();
      assertThat(validator.validateProblem(forged.text())).isEmpty();
      HttpHarness.Response notFound = server.get("/api/v1/nope");
      assertThat(validator.validateProblem(notFound.text())).isEmpty();
    }
  }
}
