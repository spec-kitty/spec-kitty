package org.speckitty.missionstatus.application.query.artifact;

import static org.assertj.core.api.Assertions.assertThat;
import static org.junit.jupiter.api.Assumptions.assumeTrue;

import java.io.IOException;
import java.nio.charset.StandardCharsets;
import java.nio.file.Files;
import java.nio.file.Path;
import java.nio.file.attribute.FileTime;
import java.time.Instant;
import java.util.ArrayList;
import java.util.Arrays;
import java.util.Comparator;
import java.util.List;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.io.TempDir;
import org.speckitty.missionstatus.adapter.out.filesystem.AllowlistAccess;
import org.speckitty.missionstatus.adapter.out.filesystem.FilesystemTextSource;
import org.speckitty.missionstatus.adapter.out.filesystem.NameEncoding;
import org.speckitty.missionstatus.application.query.port.in.exceptions.DetailRefusal;
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
import org.speckitty.missionstatus.domain.model.Diagnostic;
import org.speckitty.missionstatus.domain.model.DiagnosticCode;
import org.speckitty.missionstatus.domain.readmodel.detail.ArtifactEntry;
import org.speckitty.missionstatus.domain.redaction.TextScreen;
import org.speckitty.missionstatus.testsupport.InMemoryTextSource;
import org.speckitty.missionstatus.testsupport.LeakPatternsFile;

/** The bounded walk and the bounded sorted collection of FR-004 (AC-4.1 to AC-4.9). */
class ArtifactWalkTest {

  private static final MissionRef MISSION = new MissionRef("alpha-mission");
  private static final String MID8 = "00000000";
  private static final TextScreen SCREEN = new TextScreen(LeakPatternsFile.load());

  private final List<Diagnostic> diagnostics = new ArrayList<>();

  private static FileRef ref(String path) {
    return new FileRef.MissionFile(MISSION, path.isEmpty() ? RelativePath.ROOT : RelativePath.of(path));
  }

  private static byte[] utf8(String text) {
    return text.getBytes(StandardCharsets.UTF_8);
  }

  private ArtifactWalk walk(TextSource source) {
    return new ArtifactWalk(source, new ArtifactReader(source, SCREEN, diagnostics::add), diagnostics::add);
  }

  private static List<String> paths(ArtifactWalk.Result result) {
    return result.entries().stream().map(ArtifactEntry::path).toList();
  }

  private static DetailRefusal.Kind refusal(ArtifactWalk walk) {
    return org.assertj.core.api.Assertions.catchThrowableOfType(DetailRefusal.class, () -> walk.walk(MISSION, MID8)).kind();
  }

  // ---- AC-4.2: the order is the code-point order of the path -----------------------------------------------------------------

  @Test
  void theOrderIsTheCodePointOrderWhichEqualsUtf8ByteOrderNotUtf16NotCaseFoldedNotLocale() {
    List<String> names = List.of("～.md", "😀.md", "B.md", "a.md", "Z.md", "_x.md", "10.md", "2.md", "sub/b.md", "sub/A.md", "Sub/c.md");
    InMemoryTextSource source = new InMemoryTextSource();
    names.forEach(name -> source.file(ref(name), utf8("x")));

    List<String> served = paths(walk(source).walk(MISSION, MID8));

    List<String> utf8Order = names.stream().sorted(Comparator.comparing(name -> utf8(name), Arrays::compareUnsigned)).toList();
    assertThat(served).containsExactlyElementsOf(utf8Order);
    // the fixture sees the difference only through the two special pairs: UTF-16 order puts the supplementary character first,
    // and case folding puts a.md before B.md
    assertThat(names.stream().sorted().toList()).isNotEqualTo(utf8Order);
    assertThat(served.indexOf("～.md")).isLessThan(served.indexOf("😀.md"));
    assertThat(served.indexOf("B.md")).isLessThan(served.indexOf("a.md"));
    // the ASCII control pair every comparator orders the same
    assertThat(served.indexOf("10.md")).isLessThan(served.indexOf("2.md"));
  }

  // ---- AC-4.4: 1000, 1001 and the collector --------------------------------------------------------------------------------------

  private static InMemoryTextSource files(int count) {
    InMemoryTextSource source = new InMemoryTextSource();
    for (int i = 0; i < count; i++) {
      source.file(ref(String.format("f%05d.md", i)), utf8("x"));
    }
    return source;
  }

