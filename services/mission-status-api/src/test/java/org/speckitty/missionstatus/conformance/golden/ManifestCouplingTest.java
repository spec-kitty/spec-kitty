package org.speckitty.missionstatus.conformance.golden;

import static org.assertj.core.api.Assertions.assertThat;
import static org.assertj.core.api.Assertions.assertThatThrownBy;

import java.io.IOException;
import java.nio.file.Files;
import java.nio.file.Path;
import java.util.ArrayList;
import java.util.LinkedHashSet;
import java.util.List;
import java.util.Map;
import java.util.Set;
import java.util.TreeSet;
import java.util.regex.Matcher;
import java.util.regex.Pattern;
import java.util.stream.Stream;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.params.ParameterizedTest;
import org.junit.jupiter.params.provider.MethodSource;
import org.speckitty.missionstatus.domain.model.SupportedSchemaRange;
import org.speckitty.missionstatus.domain.redaction.LeakClasses;
import org.speckitty.missionstatus.testsupport.CanonicalJson;
import org.speckitty.missionstatus.testsupport.ConformanceTree;
import org.speckitty.missionstatus.testsupport.ConformanceTree.TreeFixture;
import org.speckitty.missionstatus.testsupport.FilesystemFixtureFactory;
import org.speckitty.missionstatus.testsupport.LeakPatternsFile;
import org.speckitty.missionstatus.testsupport.ResolverCaseTrees;

/**
 * T050: the data files that both languages consume stay coupled. The supported schema range (AC-1f), the resolver table (AC-6e),
 * the read-directory class of each fixture, and the leak patterns with their probes and digest (AC-9g) are all read from the
 * committed manifest or the committed files, never restated here.
 */
class ManifestCouplingTest {

  // ---- AC-1f ----------------------------------------------------------------------------------------------------------------

  @Test
  void theSupportedSchemaRangeEqualsTheManifest() {
    Map<String, Object> manifest = ConformanceTree.manifest();

    assertThat(((CanonicalJson.Num) manifest.get("supportedSchemaMin")).text()).isEqualTo(Integer.toString(SupportedSchemaRange.MIN));
    assertThat(((CanonicalJson.Num) manifest.get("supportedSchemaMax")).text()).isEqualTo(Integer.toString(SupportedSchemaRange.MAX));
  }

  @Test
  void theSpecKittyEventsVersionIsReadForInformationOnly() {
    assertThat(ConformanceTree.manifest().get("specKittyEventsVersion")).isInstanceOf(String.class).asString().matches("[0-9]+\\.[0-9]+\\.[0-9]+");
  }

  // ---- AC-6e ----------------------------------------------------------------------------------------------------------------

  static Stream<Map<String, Object>> resolverRows() {
    return ConformanceTree.resolverCases().stream();
  }

  @ParameterizedTest(name = "{0}")
  @MethodSource("resolverRows")
  void eachResolverRowYieldsItsExpectedReadDirectoryClassOnAMaterialisedTree(Map<String, Object> row) throws IOException {
    Path root = Files.createDirectories(ResolverCaseTrees.scratch().resolve("project"));
    String mission = ResolverCaseTrees.materialise(row, root);

    assertThat(FilesystemFixtureFactory.readDirectoryClass(root, mission)).as(row.get("id").toString()).isEqualTo(row.get("expectedClass"));
  }

  @Test
  void theExecutedIdsEqualTheFilesIdsAndTheManifestsResolverCaseIds() {
    List<String> fileIds = ConformanceTree.resolverCases().stream().map(row -> row.get("id").toString()).toList();
    @SuppressWarnings("unchecked")
    List<Object> manifestIds = (List<Object>) ConformanceTree.manifest().get("resolverCaseIds");

    assertThat(fileIds).hasSize(34).doesNotHaveDuplicates();
    assertThat(ResolverCaseTrees.verifyAll(ConformanceTree.resolverCases(), manifestIds.stream().map(Object::toString).toList(), FilesystemFixtureFactory::readDirectoryClass)).isEqualTo(34);
  }

  @Test
  void aRowRemovedFromOneLanguagesInputMakesTheCouplingRed() {
    List<Map<String, Object>> rows = new ArrayList<>(ConformanceTree.resolverCases());
    rows.removeFirst();
    @SuppressWarnings("unchecked")
    List<String> manifestIds = ((List<Object>) ConformanceTree.manifest().get("resolverCaseIds")).stream().map(Object::toString).toList();

    assertThatThrownBy(() -> ResolverCaseTrees.verifyAll(rows, manifestIds, FilesystemFixtureFactory::readDirectoryClass)).isInstanceOf(AssertionError.class).hasMessageContaining("single-branch-no-coordination");
  }

  @Test
  void aFlippedExpectationMakesTheCouplingRed() {
    List<Map<String, Object>> rows = new ArrayList<>();
    for (Map<String, Object> row : ConformanceTree.resolverCases()) {
      Map<String, Object> copy = new java.util.LinkedHashMap<>(row);
      if (copy.get("id").equals("coord-materialized")) {
        copy.put("expectedClass", "own");
      }
      rows.add(copy);
    }
    @SuppressWarnings("unchecked")
    List<String> manifestIds = ((List<Object>) ConformanceTree.manifest().get("resolverCaseIds")).stream().map(Object::toString).toList();

    assertThatThrownBy(() -> ResolverCaseTrees.verifyAll(rows, manifestIds, FilesystemFixtureFactory::readDirectoryClass)).isInstanceOf(AssertionError.class).hasMessageContaining("coord-materialized");
  }

