package org.speckitty.missionstatus.application.query;

import static org.assertj.core.api.Assertions.assertThat;
import static org.assertj.core.api.Assertions.assertThatThrownBy;

import java.io.IOException;
import java.nio.charset.StandardCharsets;
import java.nio.file.Files;
import java.nio.file.Path;
import java.util.List;
import java.util.stream.Stream;
import org.junit.jupiter.api.Test;
import org.speckitty.missionstatus.adapter.out.filesystem.Allowlist.OpenMode;
import org.speckitty.missionstatus.adapter.out.filesystem.Allowlist.PathClass;
import org.speckitty.missionstatus.application.query.port.in.dto.ArtifactPathInput;
import org.speckitty.missionstatus.application.query.port.in.exceptions.DetailRefusal;
import org.speckitty.missionstatus.application.query.port.out.TextSource;
import org.speckitty.missionstatus.domain.model.Diagnostic;
import org.speckitty.missionstatus.domain.model.DiagnosticCode;
import org.speckitty.missionstatus.domain.model.MissionId;
import org.speckitty.missionstatus.domain.readmodel.detail.ArtifactContent;
import org.speckitty.missionstatus.domain.readmodel.detail.ArtifactEntry;
import org.speckitty.missionstatus.domain.readmodel.detail.ArtifactKind;
import org.speckitty.missionstatus.domain.readmodel.detail.ArtifactListing;
import org.speckitty.missionstatus.domain.redaction.TextScreen;
import org.speckitty.missionstatus.testsupport.ConformanceTree;
import org.speckitty.missionstatus.testsupport.DetailFixture;
import org.speckitty.missionstatus.testsupport.LeakPatternsFile;

/**
 * The application service of the two artifact routes over real fixture trees: the lookup rows C2 to C7, the order of decision of the
 * content read, the diagnostics of rows A1 to A7, and the typed refusals that carry no path.
 */
class ArtifactQueryServiceTest {

  /** The helpers every test of the artifact service shares. */
  static final class Trees {
    static final String ID = "00000000000000000000000001";
    static final String UNKNOWN = "00000000000000000000000009";

    private Trees() {}

    static Path dir(String tag, String name) {
      return ConformanceTree.detailFixtures().stream().filter(f -> f.key().equals(tag + "/" + name)).findFirst().orElseThrow().dir();
    }

    static DetailFixture fixture(String tag, String name) {
      return DetailFixture.of(dir(tag, name));
    }

    static Path mission(DetailFixture fixture) {
      return fixture.root().resolve("kitty-specs").resolve("alpha-mission");
    }

    static MissionId id() {
      return MissionId.parse(ID).orElseThrow();
    }

    static MissionId unknown() {
      return MissionId.parse(UNKNOWN).orElseThrow();
    }

    static ArtifactQueryService service(DetailFixture fixture) {
      return service(fixture, new AdmissionGate(), fixture.textSource());
    }

    static ArtifactQueryService service(DetailFixture fixture, AdmissionGate gate, TextSource source) {
      return new ArtifactQueryService(fixture.readModel(), source, gate, fixture.built().handles().recorder(), new TextScreen(LeakPatternsFile.load()));
    }

    static ArtifactPathInput path(String... values) {
      return new ArtifactPathInput.Values(List.of(values));
    }

    static List<String> paths(ArtifactListing listing) {
      return listing.entries().stream().map(ArtifactEntry::path).toList();
    }

    static List<DiagnosticCode> codes(DetailFixture fixture) {
      return fixture.diagnostics().stream().map(Diagnostic::code).toList();
    }

    static DetailRefusal.Kind refusal(Runnable call) {
      return org.assertj.core.api.Assertions.catchThrowableOfType(DetailRefusal.class, call::run).kind();
    }

    static void write(Path file, String text) {
      try {
        Files.createDirectories(file.getParent());
        Files.writeString(file, text, StandardCharsets.UTF_8);
      } catch (IOException failure) {
        throw new java.io.UncheckedIOException(failure);
      }
    }

    static String meta(String missionId, String slug) {
      return "{\"mission_id\": \"" + missionId + "\", \"mission_slug\": \"" + slug + "\", \"slug\": \"" + slug
          + "\", \"friendly_name\": \"Fixture\", \"mission_number\": null, \"mission_type\": \"software-dev\", \"target_branch\": \"main\", \"created_at\": \"2026-09-01T10:00:00+00:00\"}";
    }
  }

  // ---- the listing -----------------------------------------------------------------------------------------------------------

