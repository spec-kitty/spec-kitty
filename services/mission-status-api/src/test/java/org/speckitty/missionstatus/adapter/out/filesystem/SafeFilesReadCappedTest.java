package org.speckitty.missionstatus.adapter.out.filesystem;

import static org.assertj.core.api.Assertions.assertThat;
import static org.assertj.core.api.Assertions.assertThatThrownBy;

import java.io.IOException;
import java.nio.ByteBuffer;
import java.nio.channels.SeekableByteChannel;
import java.nio.file.Files;
import java.nio.file.Path;
import java.util.Arrays;
import java.util.Optional;
import java.util.concurrent.atomic.AtomicLong;
import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.io.TempDir;
import org.speckitty.missionstatus.application.query.port.out.exceptions.SourceFault;
import org.speckitty.missionstatus.application.query.port.out.exceptions.SourceFault.Kind;

/**
 * D-68 and plan 7.1 row 5: the cap is enforced twice, in this order: the size of the open handle (no byte read when it exceeds the cap),
 * then the bytes actually read (at most {@code cap + 1}). {@code readRegular} delegates and keeps its behaviour.
 */
class SafeFilesReadCappedTest {

  @TempDir Path root;
  Path file;

  @BeforeEach
  void setUp() {
    file = root.resolve("f.bin");
  }

  private void write(int size) throws IOException {
    byte[] content = new byte[size];
    Arrays.fill(content, (byte) 'x');
    Files.write(file, content);
  }

  /** An access whose channel reports a fixed size and serves a fixed number of bytes, and counts what was read: the grow race. */
  private static final class Racing implements AllowlistAccess {
    final long reportedSize;
    final long servable;
    final AtomicLong delivered = new AtomicLong();
    final AtomicLong sizeCalls = new AtomicLong();
    final AllowlistAccess real = AllowlistAccess.passThrough();

    Racing(long reportedSize, long servable) {
      this.reportedSize = reportedSize;
      this.servable = servable;
    }

    @Override
    public SeekableByteChannel openRead(Path path) throws IOException {
      SeekableByteChannel inner = real.openRead(path);
      return new SeekableByteChannel() {
        long position;

        @Override
        public int read(ByteBuffer dst) {
          if (position >= servable) {
            return -1;
          }
          int n = (int) Math.min(dst.remaining(), servable - position);
          for (int i = 0; i < n; i++) {
            dst.put((byte) 'y');
          }
          position += n;
          delivered.addAndGet(n);
          return n;
        }

        @Override
        public long size() {
          sizeCalls.incrementAndGet();
          return reportedSize;
        }

        @Override
        public int write(ByteBuffer src) {
          throw new UnsupportedOperationException();
        }

        @Override
        public long position() {
          return position;
        }

        @Override
        public SeekableByteChannel position(long newPosition) {
          position = newPosition;
          return this;
        }

        @Override
        public SeekableByteChannel truncate(long size) {
          throw new UnsupportedOperationException();
        }

        @Override
        public boolean isOpen() {
          return inner.isOpen();
        }

        @Override
        public void close() throws IOException {
          inner.close();
        }
      };
    }

    @Override
    public java.nio.file.attribute.BasicFileAttributes stat(Path path, boolean followLinks) throws IOException {
      return real.stat(path, followLinks);
    }

    @Override
    public Path realPath(Path path) throws IOException {
      return real.realPath(path);
    }

    @Override
    public java.util.List<String> listNames(Path dir) throws IOException {
      return real.listNames(dir);
    }
  }

  @Test
  void aFileAtExactlyTheCapIsReturnedWhole() throws IOException {
    write(100);
    SafeFiles.Capped result = new SafeFiles(root, AllowlistAccess.passThrough()).readCapped(file, 100);
    assertThat(result).isInstanceOf(SafeFiles.Capped.Bytes.class);
    assertThat(((SafeFiles.Capped.Bytes) result).content()).hasSize(100);
  }

  @Test
  void aFileOneByteOverTheCapIsOverCap() throws IOException {
    write(101);
    assertThat(new SafeFiles(root, AllowlistAccess.passThrough()).readCapped(file, 100)).isInstanceOf(SafeFiles.Capped.OverCap.class);
  }

  @Test
  void aZeroByteFileIsEmptyBytesAndAMissingFileIsAbsent() throws IOException {
    write(0);
    SafeFiles files = new SafeFiles(root, AllowlistAccess.passThrough());
    assertThat(((SafeFiles.Capped.Bytes) files.readCapped(file, 10)).content()).isEmpty();
    assertThat(files.readCapped(root.resolve("missing"), 10)).isInstanceOf(SafeFiles.Capped.Absent.class);
  }

