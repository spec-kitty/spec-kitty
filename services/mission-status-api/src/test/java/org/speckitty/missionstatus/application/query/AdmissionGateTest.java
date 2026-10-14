package org.speckitty.missionstatus.application.query;

import static org.assertj.core.api.Assertions.assertThat;
import static org.assertj.core.api.Assertions.assertThatThrownBy;

import java.lang.reflect.Field;
import java.lang.reflect.Method;
import java.lang.reflect.Modifier;
import java.util.ArrayList;
import java.util.List;
import java.util.concurrent.CountDownLatch;
import java.util.concurrent.Semaphore;
import java.util.concurrent.TimeUnit;
import java.util.concurrent.atomic.AtomicBoolean;
import java.util.function.Supplier;
import org.junit.jupiter.api.Test;

/**
 * The unit contract of the admission gate (FR-022): four permits, fair, released in {@code finally}, never refuses. Every wait is bounded
 * and every ordering is made with latches and thread states, never with sleeps, so a failure is red and not a hang.
 */
class AdmissionGateTest {

  private static final long BOUND_SECONDS = 5;

  /** A caller thread that runs the gate with the given work and records the outcome. */
  private static Thread caller(AdmissionGate gate, Supplier<Object> work, List<Throwable> failures) {
    Thread thread =
        new Thread(
            () -> {
              try {
                gate.run(work);
              } catch (Throwable failure) {
                synchronized (failures) {
                  failures.add(failure);
                }
              }
            });
    thread.setDaemon(true);
    return thread;
  }

  private static void awaitWaiting(Thread thread) throws InterruptedException {
    long deadline = System.nanoTime() + TimeUnit.SECONDS.toNanos(BOUND_SECONDS);
    while (thread.getState() != Thread.State.WAITING && System.nanoTime() < deadline) {
      Thread.onSpinWait();
    }
    assertThat(thread.getState()).as("the caller is parked at the gate").isEqualTo(Thread.State.WAITING);
  }

  @Test
  void theGateAndItsRunAreTheFrozenSeamForGovernanceRoutes() throws Exception {
    // Operator ruling E-3/E-13 (2026-10-13): #5533's governance routes reuse this bean; it must stay public, with a public run(Supplier).
    assertThat(Modifier.isPublic(AdmissionGate.class.getModifiers())).isTrue();
    assertThat(Modifier.isFinal(AdmissionGate.class.getModifiers())).isTrue();
    Method run = AdmissionGate.class.getMethod("run", Supplier.class);
    assertThat(Modifier.isPublic(run.getModifiers())).isTrue();
    assertThat(run.getGenericReturnType().getTypeName()).isEqualTo("T");
    assertThat(AdmissionGate.class.getConstructor()).isNotNull();
  }

  @Test
  void itHoldsExactlyFourPermitsAndTheSemaphoreIsFair() throws Exception {
    AdmissionGate gate = new AdmissionGate();
    Field field = semaphoreField();
    Semaphore semaphore = (Semaphore) field.get(gate);

    assertThat(semaphore.availablePermits()).isEqualTo(4);
    assertThat(semaphore.isFair()).as("a fair semaphore").isTrue();
  }

  private static Field semaphoreField() throws Exception {
    Field found = null;
    for (Field field : AdmissionGate.class.getDeclaredFields()) {
      if (field.getType() == Semaphore.class) {
        assertThat(found).as("exactly one semaphore").isNull();
        field.setAccessible(true);
        found = field;
      }
    }
    assertThat(found).isNotNull();
    return found;
  }

  @Test
  void theFifthCallerBlocksUntilAPermitIsReleased() throws Exception {
    AdmissionGate gate = new AdmissionGate();
    CountDownLatch release = new CountDownLatch(1);
    CountDownLatch holding = new CountDownLatch(4);
    List<Throwable> failures = new ArrayList<>();
    List<Thread> holders = new ArrayList<>();
    for (int i = 0; i < 4; i++) {
      Thread holder =
          caller(
              gate,
              () -> {
                holding.countDown();
                await(release);
                return "held";
              },
              failures);
      holders.add(holder);
      holder.start();
    }
    assertThat(holding.await(BOUND_SECONDS, TimeUnit.SECONDS)).isTrue();
    AtomicBoolean fifthRan = new AtomicBoolean();
    Thread fifth = caller(gate, () -> fifthRan.getAndSet(true), failures);
    fifth.start();
    awaitWaiting(fifth);

    assertThat(fifthRan).as("the fifth caller has not run").isFalse();

    release.countDown();
    fifth.join(TimeUnit.SECONDS.toMillis(BOUND_SECONDS));
    for (Thread holder : holders) {
      holder.join(TimeUnit.SECONDS.toMillis(BOUND_SECONDS));
    }
    assertThat(fifthRan).isTrue();
    assertThat(failures).isEmpty();
  }

  private static void await(CountDownLatch latch) {
    try {
      assertThat(latch.await(BOUND_SECONDS, TimeUnit.SECONDS)).isTrue();
    } catch (InterruptedException interrupted) {
      Thread.currentThread().interrupt();
    }
  }

