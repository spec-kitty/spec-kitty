package org.speckitty.missionstatus.perf;

import static org.assertj.core.api.Assertions.assertThat;
import static org.assertj.core.api.Assertions.assertThatThrownBy;

import org.junit.jupiter.api.Tag;
import org.junit.jupiter.api.Test;

/** The budget helper itself: each of its three checks can fail, and a miss names every input. RATIO and CEILING are the two halves under test. */
@Tag("perf")
class RatioBudgetTest {

  private static final double RATIO_LIMIT = 10;
  private static final double CEILING = 200;

  @Test
  void aFigureInsideBothTheRatioAndTheCeilingPasses() {
    RatioBudget.Outcome outcome = RatioBudget.evaluate("overview", 40, 8, RATIO_LIMIT, CEILING, "ms", "4 cpus");
    assertThat(outcome.ratio()).isEqualTo(5.0);
    assertThat(outcome.line()).contains("overview").contains("ratio 5.00");
  }

  @Test
  void aRatioOverTheLimitFailsEvenUnderTheCeiling() {
    assertThatThrownBy(() -> RatioBudget.evaluate("overview", 120, 8, RATIO_LIMIT, CEILING, "ms", "4 cpus"))
        .isInstanceOf(AssertionError.class)
        .hasMessageContaining("budget missed (ratio)")
        .hasMessageContaining("ratio 15.00")
        .hasMessageContaining("floor 8.000 ms")
        .hasMessageContaining("4 cpus")
        .hasMessageContaining("ADR 2026-10-05-2");
  }

  @Test
  void aCeilingMissFailsEvenInsideTheRatio() {
    assertThatThrownBy(() -> RatioBudget.evaluate("overview", 250, 100, RATIO_LIMIT, CEILING, "ms", "4 cpus"))
        .isInstanceOf(AssertionError.class)
        .hasMessageContaining("budget missed (ceiling)")
        .hasMessageContaining("ceiling 200.0 ms");
  }

  @Test
  void bothMissesAreNamed() {
    assertThatThrownBy(() -> RatioBudget.evaluate("overview", 900, 8, RATIO_LIMIT, CEILING, "ms", "-"))
        .hasMessageContaining("budget missed (ratio and ceiling)");
  }

  @Test
  void aMissingBaselineIsRefusedNotTreatedAsAPass() {
    assertThatThrownBy(() -> RatioBudget.evaluate("overview", 1, 0, RATIO_LIMIT, CEILING, "ms", "-")).hasMessageContaining("no baseline");
    assertThatThrownBy(() -> RatioBudget.evaluate("overview", 1, Double.NaN, RATIO_LIMIT, CEILING, "ms", "-")).hasMessageContaining("no baseline");
    assertThatThrownBy(() -> RatioBudget.evaluate("overview", 1, -3, RATIO_LIMIT, CEILING, "ms", "-")).hasMessageContaining("no baseline");
  }

  @Test
  void aBudgetWithoutALimitOrACeilingIsRefused() {
    assertThatThrownBy(() -> RatioBudget.evaluate("overview", 1, 1, 0, CEILING, "ms", "-")).hasMessageContaining("positive ratio limit");
    assertThatThrownBy(() -> RatioBudget.evaluate("overview", 1, 1, RATIO_LIMIT, Double.NaN, "ms", "-")).hasMessageContaining("positive ratio limit");
  }
}
