package org.speckitty.missionstatus.perf;

import static org.assertj.core.api.Assertions.assertThat;

import org.junit.jupiter.api.Tag;
import org.junit.jupiter.api.Test;

/**
 * The absolute figures are the spec's own (NFR-001, NFR-002, NFR-004): provisional ceilings that change only by amending the spec row
 * with a measurement. A ceiling loosened here, or a connection count lowered, without that amendment is red. RATIO limits are
 * measurement-derived and are not pinned here; the Nfr tests assert them.
 */
@Tag("perf")
class PerfBudgetsTest {

  @Test
  void theCeilingsAreTheSpecFigures() {
    assertThat(PerfBudgets.NFR001_WARM_P95_CEILING_MS).as("NFR-001 warm p95 ceiling (ms)").isEqualTo(400);
    assertThat(PerfBudgets.NFR001_COLD_CEILING_MS).as("NFR-001 cold first call ceiling (ms)").isEqualTo(5_000);
    assertThat(PerfBudgets.NFR002_STARTUP_CEILING_MS).as("NFR-002 first request ceiling (ms)").isEqualTo(2_000);
    assertThat(PerfBudgets.NFR004_THREADS_CEILING).as("NFR-004 platform threads").isEqualTo(16);
    assertThat(PerfBudgets.NFR004_HEAP_CEILING_MIB).as("NFR-004 used heap (MiB)").isEqualTo(64);
    assertThat(PerfBudgets.NFR004_RSS_CEILING_MIB).as("NFR-004 resident set (MiB)").isEqualTo(128);
  }

  @Test
  void theScenarioIsTheSpecScenario() {
    assertThat(PerfBudgets.NFR001_MISSIONS).as("NFR-001 asks for at least 500 Missions").isGreaterThanOrEqualTo(500);
    assertThat(PerfBudgets.NFR004_CONNECTIONS).as("NFR-004 connections").isEqualTo(100);
    assertThat(PerfBudgets.NFR004_HOLD_SECONDS).as("NFR-004 hold (s)").isEqualTo(60);
    assertThat(PerfBudgets.NFR004_APPENDS).as("NFR-004 appended rows").isEqualTo(10);
  }

  @Test
  void theNfr001RatiosAreTighterThanASleepOfFiftyMillisecondsInTheRoute() {
    // measured with a 50 ms sleep in the overview route: warm ratio 48.8 to 51.2, cold ratio 78.3 to 87.4 (see PerfBudgets)
    assertThat(PerfBudgets.NFR001_WARM_P95_RATIO_LIMIT).as("warm ratio limit stays below the sleep's lowest warm ratio").isLessThan(48.8);
    assertThat(PerfBudgets.NFR001_COLD_RATIO_LIMIT).as("cold ratio limit stays below the sleep's lowest cold ratio").isLessThan(78.3);
    // and above the clean baselines (21.9 to 26.0 warm, 44.4 to 55.3 cold)
    assertThat(PerfBudgets.NFR001_WARM_P95_RATIO_LIMIT).isGreaterThan(26.0);
    assertThat(PerfBudgets.NFR001_COLD_RATIO_LIMIT).isGreaterThan(55.3);
  }

  @Test
  void everyRatioLimitIsPositiveAndTighterThanItsCeilingAllowsAtTheFloorUnit() {
    assertThat(PerfBudgets.NFR001_WARM_P95_RATIO_LIMIT).isPositive();
    assertThat(PerfBudgets.NFR001_COLD_RATIO_LIMIT).isPositive();
    assertThat(PerfBudgets.NFR002_STARTUP_RATIO_LIMIT).isPositive();
    // at the clamped floor, the ratio may not permit more than the spec ceiling already does (a ratio looser than its ceiling checks nothing)
    assertThat(PerfBudgets.NFR004_THREADS_RATIO_LIMIT * PerfBudgets.NFR004_THREADS_FLOOR_UNIT).isLessThanOrEqualTo(PerfBudgets.NFR004_THREADS_CEILING);
    assertThat(PerfBudgets.NFR004_MEMORY_RATIO_LIMIT * PerfBudgets.NFR004_MEMORY_FLOOR_UNIT_MIB).isLessThanOrEqualTo(PerfBudgets.NFR004_HEAP_CEILING_MIB);
  }
}