  @Test
  void exactly1000FilesListAll1000NotTruncatedAnd1001ListThe1000SmallestTruncated() {
    ArtifactWalk exact = walk(files(1000));
    ArtifactWalk.Result thousand = exact.walk(MISSION, MID8);
    ArtifactWalk over = walk(files(1001));
    ArtifactWalk.Result thousandAndOne = over.walk(MISSION, MID8);

    assertThat(thousand.entries()).hasSize(1000);
    assertThat(thousand.truncated()).isFalse();
    assertThat(thousandAndOne.entries()).hasSize(1000);
    assertThat(thousandAndOne.truncated()).isTrue();
    assertThat(paths(thousandAndOne).getLast()).isEqualTo("f00999.md");
    assertThat(over.collectorHighWater()).isEqualTo(1001);
    assertThat(exact.collectorHighWater()).isEqualTo(1000);
  }

  @Test
  void theCollectorNeverHoldsMoreThan1001PathsHoweverManyFilesThereAre() {
    InMemoryTextSource source = new InMemoryTextSource();
    for (int i = 4999; i >= 0; i--) {
      source.file(ref(String.format("f%05d.md", i)), utf8("x"));
    }
    ArtifactWalk walk = walk(source);

    ArtifactWalk.Result result = walk.walk(MISSION, MID8);

    assertThat(walk.collectorHighWater()).isEqualTo(1001);
    assertThat(result.entries()).hasSize(1000);
    assertThat(paths(result).getFirst()).isEqualTo("f00000.md");
    assertThat(paths(result).getLast()).isEqualTo("f00999.md");
    assertThat(result.truncated()).isTrue();
  }

  // ---- AC-4.5: eligibility ------------------------------------------------------------------------------------------------------

  @Test
  void theRootRecordsInAnyCaseAreNeverListedNorTouchedButTheSameNamesBelowARootDirectoryAre() {
    InMemoryTextSource source =
        new InMemoryTextSource()
            .file(ref("status.events.jsonl"), utf8("{}"))
            .file(ref("status.json"), utf8("{}"))
            .file(ref("STATUS.JSON"), utf8("{}"))
            .file(ref("Status.Events.Jsonl"), utf8("{}"))
            .file(ref("notes/status.json"), utf8("{}"))
            .file(ref("spec.md"), utf8("x"));

    List<String> served = paths(walk(source).walk(MISSION, MID8));

    assertThat(served).containsExactly("notes/status.json", "spec.md");
    assertThat(source.readRefs()).doesNotContain(ref("status.events.jsonl"), ref("status.json"), ref("STATUS.JSON"), ref("Status.Events.Jsonl"));
    assertThat(source.readScopes()).as("every read of the walk is under the artifact scope").containsOnly(ReadScope.ARTIFACT);
  }

  @Test
  void aLinkIsNeitherFollowedNorListedAndANameThatIsNotAPathSegmentIsNotEntered() {
    InMemoryTextSource source =
        new InMemoryTextSource()
            .file(ref("real/x.md"), utf8("x"))
            .link(ref("linkfile.md"))
            .link(ref("linkdir"))
            .file(ref("linkdir/y.md"), utf8("never"))
            .dir(ref(""), "real", "linkfile.md", "linkdir", "back\\slash");

    ArtifactWalk.Result result = walk(source).walk(MISSION, MID8);

    assertThat(paths(result)).containsExactly("real/x.md");
    assertThat(diagnostics).isEmpty();
  }

  @Test
  void aDirectoryWhosePathAlreadyHas512CharactersIsNotEnteredButOneWith511Is() {
    String segment = "d".repeat(170);
    String p511 = segment + "/" + segment + "/" + "d".repeat(169);
    String p512 = segment + "/" + segment + "/" + segment;
    assertThat(p511).hasSize(511);
    assertThat(p512).hasSize(512);
    InMemoryTextSource source = new InMemoryTextSource().file(ref(p511 + "/x.md"), utf8("x")).file(ref(p512 + "/y.md"), utf8("y")).file(ref("ok.md"), utf8("x"));

    ArtifactWalk.Result result = walk(source).walk(MISSION, MID8);

    assertThat(paths(result)).containsExactly("ok.md");
    assertThat(source.readRefs()).as("what is inside the directory with 511 characters is looked at, what is inside the one with 512 is not").contains(ref(p511 + "/x.md")).doesNotContain(ref(p512 + "/y.md"));
  }

