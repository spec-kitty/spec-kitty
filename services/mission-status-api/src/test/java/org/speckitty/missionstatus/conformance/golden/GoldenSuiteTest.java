package org.speckitty.missionstatus.conformance.golden;

import static org.assertj.core.api.Assertions.assertThat;
import static org.assertj.core.api.Assertions.assertThatThrownBy;

import java.util.ArrayList;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;
import java.util.Set;
import java.util.TreeMap;
import java.util.TreeSet;
import java.util.stream.Collectors;
import java.util.stream.Stream;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.params.ParameterizedTest;
import org.junit.jupiter.params.provider.MethodSource;
import org.speckitty.missionstatus.application.query.port.in.exceptions.MissionStatusUnavailable;
import org.speckitty.missionstatus.application.query.port.in.dto.PageRequest;
import org.speckitty.missionstatus.domain.model.Diagnostic;
import org.speckitty.missionstatus.domain.model.DiagnosticCode;
import org.speckitty.missionstatus.testsupport.CanonicalJson;
import org.speckitty.missionstatus.testsupport.ConformanceTree;
import org.speckitty.missionstatus.testsupport.ConformanceTree.ClassEntry;
import org.speckitty.missionstatus.testsupport.ConformanceTree.TreeFixture;
import org.speckitty.missionstatus.testsupport.FilesystemFixtureFactory;
import org.speckitty.missionstatus.testsupport.FilesystemFixtureFactory.Built;
import org.speckitty.missionstatus.testsupport.GoldenComparison;

/**
 * The golden suite (T049; AC-2a all classes, AC-8a, AC-8b Java side, AC-8d): every fixture of every {@code python-golden} class of the
 * manifest is copied into a scratch directory, materialised, and served by the REAL application service over the REAL filesystem
 * adapter; the raw response bytes are compared with the committed golden bytes (post-analyze ruling ANL-003). The goldens are never
 * edited here; a difference is a finding about the Java side.
 */
class GoldenSuiteTest {

  /** The per-class floors of the Python conformance test ({@code CLASS_FLOORS}); a shrinking class fails here before it is missed. */
  private static final Map<String, Integer> CLASS_FLOORS =
      Map.ofEntries(
          Map.entry("interleaved", 4), Map.entry("coordination", 2), Map.entry("coord-husk", 1), Map.entry("absent-topology", 1), Map.entry("lifecycle-only", 1),
          Map.entry("no-ledger", 1), Map.entry("log-truncated", 1), Map.entry("malformed-rows", 11), Map.entry("torn-final-line", 2), Map.entry("crlf-and-listing", 2),
          Map.entry("project-header", 9), Map.entry("projection", 3), Map.entry("secret-canaries", 1), Map.entry("symlink", 3));

  /** The one fixture whose Java outcome differs from the golden on purpose (DD-79 family; spec L4b): an unterminated but valid last line. */
  private static final String KNOWN_DIVERGENCE = "torn-final-line/valid-json-final-line";

  static Stream<TreeFixture> goldenFixtures() {
    return ConformanceTree.fixtures().stream().filter(fixture -> fixture.parity().equals(ConformanceTree.PARITY_GOLDEN)).filter(fixture -> !fixture.javaOnly());
  }

  static Stream<TreeFixture> comparedFixtures() {
    return goldenFixtures().filter(fixture -> !fixture.knownDivergence());
  }

  // ---- the comparison ---------------------------------------------------------------------------------------------------------

  @ParameterizedTest(name = "{0}")
  @MethodSource("comparedFixtures")
  void theRealServiceOverTheRealAdapterEqualsTheGoldenByRawBytes(TreeFixture fixture) {
    Built built = FilesystemFixtureFactory.fromTreeRecording(fixture.dir());

    GoldenComparison.Report report = GoldenComparison.verify(fixture, built.query());

    assertThat(report.documents()).as("both documents of " + fixture.key()).isEqualTo(2);
    assertThat(built.handles().allowlistViolations()).as("every access is on the allowlist").isEmpty();
    assertThat(built.handles().allowlistAccessCount()).as("the adapter really read the tree").isPositive();
  }

