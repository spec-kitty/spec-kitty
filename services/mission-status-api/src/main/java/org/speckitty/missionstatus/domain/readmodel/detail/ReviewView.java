package org.speckitty.missionstatus.domain.readmodel.detail;

import java.util.Locale;
import java.util.Objects;

/**
 * The review evidence of a Work Package (the contract's {@code Review}): its latest review result and any review override, each null
 * until it exists. Text members are the stored texts; the human ones are redacted by the mapper's caller, not here.
 *
 * @param latestResult the latest result, or null
 * @param override the override, or null (a partial override is present with {@code complete} false)
 */
public record ReviewView(Result latestResult, ReviewOverride override) {

  /** The verdict of a review (the contract's {@code ReviewVerdict}); also used by a review cycle. */
  public enum Verdict {
    APPROVED,
    CHANGES_REQUESTED;

    public String wire() {
      return name().toLowerCase(Locale.ROOT);
    }
  }

  /**
   * @param reviewer the reviewer handle, or null
   * @param verdict the verdict
   * @param reference the review reference as recorded
   */
  public record Result(String reviewer, Verdict verdict, String reference) {
    public Result {
      Objects.requireNonNull(verdict, "verdict");
      Objects.requireNonNull(reference, "reference");
    }
  }

  /**
   * @param complete true when time, actor, Work Package id and reason of the record are all non-empty
   * @param at when it was recorded, or null
   * @param actor the handle of whoever recorded it, or null
   * @param reason the stated reason, or null
   */
  public record ReviewOverride(boolean complete, String at, String actor, String reason) {}
}
