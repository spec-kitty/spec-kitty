package org.speckitty.missionstatus.adapter.out.filesystem;

import java.nio.file.Files;
import java.nio.file.InvalidPathException;
import java.nio.file.Path;
import java.util.Optional;

/**
 * Validates the configured project root. The directory check is a file-API call, so it lives in the filesystem adapter and
 * {@code config} only calls it (ArchUnit rule 7 holds from the first work package on).
 */
public final class ProjectRootCheck {

  /** The configuration key naming the project root. */
  public static final String KEY = "mission-status.project-root";

  private ProjectRootCheck() {}

  /**
   * The reason the value is unusable, or empty when it names an existing directory. The messages name the key and never carry an
   * operating-system message.
   */
  public static Optional<String> refusal(String value) {
    if (value == null || value.isBlank()) {
      return Optional.of(KEY + ": project root unset (pass --" + KEY + "=<directory>)");
    }
    try {
      if (Files.isDirectory(Path.of(value))) {
        return Optional.empty();
      }
    } catch (InvalidPathException notAPath) {
      // falls through to the same refusal as any other value that is not a directory
    }
    return Optional.of(KEY + ": not a directory");
  }
}
