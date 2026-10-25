package org.speckitty.missionstatus.domain.readmodel.reducer;

import org.speckitty.missionstatus.domain.model.Lane;
import org.speckitty.missionstatus.domain.model.StatusEvent;

/** Test builders for status events. */
final class Events {

  private Events() {}

  static StatusEvent move(String id, String at, String wp, Lane from, Lane to) {
    return new StatusEvent(id, at, wp, from, to, false, null, null, null, null);
  }

  /** A reconstruction seed ({@code migration:} actor) with the given canonical key. */
  static StatusEvent seed(String id, String at, String wp, Lane from, Lane to, String seedKey) {
    return new StatusEvent(id, at, wp, from, to, false, null, null, null, null, org.speckitty.missionstatus.domain.model.Actor.ofText("migration:backfill"), seedKey);
  }

  static StatusEvent forced(String id, String at, String wp, Lane from, Lane to) {
    return new StatusEvent(id, at, wp, from, to, true, null, null, null, null);
  }

  static StatusEvent withReviewRef(String id, String at, String wp, Lane from, Lane to, String reviewRef) {
    return new StatusEvent(id, at, wp, from, to, false, reviewRef, null, null, null);
  }

  static StatusEvent cancel(String id, String at, String wp, Lane from, String reason, String reasonSource) {
    return new StatusEvent(id, at, wp, from, Lane.CANCELED, false, null, reason, reasonSource, null);
  }

  static StatusEvent claim(String id, String at, String wp, String agent) {
    return new StatusEvent(id, at, wp, Lane.PLANNED, Lane.CLAIMED, false, null, null, null, agent);
  }

  static StatusEvent forcedCancel(String id, String at, String wp, Lane from, String reason) {
    return new StatusEvent(id, at, wp, from, Lane.CANCELED, true, null, reason, null, null);
  }
}
