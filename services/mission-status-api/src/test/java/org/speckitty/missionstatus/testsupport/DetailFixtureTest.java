package org.speckitty.missionstatus.testsupport;

import org.speckitty.missionstatus.testsupport.RealPermissionFixture.NotRun;
import static org.assertj.core.api.Assertions.assertThat;
import static org.assertj.core.api.Assertions.assertThatThrownBy;

import java.io.IOException;
import java.nio.charset.StandardCharsets;
import java.nio.file.Files;
import java.nio.file.LinkOption;
import java.nio.file.Path;
import java.util.List;
import java.util.concurrent.Executors;
import java.util.concurrent.TimeUnit;
import java.util.stream.Stream;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.TestInfo;
import org.opentest4j.TestAbortedException;
import org.speckitty.missionstatus.adapter.out.filesystem.Allowlist.OpenMode;
import org.speckitty.missionstatus.adapter.out.filesystem.Allowlist.PathClass;
import org.speckitty.missionstatus.adapter.out.filesystem.AllowlistAccess;
import org.speckitty.missionstatus.adapter.out.filesystem.FilesystemTextSource;
import org.speckitty.missionstatus.adapter.out.filesystem.NameEncoding;
import org.speckitty.missionstatus.adapter.out.filesystem.RecordingAllowlistAccess;
import org.speckitty.missionstatus.application.query.port.in.dto.PageRequest;
import org.speckitty.missionstatus.application.query.port.out.TextSource;
import org.speckitty.missionstatus.application.query.port.out.dto.BytesRead;
import org.speckitty.missionstatus.application.query.port.out.dto.DirListing;
import org.speckitty.missionstatus.application.query.port.out.dto.EntryStat;
import org.speckitty.missionstatus.application.query.port.out.dto.FileRef;
import org.speckitty.missionstatus.application.query.port.out.dto.MissionRef;
import org.speckitty.missionstatus.application.query.port.out.dto.ReadScope;
import org.speckitty.missionstatus.application.query.port.out.dto.RelativePath;
import org.speckitty.missionstatus.application.query.port.out.dto.TextRead;
import org.speckitty.missionstatus.application.query.port.out.exceptions.TextFault;
import org.speckitty.missionstatus.testsupport.ConformanceTree.TreeFixture;

/**
 * The detail fixture bundle and the small doubles of plan 7.1 row 11: {@link ProvisionPlan}, {@link MetaReadCounter},
 * {@link RouteMarker}, {@link InMemoryTextSource}, {@link CapRaceInjector} and {@link Utf8Host}. They are asserted together because each
 * is too small for a test file of its own and only the bundle puts them to work.
 */
class DetailFixtureTest {

  private static final MissionRef ALPHA = new MissionRef("alpha-mission");

  /** The calling test's id: its class and method. */
  private static String id(TestInfo info) {
    return info.getTestClass().map(Class::getName).orElse("?") + "#" + info.getTestMethod().map(java.lang.reflect.Method::getName).orElse("?");
  }

  private static FileRef.MissionFile file(String path) {
    return new FileRef.MissionFile(ALPHA, RelativePath.of(path));
  }

  private static TreeFixture fixture(String key) {
    return ConformanceTree.detailFixtures().stream().filter(candidate -> candidate.key().equals(key)).findFirst().orElseThrow(() -> new AssertionError("no fixture " + key));
  }

  /** A fresh project directory with one Mission directory {@code alpha-mission}. */
  private static Path project() throws IOException {
    return Files.createDirectories(ScratchDirs.create().resolve("kitty-specs").resolve("alpha-mission")).getParent().getParent();
  }

  private static Path report() {
    return ScratchDirs.create().resolve("reports").resolve("not-run.txt");
  }

  // ---- DetailFixture ---------------------------------------------------------------------------------------------------------

  @Test
  void aTextReadAndAMissionListingLandOnTheOneRecorder() {
    DetailFixture detail = DetailFixture.of(fixture("detail-populated/populated").dir());

    TextRead text = detail.textSource().readText(file("spec.md"), 65536, ReadScope.ARTIFACT);
    detail.built().query().missions(new PageRequest(50, null));

    assertThat(text).isInstanceOf(TextRead.Text.class);
    assertThat(detail.recorder()).isSameAs(detail.built().handles().allowlistRecorder()).isNotNull();
    List<RecordingAllowlistAccess.ScopedAccess> seen = detail.recorder().scopedAccesses();
    assertThat(seen).anyMatch(access -> access.scope() == ReadScope.ARTIFACT && access.path().endsWith("alpha-mission/spec.md") && access.mode() == OpenMode.READ);
    assertThat(seen).anyMatch(access -> access.pathClass() == PathClass.MISSION_META && access.mode() == OpenMode.READ);
    assertThat(seen).anyMatch(access -> access.pathClass() == PathClass.LEDGER && access.mode() == OpenMode.READ);
    assertThat(detail.recorder().violations()).isEmpty();
    assertThat(detail.root()).isEqualTo(detail.built().root());
    assertThat(detail.readModel()).isNotNull();
    assertThat(detail.diagnostics()).isEqualTo(detail.built().diagnostics());
  }