  // ---- AC-4.3: readable --------------------------------------------------------------------------------------------------------

  private static String token(String prefix, int bodyLength) {
    return prefix + "A".repeat(bodyLength);
  }

  /** Counts the files whose text was asked of the port. */
  private static final class ReadSpy implements TextSource {
    private final TextSource delegate;
    final List<String> opened = new ArrayList<>();

    ReadSpy(TextSource delegate) {
      this.delegate = delegate;
    }

    @Override
    public DirListing list(FileRef dir, int nameLimit, ReadScope scope) {
      return delegate.list(dir, nameLimit, scope);
    }

    @Override
    public EntryStat stat(FileRef path, ReadScope scope) {
      return delegate.stat(path, scope);
    }

    @Override
    public BytesRead readBytes(FileRef file, int cap, ReadScope scope) {
      return delegate.readBytes(file, cap, scope);
    }

    @Override
    public TextRead readText(FileRef file, int cap, ReadScope scope) {
      opened.add(file.path().toString());
      return delegate.readText(file, cap, scope);
    }
  }

  @Test
  void readableIsFalseWithNoDiagnosticForAnOversizeNulNonUtf8OrCredentialFileAndTrueForTheControl() {
    InMemoryTextSource source =
        new InMemoryTextSource()
            .file(ref("ok.md"), utf8("fine"))
            .file(ref("over.txt"), new byte[ArtifactLimits.READ_REQUEST_BYTES])
            .file(ref("nul.dat"), new byte[] {'a', 0})
            .file(ref("latin1.txt"), new byte[] {(byte) 0xE9})
            .file(ref("secret.txt"), utf8(token("gh" + "p_", 36)))
            .file(ref("near.txt"), utf8(token("gh" + "p_", 35)))
            .file(ref("exact.txt"), "a".repeat(ArtifactLimits.CONTENT_CAP_BYTES).getBytes(StandardCharsets.US_ASCII));

    ReadSpy spy = new ReadSpy(source);
    ArtifactWalk.Result result = walk(spy).walk(MISSION, MID8);

    assertThat(result.entries()).extracting(ArtifactEntry::path, ArtifactEntry::readable)
        .containsExactly(
            org.assertj.core.api.Assertions.tuple("exact.txt", true),
            org.assertj.core.api.Assertions.tuple("latin1.txt", false),
            org.assertj.core.api.Assertions.tuple("near.txt", true),
            org.assertj.core.api.Assertions.tuple("nul.dat", false),
            org.assertj.core.api.Assertions.tuple("ok.md", true),
            org.assertj.core.api.Assertions.tuple("over.txt", false),
            org.assertj.core.api.Assertions.tuple("secret.txt", false));
    assertThat(diagnostics).isEmpty();
    assertThat(spy.opened).as("a size above the cap is decided from stat alone: the file is not opened").doesNotContain("over.txt").contains("ok.md", "exact.txt");
  }

  /** Reads of one path fail or report a different fact; everything else passes through. */
  private static final class OnRead implements TextSource {
    private final TextSource delegate;
    private final String path;
    private final TextFault.Kind fault;
    private final TextRead answer;

    OnRead(TextSource delegate, String path, TextFault.Kind fault, TextRead answer) {
      this.delegate = delegate;
      this.path = path;
      this.fault = fault;
      this.answer = answer;
    }

    @Override
    public DirListing list(FileRef dir, int nameLimit, ReadScope scope) {
      return delegate.list(dir, nameLimit, scope);
    }

    @Override
    public EntryStat stat(FileRef ref, ReadScope scope) {
      return delegate.stat(ref, scope);
    }

    @Override
    public BytesRead readBytes(FileRef file, int cap, ReadScope scope) {
      return delegate.readBytes(file, cap, scope);
    }

    @Override
    public TextRead readText(FileRef file, int cap, ReadScope scope) {
      if (file.path().toString().equals(path)) {
        if (fault != null) {
          throw new TextFault(fault);
        }
        return answer;
      }
      return delegate.readText(file, cap, scope);
    }
  }

