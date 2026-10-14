package org.speckitty.missionstatus.testsupport;

import java.io.IOException;
import java.io.UncheckedIOException;
import java.nio.charset.StandardCharsets;
import java.nio.file.Files;
import java.nio.file.Path;
import org.junit.platform.engine.TestExecutionResult;
import org.junit.platform.engine.support.descriptor.MethodSource;
import org.junit.platform.launcher.TestExecutionListener;
import org.junit.platform.launcher.TestIdentifier;
import org.speckitty.missionstatus.testsupport.RealPermissionFixture.NotRun;

/**
 * Makes every skipped test visible in {@code build/reports/not-run.txt} (WP17, PR B obligation 21). A JUnit skip is green in
 * {@code check}, and a test whose precondition is unmet (symbolic links cannot be made, the host is not UTF-8, the runner is root) used
 * to appear there only when the test itself wrote a line first. This listener is registered by {@code ServiceLoader}
 * ({@code META-INF/services/org.junit.platform.launcher.TestExecutionListener}) and writes one line for every test the platform reports as
 * aborted (an assumption failed, {@code Assumptions.abort} included) or skipped, so a skip with no line of its own cannot be silent.
 *
 * <p>A line is {@code not run: precondition unmet: <class>#<method>}, the shape the explicit writers use, and a line the file already
 * holds is not written again, so a test that records its own line is not listed twice.
 */
public final class NotRunListener implements TestExecutionListener {

  private final Path report;

  /** The listener the platform instantiates: it writes to the default report of the build. */
  public NotRunListener() {
    this(NotRun.DEFAULT_FILE);
  }

  NotRunListener(Path report) {
    this.report = report;
  }

  @Override
  public void executionSkipped(TestIdentifier test, String reason) {
    if (test.isTest()) {
      record(line(test));
    }
  }

  @Override
  public void executionFinished(TestIdentifier test, TestExecutionResult result) {
    if (test.isTest() && result.getStatus() == TestExecutionResult.Status.ABORTED) {
      record(line(test));
    }
  }

  /** The line for a test: its class and method when the platform knows them, else its unique id. */
  static String line(TestIdentifier test) {
    String id =
        test.getSource()
            .filter(MethodSource.class::isInstance)
            .map(source -> (MethodSource) source)
            .map(source -> source.getClassName() + "#" + source.getMethodName())
            .orElse(test.getUniqueId());
    // an invocation of a parameterized or repeated test shares its method: the display name tells the invocations apart
    boolean invocation = test.getUniqueId().contains("[test-template-invocation:") || test.getUniqueId().contains("[dynamic-test:");
    return NotRun.unmet(invocation ? id + " [" + test.getDisplayName() + "]" : id);
  }

  private synchronized void record(String line) {
    try {
      if (Files.isRegularFile(report) && Files.readAllLines(report, StandardCharsets.UTF_8).contains(line)) {
        return;
      }
    } catch (IOException unreadable) {
      throw new UncheckedIOException(unreadable);
    }
    NotRun.record(report, line);
  }
}
