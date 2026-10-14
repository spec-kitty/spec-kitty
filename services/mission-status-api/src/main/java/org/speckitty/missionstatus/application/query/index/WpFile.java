package org.speckitty.missionstatus.application.query.index;

import java.util.Objects;
import org.speckitty.missionstatus.application.query.port.out.dto.FileRef;
import org.speckitty.missionstatus.application.query.port.out.dto.MissionRef;
import org.speckitty.missionstatus.application.query.port.out.dto.RelativePath;

/**
 * One candidate Work Package file: its name inside {@code tasks/} of the Mission's primary directory. It is a handle and nothing more: the
 * bytes of the file are read, decoded and dropped inside {@link WorkPackageIndex#build}, so no buffer outlives the loop that reads it.
 */
record WpFile(String name) {

  static final String TASKS = "tasks";

  WpFile {
    Objects.requireNonNull(name, "name");
  }

  /** The path as the artifact-path rule judges it: {@code tasks/<name>}. */
  String artifactPath() {
    return TASKS + "/" + name;
  }

  /** The reference the text-read port is called with; the name must already be a valid path segment. */
  FileRef in(MissionRef mission) {
    return new FileRef.MissionFile(mission, new RelativePath(java.util.List.of(TASKS, name)));
  }
}
