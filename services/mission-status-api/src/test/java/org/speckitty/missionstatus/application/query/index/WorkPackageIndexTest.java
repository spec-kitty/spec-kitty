package org.speckitty.missionstatus.application.query.index;

import static org.assertj.core.api.Assertions.assertThat;
import static org.assertj.core.api.Assertions.assertThatThrownBy;

import java.io.IOException;
import java.nio.charset.StandardCharsets;
import java.nio.file.Files;
import java.nio.file.Path;
import java.util.ArrayList;
import java.util.List;
import java.util.Map;
import java.util.Optional;
import java.util.TreeMap;
import java.util.stream.Stream;
import org.junit.jupiter.api.Test;
import org.speckitty.missionstatus.adapter.out.filesystem.YamlFrontmatterDecoder;
import org.speckitty.missionstatus.application.query.port.out.FrontmatterDecoder;
import org.speckitty.missionstatus.application.query.port.out.dto.FileRef;
import org.speckitty.missionstatus.application.query.port.out.dto.MissionRef;
import org.speckitty.missionstatus.application.query.port.out.dto.RelativePath;
import org.speckitty.missionstatus.application.query.port.out.exceptions.TextFault;
import org.speckitty.missionstatus.domain.model.Diagnostic;
import org.speckitty.missionstatus.domain.model.DiagnosticCode;
import org.speckitty.missionstatus.domain.model.WpId;
import org.speckitty.missionstatus.testsupport.CanonicalJson;
import org.speckitty.missionstatus.testsupport.ConformanceTree;
import org.speckitty.missionstatus.testsupport.ConformanceTree.TreeFixture;
import org.speckitty.missionstatus.testsupport.InMemoryTextSource;

/**
 * AC-6.1 to AC-6.3 over the text-read port: the Work Package index against the oracle outcome class of every fixture {@code wpm-01..28},
 * the duplicate fixtures, the two selectors, and the faults. The source is {@link InMemoryTextSource} loaded from the committed fixture
 * trees, so the table runs on any host; the same trees through the real file system are read by {@link WorkPackageIndexProvisionedTest}.
 */
class WorkPackageIndexTest {

  static final MissionRef MISSION = new MissionRef("alpha-mission");
  static final String MID8 = "00000000";

  private final FrontmatterDecoder decoder = new YamlFrontmatterDecoder();

  // ---- loading a committed fixture into the in-memory port ---------------------------------------------------------------------

  /** The {@code tasks/} of a fixture's {@code alpha-mission} as the port would show it: files, directories and links as they are. */
  static InMemoryTextSource sourceOf(Path fixtureDir) throws IOException {
    InMemoryTextSource source = new InMemoryTextSource();
    Path tasks = fixtureDir.resolve("kitty-specs").resolve(MISSION.name()).resolve("tasks");
    if (!Files.isDirectory(tasks)) {
      return source;
    }
    try (Stream<Path> entries = Files.list(tasks)) {
      for (Path entry : entries.toList()) {
        FileRef ref = ref("tasks/" + entry.getFileName());
        if (Files.isSymbolicLink(entry)) {
          source.link(ref);
        } else if (Files.isDirectory(entry)) {
          try (Stream<Path> children = Files.list(entry)) {
            source.dir(ref, children.map(child -> child.getFileName().toString()).sorted().toArray(String[]::new));
          }
        } else {
          source.file(ref, Files.readAllBytes(entry));
        }
      }
    }
    return source;
  }

  static FileRef ref(String path) {
    return new FileRef.MissionFile(MISSION, RelativePath.of(path));
  }

  static List<TreeFixture> workPackageFixtures() {
    return ConformanceTree.detailFixtures().stream()
        .filter(fixture -> List.of("wp-malformed-frontmatter", "wp-duplicate-id", "wp-two-selectors").contains(fixture.tag()))
        .filter(fixture -> Files.isDirectory(fixture.dir().resolve("kitty-specs").resolve(MISSION.name())))
        .toList();
  }