  @Test
  void theRawBodiesAreByteDeterministicAndHashLikeTheGoldens() throws Exception {
    java.security.MessageDigest digest = java.security.MessageDigest.getInstance("SHA-256");
    int hashed = 0;
    for (TreeFixture fixture : comparedFixtures().toList()) {
      for (String file : List.of(ConformanceTree.PROJECT_GOLDEN, ConformanceTree.MISSIONS_GOLDEN)) {
        byte[] golden = ConformanceTree.golden(fixture, file);
        if (GoldenComparison.refusalException(golden) != null || GoldenComparison.REPORTED_DIVERGENCES.containsKey(fixture.key() + "#" + file)) {
          continue;
        }
        boolean project = file.equals(ConformanceTree.PROJECT_GOLDEN);
        byte[] first = project ? GoldenComparison.projectBody(FilesystemFixtureFactory.fromTree(fixture.dir()).query()) : GoldenComparison.missionsBody(FilesystemFixtureFactory.fromTree(fixture.dir()).query());
        byte[] second = project ? GoldenComparison.projectBody(FilesystemFixtureFactory.fromTree(fixture.dir()).query()) : GoldenComparison.missionsBody(FilesystemFixtureFactory.fromTree(fixture.dir()).query());
        String goldenHash = java.util.HexFormat.of().formatHex(digest.digest(golden));
        assertThat(java.util.HexFormat.of().formatHex(digest.digest(first))).as(fixture.key() + " " + file + " hash of run 1").isEqualTo(goldenHash);
        assertThat(java.util.HexFormat.of().formatHex(digest.digest(second))).as(fixture.key() + " " + file + " hash of run 2").isEqualTo(goldenHash);
        hashed++;
      }
    }
    assertThat(hashed).as("documents hashed").isGreaterThan(40);
  }

  @Test
  void aRefusalFixtureWasRefusedWithTheCodeItsExceptionClassImplies() {
    Map<String, DiagnosticCode> expectedMissions = new TreeMap<>();
    expectedMissions.put("malformed-rows/empty-meta", DiagnosticCode.META_UNPARSEABLE);
    expectedMissions.put("malformed-rows/malformed-meta", DiagnosticCode.META_UNPARSEABLE);
    expectedMissions.put("malformed-rows/non-utf8-meta", DiagnosticCode.META_UNPARSEABLE);
    expectedMissions.put("malformed-rows/invalid-json-line", DiagnosticCode.LEDGER_UNPARSEABLE);
    expectedMissions.put("malformed-rows/invalid-utf8-ledger", DiagnosticCode.LEDGER_UNPARSEABLE);
    expectedMissions.put("malformed-rows/missing-required-key", DiagnosticCode.LEDGER_UNPARSEABLE);
    expectedMissions.put("malformed-rows/non-object-line", DiagnosticCode.LEDGER_UNPARSEABLE);
    expectedMissions.put("malformed-rows/unknown-kind", DiagnosticCode.LEDGER_UNPARSEABLE);
    expectedMissions.put("malformed-rows/unknown-lane", DiagnosticCode.LEDGER_UNPARSEABLE);
    expectedMissions.put("torn-final-line/unparseable-final-line", DiagnosticCode.LEDGER_TORN_TAIL);
    expectedMissions.put("projection/strict-field-refused", DiagnosticCode.PROJECTION_REFUSED);

    Map<String, DiagnosticCode> actual = new TreeMap<>();
    for (TreeFixture fixture : goldenFixtures().toList()) {
      byte[] golden = ConformanceTree.golden(fixture, ConformanceTree.MISSIONS_GOLDEN);
      if (GoldenComparison.refusalException(golden) != null) {
        Built built = FilesystemFixtureFactory.fromTree(fixture.dir());
        MissionStatusUnavailable refusal = null;
        try {
          built.query().missions(new PageRequest(50, null));
        } catch (MissionStatusUnavailable thrown) {
          refusal = thrown;
        }
        assertThat(refusal).as(fixture.key() + " is refused").isNotNull();
        actual.put(fixture.key(), refusal.code());
      }
    }

    assertThat(actual).isEqualTo(expectedMissions);
  }

