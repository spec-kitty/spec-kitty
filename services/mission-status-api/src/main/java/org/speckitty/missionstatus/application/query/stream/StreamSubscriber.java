package org.speckitty.missionstatus.application.query.stream;

import java.time.Duration;
import java.util.ArrayDeque;
import java.util.HashMap;
import java.util.HashSet;
import java.util.Map;
import java.util.Set;
import java.util.concurrent.locks.Condition;
import java.util.concurrent.locks.ReentrantLock;
import org.speckitty.missionstatus.application.query.port.in.dto.Closure;
import org.speckitty.missionstatus.application.query.port.in.dto.StreamScope;
import org.speckitty.missionstatus.application.query.port.in.dto.StreamSignal;
import org.speckitty.missionstatus.application.query.port.in.Subscription;
import org.speckitty.missionstatus.application.query.port.out.dto.MissionRef;

/**
 * One consumer of the feed: a bounded queue of signals and, once the stream is over, a terminal {@code Closed}. A signal that does not
 * fit is never dropped: {@link #offer} says so and the feed closes the subscriber as a slow consumer. Whatever is queued is still
 * handed out before the terminal signal. The scope, the floors and the dropped set belong to the feed and are touched only under its
 * lock. A floor belongs to one subscriber and one Mission: it is the offset in that Mission's ledger up to which this subscriber already
 * has the rows (or never wants them), so two subscribers that joined at different times each get exactly the rows written after they did.
 */
public final class StreamSubscriber implements Subscription {

  private static final StreamSignal IDLE = new StreamSignal.Idle();
  private static final long NO_FLOOR = -1;

  private final ChangeFeed feed;
  private final StreamScope scope;
  private final int capacity;
  private final ReentrantLock lock = new ReentrantLock();
  private final Condition ready = lock.newCondition();
  private final ArrayDeque<StreamSignal> queue = new ArrayDeque<>();
  private StreamSignal.Closed terminal;
  private boolean closed;

  // owned by the feed (its lock)
  private final Map<MissionRef, Long> floors = new HashMap<>();
  private final Set<MissionRef> dropped = new HashSet<>();

  StreamSubscriber(ChangeFeed feed, StreamScope scope, int capacity) {
    this.feed = feed;
    this.scope = scope;
    this.capacity = capacity;
  }

  StreamScope scope() {
    return scope;
  }

  /** Changes of this Mission at or before this offset were delivered by the catch-up, or happened before the subscriber joined. */
  long floor(MissionRef mission) {
    return floors.getOrDefault(mission, NO_FLOOR);
  }

  void floor(MissionRef mission, long offset) {
    floors.put(mission, offset);
  }

  void resetFloor(MissionRef mission) {
    floors.remove(mission);
  }

  Set<MissionRef> dropped() {
    return dropped;
  }

  /** Queues the signal; false when the queue is full. A finished or closed subscriber accepts and discards. */
  boolean offer(StreamSignal signal) {
    lock.lock();
    try {
      if (terminal != null || closed) {
        return true;
      }
      if (queue.size() >= capacity) {
        return false;
      }
      queue.add(signal);
      ready.signalAll();
      return true;
    } finally {
      lock.unlock();
    }
  }

  /** The stream is over: what is queued is delivered, then {@code Closed(closure)}, now and on every later call. */
  void finish(Closure closure) {
    lock.lock();
    try {
      if (terminal == null) {
        terminal = new StreamSignal.Closed(closure);
        ready.signalAll();
      }
    } finally {
      lock.unlock();
    }
  }

  @Override
  public StreamSignal next(Duration wait) throws InterruptedException {
    lock.lock();
    try {
      long nanos = wait.toNanos();
      while (true) {
        if (closed) {
          throw new IllegalStateException("subscription closed");
        }
        StreamSignal signal = queue.poll();
        if (signal != null) {
          return signal;
        }
        if (terminal != null) {
          return terminal;
        }
        if (nanos <= 0) {
          return IDLE;
        }
        nanos = ready.awaitNanos(nanos);
      }
    } finally {
      lock.unlock();
    }
  }

  @Override
  public void close() {
    lock.lock();
    try {
      closed = true;
      queue.clear();
      ready.signalAll();
    } finally {
      lock.unlock();
    }
    feed.detach(this);
  }
}
