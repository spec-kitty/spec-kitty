package org.speckitty.missionstatus.adapter.out.filesystem;

import java.io.ByteArrayOutputStream;
import java.io.IOException;
import java.nio.ByteBuffer;
import java.nio.channels.SeekableByteChannel;
import java.nio.file.FileSystemException;
import java.nio.file.NoSuchFileException;
import java.nio.file.NotDirectoryException;
import java.nio.file.Path;
import java.nio.file.attribute.BasicFileAttributes;
import java.util.Optional;
import org.speckitty.missionstatus.application.query.port.out.exceptions.SourceFault;
import org.speckitty.missionstatus.application.query.port.out.exceptions.SourceFault.Kind;

/**
 * Reads that never follow a final-component symbolic link, and directories that stay inside the real project root (FR-010, AC-10d).
 * It is the Java form of {@code O_NOFOLLOW} in the oracle's {@code _read_text_without_following_symlinks}, which Windows lacks: a
 * {@code NOFOLLOW_LINKS} attribute check that the target is a regular file, then a {@code NOFOLLOW_LINKS} open.
 *
 * <p>Every operation goes through the {@link AllowlistAccess} seam. A refused link is refused before it is opened, so the target's
 * content is never read and never appears in a message: faults are a {@link SourceFault} that carries only its kind.
 *
 * <p>The kind a caller passes for a refusal says which row applies: {@code LEDGER_UNREADABLE} for a ledger (L2),
 * {@code PATH_REFUSED} for a {@code meta.json} or a Mission directory (L9).
 */
public final class SafeFiles {

  private static final int CHUNK = 64 * 1024;

  /** The cap of a small document the project owner writes by hand or a tool writes whole: {@code meta.json}, {@code lanes.json}, the YAML files (1 MiB). */
  public static final int SMALL_FILE_MAX = 1024 * 1024;

  private final Path root;
  private final AllowlistAccess access;
  private Path realRoot;

  public SafeFiles(Path root, AllowlistAccess access) {
    this.root = root;
    this.access = access;
  }

  /**
   * A single path segment: no separator, no dot segment, not empty, and none of the characters Windows forbids in a name
   * ({@code < > : " | ? *} and the control characters, NUL included), so that {@code Path.resolve} cannot throw an
   * {@code InvalidPathException} on any platform. Names from the outside never reach a path otherwise.
   */
  static boolean isSafeSegment(String segment) {
    return !segment.isEmpty() && !segment.equals(".") && !segment.equals("..") && segment.chars().noneMatch(SafeFiles::isForbiddenInSegment);
  }

  private static boolean isForbiddenInSegment(int c) {
    return c < ' ' || c == 0x7f || "/\\<>:\"|?*".indexOf(c) >= 0;
  }

  /**
   * Whether the attributes of an entry read with NOFOLLOW_LINKS name a link. A symbolic link is one. So is a Windows junction (mount
   * point): the JDK reports it as a directory that is also "other" and not as a symbolic link, so a check of {@code isSymbolicLink}
   * alone walks into its target. A directory is never "other" on a POSIX system, so a FIFO, a socket or a device (other, not a
   * directory) keeps the rule it has: not a regular file.
   */
  public static boolean isLinkLike(BasicFileAttributes attributes) {
    return attributes.isSymbolicLink() || (attributes.isOther() && attributes.isDirectory());
  }

  /** The project root as configured (not resolved). */
  public Path root() {
    return root;
  }

  /** Whether the failure means "there is nothing at this path": a missing entry, or a path through something that is not a directory. */
  static boolean isAbsent(IOException failure) {
    if (failure instanceof NoSuchFileException || failure instanceof NotDirectoryException) {
      return true;
    }
    return failure instanceof FileSystemException system && "Not a directory".equals(system.getReason());
  }

  /** The attributes of {@code path} without following a final link; empty when nothing is there. */
  public Optional<BasicFileAttributes> statNoFollow(Path path) {
    try {
      return Optional.of(access.stat(path, false));
    } catch (IOException failure) {
      if (isAbsent(failure)) {
        return Optional.empty();
      }
      throw new SourceFault(Kind.DIR_UNREADABLE);
    }
  }

  /** The attributes of {@code path}, following links; empty when nothing is there (a dangling link is nothing). */
  public Optional<BasicFileAttributes> statFollow(Path path) {
    try {
      return Optional.of(access.stat(path, true));
    } catch (IOException failure) {
      if (isAbsent(failure)) {
        return Optional.empty();
      }
      throw new SourceFault(Kind.DIR_UNREADABLE);
    }
  }

  /** The result of {@link #readCapped}: a distinct outcome for each thing that can happen to a capped read. */
  public sealed interface Capped {
    /** The whole file, at most the cap. */
    record Bytes(byte[] content) implements Capped {}

    /** Nothing is there (or the path runs through something that is not a directory). */
    record Absent() implements Capped {}

    /** A directory or another entry that is not a regular file. */
    record NotRegular() implements Capped {}

    /** The open handle was larger than the cap, or more than the cap arrived while reading. */
    record OverCap() implements Capped {}
  }

  /**
   * Reads a whole regular file of at most {@code max} bytes. Empty when nothing is there. A link, a directory or any other non-regular
   * entry is refused with {@code refused}; an operating-system failure, and a file larger than {@code max} (checked on the open handle
   * and again while reading, because a file can grow), is {@code unreadable}. The cap is required: no read of a file the project owner
   * does not control can exhaust the heap. It delegates to {@link #readCapped(Path, int, Kind, Kind)}, so no second whole-file reader
   * exists (D-68).
   */
  public Optional<byte[]> readRegular(Path file, int max, Kind refused, Kind unreadable) {
    return switch (readCapped(file, max, refused, unreadable)) {
      case Capped.Bytes bytes -> Optional.of(bytes.content());
      case Capped.Absent absent -> Optional.empty();
      case Capped.NotRegular notRegular -> throw new SourceFault(refused);
      case Capped.OverCap overCap -> throw new SourceFault(unreadable);
    };
  }