  @Test
  void aLineNumberedPythonRefusalIsMatchedByTheDiagnosticLine() {
    List<String> checked = new ArrayList<>();
    for (TreeFixture fixture : goldenFixtures().toList()) {
      Integer line = GoldenComparison.refusalLine(ConformanceTree.golden(fixture, ConformanceTree.PROJECT_GOLDEN));
      if (line == null) {
        continue;
      }
      Built built = FilesystemFixtureFactory.fromTree(fixture.dir());
      assertThatThrownBy(() -> built.query().project()).isInstanceOf(MissionStatusUnavailable.class);
      List<Diagnostic> diagnostics = built.diagnostics();
      assertThat(diagnostics).as(fixture.key()).isNotEmpty();
      if (fixture.key().equals("torn-final-line/unparseable-final-line")) {
        // L4 has no line number of its own: the tail is unterminated, so the diagnostic carries none
        assertThat(diagnostics).extracting(Diagnostic::line).containsOnlyNulls();
      } else {
        assertThat(diagnostics).extracting(Diagnostic::line).as(fixture.key() + " line").contains(line);
      }
      checked.add(fixture.key());
    }
    assertThat(checked).as("at least the ledger rows that Python numbers").isNotEmpty();
  }

  @Test
  void theReportedDivergencesAreExactlyTheTwoDocumentedOnesAndEachIsHandledNotSkipped() {
    assertThat(GoldenComparison.REPORTED_DIVERGENCES.keySet()).containsExactlyInAnyOrder("projection/strict-field-refused#project.json", "project-header/git-pointer-file#project.json");

    for (String key : GoldenComparison.REPORTED_DIVERGENCES.keySet()) {
      TreeFixture fixture = ConformanceTree.fixtures().stream().filter(candidate -> candidate.key().equals(key.substring(0, key.indexOf('#')))).findFirst().orElseThrow();
      GoldenComparison.Report report = GoldenComparison.verify(fixture, FilesystemFixtureFactory.fromTree(fixture.dir()).query());
      assertThat(report.divergencesHandled()).as(key).isEqualTo(1);
    }
  }

  // ---- knownDivergence and javaOnly ------------------------------------------------------------------------------------------

  @Test
  void theKnownDivergenceIsTaggedOnExactlyOneFixtureAndJavaRefusesItWithL4b() {
    List<String> tagged = ConformanceTree.fixtures().stream().filter(TreeFixture::knownDivergence).map(TreeFixture::key).toList();
    assertThat(tagged).containsExactly(KNOWN_DIVERGENCE);

    TreeFixture fixture = ConformanceTree.fixtures().stream().filter(candidate -> candidate.key().equals(KNOWN_DIVERGENCE)).findFirst().orElseThrow();
    assertThat(GoldenComparison.refusalException(ConformanceTree.golden(fixture, ConformanceTree.MISSIONS_GOLDEN))).as("the golden records a served overview").isNull();
    Built built = FilesystemFixtureFactory.fromTree(fixture.dir());

    assertThatThrownBy(() -> built.query().project()).isInstanceOfSatisfying(MissionStatusUnavailable.class, refusal -> assertThat(refusal.code()).isEqualTo(DiagnosticCode.LEDGER_TORN_TAIL));
    assertThatThrownBy(() -> built.query().missions(new PageRequest(50, null)))
        .isInstanceOfSatisfying(MissionStatusUnavailable.class, refusal -> assertThat(refusal.code()).isEqualTo(DiagnosticCode.LEDGER_TORN_TAIL));
  }

  @Test
  void theUnparseableTornTailIsRefusedWithL4OnBothReads() {
    TreeFixture fixture = ConformanceTree.fixturesOf("torn-final-line").stream().filter(candidate -> candidate.name().equals("unparseable-final-line")).findFirst().orElseThrow();
    Built built = FilesystemFixtureFactory.fromTree(fixture.dir());

    assertThatThrownBy(() -> built.query().project()).isInstanceOfSatisfying(MissionStatusUnavailable.class, refusal -> assertThat(refusal.code()).isEqualTo(DiagnosticCode.LEDGER_TORN_TAIL));
    assertThatThrownBy(() -> built.query().missions(new PageRequest(50, null)))
        .isInstanceOfSatisfying(MissionStatusUnavailable.class, refusal -> assertThat(refusal.code()).isEqualTo(DiagnosticCode.LEDGER_TORN_TAIL));
  }

