package org.speckitty.missionstatus.application.query;

import static org.assertj.core.api.Assertions.assertThat;

import java.util.ArrayList;
import java.util.List;
import java.util.Optional;
import java.util.concurrent.CountDownLatch;
import java.util.concurrent.ExecutorService;
import java.util.concurrent.Executors;
import java.util.concurrent.Future;
import java.util.concurrent.TimeUnit;
import java.util.concurrent.atomic.AtomicInteger;
import java.util.function.Supplier;
import org.junit.jupiter.api.Test;
import org.speckitty.missionstatus.adapter.in.http.flow.DetailServices;
import org.speckitty.missionstatus.application.query.detail.DetailRoute;
import org.speckitty.missionstatus.application.query.port.in.dto.ArtifactPathInput;
import org.speckitty.missionstatus.application.query.port.in.dto.PageRequest;
import org.speckitty.missionstatus.application.query.port.out.TextSource;
import org.speckitty.missionstatus.application.query.port.out.dto.BytesRead;
import org.speckitty.missionstatus.application.query.port.out.dto.DirListing;
import org.speckitty.missionstatus.application.query.port.out.dto.EntryStat;
import org.speckitty.missionstatus.application.query.port.out.dto.FileRef;
import org.speckitty.missionstatus.application.query.port.out.dto.ReadScope;
import org.speckitty.missionstatus.application.query.port.out.dto.TextRead;
import org.speckitty.missionstatus.domain.readmodel.cursor.StreamCursor;
import org.speckitty.missionstatus.testsupport.DetailFixture;
import org.speckitty.missionstatus.testsupport.PlainCaller;
import org.speckitty.missionstatus.testsupport.Rows;

/**
 * AC-22.1 to AC-22.3 at the port, with no Spring context and no HTTP (AC-13.3's plain-Java caller). Four operations are gated (D-148:
 * {@code getWorkPackageDetail}, {@code listArtifacts}, {@code getArtifactContent} and {@code getWorkPackage} with {@code includePrompt=true};
 * the spec text of AC-22.1 still says three operations and 48 calls, the plan's four and 64 are binding):
 *
 * <ul>
 *   <li>AC-22.1: 16 concurrent calls to each of the four, 64 in all, whose first read blocks on a latch: while they block the gate's high-water
 *       mark and the number of calls inside a read are both exactly 4, and releasing the latch lets all 64 complete with normal results;
 *   <li>AC-22.2: 100 calls queued behind 4 blocked holders all complete after the release and none is answered with a status; meanwhile
 *       {@code getMission}, {@code getWorkPackage} without a prompt and the three #5529 reads still complete, because they are not behind the gate;
 *   <li>AC-22.3: a planted implementation that does not pass the gate lets more than 4 calls inside a read, so the same assertion is red.
 * </ul>
 *
 * The HTTP leg (AC-22.4) is {@code Nfr002BoundedMemoryScenarioTest}. This class is not listed in {@code portlevel-tests.txt}: it lives outside
 * {@code conformance.port} and opens no selector fixture.
 */
class AdmissionGatePortLevelTest {

  private static final int PER_OPERATION = 16;
  private static final long BOUND_SECONDS = 30;

  /**
   * A text source that blocks the first read of each call made by a thread that armed it, on one latch, and counts how many armed calls are
   * inside at once. A thread that did not arm it (the ungated operations, the #5529 reads) is never blocked.
   */
  static final class Blocking implements TextSource {
    private final TextSource delegate;
    final CountDownLatch release = new CountDownLatch(1);
    final AtomicInteger inside = new AtomicInteger();
    final AtomicInteger maxInside = new AtomicInteger();
    private final ThreadLocal<Boolean> armed = ThreadLocal.withInitial(() -> false);

    Blocking(TextSource delegate) {
      this.delegate = delegate;
    }

    /** The calling thread's next first read blocks. */
    void arm() {
      armed.set(true);
    }

