package org.speckitty.missionstatus.testsupport;

import java.nio.file.FileSystems;
import java.nio.file.Path;
import org.junit.jupiter.api.Assumptions;
import org.speckitty.missionstatus.testsupport.RealPermissionFixture.NotRun;

/**
 * The file-system precondition of every test that reads or sets POSIX permissions. A Windows host has no {@code posix} attribute view, so
 * such a test cannot run there; it must not pass either. {@link #assumePosix} writes {@code not run: precondition unmet: <test id>} to the
 * not-run report and skips by a JUnit assumption, the same way {@link Utf8Host} does.
 */
public final class PosixHost {

  private PosixHost() {}

  /** Whether the default file system offers the {@code posix} attribute view. */
  public static boolean hasPosixView() {
    return FileSystems.getDefault().supportedFileAttributeViews().contains("posix");
  }

  /** Skips the calling test unless the file system has a POSIX view; the test id is the caller's unique id (test class and method). */
  public static void assumePosix(String testId) {
    assumePosix(testId, hasPosixView(), NotRun.DEFAULT_FILE);
  }

  static void assumePosix(String testId, boolean hasView, Path report) {
    if (!hasView) {
      NotRun.record(report, NotRun.unmet(testId));
    }
    Assumptions.assumeTrue(hasView, NotRun.unmet(testId));
  }
}
