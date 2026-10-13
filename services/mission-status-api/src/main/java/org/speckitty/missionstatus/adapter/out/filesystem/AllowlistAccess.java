package org.speckitty.missionstatus.adapter.out.filesystem;

import java.io.IOException;
import java.nio.channels.SeekableByteChannel;
import java.nio.file.Path;
import java.nio.file.attribute.BasicFileAttributes;
import java.util.List;

/**
 * The seam every file operation of the filesystem adapter goes through. It offers reads, stats, real paths and name listings, and
 * nothing that changes the file system: there is no method to open for writing. Production wiring uses {@link #passThrough()}; a test
 * substitutes a recorder that notes {@code (path class, open mode)} before the operating system answers
 * ({@code RecordingAllowlistAccess}, in the test source set). It is a collaborator of the event source, not a named port.
 */
public interface AllowlistAccess {

  /** Opens for reading and never follows a final-component symbolic link. */
  SeekableByteChannel openRead(Path path) throws IOException;

  /** The attributes of {@code path}, following a final-component symbolic link only when asked to. */
  BasicFileAttributes stat(Path path, boolean followLinks) throws IOException;

  /** The real path of {@code path}: every link resolved. */
  Path realPath(Path path) throws IOException;

  /** The entry names of a directory, in the order the file system gives them (the caller sorts). */
  List<String> listNames(Path dir) throws IOException;

  /** The production implementation. */
  static AllowlistAccess passThrough() {
    return AllowlistPassThrough.INSTANCE;
  }
}
