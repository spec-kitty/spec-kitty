package org.speckitty.missionstatus.nativesmoke;

import static org.assertj.core.api.Assertions.assertThat;

import java.io.IOException;
import java.net.ServerSocket;
import java.net.URI;
import java.net.http.HttpClient;
import java.net.http.HttpRequest;
import java.net.http.HttpResponse;
import java.nio.file.Files;
import java.nio.file.Path;
import java.time.Duration;
import java.util.concurrent.TimeUnit;
import org.junit.jupiter.api.Tag;
import org.junit.jupiter.api.Test;

/**
 * Skeleton smoke test (WP12 replaces the body): starts the built binary and asks an unmapped route as 127.0.0.1:port (the answer is the service's own 404, so the test names no route a later slice could move). Tagged
 * native-binary, so only the nativeSmoke task runs it (with -PnativeBinary=path), never test or check.
 */
@Tag("native-binary")
class NativeSmokeTest {

  @Test
  void theBuiltBinaryAnswersOnTheLoopbackAddress() throws Exception {
    String binary = System.getProperty("nativeBinary");
    assertThat(binary).as("the nativeBinary system property (-PnativeBinary)").isNotBlank();
    Path projectRoot = Files.createTempDirectory("mission-status-smoke");
    int port = freePort();

    Process process =
        new ProcessBuilder(binary, "--mission-status.project-root=" + projectRoot, "--mission-status.port=" + port)
            .redirectErrorStream(true)
            .redirectOutput(ProcessBuilder.Redirect.DISCARD)
            .start();
    try {
      HttpResponse<String> response = awaitAnswer(port, process);
      assertThat(response.statusCode()).as("an unmapped route is answered 404 by the running service").isEqualTo(404);
    } finally {
      process.destroy();
      process.waitFor(10, TimeUnit.SECONDS);
      Files.deleteIfExists(projectRoot);
    }
  }

  private static HttpResponse<String> awaitAnswer(int port, Process process) throws Exception {
    HttpClient client = HttpClient.newHttpClient();
    HttpRequest request = HttpRequest.newBuilder(URI.create("http://127.0.0.1:" + port + "/api/v1/no-such-route")).GET().build();
    long deadline = System.nanoTime() + Duration.ofSeconds(60).toNanos();
    IOException last = null;
    while (System.nanoTime() < deadline) {
      if (!process.isAlive()) {
        throw new AssertionError("the binary exited early with status " + process.exitValue());
      }
      try {
        return client.send(request, HttpResponse.BodyHandlers.ofString());
      } catch (IOException notYet) {
        last = notYet;
        Thread.sleep(200);
      }
    }
    throw new AssertionError("the binary did not answer within 60 s", last);
  }

  private static int freePort() throws IOException {
    try (ServerSocket socket = new ServerSocket(0, 1, java.net.InetAddress.getLoopbackAddress())) {
      return socket.getLocalPort();
    }
  }
}
