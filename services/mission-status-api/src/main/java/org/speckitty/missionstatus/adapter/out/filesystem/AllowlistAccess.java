package org.speckitty.missionstatus.adapter.out.filesystem;

import java.io.IOException;
import java.nio.channels.SeekableByteChannel;
import java.nio.file.Path;
import java.nio.file.attribute.BasicFileAttributes;
import java.util.List;
import org.speckitty.missionstatus.application.query.port.out.dto.ReadScope;

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

  /** At most {@code limit} names of a directory, and whether more existed. */
  record NameWindow(List<String> names, boolean limitReached) {
    public NameWindow {
      names = List.copyOf(names);
    }
  }

  /**
   * A view of this seam for one read scope. The production seam does not classify, so it is its own scoped view; the recorder returns a
   * view that tags every access with the scope. A {@code default} method, so a test double that does not care still compiles.
   */
  default AllowlistAccess scoped(ReadScope scope) {
    return this;
  }

  /**
   * At most {@code limit} names of a directory (D-92). This default is a bounded view over the unbounded {@link #listNames(Path)}; the
   * production seam and the recorder override it so that no more than {@code limit + 1} names are ever pulled.
   */
  default NameWindow listNames(Path dir, int limit) throws IOException {
    List<String> all = listNames(dir);
    return all.size() > limit ? new NameWindow(all.subList(0, limit), true) : new NameWindow(all, false);
  }

  /** The production implementation. */
  static AllowlistAccess passThrough() {
    return AllowlistPassThrough.INSTANCE;
  }
}