  @Test
  void aPopulatedMissionListsItsEligibleFilesInByteOrderWithTheirClasses() {
    DetailFixture fixture = Trees.fixture("artifacts-populated", "artifacts-populated");

    ArtifactListing listing = Trees.service(fixture).list(Trees.id());

    assertThat(listing.missionId()).isEqualTo(Trees.id());
    assertThat(listing.truncated()).isFalse();
    assertThat(Trees.paths(listing))
        .containsExactly(
            "analysis-report.md", "checklists/review.md", "contracts/api.yaml", "data-model.md", "data.csv", "extra.txt", "meta.json", "plan.md", "quickstart.md",
            "research/notes.md", "spec.md", "tasks.md", "tasks/WP01-fixture.md", "tasks/WP01-fixture/review-cycle-1.md");
    assertThat(listing.entries()).extracting(ArtifactEntry::kind).contains(ArtifactKind.REVIEW_CYCLE, ArtifactKind.WORK_PACKAGE_PROMPT, ArtifactKind.CHECKLIST, ArtifactKind.CONTRACT);
    assertThat(listing.entries()).allMatch(ArtifactEntry::readable);
    assertThat(Trees.codes(fixture)).isEmpty();
  }

  @Test
  void theRootStatusRecordsInAnyCaseAreNotListedButTheSameNamesBelowARootDirectoryAre() {
    DetailFixture fixture = Trees.fixture("artifacts-populated", "artifacts-populated");
    Trees.write(Trees.mission(fixture).resolve("STATUS.JSON"), "{}");
    Trees.write(Trees.mission(fixture).resolve("notes/status.json"), "{}");

    List<String> paths = Trees.paths(Trees.service(fixture).list(Trees.id()));

    assertThat(paths).doesNotContain("status.events.jsonl", "STATUS.JSON", "status.json").contains("notes/status.json");
  }

  @Test
  void theListingNeverTouchesTheRootStatusRecordsEvenToStatThem() {
    DetailFixture fixture = Trees.fixture("artifacts-populated", "artifacts-populated");
    Trees.write(Trees.mission(fixture).resolve("status.json"), "{}");
    fixture.recorder().clear();

    Trees.service(fixture).list(Trees.id());

    assertThat(fixture.recorder().accesses()).noneMatch(access -> access.path().endsWith("/status.json") || access.path().endsWith("/status.events.jsonl"));
    assertThat(fixture.recorder().violations()).isEmpty();
  }

  // ---- the content read: the order of decision -------------------------------------------------------------------------------

  @Test
  void eachStatusOfTheContentReadHasItsOwnFixtureNextToAControlThatIsServed() {
    DetailFixture fixture = Trees.fixture("artifacts-refusals", "artifacts-refusals");
    ArtifactQueryService service = Trees.service(fixture);

    ArtifactContent control = service.content(Trees.id(), Trees.path("ok.md"));

    assertThat(control.path()).isEqualTo("ok.md");
    assertThat(control.kind()).isEqualTo(ArtifactKind.OTHER);
    assertThat(control.mediaType()).isEqualTo("text/markdown");
    assertThat(control.redacted()).isFalse();
    assertThat(Trees.refusal(() -> service.content(Trees.id(), Trees.path("missing.md")))).isEqualTo(DetailRefusal.Kind.NOT_FOUND);
    assertThat(Trees.refusal(() -> service.content(Trees.id(), Trees.path("too-large.md")))).isEqualTo(DetailRefusal.Kind.ARTIFACT_TOO_LARGE);
    assertThat(Trees.refusal(() -> service.content(Trees.id(), Trees.path("not-text-nul.dat")))).isEqualTo(DetailRefusal.Kind.ARTIFACT_NOT_TEXT);
    assertThat(Trees.refusal(() -> service.content(Trees.id(), Trees.path("not-text-latin1.txt")))).isEqualTo(DetailRefusal.Kind.ARTIFACT_NOT_TEXT);
    assertThat(Trees.refusal(() -> service.content(Trees.id(), Trees.path("secret.txt")))).isEqualTo(DetailRefusal.Kind.ARTIFACT_SECRET);
    assertThat(Trees.refusal(() -> service.content(Trees.id(), Trees.path("status.events.jsonl")))).isEqualTo(DetailRefusal.Kind.NOT_FOUND);
    assertThat(Trees.refusal(() -> service.content(Trees.id(), Trees.path("STATUS.JSON")))).isEqualTo(DetailRefusal.Kind.NOT_FOUND);
  }

