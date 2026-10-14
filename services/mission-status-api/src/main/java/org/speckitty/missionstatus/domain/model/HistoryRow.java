package org.speckitty.missionstatus.domain.model;

import java.util.Objects;

/**
 * One transition row of a Work Package's history, as the oracle's {@code history_entries} reads it from the raw ledger row: the row's own
 * texts, unprojected. {@code eventId} and {@code at} are the stored values (a non-text value is its Python {@code str()}); {@code fromLane}
 * and {@code toLane} are the stored lane texts (the route mapper shows a display lane, nulls a non-display lane and refuses the rest);
 * {@code actor} is the row's own actor, never the snapshot slot; {@code force} is true only for the literal JSON {@code true};
 * {@code reviewVerdict} is the verdict of the row's {@code review_result} when that is an object. {@code reason} is the stored text,
 * not yet redacted. {@code reviewReference} is the {@code reference} of that {@code review_result} when it is text (not yet trimmed), else
 * null: the review-cycle verdicts of the Work Package detail are read from it (WP15, the last row whose trimmed reference is the pointer).
 * {@code lineNumber} is the 1-based line of the ledger the row came from (0 when the row was not read from a ledger): the oracle's
 * {@code cycle_verdict} walks the rows in file order, which the history order (instant, then event id) is not.
 */
public record HistoryRow(
    String wpId, String eventId, String at, String fromLane, String toLane, Actor actor, boolean force, String reason, String reviewVerdict, String reviewReference,
    long lineNumber) {

  public HistoryRow {
    Objects.requireNonNull(wpId, "wpId");
    Objects.requireNonNull(actor, "actor");
  }

  /** A row with no review reference (every caller that predates the review-cycle verdicts). */
  public HistoryRow(String wpId, String eventId, String at, String fromLane, String toLane, Actor actor, boolean force, String reason, String reviewVerdict) {
    this(wpId, eventId, at, fromLane, toLane, actor, force, reason, reviewVerdict, null, 0L);
  }

  /** A row with a review reference and no ledger position. */
  public HistoryRow(
      String wpId, String eventId, String at, String fromLane, String toLane, Actor actor, boolean force, String reason, String reviewVerdict, String reviewReference) {
    this(wpId, eventId, at, fromLane, toLane, actor, force, reason, reviewVerdict, reviewReference, 0L);
  }
}
