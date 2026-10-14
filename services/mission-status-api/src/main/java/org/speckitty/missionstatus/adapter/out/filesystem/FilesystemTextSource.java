package org.speckitty.missionstatus.adapter.out.filesystem;

import java.io.IOException;
import java.nio.file.InvalidPathException;
import java.nio.file.Path;
import java.nio.file.attribute.BasicFileAttributes;
import java.util.EnumMap;
import java.util.List;
import java.util.Map;
import java.util.Objects;
import java.util.Optional;
import org.speckitty.missionstatus.adapter.out.filesystem.codec.StrictUtf8;
import org.speckitty.missionstatus.application.query.port.out.TextSource;
import org.speckitty.missionstatus.application.query.port.out.dto.BytesRead;
import org.speckitty.missionstatus.application.query.port.out.dto.DirListing;
import org.speckitty.missionstatus.application.query.port.out.dto.EntryStat;
import org.speckitty.missionstatus.application.query.port.out.dto.EntryStat.EntryKind;
import org.speckitty.missionstatus.application.query.port.out.dto.FileRef;
import org.speckitty.missionstatus.application.query.port.out.dto.ReadScope;
import org.speckitty.missionstatus.application.query.port.out.dto.TextRead;
import org.speckitty.missionstatus.application.query.port.out.exceptions.SourceFault;
import org.speckitty.missionstatus.application.query.port.out.exceptions.TextFault;

/**
 * The file-system implementation of the text-read port, and the only one (plan 7.1 row 1). It is built from a plain {@link Path}: it
 * needs no Spring, so mission #5533's documentation build can use it too (operator ruling, 2026-10-13). The configuration class that
 * exposes it as a bean is the only place that knows about the container.
 *
 * <p>Every operation goes through {@link SafeFiles} over a scoped view of the {@link AllowlistAccess} seam, so the read fence sees each
 * access with the scope of the call. Every component below the base ({@code kitty-specs/<mission>/} or the project root) is
 * {@code lstat}-ed: a link in any component is refused ({@code PATH_REFUSED}) and its target is never opened, and a missing or
 * non-directory component is "nothing there". The Mission directory itself is checked once, under the AUTHORED scope (that is a lookup,
 * not a read of an artifact): it must be a real directory, not a link, and inside the real project root. A {@code SourceFault} from
 * {@code SafeFiles} is translated into a {@link TextFault} in one place, {@link #translate}.
 */
public final class FilesystemTextSource implements TextSource {

  private static final String SPECS = "kitty-specs";

  /** The two things a scope needs: the checked file operations and the raw seam for the bounded listing. */
  private record View(SafeFiles files, AllowlistAccess access) {}

  private final Path root;
  private final NameEncoding nameEncoding;
  private final Map<ReadScope, View> views = new EnumMap<>(ReadScope.class);

  /** The production wiring: the pass-through seam and the host's file-name probe. */
  public FilesystemTextSource(Path root) {
    this(root, AllowlistAccess.passThrough(), NameEncoding.host());
  }

  /** The production wiring from the configured project root as text, so that the wiring needs no path type (rule 7). */
  public static FilesystemTextSource forRoot(String root) {
    return new FilesystemTextSource(Path.of(root));
  }

  /** For tests and for a caller that wraps the seam (a recorder) or stubs the host probe. */
  public FilesystemTextSource(Path root, AllowlistAccess access, NameEncoding nameEncoding) {
    this.root = Objects.requireNonNull(root, "root");
    this.nameEncoding = Objects.requireNonNull(nameEncoding, "nameEncoding");
    Objects.requireNonNull(access, "access");
    for (ReadScope scope : ReadScope.values()) {
      AllowlistAccess scoped = access.scoped(scope);
      views.put(scope, new View(new SafeFiles(root, scoped), scoped));
    }
  }

  // ---- the port --------------------------------------------------------------------------------------------------------------

  @Override
  public DirListing list(FileRef dir, int nameLimit, ReadScope scope) {
    try {
      View view = views.get(scope);
      Path base = base(dir);
      List<String> segments = dir.path().segments();
      if (!ancestorsAreDirectories(view.files(), base, segments)) {
        return new DirListing.Absent();
      }
      Path target = resolve(base, segments);
      Optional<BasicFileAttributes> attributes = view.files().statNoFollow(target);
      if (attributes.isEmpty()) {
        return new DirListing.Absent();
      }
      if (SafeFiles.isLinkLike(attributes.get())) {
        throw new SourceFault(SourceFault.Kind.PATH_REFUSED);
      }
      if (!attributes.get().isDirectory()) {
        return new DirListing.NotADirectory();
      }
      try {
        AllowlistAccess.NameWindow window = view.access().listNames(target, nameLimit);
        return new DirListing.Names(window.names(), window.limitReached(), nameEncoding.trustworthy());
      } catch (IOException failure) {
        if (SafeFiles.isAbsent(failure)) {
          return new DirListing.Absent();
        }
        throw new SourceFault(SourceFault.Kind.DIR_UNREADABLE);
      }
    } catch (SourceFault fault) {
      throw translate(fault, false);
    }
  }

  @Override
  public EntryStat stat(FileRef path, ReadScope scope) {
    try {
      View view = views.get(scope);
      Path base = base(path);
      List<String> segments = path.path().segments();
      if (!ancestorsAreDirectories(view.files(), base, segments)) {
        return new EntryStat.Absent();
      }
      return view.files().statNoFollow(resolve(base, segments)).<EntryStat>map(FilesystemTextSource::present).orElseGet(EntryStat.Absent::new);
    } catch (SourceFault fault) {
      throw translate(fault, false);
    }
  }

