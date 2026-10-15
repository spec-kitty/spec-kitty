package org.speckitty.missionstatus.testsupport;

import org.speckitty.missionstatus.testsupport.RealPermissionFixture.NotRun;
import java.io.IOException;
import java.io.UncheckedIOException;
import java.nio.charset.StandardCharsets;
import java.nio.file.Path;
import java.util.Map;
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

  /**
   * Skips the calling test unless a child JVM started with {@code environment} would see names it cannot trust (the child's own
   * {@code sun.jnu.encoding} is read, not guessed from the operating system). On macOS the property is always UTF-8 and on Windows the
   * JDK decodes names itself, so the locale variable changes nothing there and a test that expects the refusal must not run.
   */
  public static void assumeChildNamesUntrustworthy(String testId, Map<String, String> environment) {
    NameEncoding child = new NameEncoding(NameEncoding.host().windows(), childJnuEncoding(environment));
    assumeChildNamesUntrustworthy(testId, child, NotRun.DEFAULT_FILE);
  }

  static void assumeChildNamesUntrustworthy(String testId, NameEncoding child, Path report) {
    if (isUtf8(child)) {
      NotRun.record(report, NotRun.unmet(testId));
    }
    Assumptions.assumeFalse(isUtf8(child), NotRun.unmet(testId));
  }

  /** The {@code sun.jnu.encoding} a child JVM reports under {@code environment}, or null when it does not say. */
  static String childJnuEncoding(Map<String, String> environment) {
    try {
      ProcessBuilder builder = new ProcessBuilder(Path.of(System.getProperty("java.home"), "bin", "java").toString(), "-XshowSettings:properties", "-version").redirectErrorStream(true);
      builder.environment().putAll(environment);
      Process process = builder.start();
      String output = new String(process.getInputStream().readAllBytes(), StandardCharsets.ISO_8859_1);
      process.waitFor();
      return output.lines().map(String::strip).filter(line -> line.startsWith("sun.jnu.encoding =")).map(line -> line.substring(line.indexOf('=') + 1).strip()).findFirst().orElse(null);
    } catch (IOException failure) {
      throw new UncheckedIOException(failure);
    } catch (InterruptedException interrupted) {
      Thread.currentThread().interrupt();
      throw new IllegalStateException(interrupted);
    }
  }
}
