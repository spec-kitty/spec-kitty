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

/** The artifact content route works in the native image: a text file of the Mission is served as a 200 document, listed and read. */
@Tag("native")
@SpringBootTest(classes = MissionStatusApplication.class, webEnvironment = SpringBootTest.WebEnvironment.RANDOM_PORT)
class NativeArtifactContentOkTest {

  private static final Path ROOT = NativeProject.createWithWorkPackages();
  private static final String MISSION = "/api/v1/missions/" + NativeProject.MISSION_ID;

  @DynamicPropertySource
  static void project(DynamicPropertyRegistry registry) {
    registry.add("mission-status.project-root", ROOT::toString);
  }

  @Value("${local.server.port}")
  int port;

  @Test
  void aTextArtifactIsListedAndItsContentIsServed() throws Exception {
    var listing = NativeProject.get(port, MISSION + "/artifacts");
    assertThat(listing.statusCode()).isEqualTo(200);
    assertThat(new String(listing.body(), StandardCharsets.UTF_8)).contains("\"path\":\"spec.md\"");

    var content = NativeProject.get(port, MISSION + "/artifacts/content?path=spec.md");
    String body = new String(content.body(), StandardCharsets.UTF_8);
    assertThat(content.statusCode()).isEqualTo(200);
    assertThat(body).contains("\"content\":\"# Spec\\n\\nPlain text.\\n\"").contains("\"redacted\":false");
  }
}