  @Test
  void aFixtureWithoutTheRecordingSeamIsRefused() {
    FilesystemFixtureFactory.Built plain = FilesystemFixtureFactory.fromTree(fixture("detail-populated/populated").dir());

    assertThatThrownBy(() -> DetailFixture.over(plain)).isInstanceOf(IllegalArgumentException.class).hasMessageContaining("recording");
  }

  @Test
  void theBundleAppliesTheProvisionPlanBeforeAnyReadAndDoesNotLeakThePlanFile() throws IOException {
    DetailFixture detail = DetailFixture.of(fixture("artifacts-links/symlinked-file").dir());
    Path linked = detail.root().resolve("kitty-specs/alpha-mission/linked.md");

    assertThat(Files.isSymbolicLink(linked)).isTrue();
    assertThat(detail.textSource().stat(file("linked.md"), ReadScope.ARTIFACT)).isInstanceOfSatisfying(EntryStat.Present.class, stat -> assertThat(stat.kind()).isEqualTo(EntryStat.EntryKind.SYMLINK));
    assertThat(detail.root().resolve(ProvisionPlan.FILE)).doesNotExist();
    assertThat(detail.textSource().list(new FileRef.MissionFile(ALPHA, RelativePath.ROOT), 100, ReadScope.ARTIFACT))
        .isInstanceOfSatisfying(DirListing.Names.class, names -> assertThat(names.names()).doesNotContain(ProvisionPlan.FILE));
    assertThatThrownBy(() -> detail.textSource().readText(file("linked.md"), 65536, ReadScope.ARTIFACT)).isInstanceOfSatisfying(TextFault.class, fault -> assertThat(fault.kind()).isEqualTo(TextFault.Kind.PATH_REFUSED));
  }

  @Test
  void theReductionOfALedgerGoesThroughTheEventSourceOfTheFixture() {
    DetailFixture detail = DetailFixture.of(fixture("resolved-state/set-each-member").dir());

    assertThat(detail.reduce("alpha-mission").resolved().get("WP01").assignment().agent()).isEqualTo("implementer-iris");
  }

  // ---- ProvisionPlan ---------------------------------------------------------------------------------------------------------

  /** A fixture directory (the source of the plan) and a scratch root (the copy): the plan is written to the fixture, never to the root. */
  private static Path[] fixtureAndRoot(String plan) throws IOException {
    Path fixture = Files.createDirectories(ScratchDirs.create().resolve("fixture"));
    Path root = Files.createDirectories(ScratchDirs.create().resolve("root"));
    if (plan != null) {
      Files.writeString(fixture.resolve(ProvisionPlan.FILE), plan, StandardCharsets.UTF_8);
    }
    return new Path[] {fixture, root};
  }

  @Test
  void everyVerbDoesWhatTheGrammarSays() throws IOException {
    Path[] paths = fixtureAndRoot(
        String.join("\n",
            "# a comment",
            "",
            "dir\t.worktrees/lane-a",
            "gitentry\t.worktrees/lane-a/.git",
            "write\tkitty-specs/alpha-mission/note.md\t# note",
            "link\tkitty-specs/alpha-mission/link.md\tkitty-specs/alpha-mission/note.md",
            "mtime\tkitty-specs/alpha-mission/note.md\t1790000000",
            "substitute\tkitty-specs/alpha-mission/secret.txt\t@@TOKEN@@\tgh\tp_\taaaa",
            ""));
    Path root = paths[1];
    Files.createDirectories(root.resolve("kitty-specs/alpha-mission"));
    Files.writeString(root.resolve("kitty-specs/alpha-mission/secret.txt"), "token=@@TOKEN@@!");

    ProvisionPlan.apply(paths[0], root);

    assertThat(root.resolve(".worktrees/lane-a")).isDirectory();
    assertThat(root.resolve(".worktrees/lane-a/.git")).isRegularFile();
    assertThat(Files.readString(root.resolve("kitty-specs/alpha-mission/note.md"))).isEqualTo("# note");
    Path link = root.resolve("kitty-specs/alpha-mission/link.md");
    assertThat(Files.isSymbolicLink(link)).isTrue();
    assertThat(Files.readSymbolicLink(link)).isEqualTo(Path.of("note.md"));
    assertThat(Files.readString(link)).isEqualTo("# note");
    assertThat(Files.getLastModifiedTime(root.resolve("kitty-specs/alpha-mission/note.md")).toInstant().getEpochSecond()).isEqualTo(1790000000L);
    assertThat(Files.readString(root.resolve("kitty-specs/alpha-mission/secret.txt"))).isEqualTo("token=ghp_aaaa!");
  }

