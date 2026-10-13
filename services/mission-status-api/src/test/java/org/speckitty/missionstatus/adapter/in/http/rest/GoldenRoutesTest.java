package org.speckitty.missionstatus.adapter.in.http.rest;

import static org.assertj.core.api.Assertions.assertThat;

import java.nio.charset.StandardCharsets;
import java.util.stream.Stream;
import org.junit.jupiter.params.ParameterizedTest;
import org.junit.jupiter.params.provider.MethodSource;
import org.speckitty.missionstatus.domain.model.DiagnosticCode;
import org.speckitty.missionstatus.testsupport.CanonicalJson;
import org.speckitty.missionstatus.testsupport.ConformanceTree;
import org.speckitty.missionstatus.testsupport.ConformanceTree.TreeFixture;
import org.speckitty.missionstatus.testsupport.FilesystemFixtureFactory;
import org.speckitty.missionstatus.testsupport.GoldenComparison;
import org.speckitty.missionstatus.testsupport.http.HttpHarness;

/**
 * AC-1a, AC-2a over HTTP and NFR-005: for every python-golden fixture the RAW body of the two JSON routes equals the committed golden
 * byte for byte, or is the refusal the golden records (status 500, code by the Python exception class), with the documented
 * divergences applied exactly as the port-level golden suite applies them.
 */
class GoldenRoutesTest {

  static Stream<TreeFixture> fixtures() {
    return ConformanceTree.fixtures().stream()
        .filter(f -> f.parity().equals(ConformanceTree.PARITY_GOLDEN))
        .filter(f -> !f.javaOnly())
        .filter(f -> !f.knownDivergence());
  }

  @ParameterizedTest(name = "{0}")
  @MethodSource("fixtures")
  void bothRoutesServeTheGoldenBytesOrTheRecordedRefusal(TreeFixture fixture) {
    FilesystemFixtureFactory.Built built = FilesystemFixtureFactory.fromTreeRecording(fixture.dir());
    try (HttpHarness server = HttpHarness.start(built)) {
      for (String file : new String[] {ConformanceTree.PROJECT_GOLDEN, ConformanceTree.MISSIONS_GOLDEN}) {
        String path = file.equals(ConformanceTree.PROJECT_GOLDEN) ? "/api/v1/project" : "/api/v1/missions?pageSize=" + GoldenComparison.GOLDEN_PAGE_SIZE;
        byte[] golden = ConformanceTree.golden(fixture, file);
        HttpHarness.Response response = server.get(path);
        String exception = GoldenComparison.refusalException(golden);
        GoldenComparison.Divergence divergence = GoldenComparison.REPORTED_DIVERGENCES.get(fixture.key() + "#" + file);
        if (exception != null || (divergence != null && divergence.refusal() != null)) {
          DiagnosticCode code = divergence != null && divergence.refusal() != null ? divergence.refusal() : refusalCode(fixture, exception);
          RouteSupport.assertProblem(response, 500, code.wire(), built);
          continue;
        }
        byte[] expected = golden;
        if (divergence != null) {
          expected = new String(golden, StandardCharsets.UTF_8).replace(divergence.goldenText(), divergence.javaText()).getBytes(StandardCharsets.UTF_8);
        }
        assertThat(response.status()).as(fixture.key() + " " + file).isEqualTo(200);
        assertThat(response.header("Content-Type")).startsWith("application/json");
        CanonicalJson.assertBodyEqualsGolden(response.body(), expected);
      }
    }
    assertThat(built.handles().allowlistViolations()).isEmpty();
  }

  /** The code the Java side answers where Python raised the named exception class (the port-level suite's mapping). */
  private static DiagnosticCode refusalCode(TreeFixture fixture, String exception) {
    if (fixture.key().equals("torn-final-line/unparseable-final-line")) {
      return DiagnosticCode.LEDGER_TORN_TAIL;
    }
    return switch (exception) {
      case "StoreError", "DiaryError", "JSONDecodeError", "UnicodeDecodeError" -> DiagnosticCode.LEDGER_UNPARSEABLE;
      case "ValueError", "MissionMetaReadError" -> DiagnosticCode.META_UNPARSEABLE;
      case "ProjectionError" -> DiagnosticCode.PROJECTION_REFUSED;
      default -> throw new AssertionError(fixture.key() + ": unmapped exception " + exception);
    };
  }
}
