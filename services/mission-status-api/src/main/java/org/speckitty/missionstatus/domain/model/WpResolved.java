package org.speckitty.missionstatus.domain.model;

import java.util.Collections;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;
import java.util.Objects;

/**
 * The resolved state of one Work Package that the detail routes need and {@link WpState} does not carry (FR-020): the assignment handles,
 * the subtask map (insertion-ordered, the status of each subtask as a lane), the latest review result and the review override (each null
 * when the snapshot holds none), the actor of the latest applied change, and the ordered transition history. It sits in a map parallel to
 * {@code StatusSnapshot.workPackages}, so no overview derivation can read it.
 */
public record WpResolved(
    Assignment assignment, Map<String, Lane> subtasks, ReviewResultRecord reviewResult, ReviewOverrideRecord reviewOverride, Actor actor, List<HistoryRow> history) {

  public WpResolved {
    Objects.requireNonNull(assignment, "assignment");
    Objects.requireNonNull(subtasks, "subtasks");
    Objects.requireNonNull(actor, "actor");
    Objects.requireNonNull(history, "history");
    subtasks = Collections.unmodifiableMap(new LinkedHashMap<>(subtasks));
    history = List.copyOf(history);
  }

  /** A Work Package with no resolved state: the no-events value. */
  public static WpResolved empty() {
    return new WpResolved(Assignment.EMPTY, Map.of(), null, null, Actor.NONE, List.of());
  }
}
