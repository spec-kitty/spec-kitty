package org.speckitty.missionstatus.testsupport;

import java.io.IOException;
import java.io.UncheckedIOException;
import java.nio.charset.StandardCharsets;
import java.nio.file.Files;
import java.nio.file.Path;
import java.nio.file.StandardOpenOption;
import java.nio.file.attribute.PosixFileAttributeView;
import java.nio.file.attribute.PosixFilePermission;
import java.util.Set;
import org.junit.jupiter.api.Assumptions;

/**
 * A real file or directory whose read permission has been taken away, for the real-permission leg of a {@link PermissionCase} (D-32,
 * D-101). The case never depends on the user who runs the tests: {@link #refusedForThisUser} opens the path as the test user, and when
 * the operating system does not refuse (a root runner, a platform without POSIX permissions) it appends
 * {@code not run: precondition unmet: <test id>} to the not-run report, puts the permissions back and skips the test by a JUnit
 * assumption. A skip is never a pass. Closing the fixture restores the permissions, so the scratch tree can be deleted.
 */
public final class RealPermissionFixture implements AutoCloseable {

  /** The operating system's answer, as a seam: does it let this user open the path? The default tries to. */
  @FunctionalInterface
  interface OpenProbe {
    boolean opens(Path path);
  }

  private final Path path;
  private final Set<PosixFilePermission> original;

  private RealPermissionFixture(Path path, Set<PosixFilePermission> original) {
    this.path = path;
    this.original = original;
  }

  /** The path whose permissions were removed. */
  public Path path() {
    return path;
  }

  /**
   * Removes read permission from {@code path} and returns the fixture, or skips the calling test when this user can still open it.
   *
   * @param testId the unique id of the calling test (the calling test class and method, or a fixed label), written to the report on a skip
   */
  public static RealPermissionFixture refusedForThisUser(Path path, String testId) {
    return refusedForThisUser(path, testId, RealPermissionFixture::opensForReal, NotRun.DEFAULT_FILE);
  }

  static RealPermissionFixture refusedForThisUser(Path path, String testId, OpenProbe probe, Path report) {
    PosixFileAttributeView view = Files.getFileAttributeView(path, PosixFileAttributeView.class);
    if (view == null) {
      return unmet(testId, report);
    }
    Set<PosixFilePermission> original;
    try {
      original = view.readAttributes().permissions();
      view.setPermissions(Set.of());
    } catch (IOException failure) {
      return unmet(testId, report);
    }
    RealPermissionFixture fixture = new RealPermissionFixture(path, original);
    if (probe.opens(path)) {
      fixture.close();
      return unmet(testId, report);
    }
    return fixture;
  }

  private static RealPermissionFixture unmet(String testId, Path report) {
    NotRun.record(report, NotRun.unmet(testId));
    Assumptions.abort(NotRun.unmet(testId));
    throw new IllegalStateException("unreachable: the assumption aborts the test");
  }

  private static boolean opensForReal(Path path) {
    try {
      if (Files.isDirectory(path)) {
        Files.newDirectoryStream(path).close();
      } else {
        Files.newInputStream(path).close();
      }
      return true;
    } catch (IOException refused) {
      return false;
    }
  }

  /** Puts the original permissions back. */
  @Override
  public void close() {
    PosixFileAttributeView view = Files.getFileAttributeView(path, PosixFileAttributeView.class);
    if (view == null) {
      return;
    }
    try {
      view.setPermissions(original);
    } catch (IOException ignored) {
      // the file may already be gone; the scratch directory is removed by the shutdown hook
    }
  }

  /**
   * The one writer of the not-run report ({@code build/reports/not-run.txt}), shared by {@link Utf8Host}, {@link RealPermissionFixture}
   * and {@link ProvisionPlan}. A test that cannot meet its precondition appends one line here and skips by a JUnit assumption: a skip is
   * never a pass, and the report makes every skip visible (the skipped-test hook of the build copies the file to the job summary).
   */
  static final class NotRun {

    static final Path DEFAULT_FILE = Path.of("build", "reports", "not-run.txt");

    private NotRun() {}

    static String unmet(String testId) {
      return "not run: precondition unmet: " + testId;
    }

    /** Appends one line (creating the directory and the file when needed). */
    static synchronized void record(Path report, String line) {
      try {
        Path parent = report.toAbsolutePath().getParent();
        if (parent != null) {
          Files.createDirectories(parent);
        }
        Files.writeString(report, line + System.lineSeparator(), StandardCharsets.UTF_8, StandardOpenOption.CREATE, StandardOpenOption.APPEND);
      } catch (IOException failure) {
        throw new UncheckedIOException(failure);
      }
    }
  }
}