  @Test
  void javaOnlyClassesAreSkippedByTagAndTheTagIsAssertedPresent() {
    List<ClassEntry> javaOnlyClasses = ConformanceTree.classes().stream().filter(entry -> entry.parity().equals(ConformanceTree.PARITY_JAVA_ONLY)).toList();

    assertThat(javaOnlyClasses).extracting(ClassEntry::tag).containsExactlyInAnyOrder("secret-canaries", "symlink");
    for (ClassEntry entry : javaOnlyClasses) {
      assertThat(entry.fixtures()).as(entry.tag()).isNotEmpty().allSatisfy(fixture -> assertThat(fixture.javaOnly()).as(fixture.key() + " carries the javaOnly tag").isTrue());
    }
    assertThat(goldenFixtures().map(TreeFixture::key).filter(key -> key.startsWith("secret-canaries/") || key.startsWith("symlink/"))).as("none of them is compared with a golden").isEmpty();
    for (ClassEntry entry : javaOnlyClasses) {
      for (TreeFixture fixture : entry.fixtures()) {
        assertThat(fixture.dir().resolve(ConformanceTree.GOLDEN_DIR)).as(fixture.key() + " holds no golden").doesNotExist();
      }
    }
  }

  // ---- the census: classes exercised, floors, goldens present -----------------------------------------------------------------

  @Test
  void theTagsTheSuiteExercisedAreExactlyTheManifestsAndEveryClassMeetsItsFloor() {
    Set<String> exercised = new TreeSet<>();
    goldenFixtures().map(TreeFixture::tag).forEach(exercised::add);
    ConformanceTree.classes().stream().filter(entry -> entry.parity().equals(ConformanceTree.PARITY_JAVA_ONLY)).map(ClassEntry::tag).forEach(exercised::add);
    Set<String> manifestTags = ConformanceTree.classes().stream().map(ClassEntry::tag).collect(Collectors.toCollection(TreeSet::new));

    assertThat(exercised).isEqualTo(manifestTags);
    assertThat(manifestTags).isEqualTo(new TreeSet<>(CLASS_FLOORS.keySet()));
    for (ClassEntry entry : ConformanceTree.classes()) {
      assertThat(entry.fixtures().size()).as("fixtures of " + entry.tag()).isGreaterThanOrEqualTo(CLASS_FLOORS.get(entry.tag()));
      assertThat(entry.fixtures()).as(entry.tag() + " is not empty").isNotEmpty();
    }
  }

  @Test
  void everyFixtureTreeOnDiskIsInTheManifestAndEveryGoldenFixtureHasBothGoldens() throws Exception {
    Map<String, Set<String>> onDisk = new TreeMap<>();
    try (Stream<java.nio.file.Path> classes = java.nio.file.Files.list(ConformanceTree.root())) {
      for (java.nio.file.Path classDir : classes.filter(java.nio.file.Files::isDirectory).toList()) {
        try (Stream<java.nio.file.Path> fixtures = java.nio.file.Files.list(classDir)) {
          onDisk.put(classDir.getFileName().toString(), fixtures.filter(java.nio.file.Files::isDirectory).map(path -> path.getFileName().toString()).collect(Collectors.toCollection(TreeSet::new)));
        }
      }
    }
    Map<String, Set<String>> inManifest = new LinkedHashMap<>();
    ConformanceTree.allClasses().forEach(entry -> inManifest.put(entry.tag(), entry.fixtures().stream().map(TreeFixture::name).collect(Collectors.toCollection(TreeSet::new))));

    assertThat(onDisk).isEqualTo(new TreeMap<>(inManifest));
    for (TreeFixture fixture : goldenFixtures().toList()) {
      assertThat(ConformanceTree.golden(fixture, ConformanceTree.MISSIONS_GOLDEN)).as(fixture.key() + " missions golden").isNotNull();
      assertThat(ConformanceTree.golden(fixture, ConformanceTree.PROJECT_GOLDEN)).as(fixture.key() + " project golden").isNotNull();
    }
  }

  @Test
  void theIgnoreListIsOneNamedEmptyConstantAndTheSuiteUsesNoOther() {
    assertThat(CanonicalJson.IGNORED_MEMBERS).isEmpty();
  }

  @Test
  void aMissionsPageIsTheWholeDocumentWithPageInfo() {
    Built built = FilesystemFixtureFactory.fromTree(ConformanceTree.fixturesOf("interleaved").getFirst().dir());

    byte[] body = GoldenComparison.missionsBody(built.query());
    String text = new String(body, java.nio.charset.StandardCharsets.UTF_8);

    assertThat(text).startsWith("{\"items\":[").contains("\"pageInfo\":{\"hasNextPage\":false,\"nextPageCursor\":null,\"pageSize\":50}").endsWith("}\n");
  }
}
