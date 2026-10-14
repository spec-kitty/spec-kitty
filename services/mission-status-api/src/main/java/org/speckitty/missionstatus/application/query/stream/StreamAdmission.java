package org.speckitty.missionstatus.application.query.stream;

import java.util.Set;
import java.util.concurrent.ConcurrentHashMap;
import java.util.concurrent.atomic.AtomicInteger;
import org.speckitty.missionstatus.application.query.port.in.Subscription;
import org.speckitty.missionstatus.application.query.port.in.exceptions.StreamCapacityReached;

/**
 * The refusing cap on open streams and the registry that ends them at shutdown. One instance serves every inbound adapter of the
 * service, so an HTTP stream and any other adapter's subscription draw from the same places. It is a different mechanism from the
 * detail operations' fair semaphore, which queues and never refuses; the two share no state.
 *
 * <p>A place is taken by {@link #admit} before a subscription costs a listing and given back exactly once: by {@link #release} when the
 * connect fails, or by {@link #finished} when the subscription is closed.
 */
public final class StreamAdmission {

  private final int capacity;
  private final AtomicInteger admitted = new AtomicInteger();
  private final Set<Subscription> live = ConcurrentHashMap.newKeySet();

  public StreamAdmission(int capacity) {
    if (capacity < 1) {
      throw new IllegalArgumentException("capacity must be at least 1");
    }
    this.capacity = capacity;
  }

  /** Takes a place or refuses; a refused call takes none. */
  public void admit() {
    if (admitted.incrementAndGet() > capacity) {
      admitted.decrementAndGet();
      throw new StreamCapacityReached();
    }
  }

  /** Gives back a place taken by {@link #admit} whose subscription never came to exist. */
  public void release() {
    admitted.decrementAndGet();
  }

  /** Records an open subscription, so {@link #endAll} can end it. */
  public void register(Subscription subscription) {
    live.add(subscription);
  }

  /** A registered subscription is over: it leaves the registry and gives back its place. */
  public void finished(Subscription subscription) {
    live.remove(subscription);
    release();
  }

  /** Ends every open subscription. Idempotent: a closed subscription is no longer registered. */
  public void endAll() {
    for (Subscription subscription : Set.copyOf(live)) {
      subscription.close();
    }
  }

  /** Places in use: admitted and not yet given back. */
  public int open() {
    return admitted.get();
  }
}