    private void block() {
      if (!armed.get()) {
        return;
      }
      armed.set(false);
      maxInside.accumulateAndGet(inside.incrementAndGet(), Math::max);
      try {
        if (!release.await(BOUND_SECONDS, TimeUnit.SECONDS)) {
          throw new IllegalStateException("the latch was not released");
        }
      } catch (InterruptedException interrupted) {
        Thread.currentThread().interrupt();
        throw new IllegalStateException(interrupted);
      } finally {
        inside.decrementAndGet();
      }
    }

    @Override
    public DirListing list(FileRef dir, int nameLimit, ReadScope scope) {
      block();
      return delegate.list(dir, nameLimit, scope);
    }

    @Override
    public EntryStat stat(FileRef path, ReadScope scope) {
      block();
      return delegate.stat(path, scope);
    }

    @Override
    public BytesRead readBytes(FileRef file, int cap, ReadScope scope) {
      block();
      return delegate.readBytes(file, cap, scope);
    }

    @Override
    public TextRead readText(FileRef file, int cap, ReadScope scope) {
      block();
      return delegate.readText(file, cap, scope);
    }
  }

  /** One rig: a fixture with a Work Package, a spec and a tasks file, the blocking source, one gate and the four services. */
  private static final class Rig {
    final DetailFixture fixture = DetailRoute.fixture(root -> {
      DetailRoute.write(root, "spec.md", "# Spec\n");
      DetailRoute.write(root, "tasks.md", "- [ ] T001 One\n");
    });
    final Blocking blocking = new Blocking(fixture.textSource());
    final AdmissionGate gate = new AdmissionGate();
    final DetailServices services = DetailServices.over(fixture, blocking, gate);
    final PlainCaller caller = new PlainCaller(services.mission(), services.workPackage(), services.workPackageDetail(), services.artifact());
    final List<Throwable> failures = new ArrayList<>();
    final List<Object> results = new ArrayList<>();
    final List<Thread> threads = new ArrayList<>();

    /** The four gated operations as calls. */
    List<Supplier<Object>> gatedOperations() {
      return gatedOperations(caller);
    }

    List<Supplier<Object>> gatedOperations(PlainCaller via) {
      return List.of(
          () -> via.workPackageDetail(Rows.ALPHA_ID, "WP01"),
          () -> via.artifacts(Rows.ALPHA_ID),
          () -> via.artifact(Rows.ALPHA_ID, new ArtifactPathInput.Values(List.of("spec.md"))),
          () -> via.workPackage(Rows.ALPHA_ID, "WP01", true));
    }

    void start(Supplier<Object> call, int times) {
      for (int i = 0; i < times; i++) {
        Thread thread =
            new Thread(
                () -> {
                  blocking.arm();
                  try {
                    Object result = call.get();
                    synchronized (results) {
                      results.add(result);
                    }
                  } catch (Throwable failure) {
                    synchronized (failures) {
                      failures.add(failure);
                    }
                  }
                });
        thread.setDaemon(true);
        threads.add(thread);
        thread.start();
      }
    }

    /** Waits until every started thread is parked (four on the latch, the rest at the gate). */
    void awaitParked() {
      long deadline = System.nanoTime() + TimeUnit.SECONDS.toNanos(BOUND_SECONDS);
      while (parked() < threads.size() && System.nanoTime() < deadline) {
        Thread.onSpinWait();
      }
      assertThat(parked()).as("every caller is parked on the latch or at the gate").isEqualTo(threads.size());
    }

    private long parked() {
      return threads.stream().filter(thread -> thread.getState() == Thread.State.WAITING || thread.getState() == Thread.State.TIMED_WAITING).count();
    }

    void release() throws InterruptedException {
      blocking.release.countDown();
      for (Thread thread : threads) {
        thread.join(TimeUnit.SECONDS.toMillis(BOUND_SECONDS));
      }
      assertThat(threads).allSatisfy(thread -> assertThat(thread.isAlive()).as("every call completed").isFalse());
    }
  }

