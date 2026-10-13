package org.speckitty.missionstatus.adapter.out.filesystem;

import static org.assertj.core.api.Assertions.assertThat;

import java.io.IOException;
import java.nio.file.AccessDeniedException;
import java.nio.file.Files;
import java.nio.file.Path;
import java.util.ArrayList;
import java.util.Collections;
import java.util.List;
import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.io.TempDir;
import org.speckitty.missionstatus.adapter.out.filesystem.Allowlist.OpenMode;
import org.speckitty.missionstatus.adapter.out.filesystem.Allowlist.PathClass;
import org.speckitty.missionstatus.application.query.port.out.exceptions.SourceFault;
import org.speckitty.missionstatus.application.query.port.out.exceptions.SourceFault.Kind;

/** The Mission listing (T045): sorted by the code, a directory without {@code meta.json} is not a Mission, and the L6/L9/L11 faults. */
class ListingTest {

  @TempDir Path sandbox;
  Path root;
  RecordingAllowlistAccess recorder;
  Listing listing;

  /** Hands the names back in reverse, so a listing that relies on the file system's order cannot pass by luck. */
  private static final class Reversing implements AllowlistAccess {
    private final AllowlistAccess delegate;

    Reversing(AllowlistAccess delegate) {
      this.delegate = delegate;
    }

    @Override
    public java.nio.channels.SeekableByteChannel openRead(Path path) throws IOException {
      return delegate.openRead(path);
    }

    @Override
    public java.nio.file.attribute.BasicFileAttributes stat(Path path, boolean followLinks) throws IOException {
      return delegate.stat(path, followLinks);
    }

    @Override
    public Path realPath(Path path) throws IOException {
      return delegate.realPath(path);
    }

    @Override
    public List<String> listNames(Path dir) throws IOException {
      List<String> names = new ArrayList<>(delegate.listNames(dir));
      names.sort(java.util.Comparator.reverseOrder());
      return names;
    }
  }

  @BeforeEach
  void setUp() throws IOException {
    root = Files.createDirectory(sandbox.resolve("project"));
    recorder = new RecordingAllowlistAccess(root, new Reversing(AllowlistAccess.passThrough()));
    listing = new Listing(new SafeFiles(root, recorder), recorder);
  }

  private void mission(String name) throws IOException {
    Path dir = Files.createDirectories(root.resolve("kitty-specs").resolve(name));
    Files.writeString(dir.resolve("meta.json"), "{}");
  }

  private static String cp(int codePoint) {
    return new String(Character.toChars(codePoint));
  }

  @Test
  void namesAreSortedByCodePointNotByCreationOrderNorByListingOrderNorByUtf16Unit() throws IOException {
    // U+FF61 sorts before U+1F600 by code point, but after it by UTF-16 unit (the surrogate D83D is lower than FF61).
    List<String> created = List.of("m-b", "m-a", "M-Z", "m-" + cp(0x1F600), "m-" + cp(0xFF61), "m-" + cp(0xE9));
    for (String name : created) {
      mission(name);
    }
    assertThat(listing.missionNames()).containsExactly("M-Z", "m-a", "m-b", "m-" + cp(0xE9), "m-" + cp(0xFF61), "m-" + cp(0x1F600));
  }

  @Test
  void theSortedOrderEqualsPythonsSortOfStrings() throws IOException {
    List<String> created = new ArrayList<>(List.of("z-1", "a-2", "A-3", "m-10", "m-9", "a_1", "a-1"));
    Collections.shuffle(created, new java.util.Random(7));
    for (String name : created) {
      mission(name);
    }
    // sorted(list_of_str) in Python is code point order: uppercase before lowercase, "-" (45) before "_" (95) and digits (48-57).
    assertThat(listing.missionNames()).containsExactly("A-3", "a-1", "a-2", "a_1", "m-10", "m-9", "z-1");
  }

  @Test
  void aDirectoryWithoutMetaJsonIsNotAMissionAndNothingSaysSo() throws IOException {
    mission("real");
    Files.createDirectories(root.resolve("kitty-specs/drafts/tasks"));
    Files.writeString(root.resolve("kitty-specs/stray-file"), "x");
    Files.createDirectories(root.resolve("kitty-specs/meta-is-a-dir/meta.json"));
    assertThat(listing.missionNames()).containsExactly("real");
  }

  @Test
  void aMissingKittySpecsDirectoryIsAnEmptyListing() {
    assertThat(listing.missionNames()).isEmpty();
  }

