package org.speckitty.missionstatus.application.query.port.in.dto;

import java.util.List;
import java.util.Objects;
import org.speckitty.missionstatus.domain.readmodel.cursor.StreamCursor;

/** The projected events after a cursor, in log order, and the cursor after the last row read (the one to resume from). */
public record StreamBatch(List<StreamEvent> events, StreamCursor cursor) {

  public StreamBatch {
    events = List.copyOf(Objects.requireNonNull(events, "events"));
    Objects.requireNonNull(cursor, "cursor");
  }
}
