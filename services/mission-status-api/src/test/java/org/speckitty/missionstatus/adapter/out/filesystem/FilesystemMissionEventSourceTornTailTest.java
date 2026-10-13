package org.speckitty.missionstatus.adapter.out.filesystem;

import static org.assertj.core.api.Assertions.assertThat;
import static org.assertj.core.api.Assertions.assertThatThrownBy;

import java.io.IOException;
import java.nio.channels.FileChannel;
import java.nio.charset.StandardCharsets;
import java.nio.file.Files;
import java.nio.file.Path;
import java.nio.file.StandardOpenOption;
import java.nio.ByteBuffer;
import java.time.Duration;
import java.util.ArrayList;
import java.util.List;
import java.util.concurrent.CountDownLatch;
import java.util.concurrent.TimeUnit;
import java.util.concurrent.atomic.AtomicBoolean;
import java.util.concurrent.atomic.AtomicInteger;
import java.util.concurrent.atomic.AtomicReference;
import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.Timeout;
import org.junit.jupiter.api.io.TempDir;
import org.speckitty.missionstatus.application.query.port.in.exceptions.MissionStatusUnavailable;
import org.speckitty.missionstatus.domain.model.DiagnosticCode;
import org.speckitty.missionstatus.domain.model.Lane;
import org.speckitty.missionstatus.domain.readmodel.overview.MissionOverview;
import org.speckitty.missionstatus.testsupport.Rows;

/**
 * AC-4d at the adapter: a writer that tears its last row is seen by a reader through the real service over the real source. Every 200
 * item describes ONE prefix of complete lines of the final log in all four fields ({@code eventCount}, {@code statusLaneCounts},
 * {@code lastEventId}, {@code streamCursor}); every other answer is the L4 or L4b refusal. The HTTP legs are WP10's.
 */
@Timeout(120)
class FilesystemMissionEventSourceTornTailTest {

  private static final int ROWS = 600;

  @TempDir Path sandbox;
  AdapterServiceHarness harness;
  Path ledger;

  @BeforeEach
  void setUp() throws IOException {
    Path root = Files.createDirectory(sandbox.resolve("project"));
    AdapterServiceHarness.healthyProject(root);
    AdapterServiceHarness.mission(root, AdapterServiceHarness.ALPHA, Rows.ALPHA_ID, "2026-09-01T09:00:00+00:00", "");
    harness = new AdapterServiceHarness(root);
    ledger = root.resolve("kitty-specs").resolve(AdapterServiceHarness.ALPHA).resolve("status.events.jsonl");
  }

  /** Row {@code n} (1-based): WP01 alternates between claimed and blocked, so the lane counts name the prefix's parity. */
  private static String row(int n) {
    String from = n == 1 ? "planned" : n % 2 == 1 ? "blocked" : "claimed";
    String to = n % 2 == 1 ? "claimed" : "blocked";
    return Rows.status(Rows.id(n), String.format("2026-09-01T10:%02d:%02d+00:00", n / 60, n % 60), "WP01", from, to);
  }

  private void append(String text) throws IOException {
    try (FileChannel channel = FileChannel.open(ledger, StandardOpenOption.APPEND, StandardOpenOption.CREATE)) {
      channel.write(ByteBuffer.wrap(text.getBytes(StandardCharsets.UTF_8)));
    }
  }

  private static void awaitReads(AtomicInteger readsDone, int count) {
    awaitReads(readsDone, count, Duration.ofSeconds(30));
  }

  /** A bounded spin: it fails with a clear message instead of hanging when the reader stops making progress (F8). */
  static void awaitReads(AtomicInteger readsDone, int count, Duration limit) {
    int seen = readsDone.get();
    long deadline = System.nanoTime() + limit.toNanos();
    while (readsDone.get() < seen + count) {
      if (System.nanoTime() > deadline) {
        throw new AssertionError("the reader made no progress for " + limit + " (waited for " + count + " more reads)");
      }
      Thread.onSpinWait();
    }
  }

  @Test
  @Timeout(10)
  void aStalledReaderFailsTheWaitWithAClearMessageInsteadOfHanging() {
    assertThatThrownBy(() -> awaitReads(new AtomicInteger(), 2, Duration.ofMillis(100))).isInstanceOf(AssertionError.class).hasMessageContaining("no progress");
  }

  private MissionOverview read() {
    return harness.overviews().get(0);
  }

  private static void assertRefusedAs(Runnable read, DiagnosticCode code) {
    assertThatThrownBy(read::run).isInstanceOf(MissionStatusUnavailable.class).extracting(failure -> ((MissionStatusUnavailable) failure).code()).isEqualTo(code);
  }

