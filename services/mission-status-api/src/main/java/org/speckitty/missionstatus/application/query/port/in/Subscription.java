package org.speckitty.missionstatus.application.query.port.in;

import java.time.Duration;
import org.speckitty.missionstatus.application.query.port.in.dto.StreamSignal;

/**
 * A live stream. One thread calls {@link #next}; {@link #close} may come from any thread. A {@code next} that is blocked or called after a
 * {@code close} from another thread throws {@link IllegalStateException}: the adapter must catch it as the end of the connection.
 */
public interface Subscription extends AutoCloseable {

  /** Blocks up to {@code wait} for the next signal; {@link StreamSignal.Idle} when there is none. */
  StreamSignal next(Duration wait) throws InterruptedException;

  /** Unsubscribes. Idempotent. */
  @Override
  void close();
}
