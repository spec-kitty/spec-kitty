package org.speckitty.missionstatus.adapter.in.http.flow;

import static org.assertj.core.api.Assertions.assertThat;

import java.nio.file.Files;
import java.nio.file.Path;
import java.util.List;
import jdk.jfr.Recording;
import jdk.jfr.consumer.RecordedEvent;
import jdk.jfr.consumer.RecordingFile;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.io.TempDir;
import org.speckitty.missionstatus.testsupport.FilesystemFixtureFactory;
import org.speckitty.missionstatus.testsupport.FixtureSpec;
import org.speckitty.missionstatus.testsupport.PortFixtures;
import org.speckitty.missionstatus.testsupport.Rows;
import org.speckitty.missionstatus.testsupport.http.StreamRig;

/**
 * AC-10c, the runtime half (JVM leg only): a Java Flight Recorder recording around the full request flow, with the process-start event
 * enabled, holds no such event. The event name on the pinned JDK is {@code jdk.ProcessStart} (WP02's recorded answer). The positive
 * control starts a process in the same kind of recording and the event must appear: a recording that cannot see a spawn proves nothing.
 */
class NoProcessStartTest {

  private static final String EVENT = "jdk.ProcessStart";

  private static FixtureSpec spec() {
    return FixtureSpec.of(
        PortFixtures.mission("alpha", Rows.ALPHA_ID, PortFixtures.CREATED, Rows.status(Rows.id(1), "2026-09-01T10:00:00Z", "WP01", "planned", "claimed")),
        PortFixtures.mission("beta", Rows.BETA_ID, "2026-09-03T10:00:00+00:00", Rows.status(Rows.id(50), "2026-09-01T10:00:00Z", "WP01", "planned", "claimed")));
  }

  private static List<RecordedEvent> record(Path dir, Runnable work) throws Exception {
    Path dump = dir.resolve("flow.jfr");
    try (Recording recording = new Recording()) {
      recording.enable(EVENT);
      recording.start();
      try {
        work.run();
      } finally {
        recording.stop();
      }
      recording.dump(dump);
    }
    return RecordingFile.readAllEvents(dump);
  }

  private static void flow() {
    try (StreamRig rig = StreamRig.over(FilesystemFixtureFactory.fromSpec(spec()))) {
      Flow.requests(rig.http);
      Flow.streams(rig, "alpha", Rows.ALPHA_ID, "beta", "plain reason");
    }
  }

  @Test
  void theFullRequestFlowStartsNoProcess(@TempDir Path dir) throws Exception {
    List<RecordedEvent> events = record(dir, NoProcessStartTest::flow);

    assertThat(events).as("no " + EVENT + " during the three routes, the contract document and a stream round trip").isEmpty();
  }

  @Test
  void positiveControlAProcessStartedInTheSameKindOfRecordingIsSeen(@TempDir Path dir) throws Exception {
    List<RecordedEvent> events =
        record(
            dir,
            () -> {
              flow();
              try {
                Process child = new ProcessBuilder(Path.of(System.getProperty("java.home"), "bin", "java").toString(), "-version").redirectErrorStream(true).start();
                child.getInputStream().readAllBytes();
                child.waitFor();
              } catch (Exception failure) {
                throw new IllegalStateException(failure);
              }
            });

    assertThat(events).extracting(event -> event.getEventType().getName()).containsOnly(EVENT);
    assertThat(events).hasSize(1);
  }

  @Test
  void theRecordingFileIsReadBackFromTheDumpNotFromMemory(@TempDir Path dir) throws Exception {
    Path dump = dir.resolve("empty.jfr");
    try (Recording recording = new Recording()) {
      recording.enable(EVENT);
      recording.start();
      recording.stop();
      recording.dump(dump);
    }
    assertThat(Files.size(dump)).isPositive();
  }
}
