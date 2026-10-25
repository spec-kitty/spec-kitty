package org.speckitty.missionstatus.domain.model;

import java.util.Objects;

/**
 * The reduced state of one work package. {@code lastTransitionAt} and {@code lastEventId} are null for a work package known only
 * from annotations. The last two members are the projections of {@code materialize_snapshot}; each may be null.
 */
public record WpState(
    Lane lane, String lastTransitionAt, String lastEventId, int forceCount, String cancellationReason, String reasonSource, String implementerOfRecord) {

  public WpState {
    Objects.requireNonNull(lane, "lane");
  }
}