  @Test
  void anUnreadableFileIsReadableFalseWithExactlyOneUnreadableDiagnosticAndAVanishedOneIsOmitted() {
    InMemoryTextSource base = new InMemoryTextSource().file(ref("a.md"), utf8("a")).file(ref("bad.md"), utf8("b")).file(ref("gone.md"), utf8("g")).file(ref("swapped.md"), utf8("s")).file(ref("dir.md"), utf8("d"));
    TextSource unreadable = new OnRead(base, "bad.md", TextFault.Kind.FILE_UNREADABLE, null);
    TextSource vanished = new OnRead(unreadable, "gone.md", TextFault.Kind.VANISHED, null);
    TextSource refused = new OnRead(vanished, "swapped.md", TextFault.Kind.PATH_REFUSED, null);
    TextSource notRegular = new OnRead(refused, "dir.md", null, new TextRead.NotRegular());

    ArtifactWalk.Result result = walk(notRegular).walk(MISSION, MID8);

    assertThat(result.entries()).extracting(ArtifactEntry::path, ArtifactEntry::readable)
        .containsExactly(org.assertj.core.api.Assertions.tuple("a.md", true), org.assertj.core.api.Assertions.tuple("bad.md", false));
    assertThat(diagnostics).containsExactly(new Diagnostic(DiagnosticCode.ARTIFACT_UNREADABLE, MID8, null));
  }

  /** A fault on the listing or the stat of one path; everything else passes through. */
  private static final class OnPath implements TextSource {
    private final TextSource delegate;
    private final String path;
    private final TextFault.Kind onList;
    private final TextFault.Kind onStat;

    OnPath(TextSource delegate, String path, TextFault.Kind onList, TextFault.Kind onStat) {
      this.delegate = delegate;
      this.path = path;
      this.onList = onList;
      this.onStat = onStat;
    }

    @Override
    public DirListing list(FileRef dir, int nameLimit, ReadScope scope) {
      if (onList != null && dir.path().toString().equals(path)) {
        throw new TextFault(onList);
      }
      return delegate.list(dir, nameLimit, scope);
    }

    @Override
    public EntryStat stat(FileRef ref, ReadScope scope) {
      if (onStat != null && ref.path().toString().equals(path)) {
        throw new TextFault(onStat);
      }
      return delegate.stat(ref, scope);
    }

    @Override
    public BytesRead readBytes(FileRef file, int cap, ReadScope scope) {
      return delegate.readBytes(file, cap, scope);
    }

    @Override
    public TextRead readText(FileRef file, int cap, ReadScope scope) {
      return delegate.readText(file, cap, scope);
    }
  }

  @Test
  void aDirectoryOrEntryThatWentOrBecameALinkWhileTheWalkRanIsSkippedAndNothingIsRefused() {
    InMemoryTextSource base = new InMemoryTextSource().file(ref("a.md"), utf8("a")).file(ref("sub/b.md"), utf8("b")).file(ref("other/c.md"), utf8("c")).file(ref("swap.md"), utf8("s")).file(ref("gone.md"), utf8("g"));
    TextSource listVanished = new OnPath(base, "sub", TextFault.Kind.VANISHED, null);
    TextSource listLink = new OnPath(listVanished, "other", TextFault.Kind.PATH_REFUSED, null);
    TextSource statLink = new OnPath(listLink, "swap.md", null, TextFault.Kind.PATH_REFUSED);
    TextSource statVanished = new OnPath(statLink, "gone.md", null, TextFault.Kind.VANISHED);

    ArtifactWalk.Result result = walk(statVanished).walk(MISSION, MID8);

    assertThat(paths(result)).containsExactly("a.md");
    assertThat(diagnostics).isEmpty();
  }

  @Test
  void aListingOrStatFaultOfTheOperatingSystemRefusesTheWholeListingAtAnyDepth() {
    InMemoryTextSource base = new InMemoryTextSource().file(ref("a.md"), utf8("a")).file(ref("sub/b.md"), utf8("b"));

    assertThat(refusal(walk(new OnPath(base, "sub", TextFault.Kind.DIR_UNREADABLE, null)))).isEqualTo(DetailRefusal.Kind.ARTIFACT_LISTING_UNREADABLE);
    assertThat(refusal(walk(new OnPath(base, "a.md", null, TextFault.Kind.DIR_UNREADABLE)))).isEqualTo(DetailRefusal.Kind.ARTIFACT_LISTING_UNREADABLE);
    assertThat(refusal(walk(new OnPath(base, "", TextFault.Kind.DIR_UNREADABLE, null)))).isEqualTo(DetailRefusal.Kind.ARTIFACT_LISTING_UNREADABLE);
    assertThat(diagnostics).hasSize(3).allMatch(diagnostic -> diagnostic.code() == DiagnosticCode.ARTIFACT_LISTING_UNREADABLE);
  }

