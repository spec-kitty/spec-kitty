package org.speckitty.missionstatus.adapter.out.filesystem;

import java.io.IOException;
import java.nio.file.Path;
import java.nio.file.attribute.BasicFileAttributes;
import java.util.ArrayList;
import java.util.List;
import java.util.Optional;
import org.speckitty.missionstatus.application.query.port.out.exceptions.SourceFault;
import org.speckitty.missionstatus.application.query.port.out.exceptions.SourceFault.Kind;
import org.speckitty.missionstatus.domain.model.CodePoints;

/**
 * The Mission directories of {@code kitty-specs/}, sorted by the code and never by the order the file system gives them (NFR-005).
 * It mirrors the oracle's {@code enumerate_missions}: an entry is a Mission when {@code <entry>/meta.json} is a file (a link followed,
 * so a dangling link is not one), a directory without it is not a Mission and nothing says so, and the names sort by Unicode code
 * point as a Python {@code str} does.
 *
 * <p>Faults: an unlistable {@code kitty-specs/} is {@code DIR_UNREADABLE} (L11, the whole read is refused); a Mission directory that is
 * gone by the time it is read is {@code VANISHED} (L6); one that is a link or leaves the root is {@code PATH_REFUSED} (L9). A Mission
 * refused by link is still listed, so that the refusal is reported and the other Missions are still served.
 */
public final class Listing {

  static final String SPECS = "kitty-specs";
  static final String META = "meta.json";

  private final SafeFiles files;
  private final AllowlistAccess access;

  public Listing(SafeFiles files, AllowlistAccess access) {
    this.files = files;
    this.access = access;
  }

  /** The Mission directory names, in code point order. An absent {@code kitty-specs/} lists nothing. */
  public List<String> missionNames() {
    Path specs = files.root().resolve(SPECS);
    Optional<BasicFileAttributes> attributes = files.statFollow(specs);
    if (attributes.isEmpty() || !attributes.get().isDirectory()) {
      return List.of();
    }
    List<String> entries;
    try {
      entries = access.listNames(specs);
    } catch (IOException failure) {
      throw new SourceFault(Kind.DIR_UNREADABLE);
    }
    List<String> missions = new ArrayList<>();
    for (String entry : entries) {
      Optional<BasicFileAttributes> meta = files.statFollow(specs.resolve(entry).resolve(META));
      if (meta.isPresent() && meta.get().isRegularFile()) {
        missions.add(entry);
      }
    }
    missions.sort(CodePoints::compare);
    return List.copyOf(missions);
  }

  /** The Mission's own primary directory, checked to be one safe segment, to still be there, to be no link, and to be inside the root. */
  public Path ownDir(String name) {
    if (!SafeFiles.isSafeSegment(name)) {
      throw new SourceFault(Kind.PATH_REFUSED);
    }
    return files.requireContainedDir(files.root().resolve(SPECS).resolve(name));
  }
}