  @Test
  void sixteenCallsToEachOfTheFourGatedOperationsRunFourAtATimeAndAllComplete() throws InterruptedException {
    Rig rig = new Rig();
    rig.gatedOperations().forEach(call -> rig.start(call, PER_OPERATION));
    assertThat(rig.threads).hasSize(64);

    rig.awaitParked();
    assertThat(rig.blocking.inside.get()).as("calls inside a read while blocked").isEqualTo(4);
    assertThat(rig.gate.highWaterMark()).isEqualTo(4);
    rig.release();

    assertThat(rig.failures).isEmpty();
    assertThat(rig.results).hasSize(64).doesNotContainNull();
    assertThat(rig.blocking.maxInside.get()).isEqualTo(4);
    assertThat(rig.gate.highWaterMark()).isEqualTo(4);
  }

  @Test
  void oneHundredQueuedCallsAllCompleteAfterTheReleaseAndTheUngatedReadsAreNotBehindTheGate() throws Exception {
    Rig rig = new Rig();
    rig.start(rig.gatedOperations().get(0), 104);
    rig.awaitParked();
    assertThat(rig.blocking.inside.get()).isEqualTo(4);

    // not behind the gate: the Mission detail, the Work Package without a prompt and the three #5529 reads answer while 4 are blocked and 100 queue
    ExecutorService other = Executors.newFixedThreadPool(5);
    try {
      List<Future<Object>> ungated =
          List.of(
              other.submit(() -> rig.caller.mission(Rows.ALPHA_ID)),
              other.submit(() -> rig.caller.workPackage(Rows.ALPHA_ID, "WP01", false)),
              other.submit(() -> rig.fixture.built().query().project()),
              other.submit(() -> rig.fixture.built().query().missions(new PageRequest(null, null))),
              other.submit(() -> rig.fixture.built().query().changesSince(new org.speckitty.missionstatus.application.query.port.in.dto.StreamScope.OneMission(new org.speckitty.missionstatus.domain.model.MissionId(Rows.ALPHA_ID)), Optional.of(StreamCursor.start()))));
      for (Future<Object> future : ungated) {
        assertThat(future.get(BOUND_SECONDS, TimeUnit.SECONDS)).isNotNull();
      }
    } finally {
      other.shutdownNow();
    }
    assertThat(rig.gate.highWaterMark()).isEqualTo(4);
    rig.release();

    assertThat(rig.failures).as("a queued call is never answered with a status or an error").isEmpty();
    assertThat(rig.results).hasSize(104).doesNotContainNull();
    assertThat(rig.blocking.maxInside.get()).isEqualTo(4);
  }

  /** The planted bypass: an artifact port that gives every call a gate of its own, so no call ever waits for another. */
  private static ArtifactQueryServiceFactory bypass(DetailFixture fixture, TextSource text) {
    return () ->
        new ArtifactQueryService(
            fixture.readModel(), text, new AdmissionGate(), fixture.built().handles().recorder(), new org.speckitty.missionstatus.domain.redaction.TextScreen(org.speckitty.missionstatus.testsupport.LeakPatternsFile.load()));
  }

  @FunctionalInterface
  private interface ArtifactQueryServiceFactory {
    ArtifactQueryService create();
  }

  @Test
  void controlAnImplementationThatSkipsTheGateLetsMoreThanFourCallsIntoTheRead() throws InterruptedException {
    Rig rig = new Rig();
    ArtifactQueryServiceFactory skipping = bypass(rig.fixture, rig.blocking);
    rig.start(() -> skipping.create().list(new org.speckitty.missionstatus.domain.model.MissionId(Rows.ALPHA_ID)), PER_OPERATION);

    long deadline = System.nanoTime() + TimeUnit.SECONDS.toNanos(BOUND_SECONDS);
    while (rig.blocking.inside.get() < PER_OPERATION && System.nanoTime() < deadline) {
      Thread.onSpinWait();
    }
    int mostInside = rig.blocking.inside.get();
    rig.release();

    assertThat(rig.failures).isEmpty();
    assertThat(mostInside).as("the assertion of the first test is red for this implementation").isGreaterThan(AdmissionGate.PERMITS);
    assertThat(rig.gate.highWaterMark()).as("the shared gate never saw these calls").isZero();
  }

