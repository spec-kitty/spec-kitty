package org.speckitty.missionstatus.testsupport.http;

import java.time.Duration;
import java.util.List;
import java.util.Optional;
import java.util.concurrent.CopyOnWriteArrayList;
import java.util.concurrent.CountDownLatch;
import java.util.concurrent.atomic.AtomicBoolean;
import java.util.concurrent.atomic.AtomicInteger;
import org.speckitty.missionstatus.application.query.port.in.dto.ChangeBatch;
import org.speckitty.missionstatus.application.query.port.in.MissionStatusQuery;
import org.speckitty.missionstatus.application.query.port.in.dto.PageRequest;
import org.speckitty.missionstatus.application.query.port.in.dto.StreamScope;
import org.speckitty.missionstatus.application.query.port.in.dto.StreamSignal;
import org.speckitty.missionstatus.application.query.port.in.Subscription;
import org.speckitty.missionstatus.domain.readmodel.cursor.StreamCursor;
import org.speckitty.missionstatus.domain.readmodel.overview.MissionPage;
import org.speckitty.missionstatus.domain.readmodel.overview.ProjectHeader;

/**
 * The test-profile seam over the inbound port. It forwards every call to the query it wraps and records, for each handler call, whether
 * the calling thread was virtual (AC-9h), how many subscriptions are open (the disconnect and the 100-connection checks), and it can hold
 * one subscription's {@code next} behind a latch so that a slow consumer is exact instead of a race (the overflow check).
 */
public final class SpyQuery implements MissionStatusQuery {

  private final MissionStatusQuery delegate;
  private final List<Boolean> projectThreads = new CopyOnWriteArrayList<>();
  private final List<Boolean> missionsThreads = new CopyOnWriteArrayList<>();
  private final List<Boolean> subscribeThreads = new CopyOnWriteArrayList<>();
  private final List<Boolean> nextThreads = new CopyOnWriteArrayList<>();
  private final AtomicInteger opened = new AtomicInteger();
  private final AtomicInteger closed = new AtomicInteger();
  private volatile CountDownLatch hold;

  public SpyQuery(MissionStatusQuery delegate) {
    this.delegate = delegate;
  }

  /** The next subscription made is held: its {@code next} blocks until {@code release} is counted down. */
  public void holdNextSubscription(CountDownLatch release) {
    this.hold = release;
  }

  public List<Boolean> projectThreads() {
    return projectThreads;
  }

  public List<Boolean> missionsThreads() {
    return missionsThreads;
  }

  public List<Boolean> subscribeThreads() {
    return subscribeThreads;
  }

  public List<Boolean> nextThreads() {
    return nextThreads;
  }

  /** Subscriptions opened and not yet closed. */
  public int openSubscriptions() {
    return opened.get() - closed.get();
  }

  public int totalSubscriptions() {
    return opened.get();
  }

  @Override
  public ProjectHeader project() {
    projectThreads.add(Thread.currentThread().isVirtual());
    return delegate.project();
  }

  @Override
  public MissionPage missions(PageRequest request) {
    missionsThreads.add(Thread.currentThread().isVirtual());
    return delegate.missions(request);
  }

  @Override
  public ChangeBatch changesSince(StreamScope scope, Optional<StreamCursor> cursor) {
    return delegate.changesSince(scope, cursor);
  }

  @Override
  public Subscription subscribe(StreamScope scope, Optional<StreamCursor> cursor) {
    subscribeThreads.add(Thread.currentThread().isVirtual());
    Subscription real = delegate.subscribe(scope, cursor);
    opened.incrementAndGet();
    CountDownLatch gate = hold;
    hold = null;
    return new Subscription() {
      private final AtomicBoolean done = new AtomicBoolean();

      @Override
      public StreamSignal next(Duration wait) throws InterruptedException {
        nextThreads.add(Thread.currentThread().isVirtual());
        if (gate != null) {
          gate.await();
        }
        return real.next(wait);
      }

      @Override
      public void close() {
        real.close();
        if (done.compareAndSet(false, true)) {
          closed.incrementAndGet();
        }
      }
    };
  }
}
