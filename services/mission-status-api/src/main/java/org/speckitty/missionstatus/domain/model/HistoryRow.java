package org.speckitty.missionstatus.domain.model;

import java.util.Objects;

/**
 * One transition row of a Work Package's history, as the oracle's {@code history_entries} reads it from the raw ledger row: the row's own
 * texts, unprojected. {@code eventId} and {@code at} are the stored values (a non-text value is its Python {@code str()}); {@code fromLane}
 * and {@code toLane} are the stored lane texts (the route mapper shows a display lane, nulls a non-display lane and refuses the rest);
 * {@code actor} is the row's own actor, never the snapshot slot; {@code force} is true only for the literal JSON {@code true};
 * {@code reviewVerdict} is the verdict of the row's {@code review_result} when that is an object. {@code reason} is the stored text,
 * not yet redacted.
 */
public record HistoryRow(String wpId, String eventId, String at, String fromLane, String toLane, Actor actor, boolean force, String reason, String reviewVerdict) {

  public HistoryRow {
    Objects.requireNonNull(wpId, "wpId");
    Objects.requireNonNull(actor, "actor");
  }
}