  @Test
  void anMtimeOnALinkIsTheLinksOwnAndNotItsTargets() throws IOException {
    Path[] paths = fixtureAndRoot("write\ta.md\tx\nlink\tb.md\ta.md\nmtime\tb.md\t1790000000\n");

    ProvisionPlan.apply(paths[0], paths[1]);

    assertThat(Files.getLastModifiedTime(paths[1].resolve("b.md"), LinkOption.NOFOLLOW_LINKS).toInstant().getEpochSecond()).isEqualTo(1790000000L);
    assertThat(Files.getLastModifiedTime(paths[1].resolve("a.md")).toInstant().getEpochSecond()).isNotEqualTo(1790000000L);
  }

  @Test
  void applyingAPlanTwiceGivesTheSameTree() throws IOException {
    Path[] paths = fixtureAndRoot("dir\td\nwrite\td/f.md\ttext\nlink\td/l.md\td/f.md\nsubstitute\td/f.md\ttext\tte\txt\nmtime\td/f.md\t1790000000\n");

    ProvisionPlan.apply(paths[0], paths[1]);
    ProvisionPlan.apply(paths[0], paths[1]);

    assertThat(Files.readString(paths[1].resolve("d/f.md"))).isEqualTo("text");
    assertThat(Files.readSymbolicLink(paths[1].resolve("d/l.md"))).isEqualTo(Path.of("f.md"));
  }

  @Test
  void aStrayCopyOfThePlanAtTheRootOrInsideAMissionDirectoryIsRemoved() throws IOException {
    Path[] paths = fixtureAndRoot("dir\tmade\n");
    Path mission = Files.createDirectories(paths[1].resolve("kitty-specs/alpha-mission"));
    Files.writeString(mission.resolve(ProvisionPlan.FILE), "dir\tstray\n");
    Files.writeString(paths[1].resolve(ProvisionPlan.FILE), "dir\tstray\n");
    Files.writeString(mission.resolve("keep.md"), "kept");

    ProvisionPlan.apply(paths[0], paths[1]);

    assertThat(mission.resolve(ProvisionPlan.FILE)).doesNotExist();
    assertThat(paths[1].resolve(ProvisionPlan.FILE)).doesNotExist();
    assertThat(mission.resolve("keep.md")).exists();
    assertThat(paths[1].resolve("made")).isDirectory();
    // the plan is read from the source fixture only: a plan that exists only in the scratch tree is never applied
    assertThat(paths[1].resolve("stray")).doesNotExist();
  }

  @Test
  void aFixtureWithoutAPlanIsLeftAlone() throws IOException {
    Path[] paths = fixtureAndRoot(null);

    ProvisionPlan.apply(paths[0], paths[1]);

    try (Stream<Path> entries = Files.list(paths[1])) {
      assertThat(entries.toList()).isEmpty();
    }
  }

  @Test
  void aPathThatLeavesTheRootIsRefusedAndNothingIsWrittenOutside() throws IOException {
    for (String line : List.of("write\t../escape.md\tx", "write\t/tmp/absolute.md\tx", "dir\ta/../../up", "link\tl\t../outside-target", "mtime\t../x\t1", "gitentry\t../.git", "substitute\t../x\tm\tr")) {
      Path[] paths = fixtureAndRoot(line + "\n");

      assertThatThrownBy(() -> ProvisionPlan.apply(paths[0], paths[1])).as(line).isInstanceOf(IllegalArgumentException.class).hasMessageContaining("leaves the project root");
      assertThat(paths[1].resolveSibling("escape.md")).doesNotExist();
      assertThat(paths[1].resolveSibling("up")).doesNotExist();
    }
  }

  @Test
  void aWriteThroughALinkThatLeavesTheRootIsRefused() throws IOException {
    Path[] paths = fixtureAndRoot("link\tgate\t@outside/\nwrite\tgate/x.md\tx\n");
    Files.createDirectories(paths[0].resolve("outside"));
    Files.writeString(paths[0].resolve("outside/keep.txt"), "k");

    assertThatThrownBy(() -> ProvisionPlan.apply(paths[0], paths[1])).isInstanceOf(IllegalArgumentException.class).hasMessageContaining("through a link");

    assertThat(paths[1].resolveSibling("outside/x.md")).doesNotExist();
  }

