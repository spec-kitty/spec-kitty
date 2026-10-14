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

  /**
   * Reads a whole regular file of at most {@code max} bytes. Empty when nothing is there. A link, a directory or any other non-regular
   * entry is refused with {@code refused}; an operating-system failure, and a file larger than {@code max} (checked on the attributes
   * and again while reading, because a file can grow), is {@code unreadable}. The cap is required: this is the only whole-file read of
   * the adapter, so no read of a file the project owner does not control can exhaust the heap.
   */
  public Optional<byte[]> readRegular(Path file, int max, Kind refused, Kind unreadable) {
    Optional<OpenFile> opened = openRegular(file, refused, unreadable);
    if (opened.isEmpty()) {
      return Optional.empty();
    }
    try (SeekableByteChannel open = opened.get().channel()) {
      if (opened.get().size() > max) {
        throw new SourceFault(unreadable);
      }
      ByteArrayOutputStream out = new ByteArrayOutputStream();
      ByteBuffer buffer = ByteBuffer.allocate(CHUNK);
      while (open.read(buffer) >= 0) {
        out.write(buffer.array(), 0, buffer.position());
        buffer.clear();
        if (out.size() > max) {
          throw new SourceFault(unreadable);
        }
      }
      return Optional.of(out.toByteArray());
    } catch (IOException failure) {
      throw new SourceFault(unreadable);
    }
  }

  private record OpenFile(SeekableByteChannel channel, long size) {}

  /** Opens a regular file for reading under the rules of {@link #readRegular}; private, so a read always goes through the cap. */
  private Optional<OpenFile> openRegular(Path file, Kind refused, Kind unreadable) {
    BasicFileAttributes attributes;
    try {
      attributes = access.stat(file, false);
    } catch (IOException failure) {
      if (isAbsent(failure)) {
        return Optional.empty();
      }
      throw new SourceFault(unreadable);
    }
    if (attributes.isSymbolicLink() || !attributes.isRegularFile()) {
      throw new SourceFault(refused);
    }
    try {
      return Optional.of(new OpenFile(access.openRead(file), attributes.size()));
    } catch (IOException failure) {
      if (isAbsent(failure)) {
        return Optional.empty();
      }
      // A link swapped in between the attribute check and the open fails the NOFOLLOW open; say which row it is.
      throw new SourceFault(isLink(file) ? refused : unreadable);
    }
  }

  private boolean isLink(Path file) {
    try {
      return access.stat(file, false).isSymbolicLink();
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
    if (attributes.isSymbolicLink()) {
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