  /** The ids and titles the oracle served for the fixture's Mission (its {@code get-work-package} golden), by id. */
  @SuppressWarnings("unchecked")
  static Map<String, String> oracleTitles(TreeFixture fixture) {
    Map<String, Object> golden = (Map<String, Object>) CanonicalJson.parse(ConformanceTree.golden(fixture, "get-work-package.json"));
    Map<String, String> titles = new TreeMap<>();
    golden.forEach((id, body) -> titles.put(id, (String) ((Map<String, Object>) body).get("title")));
    return titles;
  }

  private WorkPackageIndex index(InMemoryTextSource source) {
    return new WorkPackageIndex(source, decoder);
  }

  private WorkPackageIndex.Result build(InMemoryTextSource source, List<Diagnostic> diagnostics) {
    return index(source).build(MISSION, MID8, Optional.empty(), diagnostics::add);
  }

  // ---- AC-6.1: the corpus ------------------------------------------------------------------------------------------------------

  @Test
  void theIndexEqualsTheOracleOutcomeOfEveryFixtureOfTheCorpus() throws IOException {
    List<String> differences = new ArrayList<>();
    int checked = 0;
    for (TreeFixture fixture : workPackageFixtures()) {
      List<Diagnostic> diagnostics = new ArrayList<>();
      WorkPackageIndex.Result result = build(sourceOf(fixture.dir()), diagnostics);
      Map<String, String> actual = new TreeMap<>();
      result.workPackages().forEach(entry -> actual.put(entry.id().value(), entry.metadata().title()));
      Map<String, String> expected = oracleTitles(fixture);
      checked++;
      if (!actual.equals(expected)) {
        differences.add(fixture.key() + ": " + actual + " but the oracle served " + expected);
      }
    }
    assertThat(differences).isEmpty();
    assertThat(checked).as("every fixture of the three classes that holds a Mission").isGreaterThanOrEqualTo(28 + 2);
  }

  @Test
  void theValidControlIsParsedSoAnIndexThatSkipsEverythingIsRed() throws IOException {
    TreeFixture valid = workPackageFixtures().stream().filter(fixture -> fixture.name().equals("wpm-01")).findFirst().orElseThrow();
    WorkPackageIndex.Result result = build(sourceOf(valid.dir()), new ArrayList<>());
    assertThat(result.workPackages()).hasSize(1);
    assertThat(result.workPackages().get(0).id()).isEqualTo(new WpId("WP01"));
    assertThat(result.workPackages().get(0).fileName()).isEqualTo("WP01-valid.md");
    assertThat(result.workPackages().get(0).metadata().title()).isEqualTo("Valid");
  }

  @Test
  void everySkippedFileWritesOneWpFileSkippedDiagnosticWithTheMid8AndNoPath() throws IOException {
    for (TreeFixture fixture : workPackageFixtures()) {
      if (!fixture.tag().equals("wp-malformed-frontmatter") || !oracleTitles(fixture).isEmpty()) {
        continue;
      }
      List<Diagnostic> diagnostics = new ArrayList<>();
      build(sourceOf(fixture.dir()), diagnostics);
      boolean hasCandidate = Files.isDirectory(fixture.dir().resolve("kitty-specs/alpha-mission/tasks"));
      assertThat(diagnostics).as(fixture.key()).hasSize(hasCandidate ? 1 : 0);
      diagnostics.forEach(
          diagnostic -> {
            assertThat(diagnostic.code()).isEqualTo(DiagnosticCode.WP_FILE_SKIPPED);
            assertThat(diagnostic.mid8()).isEqualTo(MID8);
            assertThat(diagnostic.line()).isNull();
          });
    }
  }

