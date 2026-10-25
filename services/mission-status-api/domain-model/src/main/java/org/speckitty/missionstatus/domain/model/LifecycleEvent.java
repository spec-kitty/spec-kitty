package org.speckitty.missionstatus.domain.model;

import java.util.List;
import java.util.Objects;

/** A lifecycle marker of one of the seven forwarded types; every other well-formed object is {@code Ignored}. */
public record LifecycleEvent(String eventId, String type, String at) {

  private static final List<String> TYPES =
      List.of("MissionCreated", "SpecifyStarted", "SpecifyCompleted", "PlanStarted", "PlanCompleted", "TasksStarted", "TasksCompleted");

  public LifecycleEvent {
    Objects.requireNonNull(eventId, "eventId");
    Objects.requireNonNull(at, "at");
    if (!isForwarded(type)) {
      throw new IllegalArgumentException("not a forwarded lifecycle type");
    }
  }

  public static boolean isForwarded(String type) {
    return TYPES.contains(type);
  }
}