  @Test
  void waitersAreServedInArrivalOrderAsPermitsAreReleasedOneByOne() throws Exception {
    AdmissionGate gate = new AdmissionGate();
    CountDownLatch[] releaseHolder = new CountDownLatch[4];
    CountDownLatch holding = new CountDownLatch(4);
    List<Throwable> failures = new ArrayList<>();
    List<Thread> all = new ArrayList<>();
    for (int i = 0; i < 4; i++) {
      CountDownLatch mine = new CountDownLatch(1);
      releaseHolder[i] = mine;
      Thread holder =
          caller(
              gate,
              () -> {
                holding.countDown();
                await(mine);
                return null;
              },
              failures);
      all.add(holder);
      holder.start();
    }
    assertThat(holding.await(BOUND_SECONDS, TimeUnit.SECONDS)).isTrue();
    List<Integer> served = new ArrayList<>();
    CountDownLatch[] admitted = new CountDownLatch[4];
    CountDownLatch finish = new CountDownLatch(1);
    for (int i = 0; i < 4; i++) {
      int arrival = i;
      admitted[i] = new CountDownLatch(1);
      Thread waiter =
          caller(
              gate,
              () -> {
                synchronized (served) {
                  served.add(arrival);
                }
                admitted[arrival].countDown();
                await(finish);
                return null;
              },
              failures);
      all.add(waiter);
      waiter.start();
      awaitWaiting(waiter);
    }

    for (int i = 0; i < 4; i++) {
      releaseHolder[i].countDown();
      assertThat(admitted[i].await(BOUND_SECONDS, TimeUnit.SECONDS)).as("waiter %d admitted next", i).isTrue();
    }
    finish.countDown();
    for (Thread thread : all) {
      thread.join(TimeUnit.SECONDS.toMillis(BOUND_SECONDS));
    }

    assertThat(failures).isEmpty();
    assertThat(served).containsExactly(0, 1, 2, 3);
  }

  @Test
  void aSupplierThatThrowsStillReleasesItsPermit() {
    AdmissionGate gate = new AdmissionGate();
    for (int i = 0; i < 8; i++) {
      assertThatThrownBy(() -> gate.run(() -> { throw new IllegalStateException("boom"); })).isInstanceOf(IllegalStateException.class);
    }

    assertThat(gate.run(() -> "next")).isEqualTo("next");
  }

  @Test
  void itNeverRefusesOneHundredQueuedCallersAllComplete() throws Exception {
    AdmissionGate gate = new AdmissionGate();
    CountDownLatch release = new CountDownLatch(1);
    CountDownLatch holding = new CountDownLatch(4);
    List<Throwable> failures = new ArrayList<>();
    List<Thread> all = new ArrayList<>();
    for (int i = 0; i < 4; i++) {
      Thread holder =
          caller(
              gate,
              () -> {
                holding.countDown();
                await(release);
                return null;
              },
              failures);
      all.add(holder);
      holder.start();
    }
    assertThat(holding.await(BOUND_SECONDS, TimeUnit.SECONDS)).isTrue();
    java.util.concurrent.atomic.AtomicInteger completed = new java.util.concurrent.atomic.AtomicInteger();
    for (int i = 0; i < 100; i++) {
      Thread waiter = caller(gate, () -> completed.incrementAndGet(), failures);
      all.add(waiter);
      waiter.start();
    }

    release.countDown();
    for (Thread thread : all) {
      thread.join(TimeUnit.SECONDS.toMillis(BOUND_SECONDS * 2));
    }

    assertThat(completed.get()).isEqualTo(100);
    assertThat(failures).as("nobody was refused or timed out").isEmpty();
  }

  @Test
  void theHighWaterMarkIsFourUnderSixteenConcurrentCallersAndNeverMore() throws Exception {
    AdmissionGate gate = new AdmissionGate();
    CountDownLatch start = new CountDownLatch(1);
    CountDownLatch fourHeld = new CountDownLatch(4);
    CountDownLatch release = new CountDownLatch(1);
    List<Throwable> failures = new ArrayList<>();
    List<Thread> all = new ArrayList<>();
    for (int i = 0; i < 16; i++) {
      Thread thread =
          caller(
              gate,
              () -> {
                fourHeld.countDown();
                await(release);
                return null;
              },
              failures);
      all.add(thread);
    }
    for (Thread thread : all) {
      thread.start();
    }
    start.countDown();
    assertThat(fourHeld.await(BOUND_SECONDS, TimeUnit.SECONDS)).isTrue();
    long deadline = System.nanoTime() + TimeUnit.SECONDS.toNanos(BOUND_SECONDS);
    while (System.nanoTime() < deadline && all.stream().filter(t -> t.getState() == Thread.State.WAITING).count() < 12) {
      Thread.onSpinWait();
    }
    release.countDown();
    for (Thread thread : all) {
      thread.join(TimeUnit.SECONDS.toMillis(BOUND_SECONDS));
    }

    assertThat(gate.highWaterMark()).isEqualTo(4);
    assertThat(failures).isEmpty();
  }

