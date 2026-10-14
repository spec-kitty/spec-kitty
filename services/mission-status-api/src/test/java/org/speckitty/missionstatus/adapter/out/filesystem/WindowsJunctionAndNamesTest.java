package org.speckitty.missionstatus.adapter.out.filesystem;

import static org.assertj.core.api.Assertions.assertThat;
import static org.assertj.core.api.Assertions.assertThatThrownBy;

import java.io.IOException;
import java.nio.channels.SeekableByteChannel;
import java.nio.file.Files;
import java.nio.file.Path;
import java.nio.file.attribute.BasicFileAttributes;
import java.nio.file.attribute.FileTime;
import java.util.List;
import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.io.TempDir;
import org.speckitty.missionstatus.application.query.port.out.TextSource;
import org.speckitty.missionstatus.application.query.port.out.dto.EntryStat;
import org.speckitty.missionstatus.application.query.port.out.dto.FileRef;
import org.speckitty.missionstatus.application.query.port.out.dto.MissionRef;
import org.speckitty.missionstatus.application.query.port.out.dto.ReadScope;
import org.speckitty.missionstatus.application.query.port.out.dto.RelativePath;
import org.speckitty.missionstatus.application.query.port.out.exceptions.SourceFault;
import org.speckitty.missionstatus.application.query.port.out.exceptions.TextFault;

/**
 * J-S2b and J-S3b. A Windows junction (mount point) opened with NOFOLLOW_LINKS reports a directory that is also "other", and is not a
 * symbolic link; there is no junction on Linux, so the attributes are faked through the seam. A path the platform cannot parse
 * (InvalidPathException) must be a refusal, never an unmapped 500.
 */
class WindowsJunctionAndNamesTest {

  private static final String MISSION = "m-01ABCDEF";

  /** The attributes of a real entry, with the flags a junction shows. */
  private record Junction(BasicFileAttributes real) implements BasicFileAttributes {
    public boolean isOther() { return true; }
    public boolean isDirectory() { return true; }
    public boolean isSymbolicLink() { return false; }
    public boolean isRegularFile() { return false; }
    public FileTime lastModifiedTime() { return real.lastModifiedTime(); }
    public FileTime lastAccessTime() { return real.lastAccessTime(); }
    public FileTime creationTime() { return real.creationTime(); }
    public long size() { return real.size(); }
    public Object fileKey() { return null; }
  }

  /** The seam, with a junction at every path whose last name is {@code jn}. */
  private record JunctionAccess(AllowlistAccess delegate) implements AllowlistAccess {
    public SeekableByteChannel openRead(Path path) throws IOException { return delegate.openRead(path); }
    public BasicFileAttributes stat(Path path, boolean followLinks) throws IOException {
      BasicFileAttributes real = delegate.stat(path, followLinks);
      return !followLinks && "jn".equals(path.getFileName().toString()) ? new Junction(real) : real;
    }
    public Path realPath(Path path) throws IOException { return delegate.realPath(path); }
    public List<String> listNames(Path dir) throws IOException { return delegate.listNames(dir); }
  }

  @TempDir Path sandbox;
  Path primary;
  TextSource source;

  @BeforeEach
  void setUp() throws IOException {
    Path root = Files.createDirectory(sandbox.resolve("project"));
    primary = Files.createDirectories(root.resolve("kitty-specs").resolve(MISSION));
    Files.createDirectories(primary.resolve("jn"));
    Files.writeString(primary.resolve("jn").resolve("f.md"), "inside");
    Files.writeString(primary.resolve("spec.md"), "# Spec\n");
    source = new FilesystemTextSource(root, new JunctionAccess(AllowlistAccess.passThrough()), NameEncoding.fixed(true));
  }

  private FileRef at(String... segments) {
    return new FileRef.MissionFile(new MissionRef(MISSION), RelativePath.of(String.join("/", segments)));
  }

  private static void assertRefused(Runnable action) {
    assertThatThrownBy(action::run).isInstanceOfSatisfying(TextFault.class, fault -> assertThat(fault.kind()).isEqualTo(TextFault.Kind.PATH_REFUSED));
  }

  // ---- J-S2b -------------------------------------------------------------------------------------------------------------

  @Test
  void theLinkPredicateCountsADirectoryThatIsOtherAsALinkButNotAFifoOrADevice() throws IOException {
    BasicFileAttributes junction = new Junction(Files.readAttributes(primary, BasicFileAttributes.class));
    assertThat(SafeFiles.isLinkLike(junction)).isTrue();
    assertThat(SafeFiles.isLinkLike(Files.readAttributes(primary, BasicFileAttributes.class))).isFalse();
    assertThat(SafeFiles.isLinkLike(Files.readAttributes(primary.resolve("spec.md"), BasicFileAttributes.class))).isFalse();
  }

  @Test
  void aJunctionAsAnAncestorIsRefusedForReadStatAndList() {
    assertRefused(() -> source.readText(at("jn", "f.md"), 100, ReadScope.ARTIFACT));
    assertRefused(() -> source.stat(at("jn", "f.md"), ReadScope.ARTIFACT));
    assertRefused(() -> source.list(at("jn", "f.md"), 10, ReadScope.ARTIFACT));
  }

  @Test
  void aJunctionAsTheTargetIsRefusedForListAndReportedAsALinkByStat() {
    assertRefused(() -> source.list(at("jn"), 10, ReadScope.ARTIFACT));
    assertThat(source.stat(at("jn"), ReadScope.ARTIFACT)).isInstanceOfSatisfying(EntryStat.Present.class, present -> assertThat(present.kind()).isEqualTo(EntryStat.EntryKind.SYMLINK));
  }

  // ---- J-S3b -------------------------------------------------------------------------------------------------------------

  @Test
  void aSegmentThePlatformCannotParseIsRefusedNotAnInvalidPathException() {
    // RelativePath already refuses NUL, the one name Linux cannot parse; the step that appends a segment must still map the exception.
    assertThatThrownBy(() -> FilesystemTextSource.child(primary, "a\0b.md"))
        .isInstanceOfSatisfying(SourceFault.class, fault -> assertThat(fault.kind()).isEqualTo(SourceFault.Kind.PATH_REFUSED));
    assertThat(FilesystemTextSource.child(primary, "spec.md")).isEqualTo(primary.resolve("spec.md"));
  }
}