  @Test
  void anOutsideTargetPointsIntoASiblingDirectoryMadeFromTheFixturesOutsideTree() throws IOException {
    Path[] paths = fixtureAndRoot("link\tkitty-specs/alpha-mission/out.md\t@outside/real.md\n");
    Files.createDirectories(paths[0].resolve("outside"));
    Files.writeString(paths[0].resolve("outside/real.md"), "outside text");

    ProvisionPlan.apply(paths[0], paths[1]);

    assertThat(Files.readString(paths[1].resolve("kitty-specs/alpha-mission/out.md"))).isEqualTo("outside text");
    assertThat(Files.readSymbolicLink(paths[1].resolve("kitty-specs/alpha-mission/out.md")).isAbsolute()).isTrue();
  }

  @Test
  void aMarkerThatIsNotInTheFileIsAnErrorAndALineThatIsNoVerbIsRefused() throws IOException {
    Path[] missing = fixtureAndRoot("substitute\tf.md\t@@NOPE@@\tx\n");
    Files.writeString(missing[1].resolve("f.md"), "no marker here");
    assertThatThrownBy(() -> ProvisionPlan.apply(missing[0], missing[1])).isInstanceOf(IllegalArgumentException.class).hasMessageContaining("marker");

    for (String bad : List.of("copy\ta\tb", "link\tonly-one", "dir\ta\tb", "mtime\ta", "write\tonly-path", "substitute\ta\tb", "gitentry")) {
      assertThatThrownBy(() -> ProvisionPlan.parse(bad + "\n")).as(bad).isInstanceOf(IllegalArgumentException.class);
    }
  }

  @Test
  void theGrammarKeepsEmptyFragmentsAndIgnoresBlankAndCommentLines() {
    List<ProvisionPlan.Step> steps = ProvisionPlan.parse("# c\n\n   \nsubstitute\tp\tm\t\tx\r\nwrite\tp\t\n");

    assertThat(steps).containsExactly(new ProvisionPlan.Step("substitute", List.of("p", "m", "", "x")), new ProvisionPlan.Step("write", List.of("p", "")));
  }

  @Test
  void aHostThatCannotMakeALinkSkipsTheTestAndWritesTheNotRunLine() throws IOException {
    Path[] paths = fixtureAndRoot("link\tl\tt\n");
    Path report = report();

    assertThatThrownBy(() -> ProvisionPlan.apply(paths[0], paths[1], (link, target) -> { throw new java.nio.file.FileSystemException("no links here"); }, report))
        .isInstanceOf(TestAbortedException.class);

    assertThat(Files.readString(report)).startsWith("not run: link unsupported");
  }

  @Test
  void everyCommittedPlanAppliesToItsFixtureAndLeavesTheMarkersGone(TestInfo info) throws IOException {
    int plans = 0;
    int substituted = 0;
    for (TreeFixture fixture : ConformanceTree.detailFixtures()) {
      if (!Files.isRegularFile(fixture.dir().resolve(ProvisionPlan.FILE))) {
        continue;
      }
      List<ProvisionPlan.Step> steps = ProvisionPlan.parse(Files.readString(fixture.dir().resolve(ProvisionPlan.FILE)));
      if (steps.stream().anyMatch(step -> step.verb().equals("write") && !step.arguments().getFirst().chars().allMatch(c -> c < 0x80)) && !Utf8Host.isUtf8()) {
        // only this fixture needs a UTF-8 host: it is reported as not run and the others are still checked
        NotRun.record(NotRun.DEFAULT_FILE, NotRun.unmet(id(info) + " [" + fixture.key() + "]"));
        continue;
      }
      DetailFixture detail = DetailFixture.of(fixture.dir());
      plans++;
      for (ProvisionPlan.Step step : steps) {
        Path target = detail.root().resolve(step.arguments().getFirst());
        switch (step.verb()) {
          case "substitute" -> {
            assertThat(Files.readString(target)).as(fixture.key()).doesNotContain(step.arguments().get(1));
            substituted++;
          }
          case "gitentry" -> assertThat(target).as(fixture.key()).isRegularFile();
          case "dir" -> assertThat(target).as(fixture.key()).isDirectory();
          case "mtime" -> assertThat(Files.getLastModifiedTime(target, LinkOption.NOFOLLOW_LINKS).toInstant().getEpochSecond()).as(fixture.key()).isEqualTo(Long.parseLong(step.arguments().get(1)));
          case "link" -> assertThat(Files.isSymbolicLink(target)).as(fixture.key()).isTrue();
          default -> assertThat(target).as(fixture.key()).exists();
        }
      }
      assertThat(detail.root().resolve(ProvisionPlan.FILE)).as(fixture.key()).doesNotExist();
    }
    assertThat(plans).isGreaterThan(Utf8Host.isUtf8() ? 25 : 24);
    assertThat(substituted).isGreaterThan(8);
  }

