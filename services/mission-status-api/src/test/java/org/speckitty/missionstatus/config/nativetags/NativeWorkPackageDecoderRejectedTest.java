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

/** The rejecting path of the Work Package file decoder works in the native image: a file with a member no Work Package file may hold is skipped, and its Work Package is a 404 Problem, not a 500 from a missing class. */
@Tag("native")
@SpringBootTest(classes = MissionStatusApplication.class, webEnvironment = SpringBootTest.WebEnvironment.RANDOM_PORT)
class NativeWorkPackageDecoderRejectedTest {

  private static final Path ROOT = NativeProject.createWithWorkPackages();
  private static final String MISSION = "/api/v1/missions/" + NativeProject.MISSION_ID;

  @DynamicPropertySource
  static void project(DynamicPropertyRegistry registry) {
    registry.add("mission-status.project-root", ROOT::toString);
  }

  @Value("${local.server.port}")
  int port;

  @Test
  void aWorkPackageFileWithAnUnknownMemberIsRejectedAndItsWorkPackageIsNotFoundWhileItsSiblingIsServed() throws Exception {
    var rejected = NativeProject.get(port, MISSION + "/work-packages/WP02");
    String body = new String(rejected.body(), StandardCharsets.UTF_8);
    assertThat(rejected.statusCode()).isEqualTo(404);
    assertThat(body).contains("\"code\":\"not_found\"").doesNotContain("mystery_key");

    assertThat(NativeProject.get(port, MISSION + "/work-packages/WP01").statusCode()).isEqualTo(200);
  }
}
