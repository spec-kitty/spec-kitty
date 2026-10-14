package org.speckitty.missionstatus.nativesmoke;

import static org.assertj.core.api.Assertions.assertThat;

import java.io.IOException;
import java.io.UncheckedIOException;
import java.nio.charset.StandardCharsets;
import java.nio.file.Files;
import java.nio.file.Path;
import java.util.List;
import java.util.Map;
import java.util.OptionalLong;
import java.util.concurrent.TimeUnit;
import org.junit.jupiter.api.Tag;
import org.junit.jupiter.api.Test;

/**
 * The native smoke replay (AC-15b, AC-15e producer side): starts the BUILT binary once per group of {@code requests.json} over a copy of
 * the group's fixture tree, replays the literal requests through raw sockets, compares every 2xx body byte for byte with its golden,
 * and writes {@code build/nativesmoke/digest-<os>-<arch>.json}. Tagged native-binary, so only the {@code nativeSmoke} task runs it
 * (with {@code -PnativeBinary=path}), never {@code test} or {@code check}.
 */
@Tag("native-binary")
class NativeSmokeTest {

  static final Path OUTPUT = Path.of("build", "nativesmoke");

  @Test
  void theBuiltBinaryServesTheGoldenRequestSetByteForByte() throws Exception {
    String binary = System.getProperty("nativeBinary");
    assertThat(binary).as("the nativeBinary system property (-PnativeBinary)").isNotBlank();
    SmokeRequests requests = SmokeRequests.load();

    Replay.Outcome outcome = Replay.replayAll(requests, (root, port) -> new BinaryProcess(Path.of(binary), root, port));

    Replay.requireCounts(outcome.exchanges().size(), outcome.bodies().size());
    Replay.requireFloors(requests, outcome.requestsPerStage());
    String sha256 = Digest.sha256(outcome.bodies());
    String os = Digest.osToken(System.getProperty("os.name"));
    String arch = Digest.archToken(System.getProperty("os.arch"));
    Path file = Digest.write(OUTPUT, os, arch, outcome.exchanges().size(), outcome.bodies().size(), sha256);

    String summary =
        "native smoke " + os + "-" + arch + ": " + outcome.exchanges().size() + " requests replayed in " + outcome.groupsStarted() + " binary starts, " + outcome.bodies().size()
            + " bodies compared and hashed, sha256 " + sha256 + "; child processes " + (outcome.childrenSamples() > 0 ? "sampled equal before and after on " + outcome.childrenSamples() + " start(s)" : "not measurable on this leg");
    System.out.println(summary);
    Files.writeString(OUTPUT.resolve("summary-" + os + "-" + arch + ".txt"), summary + "\n", StandardCharsets.UTF_8);
    assertThat(file).exists();
  }

  /**
   * The locale of the child (FR-004, D-90): on a POSIX host the binary reads file names as UTF-8 only under a UTF-8 locale, and the
   * runners differ, so the harness sets {@code LC_ALL=C.UTF-8} itself and no workflow line has to. Windows decodes names on its own and
   * is left as it is.
   */
  static void applyLocale(Map<String, String> environment, boolean windows) {
    if (!windows) {
      environment.put("LC_ALL", "C.UTF-8");
    }
  }

  /** The binary as a child process: output goes to a log file that is only ever shown path-free, after a failure. */
  static final class BinaryProcess implements Replay.Running {
    private final Process process;
    private final Path log;
    private final Path root;

    BinaryProcess(Path binary, Path projectRoot, int port) {
      this.root = projectRoot;
      try {
        this.log = Files.createTempFile("mission-status-smoke-", ".log");
        ProcessBuilder builder =
            new ProcessBuilder(binary.toString(), "--mission-status.project-root=" + projectRoot, "--mission-status.port=" + port)
                .redirectErrorStream(true)
                .redirectOutput(log.toFile());
        applyLocale(builder.environment(), Digest.osToken(System.getProperty("os.name")).equals("windows"));
        this.process = builder.start();
      } catch (IOException failure) {
        throw new UncheckedIOException(failure);
      }
    }

    /** The operating-system process id, for the thread and resident-set reads of the performance probe. */
    long pid() {
      return process.pid();
    }

    @Override
    public void requireAlive() {
      if (!process.isAlive()) {
        throw new AssertionError("the binary exited early with status " + process.exitValue() + "; log tail:\n" + tail());
      }
    }

    @Override
    public OptionalLong childProcesses() {
      try {
        return OptionalLong.of(process.toHandle().children().count());
      } catch (UnsupportedOperationException | SecurityException notMeasurable) {
        return OptionalLong.empty();
      }
    }

    @Override
    public void close() {
      process.destroy();
      try {
        if (!process.waitFor(10, TimeUnit.SECONDS)) {
          process.destroyForcibly();
          process.waitFor(10, TimeUnit.SECONDS);
        }
      } catch (InterruptedException interrupted) {
        Thread.currentThread().interrupt();
        process.destroyForcibly();
      }
      try {
        Files.deleteIfExists(log);
      } catch (IOException ignored) {
        // the operating system cleans its temporary directory
      }
    }

    /** The last lines of the log with the project root and the temporary directory replaced, so a report names no directory of the machine. */
    private String tail() {
      try {
        List<String> lines = Files.readAllLines(log, StandardCharsets.UTF_8);
        String tmp = System.getProperty("java.io.tmpdir");
        return String.join("\n", lines.subList(Math.max(0, lines.size() - 20), lines.size())).replace(root.toString(), "<project-root>").replace(tmp, "<tmp>");
      } catch (IOException | RuntimeException unreadable) {
        return "(no readable log)";
      }
    }
  }
}