  // ---- the NFR-002 high-water of the Work Package file (WP11 review: a cap of 4 MiB left every test green) ------------------------------

  /** The cap of a Work Package file read: 1 MiB, the NFR-002 high-water of {@code getWorkPackage} with the prompt and of the index every route builds. */
  static final int WORK_PACKAGE_FILE_CAP = 1_048_576;

  /** What differs between a cap and the pinned literal: empty means it is the NFR-002 figure. */
  static List<String> capProblems(int cap) {
    return cap == WORK_PACKAGE_FILE_CAP ? List.of() : List.of("the Work Package file cap is " + cap + " bytes, the NFR-002 high-water is 1048576");
  }

  private static int declaredCap() throws ReflectiveOperationException {
    java.lang.reflect.Field field = org.speckitty.missionstatus.application.query.index.WorkPackageIndex.class.getDeclaredField("FILE_CAP_BYTES");
    field.setAccessible(true);
    return field.getInt(null);
  }

  @Test
  void theWorkPackageFileCapIsTheLiteralOneMebibyteAndFourMebibytesWouldBeRed() throws ReflectiveOperationException {
    assertThat(capProblems(declaredCap())).as("WorkPackageIndex.FILE_CAP_BYTES").isEmpty();
    assertThat(declaredCap()).isEqualTo(1048576);
    assertThat(capProblems(4 * 1_048_576)).as("control: a cap of 4 MiB turns the pin red").hasSize(1);
  }

  @Test
  void aWorkPackageFileOfTwoMebibytesIsReadOnlyToTheCapPlusOneByte() throws Exception {
    org.speckitty.missionstatus.testsupport.DetailFixture fixture =
        DetailRoute.fixture(root -> DetailRoute.write(root, "tasks/WP01-one.md", DetailRoute.wpFile("WP01", "One") + "x".repeat(2 * 1_048_576)));
    java.util.concurrent.atomic.AtomicLong largest = new java.util.concurrent.atomic.AtomicLong();
    TextSource measuring =
        new TextSource() {
          @Override
          public DirListing list(FileRef dir, int nameLimit, ReadScope scope) {
            return fixture.textSource().list(dir, nameLimit, scope);
          }

          @Override
          public EntryStat stat(FileRef path, ReadScope scope) {
            return fixture.textSource().stat(path, scope);
          }

          @Override
          public BytesRead readBytes(FileRef file, int cap, ReadScope scope) {
            BytesRead read = fixture.textSource().readBytes(file, cap, scope);
            largest.accumulateAndGet(read instanceof BytesRead.Bytes bytes ? bytes.content().length : read instanceof BytesRead.OverCap ? cap + 1L : 0, Math::max);
            return read;
          }

          @Override
          public TextRead readText(FileRef file, int cap, ReadScope scope) {
            return fixture.textSource().readText(file, cap, scope);
          }
        };
    DetailServices services = DetailServices.over(fixture, measuring, new AdmissionGate());

    org.assertj.core.api.Assertions.catchThrowable(() -> services.workPackage().workPackage(new org.speckitty.missionstatus.domain.model.MissionId(Rows.ALPHA_ID), new org.speckitty.missionstatus.domain.model.WpId("WP01"), false));

    assertThat(largest.get()).as("the index read the file").isPositive();
    assertThat(largest.get()).as("an over-cap file is read to cap + 1 and no further: with a 4 MiB cap this is 2 MiB").isLessThanOrEqualTo(WORK_PACKAGE_FILE_CAP + 1L);
  }
}
