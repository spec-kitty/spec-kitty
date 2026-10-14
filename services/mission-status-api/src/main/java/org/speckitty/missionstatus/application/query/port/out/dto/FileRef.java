package org.speckitty.missionstatus.application.query.port.out.dto;

import java.util.Objects;

/** A file or directory the text-read port is asked about. */
public sealed interface FileRef {

  /** A path relative to the <em>primary</em> directory of one Mission ({@code kitty-specs/<name>/}). */
  record MissionFile(MissionRef mission, RelativePath path) implements FileRef {
    public MissionFile {
      Objects.requireNonNull(mission, "mission");
      Objects.requireNonNull(path, "path");
    }
  }

  /** A path relative to the project root. */
  record ProjectFile(RelativePath path) implements FileRef {
    public ProjectFile {
      Objects.requireNonNull(path, "path");
    }
  }

  /** The relative path inside the base the reference names. */
  RelativePath path();
}
