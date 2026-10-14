package org.speckitty.missionstatus.architecture;

import static org.assertj.core.api.Assertions.assertThat;
import static org.assertj.core.api.Assertions.assertThatThrownBy;

import com.tngtech.archunit.core.domain.JavaClass;
import com.tngtech.archunit.core.domain.JavaClasses;
import java.lang.reflect.Constructor;
import java.lang.reflect.Method;
import java.lang.reflect.Modifier;
import java.time.Clock;
import java.util.Arrays;
import java.util.List;
import java.util.Set;
import java.util.concurrent.ScheduledExecutorService;
import java.util.function.Consumer;
import java.util.stream.Collectors;
import java.util.stream.StreamSupport;
import org.junit.jupiter.api.Test;
import org.speckitty.missionstatus.adapter.out.filesystem.Allowlist;
import org.speckitty.missionstatus.adapter.out.filesystem.AllowlistAccess;
import org.speckitty.missionstatus.application.query.MissionReadModel;
import org.speckitty.missionstatus.application.query.MissionStatusQueryService;
import org.speckitty.missionstatus.application.query.port.out.MissionEventSource;
import org.speckitty.missionstatus.application.query.port.out.exceptions.SourceFault;
import org.speckitty.missionstatus.application.query.stream.StreamSettings;
import org.speckitty.missionstatus.domain.model.DiagnosticCode;
import org.speckitty.missionstatus.domain.redaction.LeakClasses;

/**
 * The shape of the symbols this mission couples to (C-005, D-107), written against the layout table of plan section 1.1. Every class is
 * loaded by its new name, every checkout (flat) name must not load, and the facts the plan relies on are pinned: the package-private
 * {@code ProjectionCache}, the two constructors of the service, the five {@code SourceFault} kinds. What this mission raises is pinned
 * with lower bounds and presence only (D-117), so the test stays green after the phases that extend those sets.
 */
class CoupledSymbolsShapeTest {

  private static final String ROOT = "org.speckitty.missionstatus.";

  /** Rows 1 to 11 of the mapping table, by their new names. */
  private static final List<String> NEW_NAMES =
      List.of(
          "application.query.MissionStatusQueryService",
          "application.query.ProjectionCache",
          "application.query.stream.ChangeFeed",
          "application.query.stream.StreamSubscriber",
          "application.query.stream.Resume",
          "application.query.stream.StreamSettings",
          "application.query.port.in.MissionStatusQuery",
          "application.query.port.in.Subscription",
          "application.query.stream.Change",
          "application.query.stream.ChangeBatch",
          "application.query.port.in.dto.Closure",
          "application.query.port.in.dto.PageRequest",
          "application.query.port.in.dto.StreamCursorText",
          "application.query.port.in.dto.StreamScope",
          "application.query.port.in.dto.StreamSignal",
          "application.query.port.in.dto.StreamEvent",
          "application.query.port.in.dto.StreamBatch",
          "application.query.port.in.dto.StreamRequest",
          "application.query.port.in.exceptions.MissionStatusUnavailable",
          "application.query.port.in.exceptions.StreamRefused",
          "application.query.port.in.exceptions.StreamCapacityReached",
          "application.query.stream.EventProjection",
          "application.query.stream.ProjectedSubscription",
          "application.query.stream.StreamAdmission",
          "application.query.stream.FeedSignal",
          "application.query.stream.FeedSubscription",
          "application.query.port.out.MissionEventSource",
          "application.query.port.out.dto.LedgerRead",
          "application.query.port.out.dto.LedgerStamp",
          "application.query.port.out.dto.LedgerWindow",
          "application.query.port.out.dto.MissionRef",
          "application.query.port.out.dto.ProjectInputs",
          "application.query.port.out.exceptions.SourceFault",
          "domain.readmodel.overview.OverviewDeriver",
          "domain.readmodel.reducer.StatusReducer",
          "domain.readmodel.paging.Pager",
          "domain.readmodel.cursor.StreamCursor",
          "domain.redaction.LeakClasses",
          "domain.redaction.Projector",
          "domain.redaction.ProjectionError");

