package org.speckitty.missionstatus.testsupport;

import org.speckitty.missionstatus.testsupport.RealPermissionFixture.NotRun;
import static org.assertj.core.api.Assertions.assertThat;
import static org.assertj.core.api.Assertions.assertThatThrownBy;

import java.io.IOException;
import java.lang.reflect.Method;
import java.nio.file.Files;
import java.nio.file.Path;
import java.nio.file.attribute.PosixFilePermission;
import java.util.ArrayList;
import java.util.Collection;
import java.util.EnumMap;
import java.util.List;
import java.util.Map;
import java.util.Set;
import java.util.TreeMap;
import org.junit.jupiter.api.Test;
import org.opentest4j.TestAbortedException;
import org.speckitty.missionstatus.testsupport.PermissionCase.Leg;

/**
 * The coverage function of {@link PermissionCase}, its controls, and the behaviour of {@link RealPermissionFixture}. The function judges the
 * classes it is given; the controls hand it planted test-local classes. There is no floor over production tests here (D-140): the
 * whole-set floor belongs to the work package that owns all the routes, and nothing in this file scans the classpath.
 */
class PermissionCaseCoverageTest {

  // ---- the coverage function -------------------------------------------------------------------------------------------------

  /**
   * The problems of a set of classes: every case id must have exactly one injected-fault leg and exactly one real-permission leg. A
   * method annotation counts once; a class annotation counts once for its class. Empty means covered.
   */
  static List<String> problems(Collection<Class<?>> classes) {
    Map<String, Map<Leg, Integer>> legs = new TreeMap<>();
    for (Class<?> type : classes) {
      count(legs, type.getAnnotation(PermissionCase.class));
      for (Method method : type.getDeclaredMethods()) {
        count(legs, method.getAnnotation(PermissionCase.class));
      }
    }
    List<String> problems = new ArrayList<>();
    legs.forEach(
        (id, byLeg) -> {
          for (Leg leg : Leg.values()) {
            int count = byLeg.getOrDefault(leg, 0);
            if (count == 0) {
              problems.add("case " + id + " has no " + leg + " leg");
            } else if (count > 1) {
              problems.add("case " + id + " has " + count + " " + leg + " legs (duplicate id)");
            }
          }
        });
    return problems;
  }

  private static void count(Map<String, Map<Leg, Integer>> legs, PermissionCase annotation) {
    if (annotation != null) {
      legs.computeIfAbsent(annotation.value(), id -> new EnumMap<>(Leg.class)).merge(annotation.leg(), 1, Integer::sum);
    }
  }

  // ---- planted classes (never run: no @Test) ---------------------------------------------------------------------------------

  static final class Complete {
    @PermissionCase(value = "read-denied", leg = Leg.INJECTED)
    void injected() {}

    @PermissionCase(value = "read-denied", leg = Leg.REAL)
    void real() {}
  }

  static final class OnlyInjected {
    @PermissionCase(value = "list-denied", leg = Leg.INJECTED)
    void injected() {}
  }

  static final class Duplicated {
    @PermissionCase(value = "stat-denied", leg = Leg.INJECTED)
    void first() {}

    @PermissionCase(value = "stat-denied", leg = Leg.INJECTED)
    void second() {}

    @PermissionCase(value = "stat-denied", leg = Leg.REAL)
    void real() {}
  }

  @PermissionCase(value = "split", leg = Leg.INJECTED)
  static final class SplitInjected {}

  @PermissionCase(value = "split", leg = Leg.REAL)
  static final class SplitReal {}

  static final class NoAnnotation {
    void plain() {}
  }

  @Test
  void aCompletePairIsGreen() {
    assertThat(problems(List.of(Complete.class))).isEmpty();
  }

  @Test
  void aMissingLegIsRed() {
    assertThat(problems(List.of(OnlyInjected.class))).containsExactly("case list-denied has no REAL leg");
    assertThat(problems(List.of(Complete.class, OnlyInjected.class))).hasSize(1);
  }

  @Test
  void aDuplicateIdIsRed() {
    assertThat(problems(List.of(Duplicated.class))).containsExactly("case stat-denied has 2 INJECTED legs (duplicate id)");
  }

  @Test
  void theTwoLegsMayLiveInDifferentClassesAndAClassAnnotationCountsOnce() {
    assertThat(problems(List.of(SplitInjected.class, SplitReal.class))).isEmpty();
    assertThat(problems(List.of(SplitInjected.class))).containsExactly("case split has no REAL leg");
    assertThat(problems(List.of(SplitInjected.class, SplitInjected.class))).contains("case split has 2 INJECTED legs (duplicate id)");
  }

  @Test
  void aClassWithNoCaseHasNoProblemAndAnEmptySetHasNone() {
    assertThat(problems(List.of(NoAnnotation.class))).isEmpty();
    assertThat(problems(List.of())).isEmpty();
  }

  @Test
  void thePlantedClassesAreNotTestsSoNothingScansThemIntoAFloor() throws NoSuchMethodException {
    Method planted = Complete.class.getDeclaredMethod("injected");
    assertThat(planted.getAnnotation(org.junit.jupiter.api.Test.class)).isNull();
    assertThat(planted.getAnnotation(PermissionCase.class).leg()).isEqualTo(Leg.INJECTED);
    assertThat(PermissionCase.class.getAnnotation(java.lang.annotation.Retention.class).value()).isEqualTo(java.lang.annotation.RetentionPolicy.RUNTIME);
  }

