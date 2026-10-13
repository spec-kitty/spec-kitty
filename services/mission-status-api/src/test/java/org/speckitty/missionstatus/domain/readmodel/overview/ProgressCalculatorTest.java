package org.speckitty.missionstatus.domain.readmodel.overview;

import static org.assertj.core.api.Assertions.assertThat;
import static org.speckitty.missionstatus.domain.readmodel.overview.Fixtures.snapshot;
import static org.speckitty.missionstatus.domain.readmodel.overview.Fixtures.wp;

import java.util.LinkedHashMap;
import java.util.Map;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.params.ParameterizedTest;
import org.junit.jupiter.params.provider.CsvSource;
import org.speckitty.missionstatus.domain.model.Lane;
import org.speckitty.missionstatus.domain.model.StatusSnapshot;
import org.speckitty.missionstatus.domain.model.WpState;

class ProgressCalculatorTest {

  @ParameterizedTest
  @CsvSource({"PLANNED,0.0", "CLAIMED,5.0", "IN_PROGRESS,30.0", "FOR_REVIEW,60.0", "IN_REVIEW,70.0", "APPROVED,80.0", "DONE,100.0", "BLOCKED,0.0", "CANCELED,0.0", "GENESIS,0.0", "UNINITIALIZED,0.0"})
  void aSingleWorkPackageContributesItsLaneWeight(Lane lane, double expected) {
    assertThat(ProgressCalculator.compute(snapshot(lane)).weightedPercentage()).isEqualTo(expected);
  }

  @Test
  void anEmptySnapshotIsZeroEverywhere() {
    Progress progress = ProgressCalculator.compute(snapshot());
    assertThat(progress.weightedPercentage()).isZero();
    assertThat(progress.donePercentage()).isZero();
    assertThat(progress.doneCount()).isZero();
  }

  @Test
  void theFractionalCaseIsRoundedHalfEvenToFourDecimals() {
    // (1.0 + 0.3 + 0.0) / 3 * 100 = 43.33333...; done 1 of 3 = 33.33333...
    Progress progress = ProgressCalculator.compute(snapshot(Lane.DONE, Lane.IN_PROGRESS, Lane.PLANNED));
    assertThat(progress.weightedPercentage()).isEqualTo(43.3333);
    assertThat(progress.donePercentage()).isEqualTo(33.3333);
    assertThat(progress.doneCount()).isEqualTo(1);
    assertThat(Progress.render(progress.weightedPercentage())).isEqualTo("43.3333");
  }

  @Test
  void floatingPointSumsAreAddedInWorkPackageIdOrder() {
    // Five claimed work packages: 0.05 summed five times is not exactly 0.25; the oracle's rounding still gives exactly 5.0.
    assertThat(ProgressCalculator.compute(snapshot(Lane.CLAIMED, Lane.CLAIMED, Lane.CLAIMED, Lane.CLAIMED, Lane.CLAIMED)).weightedPercentage()).isEqualTo(5.0);
    // Insertion order differs from id order; the result must not depend on it.
    Map<String, WpState> reversed = new LinkedHashMap<>();
    reversed.put("WP03", wp(Lane.DONE, "2026-09-01T10:00:00Z"));
    reversed.put("WP02", wp(Lane.IN_PROGRESS, "2026-09-01T10:00:00Z"));
    reversed.put("WP01", wp(Lane.PLANNED, "2026-09-01T10:00:00Z"));
    Progress progress = ProgressCalculator.compute(new StatusSnapshot(reversed, 3, "X", "t"));
    assertThat(progress.weightedPercentage()).isEqualTo(43.3333);
  }

  @Test
  void aWorkPackageHeldOnlyByAnnotationsCountsInTheDenominator() {
    Progress progress = ProgressCalculator.compute(snapshot(Lane.DONE, Lane.UNINITIALIZED));
    assertThat(progress.weightedPercentage()).isEqualTo(50.0);
    assertThat(progress.donePercentage()).isEqualTo(50.0);
  }

  @Test
  void theSemanticsIsWeightedReadiness() {
    assertThat(Progress.SEMANTICS).isEqualTo("weighted_readiness");
  }

  @Test
  void renderIsThePinnedPythonRepresentation() {
    assertThat(Progress.render(30.0)).isEqualTo("30.0");
    assertThat(Progress.render(0.0)).isEqualTo("0.0");
    assertThat(Progress.render(100.0)).isEqualTo("100.0");
    assertThat(Progress.render(5.0)).isEqualTo("5.0");
    assertThat(Progress.render(12.5)).isEqualTo("12.5");
    assertThat(Progress.render(0.0001)).isEqualTo("0.0001");
    assertThat(Progress.render(43.3333)).isEqualTo("43.3333");
    assertThat(Progress.render(66.6667)).isEqualTo("66.6667");
  }
}
