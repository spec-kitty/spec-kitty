package org.speckitty.missionstatus.perf;

import static org.assertj.core.api.Assertions.assertThat;

import java.lang.management.ManagementFactory;
import java.nio.file.Path;
import java.util.Locale;
import org.junit.jupiter.api.Tag;
import org.junit.jupiter.api.Test;
import org.speckitty.missionstatus.testsupport.http.HttpHarness;

/**
 * NFR-001 for the four detail routes (the spec's 100, 100, 1500 and 100 ms), as a ratio to a floor sampled in the same run (ADR
 * 2026-10-05-2) with the spec's absolute figure beside it as the provisional ceiling. The corpus is {@value PerfBudgets#NFR001_MISSIONS}
 * generated Missions plus the detail Mission, which sorts first, so every request pays for the duplicate-detection scan of all the others
 * (AC-1.8 c). The production application, with its own wiring, answers; the ledger cache is warm.
 *
 * <p>The floor is {@code GET /api/v1/openapi.yaml}, as for the overview: the cheapest route of the service. Both routes are timed over the
 * same number of connections, in alternating rounds, after a discarded warm-up. A miss fails once, with the classification hint: there is no retry.
 */
@Tag("perf")
class Nfr001DetailLatencyTest {

  private static final String FLOOR_ROUTE = "/api/v1/openapi.yaml";
  private static final int CONNECTIONS = 4;
  private static final int ROUNDS = 2;

  private static final String BASE = "/api/v1/missions/" + MissionCorpus.DETAIL_ID;

  // The ratio limits are PROVISIONAL (ADR 2026-10-05-2): each was set from four local runs on an idle 24-cpu machine at load 2 to 7, about 1.25 to 2
  // times the worst clean ratio, and below what a 50 ms sleep in the route would give. A CI-runner measurement amends them; a miss is classified, never retried.

  // getMission of a Mission with 40 Work Package files: spec 100 ms. Measured ratios 11.96, 13.25, 14.43, 26.98 (one run at load 7); p95 22 ms.
  private static final double GET_MISSION_RATIO_LIMIT = 38;
  private static final double GET_MISSION_CEILING_MS = 100;

  // getWorkPackageDetail: spec 100 ms. Measured ratios 10.92 to 12.24; p95 22 ms.
  private static final double GET_WORK_PACKAGE_DETAIL_RATIO_LIMIT = 25;
  private static final double GET_WORK_PACKAGE_DETAIL_CEILING_MS = 100;

  // listArtifacts of a 1000-file Mission, each file read once for `readable`: spec 1500 ms. Measured ratios 31.48 to 36.12; p95 101 to 113 ms.
  // Raised from 45 (operator ruling 2026-10-15): seven runs on a quiet 24-cpu machine (load under 4 at start) measured ratios 27.02 to 52.10 with
  // p95 94 to 109 ms; the spread is the floor (1.1 to 3.9 ms), not the route.
  private static final double LIST_ARTIFACTS_RATIO_LIMIT = 60;
  private static final double LIST_ARTIFACTS_CEILING_MS = 1_500;

  // getArtifactContent of a 262144-byte file: spec 100 ms. Measured ratios 29.18 to 30.90; p95 68 to 72 ms.
  // Raised from 45 (operator ruling 2026-10-15): the same seven runs measured ratios 25.86 to 43.47 with p95 63 to 84 ms. The absolute
  // ceiling below still catches a slow route.
  // The spec target stays 100 ms. On the 4-CPU GitHub runner the first CI run of #6265 measured a p95 of 146.4 ms (floor 5.829 ms, ratio
  // 25.12), so the ceiling is 250 ms, amended by that CI-runner measurement under ADR 2026-10-05-2. The ratio limit stays the primary check.
  private static final double GET_ARTIFACT_CONTENT_RATIO_LIMIT = 60;
  private static final double GET_ARTIFACT_CONTENT_SPEC_MS = 100;
  private static final double GET_ARTIFACT_CONTENT_CEILING_AMENDMENT_MS = 250;
  private static final double GET_ARTIFACT_CONTENT_CEILING_MS = GET_ARTIFACT_CONTENT_CEILING_AMENDMENT_MS;

  private static void measure(String name, Path root, String route, int warmup, int samples, double ratioLimit, double ceilingMs) {
    try (HttpHarness server = HttpHarness.startWired(root)) {
      int port = server.port();
      // the first call fills the cache of the requested Mission; the warm-up of both routes is discarded
      Latency.timedGet(port, route);
      Latency.run(port, route, CONNECTIONS, warmup);
      Latency.run(port, FLOOR_ROUTE, CONNECTIONS, Math.max(warmup, 30));

      long[] floor = new long[0];
      long[] measured = new long[0];
      for (int round = 0; round < ROUNDS; round++) {
        floor = Latency.concat(floor, Latency.run(port, FLOOR_ROUTE, CONNECTIONS, samples));
        measured = Latency.concat(measured, Latency.run(port, route, CONNECTIONS, samples));
      }
      RatioBudget.Outcome outcome = RatioBudget.evaluate(name, Latency.p95Ms(measured), Latency.p95Ms(floor), ratioLimit, ceilingMs, "ms", hint());
      System.out.println("PERF " + outcome.line() + " [" + measured.length + " samples each, " + CONNECTIONS + " connections, " + PerfBudgets.NFR001_MISSIONS + " Missions]; " + hint());
    }
  }

