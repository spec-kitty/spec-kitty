package org.speckitty.missionstatus.config.nativetags;

import static org.assertj.core.api.Assertions.assertThat;

import java.io.IOException;
import java.io.UncheckedIOException;
import java.net.URI;
import java.net.http.HttpClient;
import java.net.http.HttpRequest;
import java.net.http.HttpResponse;
import java.nio.file.Files;
import java.nio.file.Path;
import org.junit.jupiter.api.Tag;
import org.junit.jupiter.api.Test;
import org.speckitty.missionstatus.config.MissionStatusApplication;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.boot.test.context.SpringBootTest;
import org.springframework.test.context.DynamicPropertyRegistry;
import org.springframework.test.context.DynamicPropertySource;

/**
 * The skeleton application starts as a native image and answers on its loopback address. This is the one native-tagged test the build
 * has until the HTTP adapter arrives: it keeps {@code nativeTest} selecting a real test, so a native leg cannot go green on nothing.
 * The adapter's own native-tagged tests replace it, in the slice that adds the first route.
 */
@Tag("native")
@SpringBootTest(classes = MissionStatusApplication.class, webEnvironment = SpringBootTest.WebEnvironment.RANDOM_PORT)
class NativeBootTest {

  private static final Path ROOT = projectRoot();

  @DynamicPropertySource
  static void project(DynamicPropertyRegistry registry) {
    registry.add("mission-status.project-root", ROOT::toString);
  }

  @Value("${local.server.port}")
  int port;

  @Test
  void theApplicationStartsAndAnUnmappedRouteIsAnswered404OnTheLoopbackAddress() throws Exception {
    HttpResponse<String> answer =
        HttpClient.newHttpClient()
            .send(HttpRequest.newBuilder(URI.create("http://127.0.0.1:" + port + "/api/v1/no-such-route")).GET().build(), HttpResponse.BodyHandlers.ofString());

    assertThat(answer.statusCode()).isEqualTo(404);
  }

  private static Path projectRoot() {
    try {
      return Files.createTempDirectory("mission-status-native-boot");
    } catch (IOException failure) {
      throw new UncheckedIOException(failure);
    }
  }
}
