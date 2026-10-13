package org.speckitty.missionstatus.application.query.port.in.dto;

import java.util.Objects;
import org.speckitty.missionstatus.domain.readmodel.cursor.StreamCursor;
import org.speckitty.missionstatus.domain.model.LineKind;
import org.speckitty.missionstatus.domain.model.MissionId;

/**
 * One forwarded row: a status transition or a lifecycle event of the Mission, and the cursor after the row (the position a consumer
 * resumes from). Annotation, decision, retrospective and unknown rows are never a change.
 */
public record Change(MissionId missionId, LineKind kind, StreamCursor cursor) {

  public Change {
    Objects.requireNonNull(missionId, "missionId");
    Objects.requireNonNull(cursor, "cursor");
    if (!(kind instanceof LineKind.Status) && !(kind instanceof LineKind.Lifecycle)) {
      throw new IllegalArgumentException("only a status transition or a lifecycle event is a change");
    }
  }
}
