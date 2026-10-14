package org.speckitty.missionstatus.application.query.stream;

import java.util.Objects;
import org.speckitty.missionstatus.application.query.port.in.dto.Closure;
import org.speckitty.missionstatus.domain.model.MissionId;

/**
 * What the raw feed hands out: ledger rows as read, before the projection. Application-internal; the port's own
 * {@code StreamSignal} carries the projected form, so no inbound adapter ever sees one of these.
 */
public sealed interface FeedSignal {

  /** Forwarded rows, in log order. */
  record Forwarded(ChangeBatch batch) implements FeedSignal {

    public Forwarded {
      Objects.requireNonNull(batch, "batch");
    }
  }

  /** The Mission's log shrank or changed under the reader: a {@code log-truncated} event without an id, then a re-baseline. */
  record Truncated(MissionId missionId, Reason reason, long detectedAtOffset) implements FeedSignal {

    /** Why the reader concluded the log was truncated. */
    public enum Reason {
      SIZE_SHRINK,
      CONTENT_MISMATCH;

      public String wire() {
        return name().toLowerCase(java.util.Locale.ROOT);
      }
    }

    public Truncated {
      Objects.requireNonNull(missionId, "missionId");
      Objects.requireNonNull(reason, "reason");
    }
  }

  /** An unscoped stream stopped watching one Mission (it faulted); the connection stays. */
  record Dropped(String mid8) implements FeedSignal {

    public Dropped {
      Objects.requireNonNull(mid8, "mid8");
    }
  }

  /** The stream is over; nothing follows, now or on a later call. */
  record Closed(Closure closure) implements FeedSignal {

    public Closed {
      Objects.requireNonNull(closure, "closure");
    }
  }

  /** Nothing happened within the wait. */
  record Idle() implements FeedSignal {}
}