  @Test
  void aFreshGateHasHighWaterMarkZero() {
    assertThat(new AdmissionGate().highWaterMark()).isZero();
  }

  @Test
  void anInterruptedWaiterStillGetsItsPermitAndKeepsItsInterruptFlag() throws Exception {
    AdmissionGate gate = new AdmissionGate();
    CountDownLatch release = new CountDownLatch(1);
    CountDownLatch holding = new CountDownLatch(4);
    List<Throwable> failures = new ArrayList<>();
    List<Thread> holders = new ArrayList<>();
    for (int i = 0; i < 4; i++) {
      Thread holder =
          caller(
              gate,
              () -> {
                holding.countDown();
                await(release);
                return null;
              },
              failures);
      holders.add(holder);
      holder.start();
    }
    assertThat(holding.await(BOUND_SECONDS, TimeUnit.SECONDS)).isTrue();
    AtomicBoolean ran = new AtomicBoolean();
    AtomicBoolean flagKept = new AtomicBoolean();
    Thread waiter =
        caller(
            gate,
            () -> {
              ran.set(true);
              flagKept.set(Thread.currentThread().isInterrupted());
              return null;
            },
            failures);
    waiter.start();
    awaitWaiting(waiter);

    waiter.interrupt();
    release.countDown();
    waiter.join(TimeUnit.SECONDS.toMillis(BOUND_SECONDS));
    for (Thread holder : holders) {
      holder.join(TimeUnit.SECONDS.toMillis(BOUND_SECONDS));
    }

    assertThat(ran).as("the interrupted waiter ran").isTrue();
    assertThat(flagKept).as("the interrupt flag survived the wait").isTrue();
    assertThat(failures).isEmpty();
  }

  /**
   * Fairness as behaviour, not as a flag: a caller that arrives after a parked waiter must not overtake it, even when it sees the freed
   * permit before the waiter wakes. The late caller watches the gate's own permit count and enters the moment a permit is free; a fair
   * gate queues it behind the waiter every time, a non-fair semaphore lets it barge. Each round is ordered by latches and thread states.
   */
  @Test
  void aLateCallerNeverOvertakesAParkedWaiterEvenWhenItSeesTheFreedPermit() throws Exception {
    int overtaken = 0;
    int rounds = 300;
    for (int round = 0; round < rounds; round++) {
      AdmissionGate gate = new AdmissionGate();
      Semaphore semaphore = (Semaphore) semaphoreField().get(gate);
      CountDownLatch holding = new CountDownLatch(4);
      CountDownLatch[] releaseHolder = new CountDownLatch[4];
      List<Throwable> failures = new ArrayList<>();
      List<Thread> all = new ArrayList<>();
      for (int i = 0; i < 4; i++) {
        CountDownLatch mine = new CountDownLatch(1);
        releaseHolder[i] = mine;
        Thread holder =
            caller(
                gate,
                () -> {
                  holding.countDown();
                  await(mine);
                  return null;
                },
                failures);
        all.add(holder);
        holder.start();
      }
      assertThat(holding.await(BOUND_SECONDS, TimeUnit.SECONDS)).isTrue();
      java.util.concurrent.atomic.AtomicInteger order = new java.util.concurrent.atomic.AtomicInteger();
      int[] waiterSeq = new int[1];
      int[] lateSeq = new int[1];
      Thread waiter = caller(gate, () -> waiterSeq[0] = order.incrementAndGet(), failures);
      all.add(waiter);
      waiter.start();
      awaitWaiting(waiter);
      java.util.concurrent.atomic.AtomicBoolean armed = new java.util.concurrent.atomic.AtomicBoolean();
      Thread late =
          new Thread(
              () -> {
                armed.set(true);
                long deadline = System.nanoTime() + TimeUnit.SECONDS.toNanos(BOUND_SECONDS);
                while (semaphore.availablePermits() == 0 && System.nanoTime() < deadline) {
                  Thread.onSpinWait();
                }
                gate.run(() -> lateSeq[0] = order.incrementAndGet());
              });
      late.setDaemon(true);
      all.add(late);
      late.start();
      long armDeadline = System.nanoTime() + TimeUnit.SECONDS.toNanos(BOUND_SECONDS);
      while (!armed.get() && System.nanoTime() < armDeadline) {
        Thread.onSpinWait();
      }
      releaseHolder[0].countDown();
      waiter.join(TimeUnit.SECONDS.toMillis(BOUND_SECONDS));
      late.join(TimeUnit.SECONDS.toMillis(BOUND_SECONDS));
      for (int i = 1; i < 4; i++) {
        releaseHolder[i].countDown();
      }
      for (Thread thread : all) {
        thread.join(TimeUnit.SECONDS.toMillis(BOUND_SECONDS));
      }
      assertThat(failures).isEmpty();
      if (waiterSeq[0] > lateSeq[0]) {
        overtaken++;
      }
    }

    assertThat(overtaken).as("rounds in which a later caller was served before the parked waiter").isZero();
  }
}
