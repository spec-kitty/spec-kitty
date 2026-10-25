package org.speckitty.missionstatus.domain.readmodel.reducer;

import org.speckitty.missionstatus.domain.model.CodePoints;
import org.speckitty.missionstatus.domain.model.StatusEvent;

/**
 * The production ordering: {@code (at, event_id)}, each compared as TEXT by Unicode code point, the way Python's {@code sorted}
 * key does. {@code at} is never parsed here; the instant comparison of {@code lastActivityAt} is a separate rule.
 */
public final class AtThenEventId implements EventOrdering {

  @Override
  public int compare(StatusEvent left, StatusEvent right) {
    int byAt = CodePoints.compare(left.at(), right.at());
    return byAt != 0 ? byAt : CodePoints.compare(left.eventId(), right.eventId());
  }
}
