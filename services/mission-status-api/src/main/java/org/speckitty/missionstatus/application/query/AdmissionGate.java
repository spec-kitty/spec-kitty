package org.speckitty.missionstatus.application.query;

import java.util.Objects;
import java.util.concurrent.Semaphore;
import java.util.concurrent.atomic.AtomicInteger;
import java.util.function.Supplier;

/**
 * The admission gate of the heavy read operations (FR-022): at most {@value #PERMITS} run at once and the rest wait, in arrival order. It
 * never refuses and never times out, it creates no thread, and a permit is released in {@code finally}, so a failing operation frees its
 * place.
 *
 * <p><b>A frozen seam.</b> The class and {@link #run(Supplier)} are public on purpose (operator ruling E-3/E-13, 2026-10-13): the governance
 * routes of #5533 reuse the one {@code config.DetailInfrastructureWiring#admissionGate()} bean. Narrowing either is a change to plan
 * section 7.1 and needs the operator's word.
 */
public final class AdmissionGate {

  /** How many gated operations run at once. */
  public static final int PERMITS = 4;

  private final Semaphore permits = new Semaphore(PERMITS, true);
  private final AtomicInteger held = new AtomicInteger();
  private final AtomicInteger highWater = new AtomicInteger();

  /** Runs {@code work} once a permit is free, waiting without a limit and without being interruptible. */
  public <T> T run(Supplier<T> work) {
    Objects.requireNonNull(work, "work");
    permits.acquireUninterruptibly();
    try {
      highWater.accumulateAndGet(held.incrementAndGet(), Math::max);
      try {
        return work.get();
      } finally {
        held.decrementAndGet();
      }
    } finally {
      permits.release();
    }
  }

  /** The most permits ever held at the same time. A test accessor; nothing in production reads it. */
  public int highWaterMark() {
    return highWater.get();
  }
}
