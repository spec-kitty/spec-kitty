package org.speckitty.missionstatus.application.query.portlegs;

import static org.assertj.core.api.Assertions.assertThat;
import static org.assertj.core.api.Assertions.assertThatThrownBy;

import java.lang.reflect.Constructor;
import java.lang.reflect.InvocationTargetException;
import java.lang.reflect.Proxy;
import org.junit.jupiter.api.Test;
import org.speckitty.missionstatus.adapter.in.http.detail.WorkPackageControllerRowsTest;
import org.speckitty.missionstatus.application.query.port.in.WorkPackageQuery;
import org.speckitty.missionstatus.application.query.port.in.exceptions.DetailRefusal;
import org.speckitty.missionstatus.domain.model.Lane;
import org.speckitty.missionstatus.domain.readmodel.detail.WorkPackageView;
import org.speckitty.missionstatus.testsupport.ConformanceTree;
import org.speckitty.missionstatus.testsupport.DetailFixture;
import org.speckitty.missionstatus.testsupport.PlainCaller;
import org.speckitty.missionstatus.testsupport.Rows;
import org.speckitty.missionstatus.conformance.golden.served.WorkPackageServedRoute;

/**
 * FR-013, AC-13.3: the second adapter. {@code getWorkPackage} is driven through the plain-Java caller of the inbound ports, with no Spring
 * context and no HTTP: a populated Work Package gives the typed result with {@code includePrompt} true and false and carries the prompt only
 * in the first, an unknown Work Package is the typed {@code not_found}, and an ill-formed identifier is {@code not_found} before the port is
 * called. These legs live outside {@code conformance.port} and are not in {@code portlevel-tests.txt}: the selector fixture of that subset
 * carries only the Mission status port and cannot carry a detail port (TASKS-GREEN-001). The other three inbound ports of the caller belong
 * to other routes and are stubbed by their reflected types, so this class names only {@link WorkPackageQuery}.
 */
class WorkPackagePortLegsTest {

  private static PlainCaller caller(WorkPackageQuery workPackages) {
    try {
      Constructor<?> constructor = PlainCaller.class.getConstructors()[0];
      Class<?>[] types = constructor.getParameterTypes();
      Object[] arguments = new Object[types.length];
      for (int i = 0; i < types.length; i++) {
        Class<?> type = types[i];
        arguments[i] = type == WorkPackageQuery.class ? workPackages : Proxy.newProxyInstance(type.getClassLoader(), new Class<?>[] {type}, (proxy, method, args) -> {
          throw new UnsupportedOperationException("another route");
        });
      }
      return (PlainCaller) constructor.newInstance(arguments);
    } catch (InstantiationException | IllegalAccessException | InvocationTargetException failure) {
      throw new IllegalStateException(failure);
    }
  }

  private static DetailFixture populated() {
    return DetailFixture.of(ConformanceTree.detailFixtures().stream().filter(fixture -> fixture.key().equals("wp-prompt-bytes/crlf")).findFirst().orElseThrow().dir());
  }

  private static String missionId() {
    return WorkPackageServedRoute.missionIdOf(WorkPackageServedRoute.fixture("wp-prompt-bytes/crlf"));
  }

  private static String wpId() {
    return WorkPackageServedRoute.requestKeys(WorkPackageServedRoute.fixture("wp-prompt-bytes/crlf"), WorkPackageServedRoute.GOLDEN).get(0);
  }

  @Test
  void aPopulatedWorkPackageGivesTheTypedResultAndThePromptOnlyWhenAsked() {
    DetailFixture fixture = populated();
    PlainCaller caller = caller(WorkPackageControllerRowsTest.serviceOver(fixture));

    WorkPackageView without = caller.workPackage(missionId(), wpId(), false);
    WorkPackageView with = caller.workPackage(missionId(), wpId(), true);

    assertThat(without.wpId().value()).isEqualTo(wpId());
    assertThat(without.promptMarkdown()).isNull();
    assertThat(with.wpId()).isEqualTo(without.wpId());
    assertThat(with.promptMarkdown()).isNotNull().isNotEmpty();
    assertThat(with.title()).isEqualTo(without.title());
    assertThat(without.statusLane()).isInstanceOf(Lane.class);
    assertThat(fixture.diagnostics()).isEmpty();
  }

  @Test
  void anUnknownWorkPackageAndAnUnknownMissionAreNotFoundWithTheTypedRefusal() {
    PlainCaller caller = caller(WorkPackageControllerRowsTest.serviceOver(populated()));

    assertThatThrownBy(() -> caller.workPackage(missionId(), "WP99", false)).isInstanceOfSatisfying(DetailRefusal.class, WorkPackagePortLegsTest::isNotFound);
    assertThatThrownBy(() -> caller.workPackage(Rows.GAMMA_ID, wpId(), true)).isInstanceOfSatisfying(DetailRefusal.class, WorkPackagePortLegsTest::isNotFound);
  }

  @Test
  void anIllFormedIdentifierIsNotFoundBeforeThePortIsCalled() {
    int[] calls = {0};
    PlainCaller caller =
        caller(
            (mission, wp, includePrompt) -> {
              calls[0]++;
              throw DetailRefusal.notFound();
            });

    for (String wp : new String[] {"wp01", "WP1", "WP01x", "", "WP" + "0".repeat(70)}) {
      assertThatThrownBy(() -> caller.workPackage(missionId(), wp, true)).as(wp).isInstanceOfSatisfying(DetailRefusal.class, WorkPackagePortLegsTest::isNotFound);
    }
    assertThatThrownBy(() -> caller.workPackage("not-a-ulid", wpId(), false)).isInstanceOfSatisfying(DetailRefusal.class, WorkPackagePortLegsTest::isNotFound);
    assertThat(calls[0]).isZero();
  }

  private static void isNotFound(DetailRefusal refusal) {
    assertThat(refusal.kind()).isEqualTo(DetailRefusal.Kind.NOT_FOUND);
  }
}
