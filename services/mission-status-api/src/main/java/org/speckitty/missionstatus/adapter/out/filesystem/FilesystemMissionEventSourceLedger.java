package org.speckitty.missionstatus.adapter.out.filesystem;

import java.io.ByteArrayOutputStream;
import java.io.IOException;
import java.nio.ByteBuffer;
import java.nio.channels.SeekableByteChannel;
import java.nio.file.Path;
import java.nio.file.attribute.BasicFileAttributes;
import java.security.MessageDigest;
import java.security.NoSuchAlgorithmException;
import java.util.HexFormat;
import java.util.List;
import java.util.Optional;
import org.speckitty.missionstatus.adapter.out.filesystem.codec.LedgerLineDecoder;
import org.speckitty.missionstatus.application.query.port.out.dto.LedgerRead;
import org.speckitty.missionstatus.application.query.port.out.dto.LedgerStamp;
import org.speckitty.missionstatus.application.query.port.out.dto.LedgerWindow;
import org.speckitty.missionstatus.application.query.port.out.exceptions.SourceFault;
import org.speckitty.missionstatus.application.query.port.out.exceptions.SourceFault.Kind;
import org.speckitty.missionstatus.domain.model.TailClassification;

/**
 * The byte-level half of the ledger: the stamp, the whole read and the window from an offset. It opens the ledger itself (one stat
 * without following a link, then a read-only open) so the stamp costs one stat and a backward scan over the final physical lines, and
 * every operation goes through the {@link AllowlistAccess} seam. A ledger that is a link, a directory or any non-regular entry, or that
 * the operating system will not open, is {@code LEDGER_UNREADABLE} (row L2); an absent ledger is a normal state (row L1).
 *
 * <p>The cursor invariant is the byte count and the SHA-256 of the last <em>terminated</em> line, a blank line included (DD-92).
 * Physical lines end at {@code \n} bytes only; a {@code \r} before it stays in the raw line (DD-85).
 */
final class FilesystemMissionEventSourceLedger {

  static final String FILE = "status.events.jsonl";

  private static final int CHUNK = 64 * 1024;
  private static final String EMPTY_DIGEST = hex(newDigest().digest());

  /**
   * The largest ledger the service reads (64 MiB). The whole-ledger and window reads hold the bytes, and then the decoded lines, in
   * memory, so an unbounded ledger could end the process with an {@code OutOfMemoryError}. The largest ledger among the 594 of this
   * repository is under 1 MiB, so the cap is some seventy times what a real Mission needs; a bigger file is {@code LEDGER_UNREADABLE}
   * (row L2: the Mission is served as an empty draft with one diagnostic), never an opaque failure.
   */
  static final long MAX_BYTES = 64L * 1024 * 1024;

  private final AllowlistAccess access;
  private final long maxBytes;

  FilesystemMissionEventSourceLedger(AllowlistAccess access) {
    this(access, MAX_BYTES);
  }

  FilesystemMissionEventSourceLedger(AllowlistAccess access, long maxBytes) {
    this.access = access;
    this.maxBytes = maxBytes;
  }

  private record Open(BasicFileAttributes attributes, SeekableByteChannel channel) implements AutoCloseable {
    @Override
    public void close() throws IOException {
      channel.close();
    }
  }

  // ---- the three operations -----------------------------------------------------------------------------------------------------

  /** Size, modification time, file key, terminated length and the digest of the last terminated line. */
  LedgerStamp stamp(Path file) {
    Optional<Open> opened = open(file);
    if (opened.isEmpty()) {
      return LedgerStamp.of("absent");
    }
    try (Open open = opened.get()) {
      long size = open.attributes().size();
      long limit = Math.min(size, open.channel().size());
      long terminated = previousNewlineEnd(open.channel(), limit);
      String digest = terminated == 0 ? EMPTY_DIGEST : digestOfLineEndingAt(open.channel(), terminated);
      return LedgerStamp.of(size, open.attributes().lastModifiedTime(), String.valueOf(open.attributes().fileKey()), terminated, digest);
    } catch (IOException failure) {
      throw new SourceFault(Kind.LEDGER_UNREADABLE);
    }
  }

  /** The whole ledger, decoded by the codec, with the classification of what follows the last newline. */
  LedgerRead read(Path file) {
    Optional<Open> opened = open(file);
    if (opened.isEmpty()) {
      return new LedgerRead(List.of(), TailClassification.NONE);
    }
    try (Open open = opened.get()) {
      LedgerLineDecoder.Decoded decoded = LedgerLineDecoder.decode(readFrom(open.channel(), 0, maxBytes));
      return new LedgerRead(decoded.lines(), decoded.tail());
    } catch (IOException failure) {
      throw new SourceFault(Kind.LEDGER_UNREADABLE);
    }
  }