  @Test
  void aNonAsciiNameIsMadeAtTestTimeOnAUtf8Host(TestInfo info) throws IOException {
    Utf8Host.assumeUtf8(id(info));
    DetailFixture detail = DetailFixture.of(fixture("artifacts-sort/artifacts-sort").dir());

    DirListing listing = detail.textSource().list(new FileRef.MissionFile(ALPHA, RelativePath.ROOT), 100, ReadScope.ARTIFACT);

    assertThat(listing).isInstanceOfSatisfying(DirListing.Names.class, names -> assertThat(names.names()).contains("café.md", "日本.md", "～.md", "😀.md"));
  }

  // ---- Utf8Host --------------------------------------------------------------------------------------------------------------

  @Test
  void aHostThatIsNotUtf8SkipsTheTestAndWritesTheLineAndAUtf8HostDoesNot() throws IOException {
    Path none = report();
    Utf8Host.assumeUtf8("utf8-host", NameEncoding.fixed(true), none);
    assertThat(none).doesNotExist();

    Path some = report();
    assertThatThrownBy(() -> Utf8Host.assumeUtf8("c-locale-test", NameEncoding.fixed(false), some)).isInstanceOf(TestAbortedException.class);
    assertThat(Files.readAllLines(some)).containsExactly("not run: precondition unmet: c-locale-test");
    assertThat(Utf8Host.isUtf8(NameEncoding.fixed(true))).isTrue();
    assertThat(Utf8Host.isUtf8(NameEncoding.fixed(false))).isFalse();
    assertThat(Utf8Host.isUtf8(new NameEncoding(true, "Cp1252"))).as("Windows decodes names itself").isTrue();
    assertThat(Utf8Host.isUtf8()).isEqualTo(NameEncoding.host().trustworthy());
  }

  // ---- MetaReadCounter -------------------------------------------------------------------------------------------------------

  @Test
  void onlyAReadOfTheMissionsOwnMetaCounts() throws IOException {
    Path root = project();
    RecordingAllowlistAccess recorder = new RecordingAllowlistAccess(root);
    MetaReadCounter counter = new MetaReadCounter();
    Path meta = root.resolve("kitty-specs/alpha-mission/meta.json");

    recorder.record(meta, OpenMode.READ);
    recorder.record(meta, OpenMode.STAT);
    recorder.record(root.resolve("kitty-specs/alpha-mission/status.events.jsonl"), OpenMode.READ);
    recorder.record(root.resolve("kitty-specs/alpha-mission/spec.md"), OpenMode.READ);
    recorder.record(meta, OpenMode.READ);

    assertThat(counter.count(recorder)).isEqualTo(2);
    counter.reset(recorder);
    assertThat(counter.count(recorder)).isZero();
    recorder.record(meta, OpenMode.READ);
    assertThat(counter.count(recorder)).isEqualTo(1);
    counter.reset();
    assertThat(counter.count(recorder)).isEqualTo(3);
  }

  @Test
  void aColdListingReadsTheMetaOfEachMissionAndTheCounterSeesIt() {
    DetailFixture detail = DetailFixture.of(fixture("detail-populated/populated").dir());
    MetaReadCounter counter = new MetaReadCounter();

    detail.built().query().missions(new PageRequest(50, null));

    assertThat(counter.count(detail.recorder())).isPositive();
  }

  // ---- RouteMarker -----------------------------------------------------------------------------------------------------------

  @Test
  void theMarkerDefaultsToNoRouteAndIsSeenOnAnotherThread() throws Exception {
    RouteMarker marker = RouteMarker.create();
    assertThat(marker.supplier().get()).isEqualTo("-");

    marker.set("getMission");
    var executor = Executors.newSingleThreadExecutor();
    try {
      assertThat(executor.submit(() -> marker.supplier().get()).get(5, TimeUnit.SECONDS)).isEqualTo("getMission");
      marker.clear();
      assertThat(executor.submit(() -> marker.supplier().get()).get(5, TimeUnit.SECONDS)).isEqualTo("-");
    } finally {
      executor.shutdownNow();
    }
    assertThatThrownBy(() -> marker.set(null)).isInstanceOf(NullPointerException.class);
  }