  @Test
  void aRootThatIsNotADirectoryIsNotFoundAndANameThatIsNotASegmentOrHasNoEntryIsCountedAndSkipped() {
    InMemoryTextSource file = new InMemoryTextSource().file(ref(""), utf8("not a directory"));
    InMemoryTextSource odd = new InMemoryTextSource().file(ref("ok.md"), utf8("ok")).dir(ref(""), "", ".", "..", "a/b", "nul\0name", "ghost.md", "ok.md");

    assertThat(refusal(walk(file))).isEqualTo(DetailRefusal.Kind.NOT_FOUND);
    assertThat(paths(walk(odd).walk(MISSION, MID8))).containsExactly("ok.md");
  }

  // ---- AC-4.8: the file-name locale -------------------------------------------------------------------------------------------

  @Test
  void aNonAsciiNameOnAHostThatCannotDecodeNamesRefusesTheListingWithOneDiagnosticAndNothingIsOmitted() {
    InMemoryTextSource untrusted = new InMemoryTextSource().trustworthy(false).file(ref("café.md"), utf8("x")).file(ref("plain.md"), utf8("x"));
    InMemoryTextSource asciiOnly = new InMemoryTextSource().trustworthy(false).file(ref("plain.md"), utf8("x"));
    InMemoryTextSource trusted = new InMemoryTextSource().file(ref("café.md"), utf8("x")).file(ref("plain.md"), utf8("x"));

    assertThat(refusal(walk(untrusted))).isEqualTo(DetailRefusal.Kind.ARTIFACT_LISTING_UNREADABLE);
    assertThat(diagnostics).containsExactly(new Diagnostic(DiagnosticCode.ARTIFACT_LISTING_UNREADABLE, MID8, null));
    assertThat(paths(walk(asciiOnly).walk(MISSION, MID8))).containsExactly("plain.md");
    assertThat(paths(walk(trusted).walk(MISSION, MID8))).containsExactly("café.md", "plain.md");
  }

  // ---- A1 and the Mission directory ----------------------------------------------------------------------------------------------

  @Test
  void aDirectoryThatCannotBeListedRefusesTheWholeListing() {
    InMemoryTextSource source = new InMemoryTextSource().file(ref("a.md"), utf8("a")).fault(ref("sub"), TextFault.Kind.DIR_UNREADABLE);

    assertThat(refusal(walk(source))).isEqualTo(DetailRefusal.Kind.ARTIFACT_LISTING_UNREADABLE);
    assertThat(diagnostics).containsExactly(new Diagnostic(DiagnosticCode.ARTIFACT_LISTING_UNREADABLE, MID8, null));
  }

  @Test
  void aMissionDirectoryThatHasGoneIsNotFoundAndOneThatIsALinkIsNotFoundWithPathRefused() {
    InMemoryTextSource empty = new InMemoryTextSource();
    InMemoryTextSource gone = new InMemoryTextSource().fault(ref(""), TextFault.Kind.VANISHED);
    InMemoryTextSource link = new InMemoryTextSource().fault(ref(""), TextFault.Kind.PATH_REFUSED);

    assertThat(refusal(walk(empty))).isEqualTo(DetailRefusal.Kind.NOT_FOUND);
    assertThat(refusal(walk(gone))).isEqualTo(DetailRefusal.Kind.NOT_FOUND);
    assertThat(diagnostics).isEmpty();
    assertThat(refusal(walk(link))).isEqualTo(DetailRefusal.Kind.NOT_FOUND);
    assertThat(diagnostics).containsExactly(new Diagnostic(DiagnosticCode.PATH_REFUSED, MID8, null));
  }

  // ---- real files: AC-4.6, links, AC-4.9 --------------------------------------------------------------------------------------

  private static Path mission(Path root) throws IOException {
    return Files.createDirectories(root.resolve("kitty-specs").resolve("alpha-mission"));
  }

