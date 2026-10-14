package org.speckitty.missionstatus.domain.model;

/**
 * The latest review result of a Work Package (contract {@code ReviewResult}): {@code reviewer} is a handle (null when the stored value is
 * none), {@code verdict} and {@code reference} are the stored texts. A member the row did not carry as text, or that Java does not read as
 * the oracle does, is null; the route mapper decides what a null verdict or reference becomes.
 */
public record ReviewResultRecord(String reviewer, String verdict, String reference) {

  public ReviewResultRecord {
    reviewer = reviewer == null ? null : Actor.ofText(reviewer).tool();
  }
}