  @Test
  void aDirectoryIsNotAnArtifactAndAMissingPathBelowAFileIsNotFound() {
    DetailFixture fixture = Trees.fixture("artifacts-populated", "artifacts-populated");
    ArtifactQueryService service = Trees.service(fixture);

    assertThat(Trees.refusal(() -> service.content(Trees.id(), Trees.path("tasks")))).isEqualTo(DetailRefusal.Kind.NOT_FOUND);
    assertThat(Trees.refusal(() -> service.content(Trees.id(), Trees.path("spec.md/below")))).isEqualTo(DetailRefusal.Kind.NOT_FOUND);
    assertThat(service.content(Trees.id(), Trees.path("tasks/WP01-fixture/review-cycle-1.md")).kind()).isEqualTo(ArtifactKind.REVIEW_CYCLE);
    assertThat(Trees.codes(fixture)).as("a 404 writes no diagnostic").isEmpty();
  }

  @Test
  void theCountOfValuesAndTheArtifactPathRuleAreDecidedBehindThePortBeforeTheLookup() {
    DetailFixture fixture = Trees.fixture("artifacts-populated", "artifacts-populated");
    ArtifactQueryService service = Trees.service(fixture);
    fixture.recorder().clear();

    List<ArtifactPathInput> bad =
        List.of(
            new ArtifactPathInput.Values(List.of()), Trees.path("a", "b"), Trees.path("spec.md", "plan.md"), new ArtifactPathInput.Undecodable(), Trees.path(""),
            Trees.path("../x"), Trees.path("a//b"), Trees.path("a/"), Trees.path("/a"), Trees.path("a\\b"), Trees.path("a\u0000b"), Trees.path("a\nb"), Trees.path("C:x"),
            Trees.path("~/x"), Trees.path("x".repeat(513)), Trees.path("lone\ud800"));
    for (ArtifactPathInput input : bad) {
      assertThat(Trees.refusal(() -> service.content(Trees.id(), input))).as(input.toString()).isEqualTo(DetailRefusal.Kind.INVALID_ARTIFACT_PATH);
      // spec order: the path is judged before the Mission is looked up, so an unknown Mission with a bad path is also 400
      assertThat(Trees.refusal(() -> service.content(Trees.unknown(), input))).as("unknown Mission, " + input).isEqualTo(DetailRefusal.Kind.INVALID_ARTIFACT_PATH);
    }
    for (String accepted : List.of("a b.md", "a@b.md", ".hidden", "home/x.md", "a/".repeat(255) + "ab")) {
      assertThat(Trees.refusal(() -> service.content(Trees.id(), Trees.path(accepted))))
          .as(accepted.length() > 20 ? "512 characters" : accepted)
          .isEqualTo(DetailRefusal.Kind.NOT_FOUND);
    }
    assertThat(Trees.codes(fixture)).isEmpty();
  }

  /** The one accepted name that is not ASCII: looking it up needs a host that decodes file names as UTF-8, so it is skipped elsewhere (D-128). */
  @Test
  void aWellFormedNonAsciiArtifactPathIsNotFoundOnAUtf8Host(org.junit.jupiter.api.TestInfo info) {
    org.speckitty.missionstatus.testsupport.Utf8Host.assumeUtf8(info.getTestClass().orElseThrow().getName() + "#" + info.getTestMethod().orElseThrow().getName());
    DetailFixture fixture = Trees.fixture("artifacts-populated", "artifacts-populated");
    ArtifactQueryService service = Trees.service(fixture);

    assertThat(Trees.refusal(() -> service.content(Trees.id(), Trees.path("caf\u00e9.md")))).isEqualTo(DetailRefusal.Kind.NOT_FOUND);
  }

  @Test
  void aWellFormedUnknownMissionIsNotFoundForBothOperationsWithNoDiagnostic() {
    DetailFixture fixture = Trees.fixture("artifacts-populated", "artifacts-populated");
    ArtifactQueryService service = Trees.service(fixture);

    assertThat(Trees.refusal(() -> service.list(Trees.unknown()))).isEqualTo(DetailRefusal.Kind.NOT_FOUND);
    assertThat(Trees.refusal(() -> service.content(Trees.unknown(), Trees.path("spec.md")))).isEqualTo(DetailRefusal.Kind.NOT_FOUND);
    assertThat(Trees.codes(fixture)).isEmpty();
  }

  @Test
  void aRefusalCarriesItsKindAndNoPath() {
    DetailFixture fixture = Trees.fixture("artifacts-refusals", "artifacts-refusals");

    DetailRefusal refusal = org.assertj.core.api.Assertions.catchThrowableOfType(DetailRefusal.class, () -> Trees.service(fixture).content(Trees.id(), Trees.path("secret.txt")));

    assertThat(refusal.getMessage()).isEqualTo("artifact_secret").doesNotContain("secret.txt", "/");
    assertThat(refusal.getCause()).isNull();
  }