  @Test
  void theDd105RowsAreInTheTable() {
    Set<String> ids = new TreeSet<>();
    ConformanceTree.resolverCases().forEach(row -> ids.add(row.get("id").toString()));

    assertThat(ids).contains("coord-husk-coord-meta-present-branch-absent", "coord-registered-coord-meta-absent-branch-empty", "lanes-with-coord-husk-coord-meta-absent-branch-present");
    long withCoordinationBranch = ConformanceTree.resolverCases().stream().filter(row -> row.containsKey("coordinationBranch")).count();
    long withRootKind = ConformanceTree.resolverCases().stream().filter(row -> row.containsKey("coordRootKind")).count();
    long withCoordMeta = ConformanceTree.resolverCases().stream().filter(row -> row.containsKey("coordMeta")).count();
    assertThat(withCoordinationBranch).isEqualTo(withRootKind).isEqualTo(withCoordMeta).isEqualTo(20);
  }

  // ---- the read directory class of each fixture ------------------------------------------------------------------------------

  static Stream<TreeFixture> allFixtures() {
    return ConformanceTree.fixtures().stream();
  }

  @ParameterizedTest(name = "{0}")
  @MethodSource("allFixtures")
  void theManifestsReadDirectoryClassIsTheClassTheAdapterChose(TreeFixture fixture) throws IOException {
    Path root = Files.createDirectories(ResolverCaseTrees.scratch().resolve("project"));
    org.speckitty.missionstatus.testsupport.ProjectHeaderMaterialisation.materialise(fixture.dir(), root);
    Set<String> classes = new LinkedHashSet<>();
    Path specs = root.resolve("kitty-specs");
    if (Files.isDirectory(specs)) {
      try (Stream<Path> entries = Files.list(specs)) {
        for (Path mission : entries.filter(Files::isDirectory).sorted().toList()) {
          if (!Files.isRegularFile(mission.resolve("meta.json"))) {
            continue;
          }
          try {
            classes.add(FilesystemFixtureFactory.readDirectoryClass(root, mission.getFileName().toString()));
          } catch (RuntimeException refused) {
            assertThat(fixture.javaOnly()).as(fixture.key() + " is refused by the resolver, which only a javaOnly fixture may be").isTrue();
          }
        }
      }
    }
    String chosen = classes.contains("coord") ? "coord" : "own";

    assertThat(chosen).as(fixture.key()).isEqualTo(fixture.readDirectoryClass());
  }

  // ---- AC-9g ----------------------------------------------------------------------------------------------------------------

  @Test
  void theLeakPatternsFileHasTheManifestsSha256() {
    assertThat(LeakPatternsFile.sha256()).isEqualTo(ConformanceTree.manifest().get("leakPatternsSha256"));
  }

  @SuppressWarnings("unchecked")
  static Stream<String> probedPatternIds() {
    return ((Map<String, Object>) ConformanceTree.manifest().get("patternProbes")).keySet().stream().sorted();
  }

  @ParameterizedTest(name = "{0}")
  @MethodSource("probedPatternIds")
  @SuppressWarnings("unchecked")
  void eachPatternGivesJavaTheVerdictsPythonGave(String id) {
    LeakPatternsFile.Entry entry = LeakPatternsFile.entries().stream().filter(candidate -> candidate.id().equals(id)).findFirst().orElseThrow();
    Pattern compiled = LeakClasses.compile(entry.pattern());
    List<Object> probes = (List<Object>) ((Map<String, Object>) ConformanceTree.manifest().get("patternProbes")).get(id);

    assertThat(probes).as("probes of " + id).isNotEmpty();
    for (Object raw : probes) {
      Map<String, Object> probe = (Map<String, Object>) raw;
      Matcher matcher = compiled.matcher((String) probe.get("text"));
      assertThat(matcher.find()).as(id + " on [" + probe.get("text") + "]").isEqualTo(probe.get("matches"));
    }
  }

  @Test
  @SuppressWarnings("unchecked")
  void theProbedPatternsAreExactlyThePatternsOfTheFileAndEachHasBothVerdictsOrIsNamedForIt() {
    Set<String> fileIds = new TreeSet<>();
    LeakPatternsFile.entries().forEach(entry -> fileIds.add(entry.id()));
    Map<String, Object> probes = (Map<String, Object>) ConformanceTree.manifest().get("patternProbes");

    assertThat(new TreeSet<>(probes.keySet())).isEqualTo(fileIds);
    for (String id : probes.keySet()) {
      List<Object> list = (List<Object>) probes.get(id);
      assertThat(list.stream().map(raw -> ((Map<String, Object>) raw).get("matches")).distinct().toList()).as(id + " has a positive and a negative probe").containsExactlyInAnyOrder(true, false);
    }
  }

  @Test
  void aPatternRemovedFromAScratchCopyMakesTheDigestAndTheProbeCoverageRed() {
    byte[] original = LeakPatternsFile.bytes();
    String text = new String(original, java.nio.charset.StandardCharsets.UTF_8);
    String withoutSecretZero = text.replace("\"id\":\"secret-0\"", "\"id\":\"secret-removed\"");

    assertThat(LeakPatternsFile.sha256(withoutSecretZero.getBytes(java.nio.charset.StandardCharsets.UTF_8))).isNotEqualTo(ConformanceTree.manifest().get("leakPatternsSha256"));
    assertThat(LeakPatternsFile.sha256(original)).isEqualTo(ConformanceTree.manifest().get("leakPatternsSha256"));
  }
}
