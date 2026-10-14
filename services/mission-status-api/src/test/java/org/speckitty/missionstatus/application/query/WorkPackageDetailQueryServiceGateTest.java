package org.speckitty.missionstatus.application.query;

import static org.assertj.core.api.Assertions.assertThat;
import static org.speckitty.missionstatus.application.query.detail.DetailRoute.ID;

import java.util.ArrayList;
import java.util.List;
import java.util.Optional;
import java.util.concurrent.CountDownLatch;
import java.util.concurrent.TimeUnit;
import java.util.concurrent.atomic.AtomicInteger;
import java.util.function.Supplier;
import org.junit.jupiter.api.Test;
import org.speckitty.missionstatus.adapter.out.filesystem.YamlFrontmatterDecoder;
import org.speckitty.missionstatus.application.query.detail.DetailRoute;
import org.speckitty.missionstatus.application.query.index.WorkPackageIndex;
import org.speckitty.missionstatus.application.query.port.out.TextSource;
import org.speckitty.missionstatus.application.query.port.out.dto.BytesRead;
import org.speckitty.missionstatus.application.query.port.out.dto.DirListing;
import org.speckitty.missionstatus.application.query.port.out.dto.EntryStat;
import org.speckitty.missionstatus.application.query.port.out.dto.FileRef;
import org.speckitty.missionstatus.application.query.port.out.dto.MissionRef;
import org.speckitty.missionstatus.application.query.port.out.dto.ReadScope;
import org.speckitty.missionstatus.application.query.port.out.dto.TextRead;
import org.speckitty.missionstatus.domain.model.MissionId;
import org.speckitty.missionstatus.domain.model.WpId;
import org.speckitty.missionstatus.testsupport.DetailFixture;

/**
 * AC-22.3 for the Work Package detail: 16 concurrent calls whose reads block on a latch never run more than four at once, the gate's high-water
 * mark is four, and releasing the latch completes every call with a normal result. The control runs the same first read without the gate and
 * sees all sixteen at once, so the assertion can go red (a service that skipped the gate would make the mark exceed four).
 */
class WorkPackageDetailQueryServiceGateTest {

  private static final int CALLS = 16;
  private static final long BOUND_SECONDS = 20;

  /** Blocks the first listing of {@code tasks/} of each call on a latch and counts how many calls are inside at once. */
  private static final class Blocking implements TextSource {
    private final TextSource delegate;
    private final CountDownLatch release = new CountDownLatch(1);
    private final AtomicInteger inside = new AtomicInteger();
    private final AtomicInteger maxInside = new AtomicInteger();

    Blocking(TextSource delegate) {
      this.delegate = delegate;
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
      if (dir.path().toString().equals("tasks")) {
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

  private static void awaitInside(Blocking blocking, int expected) {
    long deadline = System.nanoTime() + TimeUnit.SECONDS.toNanos(BOUND_SECONDS);
    while (blocking.inside.get() < expected && System.nanoTime() < deadline) {
      Thread.onSpinWait();
    }
    assertThat(blocking.inside.get()).as("calls inside the blocked read").isEqualTo(expected);
  }

  private static boolean isParked(Thread thread) {
    return thread.getState() == Thread.State.WAITING || thread.getState() == Thread.State.TIMED_WAITING;
  }

  private static void awaitParked(List<Thread> threads) {
    long deadline = System.nanoTime() + TimeUnit.SECONDS.toNanos(BOUND_SECONDS);
    while (threads.stream().filter(WorkPackageDetailQueryServiceGateTest::isParked).count() < CALLS && System.nanoTime() < deadline) {
      Thread.onSpinWait();
    }
    assertThat(threads.stream().filter(WorkPackageDetailQueryServiceGateTest::isParked).count()).as("four callers wait on the latch, the rest at the gate").isEqualTo(CALLS);
  }

  @Test
  void sixteenConcurrentCallsRunAtMostFourAtOnceAndAllCompleteWhenTheLatchIsReleased() {
    DetailFixture fixture = DetailRoute.fixture(root -> {});
    AdmissionGate gate = new AdmissionGate();
    Blocking blocking = new Blocking(fixture.textSource());
    WorkPackageDetailQueryService service = DetailRoute.serviceOver(fixture, blocking, gate);
    List<Object> results = new ArrayList<>();
    List<Throwable> failures = new ArrayList<>();

    List<Thread> threads = start(() -> service.workPackageDetail(new MissionId(ID), new WpId("WP01")), results, failures);
    awaitInside(blocking, AdmissionGate.PERMITS);
    awaitParked(threads);

    assertThat(blocking.inside.get()).isEqualTo(4);
    assertThat(gate.highWaterMark()).isEqualTo(4);
    blocking.release.countDown();
    for (Thread thread : threads) {
      try {
        thread.join(TimeUnit.SECONDS.toMillis(BOUND_SECONDS));
      } catch (InterruptedException interrupted) {
        Thread.currentThread().interrupt();
        throw new IllegalStateException(interrupted);
      }
    }
    assertThat(failures).isEmpty();
    assertThat(results).hasSize(CALLS).doesNotContainNull();
    assertThat(blocking.maxInside.get()).isEqualTo(4);
    assertThat(gate.highWaterMark()).isEqualTo(4);
  }

  @Test
  void theControlWithoutTheGateSeesAllSixteenAtOnce() {
    DetailFixture fixture = DetailRoute.fixture(root -> {});
    Blocking blocking = new Blocking(fixture.textSource());
    WorkPackageIndex index = new WorkPackageIndex(blocking, new YamlFrontmatterDecoder());
    Supplier<Object> ungated = () -> index.build(new MissionRef("alpha"), "mid8", Optional.empty(), diagnostic -> {});
    List<Object> results = new ArrayList<>();
    List<Throwable> failures = new ArrayList<>();

    List<Thread> threads = start(ungated, results, failures);
    awaitInside(blocking, CALLS);
    blocking.release.countDown();
    for (Thread thread : threads) {
      try {
        thread.join(TimeUnit.SECONDS.toMillis(BOUND_SECONDS));
      } catch (InterruptedException interrupted) {
        Thread.currentThread().interrupt();
        throw new IllegalStateException(interrupted);
      }
    }

    assertThat(failures).isEmpty();
    assertThat(blocking.maxInside.get()).as("without the gate the mark is above four").isGreaterThan(AdmissionGate.PERMITS);
  }

  @Test
  void aFailingCallFreesItsPlace() {
    DetailFixture fixture = DetailRoute.fixture(root -> {});
    AdmissionGate gate = new AdmissionGate();
    WorkPackageDetailQueryService service = DetailRoute.serviceOver(fixture, fixture.textSource(), gate);

    for (int i = 0; i < 2 * AdmissionGate.PERMITS; i++) {
      org.assertj.core.api.Assertions.assertThatThrownBy(() -> service.workPackageDetail(new MissionId(ID), new WpId("WP09"))).isInstanceOf(RuntimeException.class);
    }

    assertThat(service.workPackageDetail(new MissionId(ID), new WpId("WP01"))).isNotNull();
    assertThat(gate.highWaterMark()).isEqualTo(1);
  }
}
