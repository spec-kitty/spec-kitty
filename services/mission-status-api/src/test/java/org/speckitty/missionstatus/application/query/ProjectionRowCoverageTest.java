package org.speckitty.missionstatus.application.query;

import static org.assertj.core.api.Assertions.assertThat;

import com.tngtech.archunit.core.domain.JavaClass;
import java.lang.reflect.Method;
import java.util.ArrayList;
import java.util.Collection;
import java.util.List;
import java.util.Map;
import java.util.Set;
import java.util.TreeMap;
import java.util.TreeSet;
import org.junit.jupiter.api.Test;
import org.speckitty.missionstatus.architecture.ArchitectureRules;
import org.speckitty.missionstatus.testsupport.ProjectionRow;

/**
 * The whole-set floor of {@link ProjectionRow} (D-102, FRESH3-003, plan section 8): the 26 {@code (row, route)} pairs of the 18 rows T1 to
 * T18 are each the subject of exactly one production test. The set is exact, not a count: deleting a case, adding a stray one or
 * repeating one turns this red. The planted classes below are never scanned into the floor (the scan skips this class and its members).
 */
class ProjectionRowCoverageTest {

  /** The member-to-route list of the data model: route to the rows its mapper projects. */
  static final Map<String, Set<String>> EXPECTED =
      Map.of(
          "getMission", Set.of("T1", "T2", "T3", "T4", "T5", "T6", "T10"),
          "getWorkPackage", Set.of("T5", "T6", "T7", "T8", "T10", "T11", "T12", "T13", "T14", "T17"),
          "getWorkPackageDetail", Set.of("T1", "T5", "T7", "T8", "T9", "T15", "T16", "T17", "T18"));

  static final int PAIR_FLOOR = 26;
  static final int ROW_FLOOR = 18;

  /** Every {@code route/row} found, once per annotated test (a repeat shows twice). */
  static List<String> found(Collection<Class<?>> classes) {
    List<String> pairs = new ArrayList<>();
    for (Class<?> type : classes) {
      add(pairs, type.getAnnotation(ProjectionRow.class));
      for (Method method : type.getDeclaredMethods()) {
        add(pairs, method.getAnnotation(ProjectionRow.class));
      }
    }
    return pairs;
  }

  private static void add(List<String> pairs, ProjectionRow row) {
    if (row != null) {
      pairs.add(row.route() + "/" + row.row());
    }
  }

  /** What differs between the pairs found and the expected set: empty means the floor holds. */
  static List<String> problems(List<String> found) {
    Set<String> expected = new TreeSet<>();
    EXPECTED.forEach((route, rows) -> rows.forEach(row -> expected.add(route + "/" + row)));
    List<String> problems = new ArrayList<>();
    Map<String, Integer> counts = new TreeMap<>();
    found.forEach(pair -> counts.merge(pair, 1, Integer::sum));
    expected.stream().filter(pair -> !counts.containsKey(pair)).forEach(pair -> problems.add("no test for " + pair));
    counts.forEach(
        (pair, count) -> {
          if (!expected.contains(pair)) {
            problems.add("stray pair " + pair);
          } else if (count > 1) {
            problems.add(count + " tests for " + pair);
          }
        });
    return problems;
  }

  /** The production tests that carry a {@link ProjectionRow}, minus this class and its planted members. */
  private static List<Class<?>> productionCarriers() {
    List<Class<?>> carriers = new ArrayList<>();
    for (JavaClass type : ArchitectureRules.testClasses()) {
      if (type.getName().startsWith(ProjectionRowCoverageTest.class.getName())) {
        continue;
      }
      boolean carries = type.isAnnotatedWith(ProjectionRow.class) || type.getMethods().stream().anyMatch(method -> method.isAnnotatedWith(ProjectionRow.class));
      if (carries) {
        carriers.add(type.reflect());
      }
    }
    return carriers;
  }

  // ---- planted classes (never run: no @Test) ---------------------------------------------------------------------------------

  static final class MissesOnePair {
    @ProjectionRow(row = "T1", route = "getMission")
    void one() {}
  }

  static final class StrayPair {
    @ProjectionRow(row = "T99", route = "getMission")
    void stray() {}
  }

  static final class RepeatedPair {
    @ProjectionRow(row = "T1", route = "getMission")
    void first() {}

    @ProjectionRow(row = "T1", route = "getMission")
    void second() {}
  }

  @Test
  void theExpectedSetIsTheTwentySixPairsOfTheEighteenRows() {
    Set<String> rows = new TreeSet<>();
    int pairs = 0;
    for (Set<String> routeRows : EXPECTED.values()) {
      pairs += routeRows.size();
      rows.addAll(routeRows);
    }
    assertThat(pairs).isEqualTo(PAIR_FLOOR);
    assertThat(rows).hasSize(ROW_FLOOR).contains("T1", "T18");
    assertThat(EXPECTED.get("getMission")).hasSize(7);
    assertThat(EXPECTED.get("getWorkPackage")).hasSize(10);
    assertThat(EXPECTED.get("getWorkPackageDetail")).hasSize(9);
  }

  @Test
  void theProductionTestsCoverExactlyTheTwentySixPairsOnceEach() {
    List<String> found = found(productionCarriers());

    assertThat(found).as("a scan that matches nothing must fail").hasSizeGreaterThanOrEqualTo(PAIR_FLOOR);
    assertThat(problems(found)).isEmpty();
    assertThat(found).hasSize(PAIR_FLOOR);
  }

  @Test
  void aMissingPairIsRed() {
    assertThat(problems(found(List.of(MissesOnePair.class)))).contains("no test for getMission/T2", "no test for getWorkPackageDetail/T18").hasSize(25);
  }

  @Test
  void aStrayPairIsRed() {
    assertThat(problems(found(List.of(StrayPair.class)))).contains("stray pair getMission/T99");
  }

  @Test
  void aRepeatedPairIsRed() {
    assertThat(problems(found(List.of(RepeatedPair.class)))).contains("2 tests for getMission/T1");
  }

  @Test
  void anEmptyScanIsRedForEveryPair() {
    assertThat(problems(List.of())).hasSize(PAIR_FLOOR);
  }

  @Test
  void aRepeatedPairIsCountedTwiceByTheFunctionTheScanUses() {
    assertThat(found(List.of(RepeatedPair.class))).containsExactly("getMission/T1", "getMission/T1");
  }
}