  @Test
  void aByteOrderOfNamesThatDiffersFromCaseFoldedOrderPicksTheCapitalFirst() throws IOException {
    TreeFixture fixture = workPackageFixtures().stream().filter(candidate -> candidate.name().equals("wpm-27")).findFirst().orElseThrow();
    List<Diagnostic> diagnostics = new ArrayList<>();
    WorkPackageIndex.Result result = build(sourceOf(fixture.dir()), diagnostics);
    assertThat(result.workPackages()).hasSize(1);
    assertThat(result.workPackages().get(0).fileName()).isEqualTo("WP01-B.md");
    assertThat(result.workPackages().get(0).metadata().title()).isEqualTo("Upper B");
    assertThat(diagnostics).extracting(Diagnostic::code).containsExactly(DiagnosticCode.WP_ID_DUPLICATE);
  }

  @Test
  void aSubtasksMappingIsIndexedAndCarriesTheRefusalFlagForTheRoute() throws IOException {
    TreeFixture fixture = workPackageFixtures().stream().filter(candidate -> candidate.name().equals("wpm-28")).findFirst().orElseThrow();
    WorkPackageIndex.Result result = build(sourceOf(fixture.dir()), new ArrayList<>());
    assertThat(result.workPackages()).as("the oracle parsed it: so does the index").hasSize(1);
    assertThat(result.workPackages().get(0).metadata().subtasksRefused()).as("V20: the route answers projection_refused").isTrue();
    @SuppressWarnings("unchecked")
    Map<String, Object> divergence =
        ConformanceTree.knownDivergences().stream().filter(entry -> entry.get("id").equals("V20")).findFirst().orElseThrow();
    assertThat(divergence.get("javaAssertion")).isEqualTo("projection_refused");
    assertThat((List<Object>) divergence.get("fixtures")).containsExactly("wp-malformed-frontmatter/wpm-28");
  }

  // ---- AC-6.2 and AC-6.3 -------------------------------------------------------------------------------------------------------

  @Test
  void aDuplicateIdServesTheFirstFileInByteOrderAndWritesOneDuplicateDiagnostic() throws IOException {
    TreeFixture fixture = workPackageFixtures().stream().filter(candidate -> candidate.name().equals("duplicate-wp-id")).findFirst().orElseThrow();
    List<Diagnostic> diagnostics = new ArrayList<>();
    WorkPackageIndex.Result result = build(sourceOf(fixture.dir()), diagnostics);
    assertThat(result.workPackages()).hasSize(1);
    assertThat(result.workPackages().get(0).metadata().title()).isEqualTo("First holder");
    assertThat(result.workPackages().get(0).fileName()).isEqualTo("WP01-first.md");
    assertThat(diagnostics).containsExactly(new Diagnostic(DiagnosticCode.WP_ID_DUPLICATE, MID8, null));
  }

  @Test
  void theSameMissionWithOneFileServesThatFileAndWritesNoDiagnostic() throws IOException {
    InMemoryTextSource source = new InMemoryTextSource().file(ref("tasks/WP01-first.md"), file("WP01", "First holder"));
    List<Diagnostic> diagnostics = new ArrayList<>();
    assertThat(build(source, diagnostics).workPackages()).hasSize(1);
    assertThat(diagnostics).isEmpty();
  }

  @Test
  void theFrontmatterSelectsTheWorkPackageAndTheFileNameSelectsThePrompt() throws IOException {
    TreeFixture fixture = workPackageFixtures().stream().filter(candidate -> candidate.name().equals("two-selectors")).findFirst().orElseThrow();
    WorkPackageIndex.Result result = build(sourceOf(fixture.dir()), new ArrayList<>());
    assertThat(result.workPackages()).hasSize(1);
    IndexedWorkPackage winner = result.workPackages().get(0);
    assertThat(winner.id()).isEqualTo(new WpId("WP08"));
    assertThat(winner.fileName()).as("the file that holds the frontmatter, not the file named WP08-*").isEqualTo("WP07-x.md");
    assertThat(winner.metadata().title()).isEqualTo("From file x");
  }

  @Test
  void theWinnersAreInIdOrderWhateverTheFileOrder() {
    InMemoryTextSource source =
        new InMemoryTextSource()
            .file(ref("tasks/WP01-z.md"), file("WP10", "ten"))
            .file(ref("tasks/WP02-y.md"), file("WP02", "two"))
            .file(ref("tasks/WP03-x.md"), file("WP09", "nine"));
    assertThat(build(source, new ArrayList<>()).workPackages()).extracting(entry -> entry.id().value()).containsExactly("WP02", "WP09", "WP10");
  }

