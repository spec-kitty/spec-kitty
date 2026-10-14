package org.speckitty.missionstatus.testsupport.http;

import static org.assertj.core.api.Assertions.assertThat;
import static org.assertj.core.api.Assertions.assertThatThrownBy;

import java.util.Map;
import org.junit.jupiter.api.Test;
import org.speckitty.missionstatus.adapter.out.filesystem.Allowlist.OpenMode;
import org.speckitty.missionstatus.application.query.port.in.MissionStatusQuery;
import org.speckitty.missionstatus.testsupport.ConformanceTree;
import org.speckitty.missionstatus.testsupport.FilesystemFixtureFactory;
import org.speckitty.missionstatus.testsupport.RouteMarker;

/**
 * {@link HttpHarness#startWith}: the production application over a fixture-built service with extra inbound beans registered as primary
 * under a plain {@code Class<?>} key. The harness and this test name no inbound interface of a later work package; the stand-in below
 * is declared here.
 */
class HttpHarnessDetailTest {

  /** An inbound seam declared by the test itself. */
  interface StandIn {
    String ping();
  }

  interface OtherStandIn {
    int number();
  }

  private static FilesystemFixtureFactory.Built built() {
    return FilesystemFixtureFactory.fromTreeRecording(ConformanceTree.fixturesOf("interleaved").getFirst().dir());
  }

  @Test
  void aPassedInstanceIsThePrimaryBeanOfTheStartedContextAndTheExistingRoutesStillAnswer() {
    StandIn standIn = () -> "pong";
    try (HttpHarness harness = HttpHarness.startWith(built(), Map.of(StandIn.class, standIn))) {
      assertThat(harness.context().getBean(StandIn.class)).isSameAs(standIn);
      assertThat(harness.context().getBean(StandIn.class).ping()).isEqualTo("pong");
      assertThat(harness.context().getBean(MissionStatusQuery.class)).isNotNull();
      assertThat(harness.get("/api/v1/project").status()).isEqualTo(200);
      assertThat(harness.get("/api/v1/missions").status()).isEqualTo(200);
      assertThat(harness.allowlistRecorder()).isNotNull();
      assertThat(harness.handles()).isNotNull();
    }
  }

  @Test
  void severalInstancesAreRegisteredEachUnderItsOwnKeyAndTheFixturesOwnQueryStaysInThePath() {
    FilesystemFixtureFactory.Built built = built();
    try (HttpHarness harness = HttpHarness.startWith(built, Map.of(StandIn.class, (StandIn) () -> "a", OtherStandIn.class, (OtherStandIn) () -> 7))) {
      assertThat(harness.context().getBean(StandIn.class).ping()).isEqualTo("a");
      assertThat(harness.context().getBean(OtherStandIn.class).number()).isEqualTo(7);
      assertThat(harness.context().getBean(MissionStatusQuery.class)).isSameAs(built.query());
      harness.get("/api/v1/missions");
      assertThat(harness.allowlistRecorder().accesses()).isNotEmpty();
      assertThat(harness.handles().allowlistViolations()).isEmpty();
    }
  }

  @Test
  void anInstanceThatIsNotAnInstanceOfItsKeyIsRefused() {
    assertThatThrownBy(() -> HttpHarness.startWith(built(), Map.of(StandIn.class, "not a stand-in"))).hasStackTraceContaining("Cannot cast");
  }

  @Test
  void aRouteMarkerIsInstalledOnTheRecorderSoTheRequestsCarryTheRoute() {
    RouteMarker marker = RouteMarker.create();
    marker.set("getProject");
    try (HttpHarness harness = HttpHarness.startWith(built(), Map.of(StandIn.class, (StandIn) () -> "x"), marker)) {
      harness.get("/api/v1/project");
      marker.set("listMissions");
      harness.get("/api/v1/missions");

      var reads = harness.allowlistRecorder().scopedAccesses().stream().filter(access -> access.mode() == OpenMode.READ).toList();
      assertThat(reads).extracting(access -> access.route()).contains("getProject", "listMissions");
    }
  }

  @Test
  void theExistingStartersKeepTheirMeaning() {
    FilesystemFixtureFactory.Built built = built();
    try (HttpHarness harness = HttpHarness.start(built)) {
      assertThat(harness.get("/api/v1/project").status()).isEqualTo(200);
      assertThat(harness.context().getBeansOfType(StandIn.class)).isEmpty();
    }
  }
}
