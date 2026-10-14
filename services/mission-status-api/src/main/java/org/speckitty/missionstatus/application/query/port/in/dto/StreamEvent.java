package org.speckitty.missionstatus.application.query.port.in.dto;

import java.util.Objects;
import java.util.Optional;
import org.speckitty.missionstatus.domain.readmodel.cursor.StreamCursor;

/**
 * One event of a change stream, as projected for a consumer: strings, booleans and cursors, never a ledger row. The projection
 * (allow-list, display lanes, strict handles) happens inside the application, so an inbound adapter can only serialise what is here. The
 * members are named for the wire's data, not for the raw ledger: a reason, a review reference, a reason source or a claim agent has no
 * place in this type.
 */
public sealed interface StreamEvent {

  /** The Mission the event belongs to. */
  String missionId();

  /**
   * The cursor to resume from after this event: the position after the row for a status transition or a lifecycle event, and empty for a
   * truncation (its reset cursor is data, never an id).
   */
  Optional<StreamCursor> resumeCursor();

  /** A work package moved between display lanes. {@code fromStatusLane} is null when the source lane is not a display lane. */
  record StatusTransition(
      String missionId,
      String eventId,
      String wpId,
      String fromStatusLane,
      String toStatusLane,
      String at,
      ActorHandles actor,
      boolean force,
      StreamCursor cursor)
      implements StreamEvent {

    public StatusTransition {
      Objects.requireNonNull(missionId, "missionId");
      Objects.requireNonNull(eventId, "eventId");
      Objects.requireNonNull(wpId, "wpId");
      Objects.requireNonNull(toStatusLane, "toStatusLane");
      Objects.requireNonNull(at, "at");
      Objects.requireNonNull(actor, "actor");
      Objects.requireNonNull(cursor, "cursor");
    }

    @Override
    public Optional<StreamCursor> resumeCursor() {
      return Optional.of(cursor);
    }
  }

  /** A lifecycle event of the Mission. */
  record Lifecycle(String missionId, String eventId, String eventType, String at, StreamCursor cursor) implements StreamEvent {

    public Lifecycle {
      Objects.requireNonNull(missionId, "missionId");
      Objects.requireNonNull(eventId, "eventId");
      Objects.requireNonNull(eventType, "eventType");
      Objects.requireNonNull(at, "at");
      Objects.requireNonNull(cursor, "cursor");
    }

    @Override
    public Optional<StreamCursor> resumeCursor() {
      return Optional.of(cursor);
    }
  }

  /**
   * The Mission's log shrank or changed under the reader. {@code truncationCause} holds the wire word of the cause; {@code resetCursor}
   * is where to start again (data, never a resume id).
   */
  record LogTruncated(String missionId, String truncationCause, long detectedAtOffset, StreamCursor resetCursor) implements StreamEvent {

    public LogTruncated {
      Objects.requireNonNull(missionId, "missionId");
      Objects.requireNonNull(truncationCause, "truncationCause");
      Objects.requireNonNull(resetCursor, "resetCursor");
    }

    @Override
    public Optional<StreamCursor> resumeCursor() {
      return Optional.empty();
    }
  }

  /** Who made a transition: three handles, each strict-projected and each nullable. */
  record ActorHandles(String tool, String role, String profile) {}
}
