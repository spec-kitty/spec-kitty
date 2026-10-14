package org.speckitty.missionstatus.application.query.stream;

import java.time.Duration;

/**
 * The raw feed's subscription. One thread calls {@link #next}; {@link #close} may come from any thread. A {@code next} that is blocked or
 * called after a {@code close} from another thread throws {@link IllegalStateException}.
 */
public interface FeedSubscription extends AutoCloseable {

  /** Blocks up to {@code wait} for the next signal; {@link FeedSignal.Idle} when there is none. */
  FeedSignal next(Duration wait) throws InterruptedException;

  /** Unsubscribes. Idempotent. */
  @Override
  void close();
}
