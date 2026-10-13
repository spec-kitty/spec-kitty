package org.speckitty.missionstatus.config;

import static org.assertj.core.api.Assertions.assertThat;

import java.io.IOException;
import java.net.InetSocketAddress;
import java.net.Socket;
import java.net.URI;
import java.net.http.HttpClient;
import java.net.http.HttpRequest;
import java.net.http.HttpResponse;
import java.nio.file.Files;
import java.nio.file.Path;
import java.util.List;
import java.util.Map;
import java.util.stream.Stream;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.Timeout;
import org.junit.jupiter.api.io.TempDir;
import org.junit.jupiter.params.ParameterizedTest;
import org.junit.jupiter.params.provider.MethodSource;

/**
 * Spring Boot reads {@code ./config/application.properties} and {@code ./application.properties} from the WORKING DIRECTORY by default,
 * and the environment and the command line can add more locations. A developer who starts the binary from inside a cloned, untrusted
 * project would then let that project reconfigure a "read-only" service: serve any file through the static-resource handler, or write a
 * log file anywhere. The configuration is therefore pinned to the packaged {@code application.properties}; this test starts the real
 * service in a child JVM with each of those routes carrying hostile properties and checks that none of it takes effect.
 */
class ConfigPinProcessTest {

  private static final String SECRET = "ghp_aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa";
  private static final long UP_SECONDS = 60;

  /** How the hostile file reaches the service: the working directory (two spellings), the environment (two keys) or the command line. */
  enum Route {
    CWD_CONFIG_DIRECTORY,
    CWD_PLAIN,
    ENVIRONMENT_ADDITIONAL_LOCATION,
    ENVIRONMENT_LOCATION,
    COMMAND_LINE_ADDITIONAL_LOCATION,
    COMMAND_LINE_IMPORT
  }

  static Stream<Route> routes() {
    return Stream.of(Route.values());
  }

  @ParameterizedTest(name = "hostile properties through {0}")
  @MethodSource("routes")
  @Timeout(120)
  void hostilePropertiesAreIgnored(Route route, @TempDir Path dir) throws Exception {
    Path cwd = Files.createDirectories(dir.resolve("cwd"));
    Path outside = Files.createDirectories(dir.resolve("outside"));
    Path pwned = Files.createDirectories(dir.resolve("pwned"));
    Path project = Files.createDirectories(dir.resolve("project"));
    Files.writeString(outside.resolve("secret.txt"), SECRET);
    Path logFile = pwned.resolve("written-by-service.log");
    String hostile =
        "spring.web.resources.add-mappings=true\n"
            + "spring.web.resources.static-locations=file:" + outside + "/\n"
            + "logging.file.name=" + logFile + "\n";
    int port = AppProcess.freePort();
    List<String> app = new java.util.ArrayList<>(List.of("--server.port=" + port, "--mission-status.project-root=" + project));
    Map<String, String> environment = new java.util.HashMap<>();
    switch (route) {
      case CWD_CONFIG_DIRECTORY -> Files.writeString(Files.createDirectories(cwd.resolve("config")).resolve("application.properties"), hostile);
      case CWD_PLAIN -> Files.writeString(cwd.resolve("application.properties"), hostile);
      case ENVIRONMENT_ADDITIONAL_LOCATION -> {
        Files.writeString(dir.resolve("hostile.properties"), hostile);
        environment.put("SPRING_CONFIG_ADDITIONAL_LOCATION", "file:" + dir.resolve("hostile.properties"));
      }
      case ENVIRONMENT_LOCATION -> {
        Files.writeString(dir.resolve("hostile.properties"), hostile);
        environment.put("SPRING_CONFIG_LOCATION", "file:" + dir.resolve("hostile.properties"));
      }
      case COMMAND_LINE_ADDITIONAL_LOCATION -> {
        Files.writeString(dir.resolve("hostile.properties"), hostile);
        app.add("--spring.config.additional-location=file:" + dir.resolve("hostile.properties"));
      }
      case COMMAND_LINE_IMPORT -> {
        Files.writeString(dir.resolve("hostile.properties"), hostile);
        app.add("--spring.config.import=file:" + dir.resolve("hostile.properties"));
      }
    }

    Process process = AppProcess.launch(dir.resolve("out.log"), cwd, environment, List.of(), app);
    try {
      awaitUp(process, port, dir.resolve("out.log"));
      HttpResponse<String> response =
          HttpClient.newHttpClient()
              .send(HttpRequest.newBuilder(URI.create("http://127.0.0.1:" + port + "/secret.txt")).GET().build(), HttpResponse.BodyHandlers.ofString());
      assertThat(response.statusCode()).as("a file outside the project is not served").isNotEqualTo(200);
      assertThat(response.body()).doesNotContain(SECRET);
      assertThat(logFile).as("the service created no log file where the hostile properties asked").doesNotExist();
      assertThat(Files.readString(dir.resolve("out.log"))).doesNotContain(SECRET);
    } finally {
      process.destroyForcibly();
      process.waitFor();
    }
  }

  /** The packaged file is the only configuration: pointing {@code spring.config.name} elsewhere changes nothing, so the loopback default holds. */
  @Test
  @Timeout(120)
  void aConfigNameThatPointsAwayDoesNotRemoveThePackagedDefaults(@TempDir Path dir) throws Exception {
    int port = AppProcess.freePort();
    Process process =
        AppProcess.launch(dir.resolve("out.log"), List.of(), List.of("--spring.config.name=none-such", "--server.port=" + port, "--mission-status.project-root=" + dir));
    try {
      awaitUp(process, port, dir.resolve("out.log"));
      assertThat(process.isAlive()).isTrue();
    } finally {
      process.destroyForcibly();
      process.waitFor();
    }
  }

  private static void awaitUp(Process process, int port, Path log) throws IOException, InterruptedException {
    long deadline = System.nanoTime() + UP_SECONDS * 1_000_000_000L;
    while (System.nanoTime() < deadline && process.isAlive()) {
      try (Socket socket = new Socket()) {
        socket.connect(new InetSocketAddress("127.0.0.1", port), 500);
        return;
      } catch (IOException notYet) {
        Thread.sleep(200);
      }
    }
    throw new AssertionError("the service did not come up: " + Files.readString(log));
  }
}
