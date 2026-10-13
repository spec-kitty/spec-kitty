package org.speckitty.missionstatus.adapter.in.http;

import java.util.Map;
import java.util.Optional;
import java.util.TreeMap;
import java.util.regex.Pattern;
import org.speckitty.missionstatus.application.query.port.in.dto.Change;
import org.speckitty.missionstatus.application.query.port.in.dto.StreamSignal;
import org.speckitty.missionstatus.domain.readmodel.cursor.StreamCursor;
import org.speckitty.missionstatus.domain.model.Actor;
import org.speckitty.missionstatus.domain.model.Lane;
import org.speckitty.missionstatus.domain.model.LifecycleEvent;
import org.speckitty.missionstatus.domain.model.LineKind;
import org.speckitty.missionstatus.domain.model.MissionId;
import org.speckitty.missionstatus.domain.model.StatusEvent;
import org.speckitty.missionstatus.domain.readmodel.overview.Instants;
import org.speckitty.missionstatus.domain.redaction.LeakClasses;
import org.speckitty.missionstatus.domain.redaction.ProjectionError;
import org.speckitty.missionstatus.domain.redaction.Projector;
import tools.jackson.databind.json.JsonMapper;

/**
 * The data of one stream event, built from an allow-list of members and nothing else (a raw row never reaches the wire). A strict
 * field goes through the same {@link Projector} as the overview, so a value that carries a path or a secret is refused here too: the
 * {@link org.speckitty.missionstatus.domain.redaction.ProjectionError} is the caller's to report. Members are written in sorted
 * order with explicit nulls, like every other document of the adapter.
 */
final class EventData {

  /** The contract's {@code WpId}: a row whose work package id does not match is dropped, never repaired. */
  private static final Pattern WP_ID = Pattern.compile("^WP[0-9]{2,}$");

  /** The contract's bound of {@code eventId} and {@code wpId} (landing fold A5); a longer id is no representable value. */
  private static final int MAX_ID_LENGTH = 64;

  /** An event ready to send: its name, its data text and the cursor it resumes from (the {@code id:} of a Mission-scoped stream). */
  record Frame(String name, String data, StreamCursor resumeCursor) {}

  private final JsonMapper mapper;
  private final LeakClasses leaks;

  EventData(JsonMapper mapper, LeakClasses leaks) {
    this.mapper = mapper;
    this.leaks = leaks;
  }

  /** The event of a forwarded change, or empty when the row is not a valid event (an invalid work package id, a non-display target lane). */
  Optional<Frame> of(Change change) {
    Projector projector = new Projector(leaks);
    return switch (change.kind()) {
      case LineKind.Status status -> status(change, status.event(), projector);
      case LineKind.Lifecycle lifecycle -> Optional.of(lifecycle(change, lifecycle.event(), projector));
      default -> throw new IllegalStateException("a change is a status or a lifecycle row");
    };
  }

  private Optional<Frame> status(Change change, StatusEvent event, Projector projector) {
    if (!WP_ID.matcher(event.wpId()).matches() || !event.toLane().isDisplay()) {
      return Optional.empty();
    }
    Map<String, Object> data = new TreeMap<>();
    data.put("missionId", projector.strict(change.missionId().value(), "missionId", false));
    data.put("eventId", boundedId(projector.strict(event.eventId(), "eventId", false), "eventId"));
    data.put("wpId", boundedId(event.wpId(), "wpId"));
    data.put("fromStatusLane", displayLane(event.fromLane()));
    data.put("toStatusLane", event.toLane().wire());
    data.put("at", instant(event.at(), "at"));
    data.put("actor", actor(event.actor(), projector));
    data.put("force", event.force());
    data.put("streamCursor", cursor(change.cursor()));
    return Optional.of(new Frame("status-transition", write(data), change.cursor()));
  }

  private Frame lifecycle(Change change, LifecycleEvent event, Projector projector) {
    Map<String, Object> data = new TreeMap<>();
    data.put("missionId", projector.strict(change.missionId().value(), "missionId", false));
    data.put("eventId", boundedId(projector.strict(event.eventId(), "eventId", false), "eventId"));
    data.put("eventType", event.type());
    data.put("at", instant(event.at(), "timestamp"));
    data.put("streamCursor", cursor(change.cursor()));
    return new Frame("mission-lifecycle", write(data), change.cursor());
  }

  /** The {@code log-truncated} event: the reset cursor (offset 0, digest of the empty input) is inside the data and is never an id. */
  Frame of(StreamSignal.Truncated truncated) {
    Projector projector = new Projector(leaks);
    Map<String, Object> data = new TreeMap<>();
    data.put("missionId", projector.strict(truncated.missionId().value(), "missionId", false));
    data.put("reason", truncated.reason().wire());
    data.put("detectedAtOffset", truncated.detectedAtOffset());
    data.put("streamCursor", cursor(StreamCursor.start()));
    return new Frame("log-truncated", write(data), null);
  }

  /** The Mission a truncation names, for the diagnostic of a refused projection. */
  static String mid8(MissionId id) {
    return id.mid8();
  }

  private static String displayLane(Lane lane) {
    return lane.isDisplay() ? lane.wire() : null;
  }

  /** The handles go through the strict projection (nullable): a token-, path- or e-mail-shaped handle is served as null (pre-merge fold J8). */
  private static Map<String, Object> actor(Actor actor, Projector projector) {
    Map<String, Object> handles = new TreeMap<>();
    handles.put("tool", projector.strict(actor.tool(), "actor.tool", true));
    handles.put("role", projector.strict(actor.role(), "actor.role", true));
    handles.put("profile", projector.strict(actor.profile(), "actor.profile", true));
    return handles;
  }

  /**
   * A row's instant, served as written once it parses as one with an offset (the contract's {@code date-time}); a value that is not an instant is not
   * representable, so the event is dropped with one {@code projection_refused} diagnostic, as a refused strict field is (pre-merge fold J6).
   */
  private static String instant(String value, String field) {
    if (value == null) {
      throw new ProjectionError(field, ProjectionError.Reason.MISSING);
    }
    // an instant with an offset: a value without one is no contract date-time (landing fold R-7)
    if (!Instants.hasOffset(value)) {
      throw new ProjectionError(field, ProjectionError.Reason.NOT_REPRESENTABLE);
    }
    return value;
  }

  private static String boundedId(String id, String field) {
    if (id.length() > MAX_ID_LENGTH) {
      throw new ProjectionError(field, ProjectionError.Reason.NOT_REPRESENTABLE);
    }
    return id;
  }

  private static Map<String, Object> cursor(StreamCursor cursor) {
    Map<String, Object> position = new TreeMap<>();
    position.put("offset", cursor.offset());
    position.put("invariant", cursor.invariant());
    return position;
  }

  private String write(Map<String, Object> data) {
    return mapper.writeValueAsString(data);
  }
}