  /**
   * The capped read of the text-read port (plan 7.1 row 5), for a file that is not a link: a link in the final component is refused
   * ({@code PATH_REFUSED}) before it is opened and an operating-system failure is {@code DIR_UNREADABLE}; everything else is a
   * {@link Capped} outcome. The cap is enforced twice, in this order: by the size of the <em>open handle</em> (a size above {@code cap}
   * is {@code OverCap} having read no byte), then by the bytes actually read, at most {@code cap + 1} of them.
   */
  public Capped readCapped(Path file, int cap) {
    return readCapped(file, cap, Kind.PATH_REFUSED, Kind.DIR_UNREADABLE);
  }

  Capped readCapped(Path file, int cap, Kind refused, Kind unreadable) {
    if (cap < 0) {
      throw new IllegalArgumentException("cap");
    }
    BasicFileAttributes attributes;
    try {
      attributes = access.stat(file, false);
    } catch (IOException failure) {
      if (isAbsent(failure)) {
        return new Capped.Absent();
      }
      throw new SourceFault(unreadable);
    }
    if (isLinkLike(attributes)) {
      throw new SourceFault(refused);
    }
    if (!attributes.isRegularFile()) {
      return new Capped.NotRegular();
    }
    SeekableByteChannel channel;
    try {
      channel = access.openRead(file);
    } catch (IOException failure) {
      if (isAbsent(failure)) {
        return new Capped.Absent();
      }
      // A link swapped in between the attribute check and the open fails the NOFOLLOW open; say which row it is.
      throw new SourceFault(isLink(file) ? refused : unreadable);
    }
    try (SeekableByteChannel open = channel) {
      if (open.size() > cap) {
        return new Capped.OverCap();
      }
      return drain(open, cap);
    } catch (IOException failure) {
      throw new SourceFault(unreadable);
    }
  }

  /** Reads until the end or until {@code cap + 1} bytes have arrived, whichever is first: never more, so a growing file costs a bounded read. */
  private static Capped drain(SeekableByteChannel open, int cap) throws IOException {
    long limit = (long) cap + 1;
    ByteArrayOutputStream out = new ByteArrayOutputStream();
    ByteBuffer buffer = ByteBuffer.allocate(CHUNK);
    long total = 0;
    while (total < limit) {
      buffer.clear();
      buffer.limit((int) Math.min(CHUNK, limit - total));
      int read = open.read(buffer);
      if (read < 0) {
        break;
      }
      out.write(buffer.array(), 0, read);
      total += read;
    }
    return total > cap ? new Capped.OverCap() : new Capped.Bytes(out.toByteArray());
  }

  private boolean isLink(Path file) {
    try {
      return isLinkLike(access.stat(file, false));
    } catch (IOException failure) {
      return false;
    }
  }

  /**
   * A Mission's own primary directory, checked: it exists as a real directory (not a link of any kind) and its real path is inside the
   * real path of the project root. Gone is {@code VANISHED}; a link or an escape is {@code PATH_REFUSED}; anything the operating system
   * will not say is {@code DIR_UNREADABLE}.
   */
  public Path requireContainedDir(Path dir) {
    BasicFileAttributes attributes;
    try {
      attributes = access.stat(dir, false);
    } catch (IOException failure) {
      throw new SourceFault(isAbsent(failure) ? Kind.VANISHED : Kind.DIR_UNREADABLE);
    }
    if (isLinkLike(attributes)) {
      throw new SourceFault(Kind.PATH_REFUSED);
    }
    if (!attributes.isDirectory()) {
      throw new SourceFault(Kind.VANISHED);
    }
    Path real;
    try {
      real = access.realPath(dir);
    } catch (IOException failure) {
      throw new SourceFault(isAbsent(failure) ? Kind.VANISHED : Kind.DIR_UNREADABLE);
    }
    if (!real.startsWith(realRoot())) {
      throw new SourceFault(Kind.PATH_REFUSED);
    }
    return dir;
  }

  /**
   * Whether {@code dir} is a directory (a link followed) whose real path is inside the real project root. Absent, not a directory and
   * outside are all {@code false}: the coordination fallback to the primary directory. An operating-system failure is a fault.
   */
  public boolean isContainedDirectory(Path dir) {
    Optional<BasicFileAttributes> attributes = statFollow(dir);
    if (attributes.isEmpty() || !attributes.get().isDirectory()) {
      return false;
    }
    try {
      return access.realPath(dir).startsWith(realRoot());
    } catch (IOException failure) {
      if (isAbsent(failure)) {
        return false;
      }
      throw new SourceFault(Kind.DIR_UNREADABLE);
    }
  }

  /**
   * Whether {@code file}, with every link on its way followed, lies inside the real project root. Nothing there is "contained" (there is
   * nothing to read, and the read finds that out); a path that resolves outside is not. An operating-system failure is a fault.
   */
  public boolean isContainedPath(Path file) {
    try {
      return access.realPath(file).startsWith(realRoot());
    } catch (IOException failure) {
      if (isAbsent(failure)) {
        return true;
      }
      throw new SourceFault(Kind.DIR_UNREADABLE);
    }
  }

  private Path realRoot() {
    if (realRoot == null) {
      try {
        realRoot = access.realPath(root);
      } catch (IOException failure) {
        throw new SourceFault(Kind.DIR_UNREADABLE);
      }
    }
    return realRoot;
  }
}
