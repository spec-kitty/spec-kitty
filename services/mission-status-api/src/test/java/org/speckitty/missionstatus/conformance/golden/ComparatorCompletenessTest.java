package org.speckitty.missionstatus.conformance.golden;

import static org.assertj.core.api.Assertions.assertThat;
import static org.assertj.core.api.Assertions.assertThatThrownBy;

import java.lang.reflect.RecordComponent;
import java.util.ArrayList;
import java.util.Arrays;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;
import java.util.Set;
import java.util.TreeSet;
import java.util.stream.Collectors;
import org.junit.jupiter.api.Test;
import org.speckitty.missionstatus.domain.readmodel.overview.MissionOverview;
import org.speckitty.missionstatus.domain.readmodel.overview.ProjectHeader;
import org.speckitty.missionstatus.domain.readmodel.reducer.EventOrdering;
import org.speckitty.missionstatus.testsupport.CanonicalJson;
import org.speckitty.missionstatus.testsupport.CanonicalJson.Num;
import org.speckitty.missionstatus.testsupport.ConformanceTree;
import org.speckitty.missionstatus.testsupport.ConformanceTree.TreeFixture;
import org.speckitty.missionstatus.testsupport.FilesystemFixtureFactory;
import org.speckitty.missionstatus.testsupport.GoldenComparison;

/**
 * AC-8a: the comparator catches a change to ANY member of the documents (a comparator that ignores {@code lastActivityAt}, or that
 * reorders silently, fails here), and the golden suite goes red on the {@code interleaved} class when the reducer's event ordering
 * is wrong. The mutation is applied to a copy of a passing document; the raw-byte comparison must then fail and name the member.
 */
class ComparatorCompletenessTest {

  private static TreeFixture fixture(String tag, String name) {
    return ConformanceTree.fixturesOf(tag).stream().filter(candidate -> candidate.name().equals(name)).findFirst().orElseThrow();
  }

  private static Set<String> componentNames(Class<? extends Record> type) {
    return Arrays.stream(type.getRecordComponents()).map(RecordComponent::getName).collect(Collectors.toCollection(TreeSet::new));
  }

  @SuppressWarnings("unchecked")
  private static Map<String, Object> asMap(Object tree) {
    return (Map<String, Object>) tree;
  }

  /** A different value of a different kind, so that no leaf can mutate into itself. */
  private static Object different(Object value) {
    return switch (value) {
      case null -> "mutated";
      case Boolean flag -> !flag;
      case Num number -> new Num(number.text() + "1");
      case String text -> text + "~";
      default -> "mutated";
    };
  }

  /** Every leaf of a tree as a path of keys and indexes, in document order. */
  private static void leaves(Object node, List<Object> path, List<List<Object>> out) {
    if (node instanceof Map<?, ?> map) {
      for (Map.Entry<?, ?> entry : map.entrySet()) {
        List<Object> child = new ArrayList<>(path);
        child.add(entry.getKey());
        leaves(entry.getValue(), child, out);
      }
    } else if (node instanceof List<?> list) {
      for (int i = 0; i < list.size(); i++) {
        List<Object> child = new ArrayList<>(path);
        child.add(i);
        leaves(list.get(i), child, out);
      }
    } else {
      out.add(path);
    }
  }

  /** Replaces the leaf at the path in a deep copy of the tree and returns the copy. */
  @SuppressWarnings("unchecked")
  private static Object withLeafChanged(Object tree, List<Object> path) {
    Object copy = CanonicalJson.parse(CanonicalJson.toBytes(tree));
    Object parent = copy;
    for (int i = 0; i < path.size() - 1; i++) {
      Object step = path.get(i);
      parent = step instanceof Integer index ? ((List<Object>) parent).get(index) : ((Map<String, Object>) parent).get((String) step);
    }
    Object last = path.getLast();
    if (last instanceof Integer index) {
      ((List<Object>) parent).set(index, different(((List<Object>) parent).get(index)));
    } else {
      Map<String, Object> map = (Map<String, Object>) parent;
      map.put((String) last, different(map.get((String) last)));
    }
    return copy;
  }

  private static String lastName(List<Object> path) {
    for (int i = path.size() - 1; i >= 0; i--) {
      if (path.get(i) instanceof String name) {
        return name;
      }
    }
    return "(root)";
  }