  /** The checkout (flat) names of the same rows: none may load any more. */
  private static final List<String> CHECKOUT_NAMES =
      List.of(
          "application.MissionStatusService",
          "application.ProjectionCache",
          "application.ChangeFeed",
          "application.StreamSubscriber",
          "application.Resume",
          "application.StreamSettings",
          "application.port.in.MissionStatusQuery",
          "application.port.in.Subscription",
          "application.port.in.Change",
          "application.port.in.StreamSignal",
          "application.port.in.MissionStatusUnavailable",
          "application.port.in.StreamRefused",
          "application.port.out.MissionEventSource",
          "application.port.out.LedgerStamp",
          "application.port.out.MissionRef",
          "application.port.out.SourceFault",
          "domain.overview.OverviewDeriver",
          "domain.reducer.StatusReducer",
          "domain.paging.Pager",
          "domain.cursor.StreamCursor",
          "domain.projection.LeakClasses",
          "domain.projection.Projector",
          "domain.projection.ProjectionError");

  private static Class<?> load(String name) throws ClassNotFoundException {
    return Class.forName(ROOT + name);
  }

  @Test
  void everyCoupledSymbolLoadsByItsNewName() {
    for (String name : NEW_NAMES) {
      assertThat(isLoadable(name)).as("%s loads", name).isTrue();
    }
  }

  @Test
  void noCheckoutNameLoadsAnyMore() {
    for (String name : CHECKOUT_NAMES) {
      assertThatThrownBy(() -> load(name)).as("%s must not load", name).isInstanceOf(ClassNotFoundException.class);
    }
  }

  private static boolean isLoadable(String name) {
    try {
      load(name);
      return true;
    } catch (ClassNotFoundException absent) {
      return false;
    }
  }

  @Test
  void theProjectionCacheIsPackagePrivate() throws ClassNotFoundException {
    assertThat(Modifier.isPublic(load("application.query.ProjectionCache").getModifiers())).isFalse();
  }

  @Test
  void theServiceKeepsItsPublicSixArgumentAndPackagePrivateSevenArgumentConstructors() throws Exception {
    Class<?> cache = load("application.query.ProjectionCache");
    Constructor<?> six =
        MissionStatusQueryService.class.getDeclaredConstructor(MissionEventSource.class, Clock.class, Consumer.class, ScheduledExecutorService.class, StreamSettings.class, LeakClasses.class);
    Constructor<?> seven =
        MissionStatusQueryService.class.getDeclaredConstructor(
            MissionEventSource.class, Clock.class, Consumer.class, ScheduledExecutorService.class, StreamSettings.class, LeakClasses.class, cache);

    assertThat(Modifier.isPublic(six.getModifiers())).as("six-argument constructor is public").isTrue();
    assertThat(Modifier.isPublic(seven.getModifiers()) || Modifier.isProtected(seven.getModifiers()) || Modifier.isPrivate(seven.getModifiers()))
        .as("seven-argument constructor is package-private")
        .isFalse();
  }

  @Test
  void theReadModelHasAPublicConstructorThatBuildsItsOwnCacheAndAPackagePrivateOneThatTakesACache() throws Exception {
    Class<?> cache = load("application.query.ProjectionCache");
    Constructor<?> own = MissionReadModel.class.getDeclaredConstructor(MissionEventSource.class, Consumer.class, LeakClasses.class);
    Constructor<?> given = MissionReadModel.class.getDeclaredConstructor(MissionEventSource.class, Consumer.class, LeakClasses.class, cache);

    assertThat(Modifier.isPublic(MissionReadModel.class.getModifiers())).isTrue();
    assertThat(Modifier.isPublic(own.getModifiers())).isTrue();
    assertThat(Modifier.isPublic(given.getModifiers())).isFalse();
    assertThat(Modifier.isPrivate(given.getModifiers()) || Modifier.isProtected(given.getModifiers())).isFalse();
  }