  @Test
  void aRecorderWithTheMarkerInstalledNotesTheRouteOfEachAccess() throws IOException {
    Path root = project();
    RecordingAllowlistAccess recorder = new RecordingAllowlistAccess(root);
    RouteMarker marker = RouteMarker.create();
    recorder.routeSupplier(marker.supplier());
    Path meta = root.resolve("kitty-specs/alpha-mission/meta.json");

    recorder.record(meta, OpenMode.READ);
    marker.set("getWorkPackage");
    recorder.record(meta, OpenMode.READ);
    marker.clear();
    recorder.record(meta, OpenMode.READ);

    assertThat(recorder.scopedAccesses()).extracting(RecordingAllowlistAccess.ScopedAccess::route).containsExactly("-", "getWorkPackage", "-");
  }

  // ---- InMemoryTextSource against FilesystemTextSource -------------------------------------------------------------------------

  private static final int CAP = 64;

  /** The same small tree twice: once on disk, once in memory. */
  private static Path diskTree() throws IOException {
    Path root = project();
    Path mission = root.resolve("kitty-specs/alpha-mission");
    Files.writeString(mission.resolve("ok.md"), "café text");
    Files.write(mission.resolve("bom.md"), new byte[] {(byte) 0xEF, (byte) 0xBB, (byte) 0xBF, 'h', 'i'});
    Files.write(mission.resolve("latin1.txt"), new byte[] {'a', (byte) 0xE9});
    Files.write(mission.resolve("big.md"), new byte[CAP + 1]);
    Files.write(mission.resolve("exact.md"), new byte[CAP]);
    Files.createDirectories(mission.resolve("sub"));
    Files.writeString(mission.resolve("sub/inner.md"), "inner");
    Files.writeString(mission.resolve("sub/other.md"), "other");
    Files.writeString(mission.resolve("sub/third.md"), "third");
    Files.writeString(mission.resolve("ok.md"), "café text");
    Files.createSymbolicLink(mission.resolve("link.md"), Path.of("ok.md"));
    return root;
  }

  private static InMemoryTextSource memoryTree() {
    return new InMemoryTextSource()
        .file(file("ok.md"), "café text".getBytes(StandardCharsets.UTF_8))
        .file(file("bom.md"), new byte[] {(byte) 0xEF, (byte) 0xBB, (byte) 0xBF, 'h', 'i'})
        .file(file("latin1.txt"), new byte[] {'a', (byte) 0xE9})
        .file(file("big.md"), new byte[CAP + 1])
        .file(file("exact.md"), new byte[CAP])
        .dir(file("sub"), "inner.md", "other.md", "third.md")
        .file(file("sub/inner.md"), "inner".getBytes(StandardCharsets.UTF_8))
        .link(file("link.md"));
  }

  @Test
  void theSubsetGivesIdenticalResultsFromBothSources() throws IOException {
    TextSource disk = new FilesystemTextSource(diskTree());
    TextSource memory = memoryTree();

    for (ReadScope scope : ReadScope.values()) {
      for (String path : List.of("ok.md", "bom.md", "latin1.txt", "big.md", "exact.md", "sub", "sub/inner.md", "absent.md", "sub/absent.md", "ok.md/below", "absent-dir/file.md")) {
        assertThat(memory.readText(file(path), CAP, scope)).as("readText " + path + " " + scope).isEqualTo(disk.readText(file(path), CAP, scope));
        BytesRead expectedBytes = disk.readBytes(file(path), CAP, scope);
        BytesRead actualBytes = memory.readBytes(file(path), CAP, scope);
        assertThat(actualBytes.getClass()).as("readBytes " + path).isEqualTo(expectedBytes.getClass());
        if (expectedBytes instanceof BytesRead.Bytes expected) {
          assertThat(((BytesRead.Bytes) actualBytes).content()).isEqualTo(expected.content());
        }
      }
    }
  }

  @Test
  void bothSourcesReportTheSameKindsOfTextOutcome() throws IOException {
    TextSource memory = memoryTree();

    assertThat(memory.readText(file("ok.md"), CAP, ReadScope.AUTHORED)).isInstanceOfSatisfying(TextRead.Text.class, text -> assertThat(text.text()).isEqualTo("café text"));
    assertThat(memory.readText(file("bom.md"), CAP, ReadScope.AUTHORED)).isInstanceOfSatisfying(TextRead.Text.class, text -> assertThat(text.text()).startsWith("﻿"));
    assertThat(memory.readText(file("latin1.txt"), CAP, ReadScope.AUTHORED)).isInstanceOf(TextRead.NotText.class);
    assertThat(memory.readText(file("big.md"), CAP, ReadScope.AUTHORED)).isInstanceOf(TextRead.OverCap.class);
    assertThat(memory.readText(file("exact.md"), CAP, ReadScope.AUTHORED)).isInstanceOf(TextRead.Text.class);
    assertThat(memory.readText(file("sub"), CAP, ReadScope.AUTHORED)).isInstanceOf(TextRead.NotRegular.class);
    assertThat(memory.readText(file("absent.md"), CAP, ReadScope.AUTHORED)).isInstanceOf(TextRead.Absent.class);
  }