  @Test
  void getMissionOfAFortyWorkPackageMissionIsWithinTheRatioToTheNoOpRouteAndUnderTheCeiling() {
    measure("NFR-001 getMission (40 Work Packages) p95", MissionCorpus.writeDetail(PerfBudgets.NFR001_MISSIONS, MissionCorpus.DetailShape.FORTY_WORK_PACKAGES), BASE, 30, 100, GET_MISSION_RATIO_LIMIT, GET_MISSION_CEILING_MS);
  }

  @Test
  void getWorkPackageDetailIsWithinTheRatioToTheNoOpRouteAndUnderTheCeiling() {
    measure(
        "NFR-001 getWorkPackageDetail p95",
        MissionCorpus.writeDetail(PerfBudgets.NFR001_MISSIONS, MissionCorpus.DetailShape.FORTY_WORK_PACKAGES),
        BASE + "/work-packages/WP20/detail",
        30,
        100,
        GET_WORK_PACKAGE_DETAIL_RATIO_LIMIT,
        GET_WORK_PACKAGE_DETAIL_CEILING_MS);
  }

  @Test
  void listArtifactsOfAThousandFileMissionIsWithinTheRatioToTheNoOpRouteAndUnderTheCeiling() {
    measure("NFR-001 listArtifacts (1000 files) p95", MissionCorpus.writeDetail(PerfBudgets.NFR001_MISSIONS, MissionCorpus.DetailShape.THOUSAND_FILES), BASE + "/artifacts", 3, 12, LIST_ARTIFACTS_RATIO_LIMIT, LIST_ARTIFACTS_CEILING_MS);
  }

  @Test
  void getArtifactContentOfA262144ByteFileIsWithinTheRatioToTheNoOpRouteAndUnderTheCeiling() {
    measure(
        "NFR-001 getArtifactContent (262144 bytes) p95",
        MissionCorpus.writeDetail(PerfBudgets.NFR001_MISSIONS, MissionCorpus.DetailShape.THOUSAND_FILES),
        BASE + "/artifacts/content?path=" + MissionCorpus.CONTENT_PATH,
        30,
        100,
        GET_ARTIFACT_CONTENT_RATIO_LIMIT,
        GET_ARTIFACT_CONTENT_CEILING_MS);
  }

  // ---- the controls: the budget goes red on a figure that exceeds it ---------------------------------------------------------------

  @Test
  void controlAFigureOverTheRatioIsRedEvenUnderTheCeiling() {
    org.junit.jupiter.api.Assertions.assertThrows(AssertionError.class, () -> RatioBudget.evaluate("control", GET_MISSION_CEILING_MS - 1, 1.0, GET_MISSION_RATIO_LIMIT, GET_MISSION_CEILING_MS, "ms", hint()));
  }

  @Test
  void controlAFigureOverTheCeilingIsRedEvenWithinTheRatio() {
    org.junit.jupiter.api.Assertions.assertThrows(AssertionError.class, () -> RatioBudget.evaluate("control", GET_MISSION_CEILING_MS + 1, 1_000.0, GET_MISSION_RATIO_LIMIT, GET_MISSION_CEILING_MS, "ms", hint()));
  }

  @Test
  void controlTheSpecFiguresAreThoseOfTheSpec() {
    assertThat(new double[] {GET_MISSION_CEILING_MS, GET_WORK_PACKAGE_DETAIL_CEILING_MS, LIST_ARTIFACTS_CEILING_MS, GET_ARTIFACT_CONTENT_SPEC_MS}).containsExactly(100, 100, 1_500, 100);
  }

  // Every ceiling is its spec figure or a documented amendment not below it. The only amendment is getArtifactContent, at exactly 250 ms.
  @Test
  void controlEveryCeilingIsItsSpecFigureOrADocumentedAmendment() {
    assertThat(GET_MISSION_CEILING_MS).as("getMission ceiling").isEqualTo(100);
    assertThat(GET_WORK_PACKAGE_DETAIL_CEILING_MS).as("getWorkPackageDetail ceiling").isEqualTo(100);
    assertThat(LIST_ARTIFACTS_CEILING_MS).as("listArtifacts ceiling").isEqualTo(1_500);
    assertThat(GET_ARTIFACT_CONTENT_CEILING_AMENDMENT_MS).as("getArtifactContent amendment").isEqualTo(250).isGreaterThanOrEqualTo(GET_ARTIFACT_CONTENT_SPEC_MS);
    assertThat(GET_ARTIFACT_CONTENT_CEILING_MS).as("getArtifactContent ceiling is the amendment").isEqualTo(GET_ARTIFACT_CONTENT_CEILING_AMENDMENT_MS);
  }

  private static String hint() {
    return String.format(
        Locale.ROOT,
        "%d cpus, load %.2f, %d platform threads",
        Runtime.getRuntime().availableProcessors(),
        ManagementFactory.getOperatingSystemMXBean().getSystemLoadAverage(),
        ManagementFactory.getThreadMXBean().getThreadCount());
  }
}
