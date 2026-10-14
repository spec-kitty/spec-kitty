package org.speckitty.missionstatus.adapter.in.http;

import java.util.Map;
import java.util.TreeMap;
import org.speckitty.missionstatus.application.query.port.in.dto.StreamEvent;
import org.speckitty.missionstatus.domain.readmodel.cursor.StreamCursor;
import tools.jackson.databind.json.JsonMapper;

/**
 * The wire shape of one stream event. The event arrives already projected (the allow-list and the strict fields are the application's:
 * a raw row never reaches this class), so what is left here is naming and serialisation: members are written in sorted order with
 * explicit nulls, like every other document of the adapter, and the cursor is a nested object.
 */
final class EventData {

  /** An event ready to send: its name, its data text and the cursor it resumes from (the {@code id:} of a Mission-scoped stream). */
  record Frame(String name, String data, StreamCursor resumeCursor) {}

  private final JsonMapper mapper;

  EventData(JsonMapper mapper) {
    this.mapper = mapper;
  }

  Frame of(StreamEvent event) {
    return switch (event) {
      case StreamEvent.StatusTransition status -> status(status);
      case StreamEvent.Lifecycle lifecycle -> lifecycle(lifecycle);
      case StreamEvent.LogTruncated truncated -> truncated(truncated);
    };
  }

  private Frame status(StreamEvent.StatusTransition event) {
    Map<String, Object> data = new TreeMap<>();
    data.put("missionId", event.missionId());
    data.put("eventId", event.eventId());
    data.put("wpId", event.wpId());
    data.put("fromStatusLane", event.fromStatusLane());
    data.put("toStatusLane", event.toStatusLane());
    data.put("at", event.at());
    data.put("actor", actor(event.actor()));
    data.put("force", event.force());
    data.put("streamCursor", cursor(event.cursor()));
    return new Frame("status-transition", write(data), event.cursor());
  }

  private Frame lifecycle(StreamEvent.Lifecycle event) {
    Map<String, Object> data = new TreeMap<>();
    data.put("missionId", event.missionId());
    data.put("eventId", event.eventId());
    data.put("eventType", event.eventType());
    data.put("at", event.at());
    data.put("streamCursor", cursor(event.cursor()));
    return new Frame("mission-lifecycle", write(data), event.cursor());
  }

  /** The {@code log-truncated} event: the reset cursor (offset 0, digest of the empty input) is inside the data and is never an id. */
  private Frame truncated(StreamEvent.LogTruncated event) {
    Map<String, Object> data = new TreeMap<>();
    data.put("missionId", event.missionId());
    data.put("reason", event.truncationCause());
    data.put("detectedAtOffset", event.detectedAtOffset());
    data.put("streamCursor", cursor(event.resetCursor()));
    return new Frame("log-truncated", write(data), null);
  }

  private static Map<String, Object> actor(StreamEvent.ActorHandles actor) {
    Map<String, Object> handles = new TreeMap<>();
    handles.put("tool", actor.tool());
    handles.put("role", actor.role());
    handles.put("profile", actor.profile());
    return handles;
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