  // ---- candidate selection -----------------------------------------------------------------------------------------------------

  @Test
  void onlyEntriesThatStartWithWpAndEndWithDotMdCaseSensitivelyAreCandidates() {
    InMemoryTextSource source =
        new InMemoryTextSource()
            .file(ref("tasks/WP01-ok.md"), file("WP01", "ok"))
            .file(ref("tasks/wp02.md"), file("WP02", "lower"))
            .file(ref("tasks/WP03.MD"), file("WP03", "upper suffix"))
            .file(ref("tasks/WP04.txt"), file("WP04", "txt"))
            .file(ref("tasks/README.md"), file("WP05", "readme"))
            .file(ref("tasks/XWP06.md"), file("WP06", "prefix"));
    List<Diagnostic> diagnostics = new ArrayList<>();
    assertThat(build(source, diagnostics).workPackages()).extracting(entry -> entry.id().value()).containsExactly("WP01");
    assertThat(diagnostics).as("a non-candidate is not a skipped file").isEmpty();
  }

  @Test
  void anAbsentTasksDirectoryIsAnEmptyIndex() {
    WorkPackageIndex.Result result = build(new InMemoryTextSource(), new ArrayList<>());
    assertThat(result.workPackages()).isEmpty();
    assertThat(result.capturedBody()).isEmpty();
  }

  @Test
  void aTasksEntryThatIsARegularFileIsAFaultNeverAnEmptyIndex() {
    InMemoryTextSource source = new InMemoryTextSource().file(ref("tasks"), new byte[] {'x'});
    assertThatThrownBy(() -> build(source, new ArrayList<>()))
        .isInstanceOfSatisfying(WorkPackageIndexFault.class, fault -> assertThat(fault.kind()).isEqualTo(WorkPackageIndexFault.Kind.TASKS_NOT_A_DIRECTORY));
  }

  @Test
  void aTasksEntryThatIsALinkIsAFaultOfThePort() {
    InMemoryTextSource source = new InMemoryTextSource().link(ref("tasks"));
    assertThatThrownBy(() -> build(source, new ArrayList<>()))
        .isInstanceOfSatisfying(TextFault.class, fault -> assertThat(fault.kind()).isEqualTo(TextFault.Kind.PATH_REFUSED));
  }

  @Test
  void aFaultOfThePortWhileListingOrReadingPropagatesAsTheFaultItIs() {
    InMemoryTextSource listing = new InMemoryTextSource().fault(ref("tasks"), TextFault.Kind.DIR_UNREADABLE);
    assertThatThrownBy(() -> build(listing, new ArrayList<>())).isInstanceOf(TextFault.class);
    InMemoryTextSource reading =
        new InMemoryTextSource().file(ref("tasks/WP01-a.md"), file("WP01", "a")).fault(ref("tasks/WP02-b.md"), TextFault.Kind.FILE_UNREADABLE);
    assertThatThrownBy(() -> build(reading, new ArrayList<>())).isInstanceOf(TextFault.class);
  }

  @Test
  void aCandidateOverOneMebibyteIsAFaultAndOneAtTheCapIsRead() {
    byte[] atCap = padded(file("WP01", "at the cap"), WorkPackageIndex.FILE_CAP_BYTES);
    assertThat(build(new InMemoryTextSource().file(ref("tasks/WP01-a.md"), atCap), new ArrayList<>()).workPackages()).hasSize(1);
    byte[] overCap = padded(file("WP01", "over"), WorkPackageIndex.FILE_CAP_BYTES + 1);
    assertThatThrownBy(() -> build(new InMemoryTextSource().file(ref("tasks/WP01-a.md"), overCap), new ArrayList<>()))
        .isInstanceOfSatisfying(WorkPackageIndexFault.class, fault -> assertThat(fault.kind()).isEqualTo(WorkPackageIndexFault.Kind.FILE_TOO_LARGE));
  }