  @Test
  void kittySpecsThatIsAFileIsAnEmptyListing() throws IOException {
    Files.writeString(root.resolve("kitty-specs"), "x");
    assertThat(listing.missionNames()).isEmpty();
  }

  @Test
  void anUnlistableKittySpecsIsL11() throws IOException {
    mission("real");
    recorder.failWhen(access -> access.pathClass() == PathClass.SPECS_DIR && access.mode() == OpenMode.LIST, () -> new AccessDeniedException("injected"));
    assertThat(faultOf(listing::missionNames)).isEqualTo(Kind.DIR_UNREADABLE);
  }

  @Test
  void aKittySpecsThatCannotBeStatedIsL11Too() throws IOException {
    mission("real");
    recorder.failWhen(access -> access.pathClass() == PathClass.SPECS_DIR && access.mode() == OpenMode.STAT, () -> new IOException("injected"));
    assertThat(faultOf(listing::missionNames)).isEqualTo(Kind.DIR_UNREADABLE);
  }

  @Test
  void aMetaJsonThatCannotBeStatedIsL11Too() throws IOException {
    mission("real");
    recorder.failWhen(access -> access.pathClass() == PathClass.MISSION_META, () -> new AccessDeniedException("injected"));
    assertThat(faultOf(listing::missionNames)).isEqualTo(Kind.DIR_UNREADABLE);
  }

  @Test
  void aMissionDirectoryThatVanishesBetweenListingAndReadIsL6() throws IOException {
    mission("one");
    mission("two");
    assertThat(listing.missionNames()).containsExactly("one", "two");
    Files.delete(root.resolve("kitty-specs/two/meta.json"));
    Files.delete(root.resolve("kitty-specs/two"));
    assertThat(listing.ownDir("one")).isEqualTo(root.resolve("kitty-specs/one"));
    assertThat(faultOf(() -> listing.ownDir("two"))).isEqualTo(Kind.VANISHED);
  }

  @Test
  void aMissionRefusedBySymlinkIsListedAndL9WhileTheOthersAreServed() throws IOException {
    mission("good");
    Path elsewhere = Files.createDirectories(sandbox.resolve("elsewhere/m"));
    Files.writeString(elsewhere.resolve("meta.json"), "{}");
    SymlinkSupport.link(root.resolve("kitty-specs/escape"), elsewhere);
    assertThat(listing.missionNames()).containsExactly("escape", "good");
    assertThat(faultOf(() -> listing.ownDir("escape"))).isEqualTo(Kind.PATH_REFUSED);
    assertThat(listing.ownDir("good")).isEqualTo(root.resolve("kitty-specs/good"));
  }

  @Test
  void aSymlinkedMetaJsonPointingAtAFileListsTheMissionAndADanglingOneDoesNot() throws IOException {
    Files.createDirectories(root.resolve("kitty-specs/linked"));
    Files.createDirectories(root.resolve("kitty-specs/dangling"));
    Path target = Files.writeString(sandbox.resolve("target.json"), "{}");
    SymlinkSupport.link(root.resolve("kitty-specs/linked/meta.json"), target);
    SymlinkSupport.link(root.resolve("kitty-specs/dangling/meta.json"), sandbox.resolve("no-such-file"));
    assertThat(listing.missionNames()).containsExactly("linked");
  }

  @Test
  void theListingTouchesOnlyAllowlistedPathsAndOnlyReadsNames() throws IOException {
    mission("one");
    listing.missionNames();
    listing.ownDir("one");
    assertThat(recorder.violations()).isEmpty();
    assertThat(recorder.accesses()).noneMatch(access -> access.mode() == OpenMode.READ);
  }

  @Test
  void ownDirRefusesANameThatIsNotOneSafePathSegment() {
    for (String hostile : List.of("..", ".", "", "a/../b", "../outside", "a/b", "a\\b", "x\0y")) {
      recorder.clear();
      assertThat(faultOf(() -> listing.ownDir(hostile))).as("[" + hostile + "]").isEqualTo(Kind.PATH_REFUSED);
      assertThat(recorder.accesses()).as("[" + hostile + "]").isEmpty();
    }
  }

  private static Kind faultOf(Runnable action) {
    try {
      action.run();
    } catch (SourceFault fault) {
      return fault.kind();
    }
    throw new AssertionError("no SourceFault");
  }
}
