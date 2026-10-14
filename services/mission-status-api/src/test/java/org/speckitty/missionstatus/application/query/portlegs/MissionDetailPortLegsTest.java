package org.speckitty.missionstatus.application.query.portlegs;

import static org.assertj.core.api.Assertions.assertThat;
import static org.assertj.core.api.Assertions.assertThatThrownBy;

import java.lang.reflect.Constructor;
import java.lang.reflect.InvocationTargetException;
import java.lang.reflect.Proxy;
import java.nio.file.AccessDeniedException;
import org.junit.jupiter.api.Test;
import org.speckitty.missionstatus.adapter.out.filesystem.Allowlist.OpenMode;
import org.speckitty.missionstatus.adapter.out.filesystem.Allowlist.PathClass;
import org.speckitty.missionstatus.application.query.port.in.MissionDetailQuery;
import org.speckitty.missionstatus.application.query.port.in.exceptions.DetailRefusal;
import org.speckitty.missionstatus.application.query.port.in.exceptions.MissionStatusUnavailable;
import org.speckitty.missionstatus.adapter.in.http.detail.MissionDetailRowsTest;
import org.speckitty.missionstatus.conformance.golden.served.MissionDetailServedRoute;
import org.speckitty.missionstatus.domain.model.DiagnosticCode;
import org.speckitty.missionstatus.domain.readmodel.detail.MissionDetail;
import org.speckitty.missionstatus.domain.readmodel.detail.PhaseName;
import org.speckitty.missionstatus.testsupport.ConformanceTree;
import org.speckitty.missionstatus.testsupport.DetailFixture;
import org.speckitty.missionstatus.testsupport.FixtureSpec;
import org.speckitty.missionstatus.testsupport.PlainCaller;
import org.speckitty.missionstatus.testsupport.PortFixtures;
import org.speckitty.missionstatus.testsupport.Rows;

/**
 * FR-013, AC-13.3: the second adapter. The port is obtained through the plain-Java caller of the inbound ports, with no Spring context and no
 * HTTP: a populated fixture gives the typed result, an unknown or ill-formed id is {@code not_found} before the port is called, and a row of
 * the failure table is {@link MissionStatusUnavailable} carrying the diagnostic code. These legs live outside {@code conformance.port}
 * and are not in {@code portlevel-tests.txt}: the selector fixture of that subset carries only the Mission status port and cannot carry a
 * detail port. The other three inbound ports of the caller belong to later routes and are stubbed here by their reflected types, so this
 * class names only {@link MissionDetailQuery}.
 */
class MissionDetailPortLegsTest {

  private static PlainCaller caller(MissionDetailQuery missions) {
    try {
      Constructor<?> constructor = PlainCaller.class.getConstructors()[0];
      Class<?>[] types = constructor.getParameterTypes();
      Object[] arguments = new Object[types.length];
      for (int i = 0; i < types.length; i++) {
        Class<?> type = types[i];
        arguments[i] = type == MissionDetailQuery.class ? missions : Proxy.newProxyInstance(type.getClassLoader(), new Class<?>[] {type}, (proxy, method, args) -> {
          throw new UnsupportedOperationException("a later route");
        });
      }
      return (PlainCaller) constructor.newInstance(arguments);
    } catch (InstantiationException | IllegalAccessException | InvocationTargetException failure) {
      throw new IllegalStateException(failure);
    }
  }

  private static DetailFixture populated() {
    return DetailFixture.of(ConformanceTree.detailFixtures().stream().filter(fixture -> fixture.key().equals("detail-populated/populated")).findFirst().orElseThrow().dir());
  }

  @Test
  void aPopulatedFixtureGivesTheTypedResult() {
    DetailFixture fixture = populated();
    PlainCaller caller = caller(MissionDetailRowsTest.serviceOver(fixture));
    String id = MissionDetailServedRoute.missionIdOf(ConformanceTree.detailFixtures().stream().filter(candidate -> candidate.key().equals("detail-populated/populated")).findFirst().orElseThrow());

    MissionDetail detail = caller.mission(id);

    assertThat(detail.overview().missionId().value()).isEqualTo(id);
    assertThat(detail.phases()).extracting(phase -> phase.name()).containsExactly(PhaseName.values());
    assertThat(detail.workPackages()).isNotEmpty();
    assertThat(fixture.diagnostics()).isEmpty();
  }

  @Test
  void anUnknownIdAndAnIllFormedIdAreNotFoundWithTheTypedRefusal() {
    PlainCaller caller = caller(MissionDetailRowsTest.serviceOver(populated()));

    for (String asked : new String[] {Rows.GAMMA_ID, "01J01000", "alpha", "7", "01j01000000000000000000001"}) {
      assertThatThrownBy(() -> caller.mission(asked)).as(asked).isInstanceOfSatisfying(DetailRefusal.class, refusal -> assertThat(refusal.kind()).isEqualTo(DetailRefusal.Kind.NOT_FOUND));
    }
  }

  @Test
  void aLedgerThatCannotBeDecodedCarriesItsDiagnosticCode() {
    DetailFixture fixture = MissionDetailServedRoute.fixtureOf(FixtureSpec.of(PortFixtures.mission("alpha", Rows.ALPHA_ID, "2026-09-01T10:00:00+00:00", "this is not json\n")), root -> {});

    assertThatThrownBy(() -> caller(MissionDetailRowsTest.serviceOver(fixture)).mission(Rows.ALPHA_ID))
        .isInstanceOfSatisfying(MissionStatusUnavailable.class, unavailable -> assertThat(unavailable.code()).isEqualTo(DiagnosticCode.LEDGER_UNPARSEABLE));
  }

  @Test
  void aTasksDirectoryThatCannotBeListedCarriesSourceUnreadable() {
    DetailFixture fixture =
        MissionDetailServedRoute.fixtureOf(
            FixtureSpec.of(PortFixtures.mission("alpha", Rows.ALPHA_ID, "2026-09-01T10:00:00+00:00", Rows.status(Rows.id(1), "2026-09-01T10:01:00Z", "WP01", "planned", "claimed"))),
            root -> MissionDetailServedRoute.write(root, "alpha", "tasks/WP01-one.md", MissionDetailServedRoute.workPackageFile("WP01", "One")));
    fixture.recorder().failWhen(access -> access.pathClass() == PathClass.TASKS_DIR && access.mode() == OpenMode.LIST, () -> new AccessDeniedException("injected"));

    assertThatThrownBy(() -> caller(MissionDetailRowsTest.serviceOver(fixture)).mission(Rows.ALPHA_ID))
        .isInstanceOfSatisfying(MissionStatusUnavailable.class, unavailable -> assertThat(unavailable.code()).isEqualTo(DiagnosticCode.SOURCE_UNREADABLE));
  }
}
