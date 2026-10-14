package org.speckitty.missionstatus.application.query;

import static org.assertj.core.api.Assertions.assertThat;

import java.util.ArrayList;
import java.util.List;
import java.util.concurrent.CountDownLatch;
import java.util.concurrent.TimeUnit;
import java.util.concurrent.atomic.AtomicInteger;
import java.util.function.Supplier;
import org.junit.jupiter.api.Test;
import org.speckitty.missionstatus.application.query.ArtifactQueryServiceTest.Trees;
import org.speckitty.missionstatus.application.query.artifact.ArtifactReader;
import org.speckitty.missionstatus.application.query.port.out.TextSource;
import org.speckitty.missionstatus.application.query.port.out.dto.BytesRead;
import org.speckitty.missionstatus.application.query.port.out.dto.DirListing;
import org.speckitty.missionstatus.application.query.port.out.dto.EntryStat;
import org.speckitty.missionstatus.application.query.port.out.dto.FileRef;
import org.speckitty.missionstatus.application.query.port.out.dto.MissionRef;
import org.speckitty.missionstatus.application.query.port.out.dto.ReadScope;
import org.speckitty.missionstatus.application.query.port.out.dto.TextRead;
import org.speckitty.missionstatus.domain.redaction.TextScreen;
import org.speckitty.missionstatus.testsupport.DetailFixture;
import org.speckitty.missionstatus.testsupport.LeakPatternsFile;

/**
 * AC-22.3 for the two artifact operations: 16 concurrent calls whose reads block on a latch never run more than four at once, the gate's
 * high-water mark is four, and releasing the latch completes every call with a normal result. The control runs the same reads without
 * the gate and sees all sixteen at once, so the assertion can go red.
 */
class ArtifactQueryServiceGateTest {

  private static final int CALLS = 16;
  private static final long BOUND_SECONDS = 20;

  /** Blocks the first read of each call on a latch and counts how many calls are inside at once. */
  private static final class Blocking implements TextSource {
    private final TextSource delegate;
    private final CountDownLatch release = new CountDownLatch(1);
    private final AtomicInteger inside = new AtomicInteger();
    private final AtomicInteger maxInside = new AtomicInteger();
    private final boolean onList;

    Blocking(TextSource delegate, boolean onList) {
      this.delegate = delegate;
      this.onList = onList;
    }

    private void block() {
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
      if (onList && dir.path().isRoot()) {
        block();
      }
      return delegate.list(dir, nameLimit, scope);
    }

    @Override
    public EntryStat stat(FileRef path, ReadScope scope) {
      return delegate.stat(path, scope);
    }

    @Override
    public BytesRead readBytes(FileRef file, int cap, ReadScope scope) {
      return delegate.readBytes(file, cap, scope);
    }

    @Override
    public TextRead readText(FileRef file, int cap, ReadScope scope) {
      if (!onList && file.path().toString().equals("spec.md")) {
        block();
      }
      return delegate.readText(file, cap, scope);
    }
  }

  private static List<Thread> start(Supplier<Object> call, List<Object> results, List<Throwable> failures) {
    List<Thread> threads = new ArrayList<>();
    for (int i = 0; i < CALLS; i++) {
      Thread thread =
          new Thread(
              () -> {
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
    return threads;
  }

  private static void awaitInside(Blocking blocking, int expected) throws InterruptedException {
    long deadline = System.nanoTime() + TimeUnit.SECONDS.toNanos(BOUND_SECONDS);
    while (blocking.inside.get() < expected && System.nanoTime() < deadline) {
      Thread.onSpinWait();
    }
    assertThat(blocking.inside.get()).as("calls inside the blocked read").isEqualTo(expected);
  }

  private static boolean isParked(Thread thread) {
    return thread.getState() == Thread.State.WAITING || thread.getState() == Thread.State.TIMED_WAITING;
  }

  private static void awaitWaiters(List<Thread> threads, int waiting) {
    long deadline = System.nanoTime() + TimeUnit.SECONDS.toNanos(BOUND_SECONDS);
    while (threads.stream().filter(thread -> isParked(thread)).count() < waiting && System.nanoTime() < deadline) {
      Thread.onSpinWait();
    }
    assertThat(threads.stream().filter(ArtifactQueryServiceGateTest::isParked).count()).as("four callers wait on the latch, the rest at the gate").isGreaterThanOrEqualTo(waiting);
  }

  private void gated(boolean listing) throws Exception {
    DetailFixture fixture = Trees.fixture("artifacts-populated", "artifacts-populated");
    AdmissionGate gate = new AdmissionGate();
    Blocking blocking = new Blocking(fixture.textSource(), listing);
    ArtifactQueryService service = Trees.service(fixture, gate, blocking);
    Supplier<Object> call = listing ? () -> service.list(Trees.id()) : () -> service.content(Trees.id(), Trees.path("spec.md"));
    List<Object> results = new ArrayList<>();
    List<Throwable> failures = new ArrayList<>();

    List<Thread> threads = start(call, results, failures);
    awaitInside(blocking, AdmissionGate.PERMITS);
    awaitWaiters(threads, CALLS);

    assertThat(blocking.inside.get()).isEqualTo(4);
    assertThat(gate.highWaterMark()).isEqualTo(4);
    blocking.release.countDown();
    for (Thread thread : threads) {
      thread.join(TimeUnit.SECONDS.toMillis(BOUND_SECONDS));
    }
    assertThat(failures).isEmpty();
    assertThat(results).hasSize(CALLS).doesNotContainNull();
    assertThat(blocking.maxInside.get()).isEqualTo(4);
    assertThat(gate.highWaterMark()).isEqualTo(4);
  }

  @Test
  void listArtifactsRunsAtMostFourAtOnce() throws Exception {
    gated(true);
  }

  @Test
  void getArtifactContentRunsAtMostFourAtOnce() throws Exception {
    gated(false);
  }

  @Test
  void theControlWithoutTheGateSeesAllSixteenAtOnce() throws Exception {
    DetailFixture fixture = Trees.fixture("artifacts-populated", "artifacts-populated");
    Blocking blocking = new Blocking(fixture.textSource(), false);
    ArtifactReader reader = new ArtifactReader(blocking, new TextScreen(LeakPatternsFile.load()), fixture.built().handles().recorder());
    MissionRef mission = new MissionRef("alpha-mission");
    Supplier<Object> ungated = () -> reader.read(mission, Trees.ID.substring(0, 8), "spec.md");
    List<Object> results = new ArrayList<>();
    List<Throwable> failures = new ArrayList<>();

    List<Thread> threads = start(ungated, results, failures);
    awaitInside(blocking, CALLS);
    blocking.release.countDown();
    for (Thread thread : threads) {
      thread.join(TimeUnit.SECONDS.toMillis(BOUND_SECONDS));
    }

    assertThat(failures).isEmpty();
    assertThat(blocking.maxInside.get()).as("without the gate the mark is above four").isGreaterThan(AdmissionGate.PERMITS);
  }
}