  @Test
  void aListingIsCutAtTheLimitAndSaysSoOnBothSources() throws IOException {
    TextSource disk = new FilesystemTextSource(diskTree());
    TextSource memory = memoryTree().trustworthy(NameEncoding.host().trustworthy());

    for (int limit : new int[] {10, 3, 2, 1}) {
      DirListing onDisk = disk.list(file("sub"), limit, ReadScope.ARTIFACT);
      DirListing inMemory = memory.list(file("sub"), limit, ReadScope.ARTIFACT);
      DirListing.Names expected = (DirListing.Names) onDisk;
      DirListing.Names actual = (DirListing.Names) inMemory;
      assertThat(actual.limitReached()).as("limit " + limit).isEqualTo(expected.limitReached());
      assertThat(actual.names()).hasSameSizeAs(expected.names());
      assertThat(actual.trustworthy()).isEqualTo(expected.trustworthy());
    }
    assertThat(((DirListing.Names) memory.list(file("sub"), 2, ReadScope.ARTIFACT)).limitReached()).isTrue();
    assertThat(((DirListing.Names) memory.list(file("sub"), 3, ReadScope.ARTIFACT)).limitReached()).isFalse();
    assertThat(memory.list(file("ok.md"), 5, ReadScope.ARTIFACT)).isInstanceOf(DirListing.NotADirectory.class);
    assertThat(memory.list(file("nothing"), 5, ReadScope.ARTIFACT)).isInstanceOf(DirListing.Absent.class);
    assertThat(((DirListing.Names) memoryTree().trustworthy(false).list(file("sub"), 5, ReadScope.ARTIFACT)).trustworthy()).isFalse();
  }

  @Test
  void aLinkIsRefusedAndNeverFollowedAndAFaultIsThrownAsRegistered() {
    InMemoryTextSource memory = memoryTree().file(file("through/inner.md"), new byte[] {'x'}).link(file("through")).fault(file("broken.md"), TextFault.Kind.FILE_UNREADABLE);

    assertThatThrownBy(() -> memory.readText(file("link.md"), CAP, ReadScope.AUTHORED)).isInstanceOfSatisfying(TextFault.class, fault -> assertThat(fault.kind()).isEqualTo(TextFault.Kind.PATH_REFUSED));
    assertThatThrownBy(() -> memory.readText(file("through/inner.md"), CAP, ReadScope.AUTHORED)).isInstanceOfSatisfying(TextFault.class, fault -> assertThat(fault.kind()).isEqualTo(TextFault.Kind.PATH_REFUSED));
    assertThatThrownBy(() -> memory.readBytes(file("broken.md"), CAP, ReadScope.AUTHORED)).isInstanceOfSatisfying(TextFault.class, fault -> assertThat(fault.kind()).isEqualTo(TextFault.Kind.FILE_UNREADABLE));
    assertThat(memory.stat(file("link.md"), ReadScope.AUTHORED)).isInstanceOfSatisfying(EntryStat.Present.class, stat -> assertThat(stat.kind()).isEqualTo(EntryStat.EntryKind.SYMLINK));
    assertThat(memory.stat(file("ok.md"), ReadScope.AUTHORED)).isInstanceOfSatisfying(EntryStat.Present.class, stat -> assertThat(stat.kind()).isEqualTo(EntryStat.EntryKind.FILE));
    assertThat(memory.stat(file("sub"), ReadScope.AUTHORED)).isInstanceOfSatisfying(EntryStat.Present.class, stat -> assertThat(stat.kind()).isEqualTo(EntryStat.EntryKind.DIRECTORY));
    assertThat(memory.stat(file("nothing"), ReadScope.AUTHORED)).isInstanceOf(EntryStat.Absent.class);
  }

  @Test
  void anEntryRegisteredUnderOneScopeIsAbsentUnderTheOtherAndTheReadsAreRecorded() {
    FileRef ref = file("only-artifact.md");
    InMemoryTextSource memory = new InMemoryTextSource().file(ref, ReadScope.ARTIFACT, new byte[] {'x'});

    assertThat(memory.readText(ref, CAP, ReadScope.ARTIFACT)).isInstanceOf(TextRead.Text.class);
    assertThat(memory.readText(ref, CAP, ReadScope.AUTHORED)).isInstanceOf(TextRead.Absent.class);
    assertThat(memory.readScopes()).containsExactly(ReadScope.ARTIFACT, ReadScope.AUTHORED);
    assertThat(memory.readRefs()).containsExactly(ref, ref);
  }

