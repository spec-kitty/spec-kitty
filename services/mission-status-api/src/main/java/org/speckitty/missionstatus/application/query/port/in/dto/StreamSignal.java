package org.speckitty.missionstatus.application.query.port.in.dto;

import java.util.List;
import java.util.Objects;

/** What a subscription hands out: projected events only, never a ledger row. */
public sealed interface StreamSignal {

  /**
   * The events of one consumed signal, in log order. An empty list is legal and means "a row was consumed and dropped" (a row the
   * allow-list does not admit, or one whose projection was refused): the stream goes on.
   */
  record Events(List<StreamEvent> events) implements StreamSignal {

    public Events {
      events = List.copyOf(Objects.requireNonNull(events, "events"));
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
