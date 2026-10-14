package org.speckitty.missionstatus.testsupport;

import org.speckitty.missionstatus.testsupport.RealPermissionFixture.NotRun;
import java.nio.file.Path;
import org.junit.jupiter.api.Assumptions;
import org.speckitty.missionstatus.adapter.out.filesystem.NameEncoding;

/**
 * The locale precondition of every test that creates a non-ASCII file name (D-128). On a host whose {@code sun.jnu.encoding} is not
 * UTF-8 such a name cannot be created or read back faithfully, so the test must not run; it must not pass either. {@link #assumeUtf8}
 * writes {@code not run: precondition unmet: <test id>} to the not-run report and skips by a JUnit assumption. The cases that inject
 * the {@link NameEncoding} stub (AC-6.6 stub leg, AC-4.8 stub twin) never call it: they run under any locale.
 */
public final class Utf8Host {

  private Utf8Host() {}

  /** Whether the running host decodes file names as UTF-8 (a Windows host does, whatever the property says). */
  public static boolean isUtf8() {
    return isUtf8(NameEncoding.host());
  }

  public static boolean isUtf8(NameEncoding encoding) {
    return encoding.trustworthy();
  }

  /** Skips the calling test unless the host is UTF-8; the test id is the caller's unique id (the test class and method, or a fixed label). */
  public static void assumeUtf8(String testId) {
    assumeUtf8(testId, NameEncoding.host(), NotRun.DEFAULT_FILE);
  }

  static void assumeUtf8(String testId, NameEncoding encoding, Path report) {
    if (!isUtf8(encoding)) {
      NotRun.record(report, NotRun.unmet(testId));
    }
    Assumptions.assumeTrue(isUtf8(encoding), NotRun.unmet(testId));
  }
}
