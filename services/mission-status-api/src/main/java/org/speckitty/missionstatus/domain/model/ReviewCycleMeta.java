package org.speckitty.missionstatus.domain.model;

/**
 * The two members of a review-cycle file a response shows (row M11): the review time when it is an RFC 3339 date-time, and the reviewer
 * as stored. A file that does not parse gives {@link #UNPARSED}, two nulls, and no diagnostic: its verdict comes from the ledger.
 */
public record ReviewCycleMeta(String reviewedAt, String reviewer) {

  /** A file that did not parse, or was over the cap: an entry with null members. */
  public static final ReviewCycleMeta UNPARSED = new ReviewCycleMeta(null, null);
}