  @Override
  public BytesRead readBytes(FileRef file, int cap, ReadScope scope) {
    SafeFiles.Capped read = capped(file, cap, scope);
    return switch (read) {
      case SafeFiles.Capped.Bytes bytes -> new BytesRead.Bytes(bytes.content());
      case SafeFiles.Capped.Absent absent -> new BytesRead.Absent();
      case SafeFiles.Capped.NotRegular notRegular -> new BytesRead.NotRegular();
      case SafeFiles.Capped.OverCap overCap -> new BytesRead.OverCap();
    };
  }

  @Override
  public TextRead readText(FileRef file, int cap, ReadScope scope) {
    SafeFiles.Capped read = capped(file, cap, scope);
    return switch (read) {
      case SafeFiles.Capped.Bytes bytes -> decoded(bytes.content());
      case SafeFiles.Capped.Absent absent -> new TextRead.Absent();
      case SafeFiles.Capped.NotRegular notRegular -> new TextRead.NotRegular();
      case SafeFiles.Capped.OverCap overCap -> new TextRead.OverCap();
    };
  }

  // ---- the shared steps ------------------------------------------------------------------------------------------------------

  private static TextRead decoded(byte[] content) {
    return switch (StrictUtf8.decode(content)) {
      case StrictUtf8.Decoded.Text text -> new TextRead.Text(text.text(), content.length);
      case StrictUtf8.Decoded.Rejected rejected -> new TextRead.NotText();
    };
  }

  private SafeFiles.Capped capped(FileRef file, int cap, ReadScope scope) {
    try {
      SafeFiles files = views.get(scope).files();
      Path base = base(file);
      List<String> segments = file.path().segments();
      if (!ancestorsAreDirectories(files, base, segments)) {
        return new SafeFiles.Capped.Absent();
      }
      return files.readCapped(resolve(base, segments), cap);
    } catch (SourceFault fault) {
      throw translate(fault, true);
    }
  }

  /** The directory the reference is relative to. A Mission's primary directory is checked here, under the AUTHORED scope. */
  private Path base(FileRef ref) {
    return switch (ref) {
      case FileRef.MissionFile mission -> {
        String name = mission.mission().name();
        if (!SafeFiles.isSafeSegment(name)) {
          throw new SourceFault(SourceFault.Kind.PATH_REFUSED);
        }
        yield views.get(ReadScope.AUTHORED).files().requireContainedDir(child(root.resolve(SPECS), name));
      }
      case FileRef.ProjectFile project -> root;
    };
  }

  /**
   * One segment appended. A name the platform cannot parse (a NUL, or on Windows a colon, a wildcard or a reserved shape) raises the
   * unchecked {@code InvalidPathException}; that is a refused path, not an internal error.
   */
  static Path child(Path parent, String segment) {
    try {
      return parent.resolve(segment);
    } catch (InvalidPathException unparseable) {
      throw new SourceFault(SourceFault.Kind.PATH_REFUSED);
    }
  }

  private static Path resolve(Path base, List<String> segments) {
    Path current = base;
    for (String segment : segments) {
      current = child(current, segment);
    }
    return current;
  }

  /**
   * Whether every component before the last is a real directory. A link is refused; a missing component, or one that is not a
   * directory, means there is nothing at the path.
   */
  private static boolean ancestorsAreDirectories(SafeFiles files, Path base, List<String> segments) {
    Path current = base;
    for (int i = 0; i < segments.size() - 1; i++) {
      current = child(current, segments.get(i));
      Optional<BasicFileAttributes> attributes = files.statNoFollow(current);
      if (attributes.isEmpty()) {
        return false;
      }
      if (SafeFiles.isLinkLike(attributes.get())) {
        throw new SourceFault(SourceFault.Kind.PATH_REFUSED);
      }
      if (!attributes.get().isDirectory()) {
        return false;
      }
    }
    return true;
  }

  private static EntryStat present(BasicFileAttributes attributes) {
    EntryKind kind =
        SafeFiles.isLinkLike(attributes)
            ? EntryKind.SYMLINK
            : attributes.isRegularFile() ? EntryKind.FILE : attributes.isDirectory() ? EntryKind.DIRECTORY : EntryKind.OTHER;
    return new EntryStat.Present(kind, attributes.size(), attributes.lastModifiedTime().toInstant().getEpochSecond());
  }

  /**
   * The one place a {@code SourceFault} of {@code SafeFiles} becomes a {@link TextFault} (D-68, D-91). {@code VANISHED} and
   * {@code PATH_REFUSED} keep their names; {@code DIR_UNREADABLE} stays so for a listing or a stat and becomes {@code FILE_UNREADABLE}
   * for a read; {@code META_UNPARSEABLE} and {@code LEDGER_UNREADABLE} cannot come from these calls and read as a failed read.
   */
  private static TextFault translate(SourceFault fault, boolean fileRead) {
    return new TextFault(
        switch (fault.kind()) {
          case VANISHED -> TextFault.Kind.VANISHED;
          case PATH_REFUSED -> TextFault.Kind.PATH_REFUSED;
          case DIR_UNREADABLE -> fileRead ? TextFault.Kind.FILE_UNREADABLE : TextFault.Kind.DIR_UNREADABLE;
          case META_UNPARSEABLE, LEDGER_UNREADABLE -> TextFault.Kind.FILE_UNREADABLE;
        });
  }
}