  // ---- the diagnostics of rows A4 to A7: one line, the code and the mid8 ---------------------------------------------------------

  @Test
  void eachContentRefusalWritesExactlyOneDiagnosticWithTheMissionsMid8() {
    DetailFixture fixture = Trees.fixture("artifacts-refusals", "artifacts-refusals");
    ArtifactQueryService service = Trees.service(fixture);
    record Row(String path, DiagnosticCode code) {}

    for (Row row : List.of(new Row("too-large.md", DiagnosticCode.ARTIFACT_TOO_LARGE), new Row("not-text-nul.dat", DiagnosticCode.ARTIFACT_NOT_TEXT), new Row("secret.txt", DiagnosticCode.ARTIFACT_SECRET))) {
      int before = fixture.diagnostics().size();
      Trees.refusal(() -> service.content(Trees.id(), Trees.path(row.path())));
      assertThat(fixture.diagnostics().subList(before, fixture.diagnostics().size())).as(row.path()).containsExactly(new Diagnostic(row.code(), Trees.ID.substring(0, 8), null));
    }
  }

  // ---- the lookup rows C3 to C7 ------------------------------------------------------------------------------------------------

  @Test
  void rowC3AMissionDirectoryRefusedAsALinkWithNoMatchIsNotFoundWithPathRefused() {
    DetailFixture fixture = Trees.fixture("lookup-faults", "bad-sibling-unknown-link");
    ArtifactQueryService service = Trees.service(fixture);

    assertThat(Trees.refusal(() -> service.list(Trees.unknown()))).isEqualTo(DetailRefusal.Kind.NOT_FOUND);
    assertThat(Trees.refusal(() -> service.content(Trees.unknown(), Trees.path("spec.md")))).isEqualTo(DetailRefusal.Kind.NOT_FOUND);
    assertThat(Trees.codes(fixture)).containsExactly(DiagnosticCode.PATH_REFUSED, DiagnosticCode.PATH_REFUSED);
  }

  @Test
  void rowC4AnUnusableMetaJsonWithNoMatchIs500WithTheRoutesCodeAndMetaUnparseable() {
    DetailFixture fixture = Trees.fixture("lookup-faults", "bad-sibling-unknown-meta");
    ArtifactQueryService service = Trees.service(fixture);

    assertThat(Trees.refusal(() -> service.list(Trees.unknown()))).isEqualTo(DetailRefusal.Kind.ARTIFACT_LISTING_UNREADABLE);
    assertThat(Trees.refusal(() -> service.content(Trees.unknown(), Trees.path("spec.md")))).isEqualTo(DetailRefusal.Kind.ARTIFACT_UNREADABLE);
    assertThat(Trees.codes(fixture)).containsExactly(DiagnosticCode.META_UNPARSEABLE, DiagnosticCode.META_UNPARSEABLE);
  }

  @Test
  void rowC5ASpecsDirectoryThatCannotBeListedIs500WithMissionDirUnreadable() {
    DetailFixture fixture = Trees.fixture("artifacts-populated", "artifacts-populated");
    fixture.recorder().failWhen(access -> access.pathClass() == PathClass.SPECS_DIR && access.mode() == OpenMode.LIST, () -> new java.nio.file.AccessDeniedException("injected"));
    ArtifactQueryService service = Trees.service(fixture);

    assertThat(Trees.refusal(() -> service.list(Trees.id()))).isEqualTo(DetailRefusal.Kind.ARTIFACT_LISTING_UNREADABLE);
    assertThat(Trees.refusal(() -> service.content(Trees.id(), Trees.path("spec.md")))).isEqualTo(DetailRefusal.Kind.ARTIFACT_UNREADABLE);
    assertThat(Trees.codes(fixture)).containsExactly(DiagnosticCode.MISSION_DIR_UNREADABLE, DiagnosticCode.MISSION_DIR_UNREADABLE);
  }

  @Test
  void rowC5ASiblingDirectoryThatCannotBeStatedWithNoMatchIs500WithMissionDirUnreadable() {
    DetailFixture fixture = Trees.fixture("artifacts-populated", "artifacts-populated");
    Trees.write(fixture.root().resolve("kitty-specs").resolve("sibling").resolve("meta.json"), Trees.meta("00000000000000000000000007", "sibling"));
    fixture.recorder().failWhen(access -> access.pathClass() == PathClass.MISSION_DIR && access.path().endsWith("/sibling"), () -> new java.nio.file.AccessDeniedException("injected"));
    ArtifactQueryService service = Trees.service(fixture);

    assertThat(Trees.refusal(() -> service.list(Trees.unknown()))).isEqualTo(DetailRefusal.Kind.ARTIFACT_LISTING_UNREADABLE);
    assertThat(Trees.codes(fixture)).containsExactly(DiagnosticCode.MISSION_DIR_UNREADABLE);
    assertThat(service.list(Trees.id()).entries()).as("the readable Mission is served: a faulted sibling is ignored").isNotEmpty();
  }

