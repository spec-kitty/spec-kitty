package org.speckitty.missionstatus.config.nativetags;

import static org.assertj.core.api.Assertions.assertThat;

import java.nio.charset.StandardCharsets;
import java.nio.file.Path;
import org.junit.jupiter.api.Tag;
import org.junit.jupiter.api.Test;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.boot.test.context.SpringBootTest;
import org.springframework.test.context.DynamicPropertyRegistry;
import org.springframework.test.context.DynamicPropertySource;
import org.speckitty.missionstatus.config.MissionStatusApplication;

/** The Work Package detail assembly works in the native image: owned files, artifact references and a review cycle are read from the Mission directory and served in one document. */
@Tag("native")
@SpringBootTest(classes = MissionStatusApplication.class, webEnvironment = SpringBootTest.WebEnvironment.RANDOM_PORT)
class NativeWorkPackageDetailTest {

  private static final Path ROOT = NativeProject.createWithWorkPackages();
  private static final String MISSION = "/api/v1/missions/" + NativeProject.MISSION_ID;

  @DynamicPropertySource
  static void project(DynamicPropertyRegistry registry) {
    registry.add("mission-status.project-root", ROOT::toString);
  }

  @Value("${local.server.port}")
  int port;

  @Test
  void theDetailOfAWorkPackageCarriesItsOwnedFilesItsArtifactReferencesAndItsReviewCycle() throws Exception {
    var detail = NativeProject.get(port, MISSION + "/work-packages/WP01/detail");
    String body = new String(detail.body(), StandardCharsets.UTF_8);
    assertThat(detail.statusCode()).isEqualTo(200);
    assertThat(body).contains("\"pattern\":\"src/app/**\"").contains("\"isGlob\":true").contains("\"artifactReferences\"").contains("\"cycleNumber\":1");
  }
}
