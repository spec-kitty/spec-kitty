package org.speckitty.missionstatus.application.query.port.in.dto;

import java.util.Objects;
import org.speckitty.missionstatus.domain.model.MissionId;

/** What a subscription hands out. */
public sealed interface StreamSignal {

  /** Forwarded rows, in log order. */
  record Forwarded(ChangeBatch batch) implements StreamSignal {

    public Forwarded {
      Objects.requireNonNull(batch, "batch");
    }
  }

  /** The Mission's log shrank or changed under the reader: a {@code log-truncated} frame without an id, then a re-baseline. */
  record Truncated(MissionId missionId, Reason reason, long detectedAtOffset) implements StreamSignal {

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
  record Dropped(String mid8) implements StreamSignal {

    public Dropped {
      Objects.requireNonNull(mid8, "mid8");
    }
  }

  /** The stream is over; nothing follows, now or on a later call. */
  record Closed(Closure closure) implements StreamSignal {

    public Closed {
      Objects.requireNonNull(closure, "closure");
    }
  }

  /** Nothing happened within the wait; the adapter turns this into a heartbeat. */
  record Idle() implements StreamSignal {}
}
