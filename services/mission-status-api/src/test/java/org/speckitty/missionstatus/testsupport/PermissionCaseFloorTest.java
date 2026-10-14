package org.speckitty.missionstatus.testsupport;

import static org.assertj.core.api.Assertions.assertThat;

import com.tngtech.archunit.core.domain.JavaClass;
import java.lang.reflect.Method;
import java.util.ArrayList;
import java.util.Collection;
import java.util.List;
import java.util.Set;
import java.util.TreeSet;
import org.junit.jupiter.api.Test;
import org.speckitty.missionstatus.architecture.ArchitectureRules;
import org.speckitty.missionstatus.testsupport.PermissionCase.Leg;

/**
 * The whole-set floor of {@link PermissionCase} (D-140, plan "Permission-denied fixtures"): the four ids the route work packages wrote, each
 * with exactly one injected-fault test and one real-permission test. {@code PermissionCaseCoverageTest} holds the coverage function and
 * judges the classes it is given; this class only applies it to the production tests, because WP15 and WP16 wrote those. The scan skips
 * the planted classes of the coverage test and of this one.
 */
class PermissionCaseFloorTest {

  /** The ids of the floor: two of {@code getWorkPackageDetail} (AC-10.3), two of the artifact routes (AC-4.3, AC-4.7). */
  static final Set<String> FLOOR =
      Set.of("AC-10.3/worktree-stat-denied", "AC-10.3/cycle-directory-denied", "AC-4.3/listing-denied", "AC-4.7/entry-denied");

  /** The ids carried by these classes (a method or class annotation each). */
  static Set<String> ids(Collection<Class<?>> classes) {
    Set<String> ids = new TreeSet<>();
    for (Class<?> type : classes) {
      if (type.getAnnotation(PermissionCase.class) != null) {
        ids.add(type.getAnnotation(PermissionCase.class).value());
      }
      for (Method method : type.getDeclaredMethods()) {
        if (method.getAnnotation(PermissionCase.class) != null) {
          ids.add(method.getAnnotation(PermissionCase.class).value());
        }
      }
    }
    return ids;
  }

  /** The coverage problems plus the difference between the ids found and the floor: empty means the floor holds. */
  static List<String> floorProblems(Collection<Class<?>> classes, Set<String> floor) {
    List<String> problems = new ArrayList<>(PermissionCaseCoverageTest.problems(classes));
    Set<String> found = ids(classes);
    floor.stream().filter(id -> !found.contains(id)).sorted().forEach(id -> problems.add("floor id " + id + " has no test"));
    found.stream().filter(id -> !floor.contains(id)).sorted().forEach(id -> problems.add("id " + id + " is outside the floor"));
    return problems;
  }

  private static List<Class<?>> productionCarriers() {
    List<Class<?>> carriers = new ArrayList<>();
    for (JavaClass type : ArchitectureRules.testClasses()) {
      String name = type.getName();
      if (name.startsWith(PermissionCaseCoverageTest.class.getName()) || name.startsWith(PermissionCaseFloorTest.class.getName())) {
        continue;
      }
      if (type.isAnnotatedWith(PermissionCase.class) || type.getMethods().stream().anyMatch(method -> method.isAnnotatedWith(PermissionCase.class))) {
        carriers.add(type.reflect());
      }
    }
    return carriers;
  }

  // ---- planted classes (never run: no @Test) ---------------------------------------------------------------------------------

  static final class FullFloor {
    @PermissionCase(value = "AC-10.3/worktree-stat-denied", leg = Leg.INJECTED)
    void a() {}

    @PermissionCase(value = "AC-10.3/worktree-stat-denied", leg = Leg.REAL)
    void b() {}

    @PermissionCase(value = "AC-10.3/cycle-directory-denied", leg = Leg.INJECTED)
    void c() {}

    @PermissionCase(value = "AC-10.3/cycle-directory-denied", leg = Leg.REAL)
    void d() {}

    @PermissionCase(value = "AC-4.3/listing-denied", leg = Leg.INJECTED)
    void e() {}

    @PermissionCase(value = "AC-4.3/listing-denied", leg = Leg.REAL)
    void f() {}

    @PermissionCase(value = "AC-4.7/entry-denied", leg = Leg.INJECTED)
    void g() {}

    @PermissionCase(value = "AC-4.7/entry-denied", leg = Leg.REAL)
    void h() {}
  }

  static final class MissingRealLeg {
    @PermissionCase(value = "AC-4.7/entry-denied", leg = Leg.INJECTED)
    void only() {}
  }

  static final class DuplicateId {
    @PermissionCase(value = "AC-4.7/entry-denied", leg = Leg.INJECTED)
    void first() {}

    @PermissionCase(value = "AC-4.7/entry-denied", leg = Leg.INJECTED)
    void second() {}

    @PermissionCase(value = "AC-4.7/entry-denied", leg = Leg.REAL)
    void real() {}
  }

  @Test
  void theProductionTestsCarryExactlyTheFourFloorIdsWithBothLegs() {
    List<Class<?>> carriers = productionCarriers();

    assertThat(ids(carriers)).as("a scan that matches nothing must fail").hasSize(4);
    assertThat(floorProblems(carriers, FLOOR)).isEmpty();
  }

  @Test
  void theFloorIsTheFourNamedIds() {
    assertThat(FLOOR).hasSize(4);
    assertThat(floorProblems(List.of(FullFloor.class), FLOOR)).isEmpty();
  }

  @Test
  void aMissingLegIsRedAndSoIsEveryAbsentFloorId() {
    assertThat(floorProblems(List.of(MissingRealLeg.class), FLOOR))
        .contains("case AC-4.7/entry-denied has no REAL leg", "floor id AC-10.3/worktree-stat-denied has no test", "floor id AC-4.3/listing-denied has no test")
        .hasSize(4);
  }

  @Test
  void aDuplicateIdIsRed() {
    assertThat(floorProblems(List.of(FullFloor.class, DuplicateId.class), FLOOR)).contains("case AC-4.7/entry-denied has 3 INJECTED legs (duplicate id)", "case AC-4.7/entry-denied has 2 REAL legs (duplicate id)");
  }

  @Test
  void anIdOutsideTheFloorIsRed() {
    assertThat(floorProblems(List.of(FullFloor.class), Set.of("AC-4.3/listing-denied"))).contains("id AC-10.3/worktree-stat-denied is outside the floor");
  }

  @Test
  void anEmptyScanIsRedForEveryFloorId() {
    assertThat(floorProblems(List.of(), FLOOR)).hasSize(4);
  }
}