  private static void everyLeafChangeIsNamed(byte[] golden) {
    Object tree = CanonicalJson.parse(golden);
    CanonicalJson.assertBodyEqualsGolden(CanonicalJson.toBytes(tree), golden);
    List<List<Object>> leaves = new ArrayList<>();
    leaves(tree, new ArrayList<>(), leaves);
    assertThat(leaves).isNotEmpty();
    for (List<Object> path : leaves) {
      byte[] mutated = CanonicalJson.toBytes(withLeafChanged(tree, path));
      assertThatThrownBy(() -> CanonicalJson.assertBodyEqualsGolden(mutated, golden))
          .as("a change at " + path)
          .isInstanceOf(AssertionError.class)
          .hasMessageContaining("member " + lastName(path));
    }
  }

  @Test
  void aGoldenRoundTripsThroughTheTreeAndTheWriterByteForByte() {
    byte[] golden = ConformanceTree.golden(fixture("interleaved", "two-missions"), ConformanceTree.MISSIONS_GOLDEN);

    CanonicalJson.assertBodyEqualsGolden(CanonicalJson.toBytes(CanonicalJson.parse(golden)), golden);
  }

  @Test
  void everyMemberOfMissionOverviewIsInTheGoldenAndANamedChangeToItFails() {
    byte[] golden = ConformanceTree.golden(fixture("interleaved", "two-missions"), ConformanceTree.MISSIONS_GOLDEN);
    Map<String, Object> item = asMap(((List<?>) asMap(CanonicalJson.parse(golden)).get("items")).getFirst());

    assertThat(new TreeSet<>(item.keySet())).as("the golden's members are the type's members").isEqualTo(componentNames(MissionOverview.class));
    everyLeafChangeIsNamed(golden);
  }

  @Test
  void everyMemberOfProjectIsInTheGoldenAndANamedChangeToItFails() {
    byte[] golden = ConformanceTree.golden(fixture("project-header", "healthy"), ConformanceTree.PROJECT_GOLDEN);

    assertThat(new TreeSet<>(asMap(CanonicalJson.parse(golden)).keySet())).isEqualTo(componentNames(ProjectHeader.class));
    everyLeafChangeIsNamed(golden);
  }

  @Test
  void lastActivityAtInParticularCannotBeIgnoredOrReordered() {
    byte[] golden = ConformanceTree.golden(fixture("interleaved", "two-missions"), ConformanceTree.MISSIONS_GOLDEN);
    String text = new String(golden, java.nio.charset.StandardCharsets.UTF_8);
    String changed = text.replaceFirst("\"lastActivityAt\":\"[^\"]*\"", "\"lastActivityAt\":\"2000-01-01T00:00:00Z\"");

    assertThat(changed).isNotEqualTo(text);
    assertThatThrownBy(() -> CanonicalJson.assertBodyEqualsGolden(changed.getBytes(java.nio.charset.StandardCharsets.UTF_8), golden)).hasMessageContaining("member lastActivityAt");
  }

  @Test
  void aWrongEventOrderingMakesTheInterleavedClassRed() {
    EventOrdering atOnly = (left, right) -> left.at().compareTo(right.at());
    TreeFixture interleaved = fixture("interleaved", "two-missions");

    // the production ordering passes ...
    GoldenComparison.verify(interleaved, FilesystemFixtureFactory.fromTree(interleaved.dir()).query());
    // ... and sorting by `at` only (no event_id tie-break) makes the comparison red
    assertThatThrownBy(() -> GoldenComparison.verify(interleaved, FilesystemFixtureFactory.fromTreeWithOrdering(interleaved.dir(), atOnly).query()))
        .isInstanceOf(AssertionError.class)
        .hasMessageContaining("difference at");
  }

  @Test
  void theMemberSetsAreTheDocumentedOnes() {
    assertThat(componentNames(MissionOverview.class)).hasSize(22);
    assertThat(componentNames(ProjectHeader.class)).hasSize(7);
    Map<String, Object> shape = new LinkedHashMap<>();
    shape.put("overview", componentNames(MissionOverview.class));
    assertThat(shape).containsKey("overview");
  }
}
