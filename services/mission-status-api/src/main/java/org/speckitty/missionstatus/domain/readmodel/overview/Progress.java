package org.speckitty.missionstatus.domain.readmodel.overview;

import java.math.BigDecimal;

/** Weighted readiness and done-only completion, already rounded half-even to four decimals like Python's {@code round(x, 4)}. */
public record Progress(double weightedPercentage, double donePercentage, int doneCount) {

  public static final String SEMANTICS = "weighted_readiness";

  /**
   * The one pinned rendering of a percentage for serialisation: the shortest digits that round-trip, in plain notation, with at
   * least one fractional digit, which is what Python's {@code json.dumps} writes for a float in this range.
   */
  public static String render(double value) {
    String plain = new BigDecimal(Double.toString(value)).stripTrailingZeros().toPlainString();
    return plain.contains(".") ? plain : plain + ".0";
  }
}
