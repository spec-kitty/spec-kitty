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

/** The Work Package file decoder (YAML front matter into the served document) works in the native image: a valid file is decoded, with its subtasks and owned files, and served with the prompt body only on request. */
@Tag("native")
@SpringBootTest(classes = MissionStatusApplication.class, webEnvironment = SpringBootTest.WebEnvironment.RANDOM_PORT)
class NativeWorkPackageDecoderValidTest {

  private static final Path ROOT = NativeProject.createWithWorkPackages();
  private static final String MISSION = "/api/v1/missions/" + NativeProject.MISSION_ID;

  @DynamicPropertySource
  static void project(DynamicPropertyRegistry registry) {
    registry.add("mission-status.project-root", ROOT::toString);
  }

  @Value("${local.server.port}")
  int port;

  @Test
  void aValidWorkPackageFileIsDecodedAndServedWithItsAuthoredMembersAndThePromptOnlyOnRequest() throws Exception {
    var plain = NativeProject.get(port, MISSION + "/work-packages/WP01");
    String body = new String(plain.body(), StandardCharsets.UTF_8);
    assertThat(plain.statusCode()).isEqualTo(200);
    assertThat(body).contains("\"wpId\":\"WP01\"").contains("\"T001\"").contains("\"python-pedro\"").doesNotContain("Body of WP01");

    var withPrompt = NativeProject.get(port, MISSION + "/work-packages/WP01?includePrompt=true");
    assertThat(withPrompt.statusCode()).isEqualTo(200);
    assertThat(new String(withPrompt.body(), StandardCharsets.UTF_8)).contains("# Body of WP01");
  }
}
