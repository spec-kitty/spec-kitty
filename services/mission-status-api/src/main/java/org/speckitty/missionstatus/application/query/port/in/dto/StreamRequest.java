package org.speckitty.missionstatus.application.query.port.in.dto;

import java.util.Objects;
import java.util.Optional;
import org.speckitty.missionstatus.application.query.port.in.exceptions.StreamRefused;
import org.speckitty.missionstatus.domain.readmodel.cursor.StreamCursor;

/**
 * A stream request decoded from the text an adapter received. {@link #parse} fixes the order of the connect-time decisions once, for
 * every adapter: a cursor text without a Mission is refused first, then the cursor text, then the scope. Capacity and the lookup of the
 * Mission follow inside {@code MissionStatusQuery#subscribe}.
 */
public record StreamRequest(StreamScope scope, Optional<StreamCursor> cursor) {

  public StreamRequest {
    Objects.requireNonNull(scope, "scope");
    Objects.requireNonNull(cursor, "cursor");
  }

  /**
   * @param missionIdOrNull the Mission id text, or null for every Mission
   * @param cursorTextOrNull the cursor text ({@code offset:invariant}), or null for none
   * @throws StreamRefused for a cursor text without a Mission, a cursor text that does not parse, or a Mission id that is no ULID
   */
  public static StreamRequest parse(String missionIdOrNull, String cursorTextOrNull) {
    if (cursorTextOrNull != null && missionIdOrNull == null) {
      throw new StreamRefused(StreamRefused.Kind.CURSOR_WITHOUT_MISSION);
    }
    Optional<StreamCursor> cursor = cursorTextOrNull == null ? Optional.empty() : Optional.of(StreamCursorText.parse(cursorTextOrNull));
    return new StreamRequest(StreamScope.parse(missionIdOrNull), cursor);
  }
}
