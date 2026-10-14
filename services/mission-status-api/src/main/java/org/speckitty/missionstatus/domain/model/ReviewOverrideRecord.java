package org.speckitty.missionstatus.domain.model;

import java.util.Objects;

/**
 * The review override slot of a Work Package ({@code ReviewOverride} of spec-kitty-events): four stored texts, the empty string meaning "no
 * value". The decoder {@code str()}-coerces each member, so a JSON {@code null} arrives as the text {@code None}, which is a value.
 * {@link #complete} is plain truthiness of all four (whitespace included); {@link #releaseSentinel} is "all four empty", the record a
 * rollback emits to clear a stale override. {@code wpId} is read for the rule and is not shown by the contract.
 */
public record ReviewOverrideRecord(String at, String actor, String wpId, String reason) {

  public ReviewOverrideRecord {
    Objects.requireNonNull(at, "at");
    Objects.requireNonNull(actor, "actor");
    Objects.requireNonNull(wpId, "wpId");
    Objects.requireNonNull(reason, "reason");
  }

  public boolean complete() {
    return !at.isEmpty() && !actor.isEmpty() && !wpId.isEmpty() && !reason.isEmpty();
  }

  public boolean releaseSentinel() {
    return at.isEmpty() && actor.isEmpty() && wpId.isEmpty() && reason.isEmpty();
  }
}