  // ---- RealPermissionFixture -------------------------------------------------------------------------------------------------

  private static Path scratchFile() throws IOException {
    Path dir = ScratchDirs.create();
    return Files.writeString(dir.resolve("secret.txt"), "x");
  }

  private static Path report() {
    return ScratchDirs.create().resolve("reports").resolve("not-run.txt");
  }

  @Test
  void whenTheOperatingSystemRefusesThePermissionsAreGoneUntilTheFixtureIsClosed() throws IOException {
    PosixHost.assumePosix("PermissionCaseCoverageTest.whenTheOperatingSystemRefusesThePermissionsAreGoneUntilTheFixtureIsClosed");
    Path file = scratchFile();

    try (RealPermissionFixture fixture = RealPermissionFixture.refusedForThisUser(file, "refuses", path -> false, report())) {
      assertThat(fixture.path()).isEqualTo(file);
      assertThat(Files.getPosixFilePermissions(file)).isEmpty();
    }

    assertThat(Files.getPosixFilePermissions(file)).contains(PosixFilePermission.OWNER_READ, PosixFilePermission.OWNER_WRITE);
  }

  @Test
  void whenTheOperatingSystemDoesNotRefuseTheTestIsSkippedTheLineIsWrittenAndThePermissionsAreBack() throws IOException {
    PosixHost.assumePosix("PermissionCaseCoverageTest.whenTheOperatingSystemDoesNotRefuseTheTestIsSkippedTheLineIsWrittenAndThePermissionsAreBack");
    Path file = scratchFile();
    Set<PosixFilePermission> before = Files.getPosixFilePermissions(file);
    Path report = report();

    assertThatThrownBy(() -> RealPermissionFixture.refusedForThisUser(file, "some-test-id", path -> true, report)).isInstanceOf(TestAbortedException.class);

    assertThat(Files.readAllLines(report)).containsExactly("not run: precondition unmet: some-test-id");
    assertThat(Files.getPosixFilePermissions(file)).isEqualTo(before);
  }

  @Test
  void aDirectoryIsHandledLikeAFileAndTheLinesAccumulate() throws IOException {
    PosixHost.assumePosix("PermissionCaseCoverageTest.aDirectoryIsHandledLikeAFileAndTheLinesAccumulate");
    Path dir = Files.createDirectory(ScratchDirs.create().resolve("listed"));
    Path report = report();

    assertThatThrownBy(() -> RealPermissionFixture.refusedForThisUser(dir, "first", path -> true, report)).isInstanceOf(TestAbortedException.class);
    assertThatThrownBy(() -> RealPermissionFixture.refusedForThisUser(dir, "second", path -> true, report)).isInstanceOf(TestAbortedException.class);

    assertThat(Files.readAllLines(report)).containsExactly("not run: precondition unmet: first", "not run: precondition unmet: second");
    try (RealPermissionFixture fixture = RealPermissionFixture.refusedForThisUser(dir, "third", path -> false, report)) {
      assertThat(Files.getPosixFilePermissions(dir)).isEmpty();
    }
  }

  @Test
  void aPathThatDoesNotExistIsAPreconditionNotMetNotAPass() {
    Path missing = ScratchDirs.create().resolve("nothing-here");
    Path report = report();

    assertThatThrownBy(() -> RealPermissionFixture.refusedForThisUser(missing, "missing", path -> false, report)).isInstanceOf(TestAbortedException.class);

    assertThat(report).exists();
  }

  @Test
  void withoutAPosixViewTheTestIsSkippedAndTheNotRunLineIsWritten() throws IOException {
    Path report = report();

    assertThatThrownBy(() -> PosixHost.assumePosix("no-posix-test-id", false, report)).isInstanceOf(TestAbortedException.class);

    assertThat(Files.readAllLines(report)).containsExactly("not run: precondition unmet: no-posix-test-id");
  }

  @Test
  void withAPosixViewTheGuardWritesNothingAndLetsTheTestRun() {
    Path report = report();

    PosixHost.assumePosix("posix-test-id", true, report);

    assertThat(report).doesNotExist();
  }

  @Test
  void withTheRealOperatingSystemEitherTheFileIsRefusedOrTheTestIsSkippedWithItsLine() throws IOException {
    Path file = scratchFile();

    try (RealPermissionFixture fixture = RealPermissionFixture.refusedForThisUser(file, "real-os")) {
      // a non-root user: the operating system refused, so opening the file must really fail
      assertThatThrownBy(() -> Files.readAllBytes(fixture.path())).isInstanceOf(IOException.class);
    } catch (TestAbortedException rootOrNoPosix) {
      // a root runner: the precondition was unmet and the helper wrote its line (deterministic as root: the seam tests above)
      assertThat(Files.readString(NotRun.DEFAULT_FILE)).contains("not run: precondition unmet: real-os");
      throw rootOrNoPosix;
    }
  }
}
