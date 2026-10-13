package org.speckitty.missionstatus.adapter.out.filesystem;

import static org.assertj.core.api.Assertions.assertThat;
import static org.assertj.core.api.Assertions.assertThatThrownBy;

import java.io.IOException;
import java.nio.ByteBuffer;
import java.nio.channels.SeekableByteChannel;
import java.nio.file.Files;
import java.nio.file.NoSuchFileException;
import java.nio.file.Path;
import java.nio.file.attribute.BasicFileAttributes;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.io.TempDir;

/** The production seam: a read never follows a final-component link (T043 step 1), and the seam offers no way to write. */
class AllowlistPassThroughTest {

  @TempDir Path dir;

  @Test
  void aRegularFileIsReadThroughTheSeam() throws IOException {
    Path file = Files.writeString(dir.resolve("a.txt"), "hello");
    try (SeekableByteChannel channel = AllowlistAccess.passThrough().openRead(file)) {
      ByteBuffer buffer = ByteBuffer.allocate(16);
      channel.read(buffer);
      assertThat(buffer.position()).isEqualTo(5);
    }
  }

  @Test
  void aFinalComponentSymbolicLinkIsNotFollowedWhenOpeningForRead() throws IOException {
    Path target = Files.writeString(dir.resolve("target.txt"), "secret");
    Path link = dir.resolve("link.txt");
    SymlinkSupport.link(link, target);
    assertThatThrownBy(() -> AllowlistAccess.passThrough().openRead(link)).isInstanceOf(IOException.class);
  }

  @Test
  void statWithoutFollowingReportsTheLinkAndFollowingReportsTheTarget() throws IOException {
    Path target = Files.writeString(dir.resolve("target.txt"), "secret");
    Path link = dir.resolve("link.txt");
    SymlinkSupport.link(link, target);
    BasicFileAttributes plain = AllowlistAccess.passThrough().stat(link, false);
    BasicFileAttributes followed = AllowlistAccess.passThrough().stat(link, true);
    assertThat(plain.isSymbolicLink()).isTrue();
    assertThat(followed.isRegularFile()).isTrue();
  }

  @Test
  void aMissingFileIsANoSuchFileException() {
    assertThatThrownBy(() -> AllowlistAccess.passThrough().openRead(dir.resolve("absent"))).isInstanceOf(NoSuchFileException.class);
    assertThatThrownBy(() -> AllowlistAccess.passThrough().stat(dir.resolve("absent"), false)).isInstanceOf(NoSuchFileException.class);
  }

  @Test
  void listingGivesNamesOnlyAndRealPathResolves() throws IOException {
    Files.createDirectory(dir.resolve("sub"));
    Files.writeString(dir.resolve("f"), "x");
    assertThat(AllowlistAccess.passThrough().listNames(dir)).containsExactlyInAnyOrder("sub", "f");
    assertThat(AllowlistAccess.passThrough().realPath(dir)).isEqualTo(dir.toRealPath());
  }
}
