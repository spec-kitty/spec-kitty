package org.speckitty.missionstatus.adapter.out.filesystem;

import static org.junit.jupiter.api.Assumptions.assumeTrue;

import java.io.IOException;
import java.nio.file.Files;
import java.nio.file.Path;

/**
 * Creates a symbolic link at test time (never committed). When the runner cannot create one, the test says so in its output and is
 * reported as skipped with that reason, never skipped silently (AC-10d).
 */
final class SymlinkSupport {

  private SymlinkSupport() {}

  static void link(Path link, Path target) {
    try {
      Files.createDirectories(link.getParent());
      Files.createSymbolicLink(link, target);
    } catch (IOException | UnsupportedOperationException | SecurityException cannot) {
      String line = "NOT RUN ON THIS LEG: the runner cannot create a symbolic link (" + cannot.getClass().getSimpleName() + ")";
      System.out.println(line);
      assumeTrue(false, line);
    }
  }
}