  @Test
  void aListingLongerThanTheWindowIsRefusedNotIndexedInPart() {
    String[] names = new String[WorkPackageIndex.LISTING_LIMIT + 1];
    for (int i = 0; i < names.length; i++) {
      names[i] = "WP" + i + ".md";
    }
    InMemoryTextSource source = new InMemoryTextSource().dir(ref("tasks"), names);
    assertThatThrownBy(() -> build(source, new ArrayList<>()))
        .isInstanceOfSatisfying(WorkPackageIndexFault.class, fault -> assertThat(fault.kind()).isEqualTo(WorkPackageIndexFault.Kind.LISTING_TOO_LARGE));
  }

  @Test
  void aCandidateListedButGoneWhenReadIsAFaultAndOneTurnedIntoANonFileIsSkipped() {
    // listed by the directory entry, but no entry of its own: the stat sees nothing, so it is skipped like an ineligible path
    InMemoryTextSource gone = new InMemoryTextSource().dir(ref("tasks"), "WP01-a.md");
    List<Diagnostic> diagnostics = new ArrayList<>();
    assertThat(build(gone, diagnostics).workPackages()).isEmpty();
    assertThat(diagnostics).hasSize(1);
  }

  @Test
  void aCandidateWhoseNameIsNotAValidPathSegmentOrArtifactPathIsSkippedWithoutAnyRead() {
    InMemoryTextSource source = new InMemoryTextSource().dir(ref("tasks"), "WP01-a\\b.md", "WP02-\ufffd.md", "WP03-a\nb.md");
    List<Diagnostic> diagnostics = new ArrayList<>();
    assertThat(build(source, diagnostics).workPackages()).isEmpty();
    assertThat(diagnostics).hasSize(3);
    assertThat(source.readRefs()).as("only the listing was asked for").containsExactly(ref("tasks"));
  }

  @Test
  void aFileThatIsNotAWorkPackageFileOfTheOracleIsSkippedAndOneWithNoValidIdToo() {
    InMemoryTextSource source =
        new InMemoryTextSource()
            .file(ref("tasks/WP01-bad.md"), "no frontmatter".getBytes(StandardCharsets.UTF_8))
            .file(ref("tasks/WP02-noid.md"), "---\ntitle: x\n---\n".getBytes(StandardCharsets.UTF_8))
            .file(ref("tasks/WP03-ok.md"), file("WP03", "ok"));
    List<Diagnostic> diagnostics = new ArrayList<>();
    assertThat(build(source, diagnostics).workPackages()).extracting(entry -> entry.id().value()).containsExactly("WP03");
    assertThat(diagnostics).extracting(Diagnostic::code).containsExactly(DiagnosticCode.WP_FILE_SKIPPED, DiagnosticCode.WP_FILE_SKIPPED);
  }

  @Test
  void anIdThatPassesPydanticButNotTheContractIdIsSkipped() {
    InMemoryTextSource source =
        new InMemoryTextSource()
            .file(ref("tasks/WP01-nl.md"), "---\nwork_package_id: \"WP01\\n\"\n---\n".getBytes(StandardCharsets.UTF_8))
            .file(ref("tasks/WP02-ok.md"), file("WP02", "ok"));
    List<Diagnostic> diagnostics = new ArrayList<>();
    assertThat(build(source, diagnostics).workPackages()).extracting(entry -> entry.id().value()).containsExactly("WP02");
    assertThat(diagnostics).hasSize(1);
  }

  // ---- the body of one id ------------------------------------------------------------------------------------------------------