  @Test
  void theFixtureFactoryReflectsTheProjectionCacheByTheNameThisTestPins() throws Exception {
    // FilesystemFixtureFactory#fromTreeWithOrdering loads this literal; if the class moves, that reflection (AC-8a) breaks silently at run time.
    assertThat(load("application.query.ProjectionCache").getName()).isEqualTo("org.speckitty.missionstatus.application.query.ProjectionCache");
    String factory = java.nio.file.Files.readString(java.nio.file.Path.of("src/test/java/org/speckitty/missionstatus/testsupport/FilesystemFixtureFactory.java"));
    assertThat(factory).contains("\"org.speckitty.missionstatus.application.query.ProjectionCache\"");
  }

  @Test
  void sourceFaultHasExactlyFiveKinds() {
    assertThat(SourceFault.Kind.values()).hasSize(5);
  }

  @Test
  void allowlistAccessDeclaresTheFourReadMethods() {
    Set<String> names = Arrays.stream(AllowlistAccess.class.getDeclaredMethods()).map(Method::getName).collect(Collectors.toSet());

    assertThat(names).contains("openRead", "stat", "realPath", "listNames");
  }

  @Test
  void theSetsThisMissionExtendsHaveLowerBoundsOnly() {
    assertThat(Allowlist.PathClass.values().length).isGreaterThanOrEqualTo(15);
    assertThat(Allowlist.ENTRIES.size()).isGreaterThanOrEqualTo(11);
    assertThat(DiagnosticCode.values().length).isGreaterThanOrEqualTo(8);
    assertThat(ArchitectureRules.DEFINED_RULE_COUNT).isGreaterThanOrEqualTo(12);
  }

  @Test
  void theStreamSymbolsHaveTheirPostRulingShape() throws Exception {
    // operator ruling A3: the raw feed is application-internal and the port speaks projected events only (lower bounds and presence)
    assertThat(load("application.query.stream.Change").isRecord()).isTrue();
    assertThat(load("application.query.stream.ChangeBatch").isRecord()).isTrue();
    assertThatThrownBy(() -> load("application.query.port.in.dto.Change")).isInstanceOf(ClassNotFoundException.class);
    assertThatThrownBy(() -> load("application.query.port.in.dto.ChangeBatch")).isInstanceOf(ClassNotFoundException.class);
    List<String> feedSignals = Arrays.stream(load("application.query.stream.FeedSignal").getDeclaredClasses()).map(Class::getSimpleName).toList();
    assertThat(feedSignals).contains("Forwarded", "Truncated", "Dropped", "Closed", "Idle");
    List<String> signals = Arrays.stream(load("application.query.port.in.dto.StreamSignal").getDeclaredClasses()).map(Class::getSimpleName).toList();
    assertThat(signals).contains("Events", "Dropped", "Closed", "Idle");
    List<String> events = Arrays.stream(load("application.query.port.in.dto.StreamEvent").getDeclaredClasses()).map(Class::getSimpleName).toList();
    assertThat(events).contains("StatusTransition", "Lifecycle", "LogTruncated", "ActorHandles");
    assertThat(Arrays.stream(load("application.query.port.in.MissionStatusQuery").getDeclaredMethods()).map(Method::getName)).contains("endStreams", "changesSince", "subscribe");
    assertThat(Arrays.stream(load("application.query.stream.StreamSettings").getRecordComponents()).map(component -> component.getName())).contains("maxConnections");
  }

  @Test
  void everyProductionClassSitsUnderAdapterApplicationConfigOrDomain() {
    JavaClasses main = ArchitectureRules.mainClasses();
    List<String> stray =
        StreamSupport.stream(main.spliterator(), false)
            .map(JavaClass::getPackageName)
            .filter(name -> name.startsWith("org.speckitty.missionstatus"))
            .filter(name -> List.of("adapter", "application", "config", "domain").stream().noneMatch(top -> name.equals(ROOT + top) || name.startsWith(ROOT + top + ".")))
            .distinct()
            .toList();

    assertThat(StreamSupport.stream(main.spliterator(), false).count()).isGreaterThan(0);
    assertThat(stray).as("production packages outside the four top-level packages").isEmpty();
  }
}
