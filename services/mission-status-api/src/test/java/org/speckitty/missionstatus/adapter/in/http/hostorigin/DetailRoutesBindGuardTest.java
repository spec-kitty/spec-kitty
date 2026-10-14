package org.speckitty.missionstatus.adapter.in.http.hostorigin;

import static org.assertj.core.api.Assertions.assertThat;

import java.io.IOException;
import java.net.ServerSocket;
import java.nio.file.Files;
import java.nio.file.Path;
import java.util.ArrayList;
import java.util.List;
import java.util.Set;
import java.util.TreeSet;
import java.util.concurrent.TimeUnit;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.Timeout;
import org.junit.jupiter.api.io.TempDir;
import org.speckitty.missionstatus.testsupport.http.HttpHarness;
import org.springframework.web.servlet.mvc.method.RequestMappingInfo;
import org.springframework.web.servlet.mvc.method.annotation.RequestMappingHandlerMapping;

/**
 * AC-17.2: #5529's AC-9a (a non-loopback bind is refused; a port in use is refused) holds with the five detail routes registered. The bind
 * guards end the process, so they run in a child JVM of the same application classes; this test also asserts, in process, that the five routes
 * are registered in that application, because a startup that lacked them would leave the acceptance criterion vacuous.
 */
class DetailRoutesBindGuardTest {

  private static final long BOUND_SECONDS = 60;

  /** The five detail paths, as the application registers them (the prefix is the contract's server path). */
  static final Set<String> DETAIL_PATTERNS =
      Set.of(
          "/api/v1/missions/{missionId}",
          "/api/v1/missions/{missionId}/work-packages/{wpId}",
          "/api/v1/missions/{missionId}/work-packages/{wpId}/detail",
          "/api/v1/missions/{missionId}/artifacts",
          "/api/v1/missions/{missionId}/artifacts/content");

  @Test
  void theApplicationRegistersTheFiveDetailRoutes(@TempDir Path root) {
    try (HttpHarness server = HttpHarness.startWired(root)) {
      Set<String> registered = new TreeSet<>();
      for (RequestMappingInfo info : server.context().getBean(RequestMappingHandlerMapping.class).getHandlerMethods().keySet()) {
        registered.addAll(info.getPathPatternsCondition().getPatternValues());
      }
      assertThat(registered).containsAll(DETAIL_PATTERNS);
    }
  }

  private record Result(boolean exited, int exitCode, String output) {}

  private static Result run(Path dir, List<String> appArgs) throws IOException, InterruptedException {
    List<String> command = new ArrayList<>();
    command.add(Path.of(System.getProperty("java.home"), "bin", "java").toString());
    command.add("-cp");
    command.add(System.getProperty("java.class.path"));
    command.add("org.speckitty.missionstatus.config.MissionStatusApplication");
    command.addAll(appArgs);
    Path log = dir.resolve("out.log");
    Process process = new ProcessBuilder(command).redirectErrorStream(true).redirectOutput(log.toFile()).start();
    boolean exited = process.waitFor(BOUND_SECONDS, TimeUnit.SECONDS);
    if (!exited) {
      process.destroyForcibly();
      process.waitFor(30, TimeUnit.SECONDS);
    }
    return new Result(exited, exited ? process.exitValue() : -1, Files.readString(log));
  }

  private static int freePort() throws IOException {
    try (ServerSocket socket = new ServerSocket(0)) {
      return socket.getLocalPort();
    }
  }

  @Test
  @Timeout(240)
  void aNonLoopbackBindIsRefusedAndNamedWithTheDetailRoutesRegistered(@TempDir Path dir) throws Exception {
    Result result = run(dir, List.of("--server.address=0.0.0.0", "--server.port=" + freePort(), "--mission-status.project-root=" + dir));

    assertThat(result.exited()).isTrue();
    assertThat(result.exitCode()).isNotZero();
    assertThat(result.output()).contains("0.0.0.0");
  }

  @Test
  @Timeout(240)
  void aPortInUseIsRefusedAndNamedWithTheDetailRoutesRegistered(@TempDir Path dir) throws Exception {
    try (ServerSocket taken = new ServerSocket(0, 1, java.net.InetAddress.getByName("127.0.0.1"))) {
      int port = taken.getLocalPort();

      Result result = run(dir, List.of("--server.port=" + port, "--mission-status.project-root=" + dir));

      assertThat(result.exited()).isTrue();
      assertThat(result.exitCode()).isNotZero();
      assertThat(result.output()).contains(Integer.toString(port));
    }
  }

  @Test
  @Timeout(240)
  void controlTheSameStartWithALoopbackBindComesUpAndServesADetailRouteRefusal(@TempDir Path dir) throws Exception {
    int port = freePort();
    List<String> command = List.of(Path.of(System.getProperty("java.home"), "bin", "java").toString(), "-cp", System.getProperty("java.class.path"), "org.speckitty.missionstatus.config.MissionStatusApplication", "--server.port=" + port, "--mission-status.project-root=" + dir);
    Process process = new ProcessBuilder(command).redirectErrorStream(true).redirectOutput(dir.resolve("up.log").toFile()).start();
    try {
      long deadline = System.nanoTime() + TimeUnit.SECONDS.toNanos(BOUND_SECONDS);
      java.net.http.HttpResponse<String> response = null;
      while (System.nanoTime() < deadline && process.isAlive() && response == null) {
        try {
          response = java.net.http.HttpClient.newHttpClient().send(java.net.http.HttpRequest.newBuilder(java.net.URI.create("http://127.0.0.1:" + port + "/api/v1/missions/01J09999999999999999999999/artifacts")).GET().build(), java.net.http.HttpResponse.BodyHandlers.ofString());
        } catch (IOException notYet) {
          Thread.sleep(300);
        }
      }
      assertThat(response).as("the loopback start answered").isNotNull();
      assertThat(response.statusCode()).isEqualTo(404);
      assertThat(response.body()).contains("\"code\":\"not_found\"");
    } finally {
      process.destroyForcibly();
      process.waitFor();
    }
  }
}
