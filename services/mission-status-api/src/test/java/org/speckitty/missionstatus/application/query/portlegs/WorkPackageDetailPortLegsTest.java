package org.speckitty.missionstatus.application.query.portlegs;

import static org.assertj.core.api.Assertions.assertThat;
import static org.assertj.core.api.Assertions.assertThatThrownBy;

import java.lang.reflect.Constructor;
import java.lang.reflect.InvocationTargetException;
import java.lang.reflect.Proxy;
import org.junit.jupiter.api.Test;
import org.speckitty.missionstatus.application.query.detail.DetailRoute;
import org.speckitty.missionstatus.application.query.port.in.WorkPackageDetailQuery;
import org.speckitty.missionstatus.application.query.port.in.exceptions.DetailRefusal;
import org.speckitty.missionstatus.application.query.port.in.exceptions.MissionStatusUnavailable;
import org.speckitty.missionstatus.conformance.golden.served.WorkPackageDetailServedRoute;
import org.speckitty.missionstatus.domain.model.DiagnosticCode;
import org.speckitty.missionstatus.domain.readmodel.detail.WorkPackageDetail;
import org.speckitty.missionstatus.testsupport.ConformanceTree;
import org.speckitty.missionstatus.testsupport.DetailFixture;
import org.speckitty.missionstatus.testsupport.PlainCaller;

/**
 * FR-013, AC-13.3: the second adapter. The port is obtained through the plain-Java caller of the inbound ports, with no Spring context and no
 * HTTP: a populated fixture gives the typed result, an unknown or ill-formed id is {@code not_found} before the port is called, and a corrupt
 * {@code lanes.json} is {@link MissionStatusUnavailable} carrying {@code source_unreadable}. These legs live outside {@code conformance.port} and
 * are not in {@code portlevel-tests.txt}: the selector fixture of that subset carries only the Mission status port and cannot carry a detail
 * port (TASKS-GREEN-001). The other three inbound ports of the caller belong to other routes and are stubbed here by their reflected types, so
 * this class names only {@link WorkPackageDetailQuery}.
 */
class WorkPackageDetailPortLegsTest {

  private static PlainCaller caller(WorkPackageDetailQuery details) {
    try {
      Constructor<?> constructor = PlainCaller.class.getConstructors()[0];
      Class<?>[] types = constructor.getParameterTypes();
      Object[] arguments = new Object[types.length];
      for (int i = 0; i < types.length; i++) {
        Class<?> type = types[i];
        arguments[i] = type == WorkPackageDetailQuery.class ? details : Proxy.newProxyInstance(type.getClassLoader(), new Class<?>[] {type}, (proxy, method, args) -> {
          throw new UnsupportedOperationException("another route");
        });
      }
      return (PlainCaller) constructor.newInstance(arguments);
    } catch (InstantiationException | IllegalAccessException | InvocationTargetException failure) {
      throw new IllegalStateException(failure);
    }
  }

  private static final String POPULATED = "detail-populated/populated";

  private static DetailFixture populated() {
    return DetailFixture.of(ConformanceTree.detailFixtures().stream().filter(fixture -> fixture.key().equals(POPULATED)).findFirst().orElseThrow().dir());
  }

  private static String id() {
    return WorkPackageDetailServedRoute.missionIdOf(WorkPackageDetailServedRoute.fixture(POPULATED));
  }

  @Test
  void aPopulatedFixtureGivesTheTypedResult() {
    DetailFixture fixture = populated();
    PlainCaller caller = caller(DetailRoute.serviceOver(fixture));

    WorkPackageDetail detail = caller.workPackageDetail(id(), "WP02");

    assertThat(detail.missionId().value()).isEqualTo(id());
    assertThat(detail.wpId().value()).isEqualTo("WP02");
    assertThat(detail.dependencies()).extracting(entry -> entry.title()).containsExactly("Foundation");
    assertThat(detail.ownedFiles()).extracting(entry -> entry.pattern()).containsExactly("src/feature/*.py");
    assertThat(fixture.diagnostics()).isEmpty();
  }

  @Test
  void anUnknownWorkPackageAnUnknownMissionAndAnIllFormedIdAreNotFoundWithTheTypedRefusal() {
    PlainCaller caller = caller(DetailRoute.serviceOver(populated()));

    for (String[] asked : new String[][] {{id(), "WP99"}, {"01J03000000000000000000003", "WP01"}, {"alpha", "WP01"}, {id(), "wp01"}, {id(), "WP1"}, {id(), ""}, {"", "WP01"}}) {
      assertThatThrownBy(() -> caller.workPackageDetail(asked[0], asked[1]))
          .as(asked[0] + " " + asked[1])
          .isInstanceOfSatisfying(DetailRefusal.class, refusal -> assertThat(refusal.kind()).isEqualTo(DetailRefusal.Kind.NOT_FOUND));
    }
  }

  @Test
  void aCorruptLanesJsonCarriesSourceUnreadable() {
    DetailFixture fixture = DetailRoute.fixture(root -> DetailRoute.write(root, "lanes.json", "{not json"));
    PlainCaller caller = caller(DetailRoute.serviceOver(fixture));

    assertThatThrownBy(() -> caller.workPackageDetail(DetailRoute.ID, "WP01"))
        .isInstanceOfSatisfying(MissionStatusUnavailable.class, unavailable -> assertThat(unavailable.code()).isEqualTo(DiagnosticCode.SOURCE_UNREADABLE));
  }
}