  /**
   * The ledger from {@code offset} on. Lines are numbered from 1 inside the window. An offset that is negative, past the end or not
   * just after a newline is not aligned and holds nothing; the digest of the line that ends the offset is the digest of nothing at
   * offset 0 and for every offset that is not aligned.
   */
  LedgerWindow window(Path file, long offset) {
    Optional<Open> opened = open(file);
    if (opened.isEmpty()) {
      return new LedgerWindow(0, offset == 0, EMPTY_DIGEST, List.of(), TailClassification.NONE);
    }
    try (Open open = opened.get()) {
      long size = open.channel().size();
      if (offset < 0 || offset > size || (offset > 0 && byteAt(open.channel(), offset - 1) != '\n')) {
        return new LedgerWindow(size, false, EMPTY_DIGEST, List.of(), TailClassification.NONE);
      }
      String preceding = offset == 0 ? EMPTY_DIGEST : digestOfLineEndingAt(open.channel(), offset);
      byte[] later = readFrom(open.channel(), offset, maxBytes);
      LedgerLineDecoder.Decoded decoded = LedgerLineDecoder.decode(later);
      return new LedgerWindow(offset + later.length, true, preceding, decoded.lines(), decoded.tail());
    } catch (IOException failure) {
      throw new SourceFault(Kind.LEDGER_UNREADABLE);
    }
  }

  // ---- opening ------------------------------------------------------------------------------------------------------------------

  private Optional<Open> open(Path file) {
    BasicFileAttributes attributes;
    try {
      attributes = access.stat(file, false);
    } catch (IOException failure) {
      if (SafeFiles.isAbsent(failure)) {
        return Optional.empty();
      }
      throw new SourceFault(Kind.LEDGER_UNREADABLE);
    }
    if (attributes.isSymbolicLink() || !attributes.isRegularFile() || attributes.size() > maxBytes) {
      throw new SourceFault(Kind.LEDGER_UNREADABLE);
    }
    try {
      return Optional.of(new Open(attributes, access.openRead(file)));
    } catch (IOException failure) {
      if (SafeFiles.isAbsent(failure)) {
        return Optional.empty();
      }
      // A link swapped in between the stat and the open fails the no-follow open: the same row.
      throw new SourceFault(Kind.LEDGER_UNREADABLE);
    }
  }

  // ---- byte scanning --------------------------------------------------------------------------------------------------------------

  /** The position just after the last {@code \n} that lies before {@code limit}, or 0 when there is none. Reads backward in chunks. */
  private static long previousNewlineEnd(SeekableByteChannel channel, long limit) throws IOException {
    ByteBuffer buffer = ByteBuffer.allocate(CHUNK);
    long end = limit;
    while (end > 0) {
      long start = Math.max(0, end - CHUNK);
      buffer.clear().limit((int) (end - start));
      fill(channel, start, buffer);
      for (int i = buffer.position() - 1; i >= 0; i--) {
        if (buffer.array()[i] == '\n') {
          return start + i + 1;
        }
      }
      end = start;
    }
    return 0;
  }

  /** The SHA-256 of the physical line that ends at {@code end} (just after a newline), its newline included. */
  private static String digestOfLineEndingAt(SeekableByteChannel channel, long end) throws IOException {
    long start = previousNewlineEnd(channel, end - 1);
    MessageDigest digest = newDigest();
    ByteBuffer buffer = ByteBuffer.allocate(CHUNK);
    long position = start;
    while (position < end) {
      buffer.clear().limit((int) Math.min(CHUNK, end - position));
      fill(channel, position, buffer);
      if (buffer.position() == 0) {
        break;
      }
      digest.update(buffer.array(), 0, buffer.position());
      position += buffer.position();
    }
    return hex(digest.digest());
  }

  private static int byteAt(SeekableByteChannel channel, long position) throws IOException {
    ByteBuffer one = ByteBuffer.allocate(1);
    fill(channel, position, one);
    return one.position() == 0 ? -1 : one.get(0);
  }

  /** The bytes from {@code position} on; a file that has grown past {@code max} since it was opened is an {@link IOException} (row L2). */
  private static byte[] readFrom(SeekableByteChannel channel, long position, long max) throws IOException {
    ByteArrayOutputStream out = new ByteArrayOutputStream();
    ByteBuffer buffer = ByteBuffer.allocate(CHUNK);
    long at = position;
    while (true) {
      buffer.clear();
      fill(channel, at, buffer);
      if (buffer.position() == 0) {
        return out.toByteArray();
      }
      out.write(buffer.array(), 0, buffer.position());
      at += buffer.position();
      if (out.size() > max) {
        throw new IOException("ledger larger than the cap");
      }
    }
  }

  /** Reads into {@code buffer} from {@code position} until it is full or the file ends. */
  private static void fill(SeekableByteChannel channel, long position, ByteBuffer buffer) throws IOException {
    channel.position(position);
    while (buffer.hasRemaining()) {
      if (channel.read(buffer) < 0) {
        return;
      }
    }
  }

  private static MessageDigest newDigest() {
    try {
      return MessageDigest.getInstance("SHA-256");
    } catch (NoSuchAlgorithmException impossible) {
      throw new IllegalStateException("SHA-256 is a required JDK algorithm", impossible);
    }
  }

  private static String hex(byte[] digest) {
    return HexFormat.of().formatHex(digest);
  }
}