  /** The four fields of the prefix of the first {@code k} rows. */
  private static void assertPrefix(MissionOverview item, int k) {
    long offset = 0;
    String last = "";
    for (int n = 1; n <= k; n++) {
      last = row(n);
      offset += last.getBytes(StandardCharsets.UTF_8).length;
    }
    assertThat(item.eventCount()).isEqualTo(k);
    assertThat(item.lastEventId()).isEqualTo(k == 0 ? null : Rows.id(k));
    assertThat(item.streamCursor().offset()).isEqualTo(offset);
    assertThat(item.streamCursor().invariant()).isEqualTo(FilesystemMissionEventSourceTest.sha(k == 0 ? new byte[0] : last.getBytes(StandardCharsets.UTF_8)));
    int claimed = k == 0 ? 0 : k % 2 == 1 ? 1 : 0;
    int blocked = k == 0 ? 0 : k % 2 == 0 ? 1 : 0;
    assertThat(item.statusLaneCounts().get(Lane.CLAIMED)).isEqualTo(claimed);
    assertThat(item.statusLaneCounts().get(Lane.BLOCKED)).isEqualTo(blocked);
  }

  @Test
  void theLatchControlledWriterIsSeenAsL4ThenL4bThenTheNewPrefix() throws Exception {
    append(row(1));
    assertPrefix(read(), 1);

    String next = row(2);
    String half = next.substring(0, next.length() / 2);
    String restWithoutNewline = next.substring(next.length() / 2, next.length() - 1);

    CountDownLatch[] go = {new CountDownLatch(1), new CountDownLatch(1), new CountDownLatch(1)};
    CountDownLatch[] done = {new CountDownLatch(1), new CountDownLatch(1), new CountDownLatch(1)};
    AtomicReference<Throwable> writerFailure = new AtomicReference<>();
    Thread writer =
        Thread.ofPlatform()
            .daemon(true)
            .name("latch-writer")
            .start(
                () -> {
                  try {
                    String[] steps = {half, restWithoutNewline, "\n"};
                    for (int step = 0; step < steps.length; step++) {
                      go[step].await();
                      append(steps[step]);
                      done[step].countDown();
                    }
                  } catch (IOException | InterruptedException failure) {
                    writerFailure.set(failure);
                  }
                });

    go[0].countDown();
    assertThat(done[0].await(30, TimeUnit.SECONDS)).isTrue();
    assertRefusedAs(this::read, DiagnosticCode.LEDGER_TORN_TAIL);

    go[1].countDown();
    assertThat(done[1].await(30, TimeUnit.SECONDS)).isTrue();
    assertThat(Files.readString(ledger)).as("the row is valid JSON now, only its newline is missing").endsWith("}");
    assertRefusedAs(this::read, DiagnosticCode.LEDGER_TORN_TAIL);

    go[2].countDown();
    assertThat(done[2].await(30, TimeUnit.SECONDS)).isTrue();
    writer.join(30_000);
    assertThat(writerFailure.get()).isNull();
    assertPrefix(read(), 2);
  }

  @Test
  void aFreeRunningWriterIsNeverSeenAsAMixedPrefix() throws Exception {
    AtomicBoolean finished = new AtomicBoolean();
    AtomicInteger readsDone = new AtomicInteger();
    AtomicReference<Throwable> writerFailure = new AtomicReference<>();
    CountDownLatch started = new CountDownLatch(1);
    Thread writer =
        Thread.ofPlatform()
            .daemon(true)
            .name("free-writer")
            .start(
                () -> {
                  try {
                    started.countDown();
                    for (int n = 1; n <= ROWS; n++) {
                      String text = row(n);
                      // the body and the newline are separate writes ...
                      append(text.substring(0, text.length() - 1));
                      // ... and the writer holds the torn state until two reads that began after the body have finished
                      awaitReads(readsDone, 2);
                      append("\n");
                      // then the complete row is served by the next two reads before the next row starts
                      awaitReads(readsDone, 2);
                    }
                  } catch (IOException | AssertionError failure) {
                    writerFailure.set(failure);
                  } finally {
                    finished.set(true);
                  }
                });
    started.await();

    List<MissionOverview> served = new ArrayList<>();
    int refused = 0;
    int reads = 0;
    int readsWhileWriting = 0;
    while (reads < 200 || !finished.get()) {
      reads++;
      readsWhileWriting += finished.get() ? 0 : 1;
      try {
        served.add(read());
      } catch (MissionStatusUnavailable refusal) {
        assertThat(refusal.code()).as("every refusal is the L4 or L4b refusal").isEqualTo(DiagnosticCode.LEDGER_TORN_TAIL);
        refused++;
      }
      readsDone.set(reads);
    }
    writer.join(30_000);
    assertThat(writerFailure.get()).isNull();
    assertThat(reads).isGreaterThanOrEqualTo(200);
    assertThat(readsWhileWriting).as("reads that overlapped the writer").isGreaterThanOrEqualTo(200);
    assertThat(refused).as("every row was held torn for at least one read").isGreaterThanOrEqualTo(ROWS);

    for (MissionOverview item : served) {
      assertPrefix(item, item.eventCount());
    }
    assertPrefix(read(), ROWS);
    assertThat(served).as("every row was also served complete").hasSizeGreaterThanOrEqualTo(ROWS);
    System.out.println("free-running torn-tail leg: " + reads + " reads (" + readsWhileWriting + " while the writer ran), " + served.size() + " served, " + refused + " refused");
  }
}
