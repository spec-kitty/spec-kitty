package org.speckitty.missionstatus.application.query.stream;

import java.util.List;
import java.util.Objects;
import org.speckitty.missionstatus.domain.readmodel.cursor.StreamCursor;

/** The changes after a cursor, in log order, and the cursor after the last row read (the one to resume from). */
public record ChangeBatch(List<Change> changes, StreamCursor cursor) {

  public ChangeBatch {
    changes = List.copyOf(Objects.requireNonNull(changes, "changes"));
    Objects.requireNonNull(cursor, "cursor");
  }
}