  @Test
  void aDirectoryIsNotRegularAndALinkIsRefused() throws IOException {
    SafeFiles files = new SafeFiles(root, AllowlistAccess.passThrough());
    Path dir = Files.createDirectory(root.resolve("d"));
    assertThat(files.readCapped(dir, 10)).isInstanceOf(SafeFiles.Capped.NotRegular.class);
    write(5);
    SymlinkSupport.link(root.resolve("ln"), file);
    assertThatThrownBy(() -> files.readCapped(root.resolve("ln"), 10)).isInstanceOfSatisfying(SourceFault.class, fault -> assertThat(fault.kind()).isEqualTo(Kind.PATH_REFUSED));
  }

  @Test
  void aHandleSizeAboveTheCapReturnsOverCapHavingReadZeroBytes() throws IOException {
    write(262145);
    Racing racing = new Racing(262145, 262145);
    SafeFiles.Capped result = new SafeFiles(root, racing).readCapped(file, 262144);
    assertThat(result).isInstanceOf(SafeFiles.Capped.OverCap.class);
    assertThat(racing.delivered.get()).as("AC-5.4: no byte is read when the open handle is already over the cap").isZero();
    assertThat(racing.sizeCalls.get()).isEqualTo(1);
  }

  @Test
  void aFileThatGrowsBetweenTheSizeAndTheReadIsOverCapWithAtMostCapPlusOneBytesRead() throws IOException {
    write(100);
    Racing racing = new Racing(100, 300000);
    SafeFiles.Capped result = new SafeFiles(root, racing).readCapped(file, 262144);
    assertThat(result).as("AC-7.1: size 100 at the handle, 300000 at read").isInstanceOf(SafeFiles.Capped.OverCap.class);
    assertThat(racing.delivered.get()).isLessThanOrEqualTo(262145);
    assertThat(racing.delivered.get()).as("the extra byte did arrive").isEqualTo(262145);
  }

  @Test
  void aShortReadIsNotSuccessTheLoopReadsUntilTheEnd() throws IOException {
    write(0);
    Racing racing = new Racing(200_000, 200_000);
    SafeFiles.Capped result = new SafeFiles(root, racing).readCapped(file, 262144);
    assertThat(((SafeFiles.Capped.Bytes) result).content()).hasSize(200_000);
  }

  @Test
  void readingThroughTheCapIsBoundedToCapPlusOneEvenForAHugeCap() throws IOException {
    write(100);
    Racing racing = new Racing(100, 10_000);
    assertThat(new SafeFiles(root, racing).readCapped(file, 50)).isInstanceOf(SafeFiles.Capped.OverCap.class);
    assertThat(racing.delivered.get()).isLessThanOrEqualTo(51);
  }

  @Test
  void readRegularDelegatesAndKeepsItsObservableBehaviour() throws IOException {
    SafeFiles files = new SafeFiles(root, AllowlistAccess.passThrough());
    write(100);
    assertThat(files.readRegular(file, 100, Kind.PATH_REFUSED, Kind.META_UNPARSEABLE)).map(bytes -> bytes.length).isEqualTo(Optional.of(100));
    write(101);
    assertThatThrownBy(() -> files.readRegular(file, 100, Kind.PATH_REFUSED, Kind.META_UNPARSEABLE)).isInstanceOfSatisfying(SourceFault.class, fault -> assertThat(fault.kind()).isEqualTo(Kind.META_UNPARSEABLE));
    assertThat(files.readRegular(root.resolve("missing"), 100, Kind.PATH_REFUSED, Kind.META_UNPARSEABLE)).isEmpty();
    Path dir = Files.createDirectory(root.resolve("d"));
    assertThatThrownBy(() -> files.readRegular(dir, 100, Kind.PATH_REFUSED, Kind.META_UNPARSEABLE)).isInstanceOfSatisfying(SourceFault.class, fault -> assertThat(fault.kind()).isEqualTo(Kind.PATH_REFUSED));
    Racing racing = new Racing(100, 300000);
    assertThatThrownBy(() -> new SafeFiles(root, racing).readRegular(file, 262144, Kind.PATH_REFUSED, Kind.LEDGER_UNREADABLE)).isInstanceOfSatisfying(SourceFault.class, fault -> assertThat(fault.kind()).isEqualTo(Kind.LEDGER_UNREADABLE));
  }

  @Test
  void anOperatingSystemFailureWhileOpeningIsTheUnreadableKind() throws IOException {
    write(5);
    RecordingAllowlistAccess recorder = new RecordingAllowlistAccess(root);
    recorder.failWhen(access -> access.mode() == Allowlist.OpenMode.READ, () -> new java.nio.file.AccessDeniedException("injected"));
    assertThatThrownBy(() -> new SafeFiles(root, recorder).readCapped(file, 10)).isInstanceOfSatisfying(SourceFault.class, fault -> assertThat(fault.kind()).isEqualTo(Kind.DIR_UNREADABLE));
  }
}
