package org.speckitty.missionstatus.nativesmoke;

import static org.assertj.core.api.Assertions.assertThat;

import java.io.IOException;
import java.io.UncheckedIOException;
import java.nio.file.Files;
import java.nio.file.Path;
import java.util.OptionalLong;
import org.junit.jupiter.api.Test;
import org.speckitty.missionstatus.config.MissionStatusApplication;
import org.springframework.boot.builder.SpringApplicationBuilder;
import org.springframework.context.ConfigurableApplicationContext;

/**
 * The same replay, the same requests.json and the same comparison, against the JVM service. It runs in {@code check}, so a wrong
 * expectation in the request set shows before a native image is built, and it gives the digest the native legs must reproduce.
 */
class JvmReplayTest {

  @Test
  void theJvmServiceServesTheGoldenRequestSetByteForByte() {
    SmokeRequests requests = SmokeRequests.load();

    Replay.Outcome outcome = Replay.replayAll(requests, (root, port) -> new Jvm(root, port, -1, 0));

    Replay.requireCounts(outcome.exchanges().size(), outcome.bodies().size());
    Replay.requireFloors(requests, outcome.requestsPerStage());
    assertThat(outcome.exchanges()).hasSize(requests.allRequests().size());
    String sha256 = Digest.sha256(outcome.bodies());
    assertThat(sha256).hasSize(64);
    // the digest the native legs must reproduce; kept in the build directory so a local run can compare the two
    try {
      Path output = NativeSmokeTest.OUTPUT;
      Files.createDirectories(output);
      Files.writeString(output.resolve("jvm-sha256.txt"), sha256 + "\n");
    } catch (IOException failure) {
      throw new UncheckedIOException(failure);
    }
  }

  /**
   * Pre-merge fold J13, corrected after the Windows leg: a service that starts a process during the replay fails it. The count is
   * compared with the count taken before the replay; a service that spawns a child while serving shows one more after.
   */
  @Test
  void aServiceThatStartsAChildProcessDuringTheReplayFailsTheReplay() {
    SmokeRequests requests = SmokeRequests.load();
    org.assertj.core.api.Assertions.assertThatThrownBy(() -> Replay.replayAll(requests, (root, port) -> new Jvm(root, port, 0, 1)))
        .isInstanceOf(AssertionError.class)
        .hasMessageContaining("must start no process");
    org.assertj.core.api.Assertions.assertThatThrownBy(() -> Replay.replayAll(requests, (root, port) -> new Jvm(root, port, 1, 2)))
        .isInstanceOf(AssertionError.class)
        .hasMessageContaining("must start no process");
  }

  /** A child the service already had before the replay (the Windows console host) is not a process the replay started. */
  @Test
  void aChildThatWasThereBeforeTheReplayDoesNotFailTheReplay() {
    SmokeRequests requests = SmokeRequests.load();
    Replay.Outcome outcome = Replay.replayAll(requests, (root, port) -> new Jvm(root, port, 1, 0));
    assertThat(outcome.childrenSamples()).as("the child count was sampled").isEqualTo(requests.groups().size());
  }

  private static final class Jvm implements Replay.Running {
    private final ConfigurableApplicationContext context;
    private final long before;
    private final long added;
    private int samples;

    /** {@code before} children at the first count (negative: the platform cannot count); {@code added} more from the second count on (a process the replay started). */
    Jvm(Path root, int port, long before, long added) {
      this.before = before;
      this.added = added;
      this.context = new SpringApplicationBuilder(MissionStatusApplication.class).run("--mission-status.project-root=" + root, "--mission-status.port=" + port);
    }

    @Override
    public void requireAlive() {
      assertThat(context.isRunning()).as("the JVM service is running").isTrue();
    }

    @Override
    public OptionalLong childProcesses() {
      if (before < 0) {
        return OptionalLong.empty();
      }
      samples++;
      return OptionalLong.of(samples == 1 ? before : before + added);
    }

    @Override
    public void close() {
      context.close();
    }
  }
}
