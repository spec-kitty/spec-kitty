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

/** The refusing path of the artifact content route works in the native image: a file that holds a credential is a 422 Problem that quotes none of it. */
@Tag("native")
@SpringBootTest(classes = MissionStatusApplication.class, webEnvironment = SpringBootTest.WebEnvironment.RANDOM_PORT)
class NativeArtifactContentUnprocessableTest {

  private static final Path ROOT = NativeProject.createWithWorkPackages();
  private static final String MISSION = "/api/v1/missions/" + NativeProject.MISSION_ID;

  @DynamicPropertySource
  static void project(DynamicPropertyRegistry registry) {
    registry.add("mission-status.project-root", ROOT::toString);
  }

  @Value("${local.server.port}")
  int port;

  @Test
  void aFileThatHoldsACredentialIsRefusedWith422AndTheProblemQuotesNothingOfIt() throws Exception {
    var refused = NativeProject.get(port, MISSION + "/artifacts/content?path=secret.txt");
    String body = new String(refused.body(), StandardCharsets.UTF_8);
    assertThat(refused.statusCode()).isEqualTo(422);
    assertThat(body).contains("\"code\":\"artifact_secret\"").doesNotContain("ghp_").doesNotContain("secret.txt");
  }
}