  @Test
  void aDirectoryWithNoEntryOfItsOwnExistsWhenSomethingIsBelowIt() {
    InMemoryTextSource memory = new InMemoryTextSource().file(file("deep/er/file.md"), new byte[] {'x'});

    assertThat(memory.stat(file("deep"), ReadScope.AUTHORED)).isInstanceOfSatisfying(EntryStat.Present.class, stat -> assertThat(stat.kind()).isEqualTo(EntryStat.EntryKind.DIRECTORY));
    assertThat(memory.list(file("deep"), 5, ReadScope.AUTHORED)).isInstanceOfSatisfying(DirListing.Names.class, names -> assertThat(names.names()).containsExactly("er"));
    assertThat(memory.readText(file("deep/er"), CAP, ReadScope.AUTHORED)).isInstanceOf(TextRead.NotRegular.class);
    assertThat(memory.readText(file("deep/er/file.md"), CAP, ReadScope.AUTHORED)).isInstanceOf(TextRead.Text.class);
  }

  // ---- CapRaceInjector -------------------------------------------------------------------------------------------------------

  @Test
  void aFileThatGrowsBetweenTheSizeCheckAndTheReadIsOverCapAndAtMostCapPlusOneBytesAreRead() throws IOException {
    for (CapRaceInjector.Variant variant : CapRaceInjector.Variant.values()) {
      Path root = project();
      Path victim = root.resolve("kitty-specs/alpha-mission/race.md");
      Files.write(victim, new byte[100]);
      Files.write(root.resolve("kitty-specs/alpha-mission/calm.md"), new byte[100]);
      CapRaceInjector injector = new CapRaceInjector(AllowlistAccess.passThrough(), path -> path.getFileName().toString().equals("race.md"), 100, new byte[300000], variant);
      FilesystemTextSource source = new FilesystemTextSource(root, injector, NameEncoding.host());

      assertThat(source.readText(file("race.md"), 65536, ReadScope.ARTIFACT)).as(variant.name()).isInstanceOf(TextRead.OverCap.class);
      assertThat(injector.bytesRead()).as(variant.name()).isEqualTo(65537);
      assertThat(source.readBytes(file("race.md"), 65536, ReadScope.AUTHORED)).isInstanceOf(BytesRead.OverCap.class);
      assertThat(injector.bytesRead()).as("at most cap + 1 per read").isEqualTo(2L * 65537);
      // the stat of the lying path shows the declared size; every other path is passed through
      assertThat(source.stat(file("race.md"), ReadScope.ARTIFACT)).isInstanceOfSatisfying(EntryStat.Present.class, stat -> assertThat(stat.sizeBytes()).isEqualTo(100));
      assertThat(source.readText(file("calm.md"), 65536, ReadScope.ARTIFACT)).isInstanceOf(TextRead.Text.class);
    }
  }

  @Test
  void withoutTheInjectorTheSameFileIsAnHonestSmallReadAndABigOneIsOverCapByItsHandle() throws IOException {
    Path root = project();
    Files.write(root.resolve("kitty-specs/alpha-mission/race.md"), new byte[100]);
    Files.write(root.resolve("kitty-specs/alpha-mission/huge.md"), new byte[300000]);
    FilesystemTextSource source = new FilesystemTextSource(root);

    assertThat(source.readText(file("race.md"), 65536, ReadScope.ARTIFACT)).isInstanceOf(TextRead.Text.class);
    assertThat(source.readText(file("huge.md"), 65536, ReadScope.ARTIFACT)).isInstanceOf(TextRead.OverCap.class);
  }

  @Test
  void theInjectorStaysOnTheRecordOfTheDelegateWhenViewedUnderAScope() throws IOException {
    Path root = project();
    Files.write(root.resolve("kitty-specs/alpha-mission/race.md"), new byte[100]);
    RecordingAllowlistAccess recorder = new RecordingAllowlistAccess(root);
    CapRaceInjector injector = new CapRaceInjector(recorder, path -> true, 100, new byte[70000]);
    FilesystemTextSource source = new FilesystemTextSource(root, injector, NameEncoding.host());

    source.readText(file("race.md"), 65536, ReadScope.ARTIFACT);

    assertThat(recorder.scopedAccesses()).anyMatch(access -> access.scope() == ReadScope.ARTIFACT && access.mode() == OpenMode.READ && access.path().endsWith("race.md"));
    assertThat(recorder.scopedAccesses()).extracting(RecordingAllowlistAccess.ScopedAccess::scope).contains(ReadScope.ARTIFACT);
  }
}
