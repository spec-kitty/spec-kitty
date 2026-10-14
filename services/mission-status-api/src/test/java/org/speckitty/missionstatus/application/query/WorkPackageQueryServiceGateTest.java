package org.speckitty.missionstatus.application.query;

import static org.assertj.core.api.Assertions.assertThat;

import java.util.ArrayList;
import java.util.List;
import java.util.concurrent.CountDownLatch;
import java.util.concurrent.TimeUnit;
import java.util.concurrent.atomic.AtomicInteger;
import org.junit.jupiter.api.Test;
import org.speckitty.missionstatus.adapter.in.http.detail.WorkPackageControllerRowsTest;
import org.speckitty.missionstatus.adapter.out.filesystem.Allowlist.OpenMode;
import org.speckitty.missionstatus.adapter.out.filesystem.Allowlist.PathClass;
import org.speckitty.missionstatus.domain.model.MissionId;
import org.speckitty.missionstatus.domain.model.WpId;
import org.speckitty.missionstatus.testsupport.DetailFixture;
import org.speckitty.missionstatus.testsupport.Rows;

/**
 * AC-22.3 for {@code getWorkPackage} (S-13, E-1, operator ruling D-148): the admission gate is held for {@code includePrompt=true} only. Sixteen
 * concurrent calls whose Work Package file reads block on a latch: with the prompt at most four are inside the read at once and the gate's
 * high-water mark is exactly four; without it the gate is not touched (mark 0) and all sixteen are inside the read together. A service that
 * skipped the gate for the prompt variant would see sixteen in the read and fail the first assertion; one that gated the prompt-less call
 * would see four in the read and a mark above zero. Every wait is bounded, so a failure is red and not a hang.
 */
class WorkPackageQueryServiceGateTest {

  private static final int CALLS = 16;
  private static final long BOUND_SECONDS = 20;

  /** The result of one run of {@code CALLS} concurrent calls. */
  private record Run(int mostInTheRead, int highWaterMark, int completed, List<Throwable> failures) {}

  private static Run run(boolean includePrompt) throws InterruptedException {
    DetailFixture fixture = WorkPackageControllerRowsTest.build(root -> {});
    AdmissionGate gate = new AdmissionGate();
    WorkPackageQueryService service = WorkPackageControllerRowsTest.serviceOver(fixture, gate);
    // warm the shared head cache so that the calls differ only by what they read for the Work Package
    service.workPackage(new MissionId(Rows.ALPHA_ID), new WpId("WP01"), false);

    AtomicInteger inTheRead = new AtomicInteger();
    AtomicInteger most = new AtomicInteger();
    CountDownLatch release = new CountDownLatch(1);
    CountDownLatch enough = new CountDownLatch(includePrompt ? 4 : CALLS);
    fixture.recorder().failWhen(
        access -> {
          if (access.pathClass() == PathClass.WP_FILE && access.mode() == OpenMode.READ) {
            most.accumulateAndGet(inTheRead.incrementAndGet(), Math::max);
            enough.countDown();
            try {
              release.await(BOUND_SECONDS, TimeUnit.SECONDS);
            } catch (InterruptedException interrupted) {
              Thread.currentThread().interrupt();
            }
            inTheRead.decrementAndGet();
          }
          return false;
        },
        () -> new java.io.IOException("never raised"));

    List<Throwable> failures = new ArrayList<>();
    AtomicInteger completed = new AtomicInteger();
    List<Thread> callers = new ArrayList<>();
    for (int i = 0; i < CALLS; i++) {
      Thread caller =
          new Thread(
              () -> {
                try {
                  service.workPackage(new MissionId(Rows.ALPHA_ID), new WpId("WP01"), includePrompt);
                  completed.incrementAndGet();
                } catch (Throwable failure) {
                  synchronized (failures) {
                    failures.add(failure);
                  }
                }
              });
      caller.setDaemon(true);
      callers.add(caller);
      caller.start();
    }
    assertThat(enough.await(BOUND_SECONDS, TimeUnit.SECONDS)).as("the calls reached the blocked read").isTrue();
    int mostWhileBlocked = most.get();
    int markWhileBlocked = gate.highWaterMark();
    release.countDown();
    for (Thread caller : callers) {
      caller.join(TimeUnit.SECONDS.toMillis(BOUND_SECONDS));
    }
    assertThat(callers).allSatisfy(caller -> assertThat(caller.isAlive()).as("every call completed").isFalse());
    return new Run(mostWhileBlocked, Math.max(markWhileBlocked, gate.highWaterMark()), completed.get(), failures);
  }

  @Test
  void withThePromptAtMostFourCallsAreInsideTheReadAndTheGateMarkIsFour() throws InterruptedException {
    Run run = run(true);

    assertThat(run.failures()).isEmpty();
    assertThat(run.completed()).isEqualTo(CALLS);
    assertThat(run.mostInTheRead()).as("the gate admits four at a time").isEqualTo(4);
    assertThat(run.highWaterMark()).isEqualTo(4);
  }

  @Test
  void withoutThePromptTheCallIsNotGated() throws InterruptedException {
    Run run = run(false);

    assertThat(run.failures()).isEmpty();
    assertThat(run.completed()).isEqualTo(CALLS);
    assertThat(run.highWaterMark()).as("the gate is not entered").isZero();
    assertThat(run.mostInTheRead()).as("all sixteen are inside the read together").isEqualTo(CALLS);
  }
}
