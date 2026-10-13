package org.speckitty.missionstatus.perf;

import java.util.Locale;

/**
 * One performance budget in the shape of ADR 2026-10-05-2: a measured figure, a floor sampled in the SAME run, a ratio limit and the
 * absolute ceiling beside it. {@link #evaluate} fails once, with every input in the message, and never retries: a miss is classified
 * (runner noise versus regression) by a person reading that message.
 */
public final class RatioBudget {

  /** What an evaluation saw, for the summary line of a pass. */
  public record Outcome(String name, double measured, double floor, double ratio, double ratioLimit, double ceiling, String unit) {

    public String line() {
      return String.format(
          Locale.ROOT,
          "%s: measured %.3f %s, floor %.3f %s, ratio %.2f (limit %.2f), ceiling %.1f %s",
          name,
          measured,
          unit,
          floor,
          unit,
          ratio,
          ratioLimit,
          ceiling,
          unit);
    }
  }

  private RatioBudget() {}

  /**
   * @param name what is measured
   * @param measured the figure under test
   * @param floor the figure of the no-op route, the one-connection run or the trivial binary, sampled in the same run; it must be a
   *     positive number or there is no baseline and the budget refuses to be evaluated
   * @param ratioLimit the primary assertion: {@code measured / floor} must not exceed it
   * @param ceiling the provisional absolute figure of the spec: {@code measured} must not exceed it
   * @param unit the unit of {@code measured}, {@code floor} and {@code ceiling}
   * @param hint run context to print on a miss (threads, CPUs), never used to decide
   */
  public static Outcome evaluate(String name, double measured, double floor, double ratioLimit, double ceiling, String unit, String hint) {
    if (!(floor > 0) || Double.isInfinite(floor)) {
      throw new AssertionError(name + ": no baseline. The floor must be sampled in the same run and be positive (ADR 2026-10-05-2); got " + floor + ".");
    }
    if (!(ratioLimit > 0) || !(ceiling > 0)) {
      throw new AssertionError(name + ": a budget needs a positive ratio limit and a positive ceiling; got " + ratioLimit + " and " + ceiling + ".");
    }
    double ratio = measured / floor;
    Outcome outcome = new Outcome(name, measured, floor, ratio, ratioLimit, ceiling, unit);
    boolean ratioMissed = ratio > ratioLimit;
    boolean ceilingMissed = measured > ceiling;
    if (ratioMissed || ceilingMissed) {
      throw new AssertionError(
          "budget missed ("
              + (ratioMissed ? "ratio" : "")
              + (ratioMissed && ceilingMissed ? " and " : "")
              + (ceilingMissed ? "ceiling" : "")
              + "): "
              + outcome.line()
              + "; run: "
              + hint
              + ". Classify the miss under ADR 2026-10-05-2 (runner noise versus a regression); it is not retried and the limits are amended only by a measurement.");
    }
    return outcome;
  }
}