  @Test
  void theBodyOfTheRequestedIdIsCapturedFromTheSameReadAndNoOtherBodyIs() {
    InMemoryTextSource source =
        new InMemoryTextSource()
            .file(ref("tasks/WP01-a.md"), "---\nwork_package_id: WP01\n---\nbody one\n".getBytes(StandardCharsets.UTF_8))
            .file(ref("tasks/WP02-b.md"), "---\nwork_package_id: WP02\n---\nbody two\n".getBytes(StandardCharsets.UTF_8));
    WorkPackageIndex.Result two = index(source).build(MISSION, MID8, Optional.of(new WpId("WP02")), diagnostic -> {});
    assertThat(two.capturedBody()).contains("body two\n");
    WorkPackageIndex.Result none = index(source).build(MISSION, MID8, Optional.of(new WpId("WP09")), diagnostic -> {});
    assertThat(none.capturedBody()).isEmpty();
    assertThat(index(source).build(MISSION, MID8, Optional.empty(), diagnostic -> {}).capturedBody()).isEmpty();
  }

  @Test
  void theBodyOfTheWinnerIsCapturedNotThatOfALaterDuplicate() {
    InMemoryTextSource source =
        new InMemoryTextSource()
            .file(ref("tasks/WP01-a.md"), "---\nwork_package_id: WP01\n---\nfirst\n".getBytes(StandardCharsets.UTF_8))
            .file(ref("tasks/WP01-b.md"), "---\nwork_package_id: WP01\n---\nsecond\n".getBytes(StandardCharsets.UTF_8));
    assertThat(index(source).build(MISSION, MID8, Optional.of(new WpId("WP01")), diagnostic -> {}).capturedBody()).contains("first\n");
  }

  // ---- construction ------------------------------------------------------------------------------------------------------------

  @Test
  void thePublicConstructorTakesExactlyThePortAndTheDecoder() throws NoSuchMethodException {
    assertThat(WorkPackageIndex.class.getConstructors()).hasSize(1);
    assertThat(WorkPackageIndex.class.getConstructor(org.speckitty.missionstatus.application.query.port.out.TextSource.class, FrontmatterDecoder.class)).isNotNull();
    assertThat(java.lang.reflect.Modifier.isFinal(WorkPackageIndex.class.getModifiers())).isTrue();
    assertThat(java.lang.reflect.Modifier.isPublic(WorkPackageIndex.class.getModifiers())).isTrue();
    assertThatThrownBy(() -> new WorkPackageIndex(null, decoder)).isInstanceOf(NullPointerException.class);
    assertThatThrownBy(() -> new WorkPackageIndex(new InMemoryTextSource(), null)).isInstanceOf(NullPointerException.class);
  }

  @Test
  void theIndexResultAndTheEntryAreImmutableAndRequireTheirMembers() {
    WorkPackageIndex.Result result = new WorkPackageIndex.Result(new ArrayList<>(), Optional.empty());
    assertThatThrownBy(() -> result.workPackages().add(null)).isInstanceOf(UnsupportedOperationException.class);
    assertThatThrownBy(() -> new IndexedWorkPackage(null, "f", null)).isInstanceOf(NullPointerException.class);
    assertThatThrownBy(() -> new IndexedWorkPackage(new WpId("WP01"), null, null)).isInstanceOf(NullPointerException.class);
    assertThatThrownBy(() -> new IndexedWorkPackage(new WpId("WP01"), "f", null)).isInstanceOf(NullPointerException.class);
    assertThatThrownBy(() -> new WpFile(null)).isInstanceOf(NullPointerException.class);
    assertThatThrownBy(() -> new WorkPackageIndexFault(null)).isInstanceOf(NullPointerException.class);
  }

  // ---- helpers -----------------------------------------------------------------------------------------------------------------

  static byte[] file(String id, String title) {
    return ("---\nwork_package_id: " + id + "\ntitle: " + title + "\n---\n\n# Body\n").getBytes(StandardCharsets.UTF_8);
  }

  /** The bytes padded with a comment in the body until they are exactly {@code size} long. */
  private static byte[] padded(byte[] content, int size) {
    byte[] out = new byte[size];
    System.arraycopy(content, 0, out, 0, content.length);
    for (int i = content.length; i < size; i++) {
      out[i] = (byte) 'x';
    }
    return out;
  }
}