  private static TextSource fs(Path root) {
    return new FilesystemTextSource(root, AllowlistAccess.passThrough(), NameEncoding.fixed(true));
  }

  @Test
  void theModifiedTimeIsFlooredNotRounded(@TempDir Path root) throws Exception {
    Path dir = mission(root);
    Path file = Files.writeString(dir.resolve("a.md"), "x");
    Files.setLastModifiedTime(file, FileTime.from(Instant.ofEpochSecond(1_790_000_000L, 999_900_000L)));

    ArtifactEntry entry = walk(fs(root)).walk(MISSION, MID8).entries().getFirst();

    assertThat(entry.modifiedAt()).isEqualTo("2026-09-21T14:13:20Z");
    assertThat(entry.sizeBytes()).isEqualTo(1);
  }

  @Test
  void aSymbolicLinkToAFileAndToADirectoryIsNeitherListedNorFollowed(@TempDir Path root) throws Exception {
    Path dir = mission(root);
    Files.createDirectories(dir.resolve("real"));
    Files.writeString(dir.resolve("real/x.md"), "x");
    Files.writeString(dir.resolve("target.md"), "t");
    try {
      Files.createSymbolicLink(dir.resolve("linkfile.md"), dir.resolve("target.md"));
      Files.createSymbolicLink(dir.resolve("linkdir"), dir.resolve("real"));
    } catch (IOException | UnsupportedOperationException cannot) {
      assumeTrue(false, "the runner cannot create a symbolic link");
    }

    List<String> served = paths(walk(fs(root)).walk(MISSION, MID8));

    assertThat(served).containsExactly("real/x.md", "target.md");
  }

  private static void touch(Path file) throws IOException {
    Files.createFile(file);
  }

  /** The three root records plus 99997 regular files: the counter is exactly 100000 and 99998 files are eligible. */
  @Test
  void theFlatBoundTreeIsServedAt100000NamesAndRefusedAt100001(@TempDir Path root) throws Exception {
    Path dir = mission(root);
    for (String record : List.of("meta.json", "status.events.jsonl", "status.json")) {
      touch(dir.resolve(record));
    }
    for (int i = 0; i < 99_997; i++) {
      touch(dir.resolve(String.format("f%05d.md", i)));
    }
    ArtifactWalk walk = walk(fs(root));

    ArtifactWalk.Result served = walk.walk(MISSION, MID8);

    assertThat(served.entries()).hasSize(1000);
    assertThat(served.truncated()).isTrue();
    assertThat(walk.collectorHighWater()).isLessThanOrEqualTo(1001);
    assertThat(diagnostics).isEmpty();

    touch(dir.resolve("one-more.md"));

    assertThat(refusal(walk)).isEqualTo(DetailRefusal.Kind.ARTIFACT_LISTING_UNREADABLE);
    assertThat(diagnostics).containsExactly(new Diagnostic(DiagnosticCode.ARTIFACT_LISTING_UNREADABLE, MID8, null));
  }

  /**
   * The three root records, 997 regular files and 99 directories of 999 files each: 3 + 997 + 99 + 98901 = 100000. A directory or a
   * root record that was not counted would let this tree pass at 100001.
   */
  @Test
  void theNestedBoundTreeIsServedAt100000NamesAndRefusedAt100001(@TempDir Path root) throws Exception {
    Path dir = mission(root);
    for (String record : List.of("meta.json", "status.events.jsonl", "status.json")) {
      touch(dir.resolve(record));
    }
    for (int i = 0; i < 997; i++) {
      touch(dir.resolve(String.format("r%04d.md", i)));
    }
    for (int d = 0; d < 99; d++) {
      Path sub = Files.createDirectory(dir.resolve(String.format("d%02d", d)));
      for (int i = 0; i < 999; i++) {
        touch(sub.resolve(String.format("f%04d.md", i)));
      }
    }
    ArtifactWalk walk = walk(fs(root));

    ArtifactWalk.Result served = walk.walk(MISSION, MID8);

    assertThat(served.entries()).hasSize(1000);
    assertThat(served.truncated()).isTrue();
    assertThat(walk.collectorHighWater()).isLessThanOrEqualTo(1001);

    touch(dir.resolve("d00").resolve("one-more.md"));

    assertThat(refusal(walk)).isEqualTo(DetailRefusal.Kind.ARTIFACT_LISTING_UNREADABLE);
  }
}