  @Test
  void rowC6TwoDirectoriesWithTheIdServeTheFirstInByteOrderAndWriteTheDuplicateDiagnostic() {
    DetailFixture fixture = Trees.fixture("artifacts-populated", "artifacts-populated");
    Path copy = fixture.root().resolve("kitty-specs").resolve("alpha-copy");
    Trees.write(copy.resolve("meta.json"), Trees.meta(Trees.ID, "alpha-copy"));
    Trees.write(copy.resolve("only-in-the-first.md"), "first\n");

    ArtifactListing listing = Trees.service(fixture).list(Trees.id());

    assertThat(Trees.paths(listing)).containsExactly("meta.json", "only-in-the-first.md");
    assertThat(Trees.codes(fixture)).containsExactly(DiagnosticCode.MISSION_ID_DUPLICATE);
    assertThat(Trees.service(fixture).content(Trees.id(), Trees.path("only-in-the-first.md")).content()).isEqualTo("first\n");
  }

  @Test
  void rowC7AFaultedSiblingBeforeOrAfterTheMatchIsIgnoredWithNoDiagnostic() {
    DetailFixture fixture = Trees.fixture("lookup-faults", "bad-sibling-unknown-meta");
    Trees.write(fixture.root().resolve("kitty-specs").resolve("0-broken-before").resolve("meta.json"), "{not json");
    Trees.write(Trees.mission(fixture).resolve("extra.md"), "x\n");

    ArtifactListing listing = Trees.service(fixture).list(Trees.id());

    assertThat(Trees.paths(listing)).contains("extra.md", "meta.json");
    assertThat(Trees.service(fixture).content(Trees.id(), Trees.path("extra.md")).content()).isEqualTo("x\n");
    assertThat(Trees.codes(fixture)).isEmpty();
  }

  @Test
  void aMissionWhoseLedgerIsUnreadableIsAnsweredAsAHealthyOne() {
    DetailFixture fixture = Trees.fixture("artifacts-populated", "artifacts-populated");
    Trees.write(Trees.mission(fixture).resolve("status.events.jsonl"), "{this is not json\n\u0000\n");

    ArtifactListing listing = Trees.service(fixture).list(Trees.id());

    assertThat(Trees.paths(listing)).contains("spec.md").doesNotContain("status.events.jsonl");
    assertThat(Trees.codes(fixture)).isEmpty();
  }

  @Test
  void bothOperationsReadUnderTheArtifactScopeOnlyAndLeaveNoViolation() {
    DetailFixture fixture = Trees.fixture("artifacts-populated", "artifacts-populated");
    ArtifactQueryService service = Trees.service(fixture);
    fixture.recorder().clear();

    service.list(Trees.id());
    service.content(Trees.id(), Trees.path("spec.md"));

    var scoped = fixture.recorder().scopedAccesses().stream().filter(access -> access.pathClass() == PathClass.ARTIFACT_DIR || access.pathClass() == PathClass.ARTIFACT_FILE).toList();
    assertThat(scoped).isNotEmpty().allMatch(access -> access.scope() == org.speckitty.missionstatus.application.query.port.out.dto.ReadScope.ARTIFACT);
    assertThat(scoped).anyMatch(access -> access.pathClass() == PathClass.ARTIFACT_DIR && access.mode() == OpenMode.LIST);
    assertThat(scoped).anyMatch(access -> access.pathClass() == PathClass.ARTIFACT_FILE && access.mode() == OpenMode.READ && access.path().endsWith("/spec.md"));
    assertThat(fixture.recorder().violations()).isEmpty();
  }

  @Test
  void aRefusedStreamOfFixturesIsNotEmptyAtAll() {
    // the control of the whole file: the helpers see the committed fixtures
    assertThat(Stream.of("artifacts-populated", "artifacts-refusals", "artifacts-sort", "artifacts-redaction").map(tag -> Trees.dir(tag, tag))).allMatch(Files::isDirectory);
    assertThatThrownBy(() -> Trees.dir("no-such-tag", "no-such")).isInstanceOf(java.util.NoSuchElementException.class);
  }
}
