package org.speckitty.missionstatus.testsupport;

import static org.assertj.core.api.Assertions.assertThat;

import java.io.IOException;
import java.nio.charset.StandardCharsets;
import java.nio.file.Files;
import java.nio.file.Path;
import java.util.List;
import org.junit.jupiter.api.Test;
import org.opentest4j.TestAbortedException;
import org.junit.platform.engine.TestDescriptor;
import org.junit.platform.engine.TestExecutionResult;
import org.junit.platform.engine.UniqueId;
import org.junit.platform.engine.support.descriptor.AbstractTestDescriptor;
import org.junit.platform.engine.support.descriptor.MethodSource;
import org.junit.platform.launcher.TestIdentifier;
import org.speckitty.missionstatus.testsupport.RealPermissionFixture.NotRun;

/**
 * The skip report lists every aborted or skipped test (WP17, obligation 21). The descriptors are built by hand, as the platform builds
 * them, so the listener is driven the way a real run drives it; the build reads the file that this listener writes.
 */
class NotRunListenerTest {

  private static final String CLASS = "org.speckitty.missionstatus.adapter.in.http.detail.WorkPackageControllerRowsTest";

  private static TestIdentifier test(String method, String uniqueSegment) {
    UniqueId id = UniqueId.forEngine("junit-jupiter").append("class", CLASS).append(uniqueSegment, method + "()");
    TestDescriptor descriptor =
        new AbstractTestDescriptor(id, method + "()", MethodSource.from(CLASS, method)) {
          @Override
          public Type getType() {
            return Type.TEST;
          }
        };
    return TestIdentifier.from(descriptor);
  }

  private static List<String> lines(Path report) throws IOException {
    return Files.isRegularFile(report) ? Files.readAllLines(report, StandardCharsets.UTF_8) : List.of();
  }

  @Test
  void anAbortedTestIsListedWithItsClassAndMethodAndAFailedOrPassedTestIsNot() throws IOException {
    Path report = ScratchDirs.create().resolve("reports").resolve("not-run.txt");
    NotRunListener listener = new NotRunListener(report);

    // WorkPackageControllerRowsTest#symlink uses Assumptions.abort, which writes nothing of its own
    listener.executionFinished(test("aLinkedPromptIsRefused", "method"), TestExecutionResult.aborted(new TestAbortedException("symbolic links cannot be made here")));
    listener.executionFinished(test("passes", "method"), TestExecutionResult.successful());
    listener.executionFinished(test("fails", "method"), TestExecutionResult.failed(new AssertionError("red")));

    assertThat(lines(report)).containsExactly("not run: precondition unmet: " + CLASS + "#aLinkedPromptIsRefused");
  }

  @Test
  void aSkippedTestIsListedToo() throws IOException {
    Path report = ScratchDirs.create().resolve("reports").resolve("not-run.txt");

    new NotRunListener(report).executionSkipped(test("disabled", "method"), "disabled for a reason");

    assertThat(lines(report)).containsExactly("not run: precondition unmet: " + CLASS + "#disabled");
  }

  @Test
  void aTestThatAlreadyWroteItsOwnLineIsNotListedTwiceAndTwoInvocationsOfOneMethodAreTwoLines() throws IOException {
    Path report = ScratchDirs.create().resolve("reports").resolve("not-run.txt");
    NotRunListener listener = new NotRunListener(report);
    NotRun.record(report, NotRun.unmet(CLASS + "#ownLine"));

    listener.executionFinished(test("ownLine", "method"), TestExecutionResult.aborted(new TestAbortedException("x")));
    listener.executionFinished(test("ownLine", "method"), TestExecutionResult.aborted(new TestAbortedException("x")));
    listener.executionFinished(test("twice", "test-template-invocation"), TestExecutionResult.aborted(null));

    assertThat(lines(report)).containsExactly("not run: precondition unmet: " + CLASS + "#ownLine", "not run: precondition unmet: " + CLASS + "#twice [twice()]");
  }

  @Test
  void aContainerIsNeverListed() throws IOException {
    Path report = ScratchDirs.create().resolve("reports").resolve("not-run.txt");
    TestDescriptor container =
        new AbstractTestDescriptor(UniqueId.forEngine("junit-jupiter").append("class", CLASS), "WorkPackageControllerRowsTest") {
          @Override
          public Type getType() {
            return Type.CONTAINER;
          }
        };

    new NotRunListener(report).executionSkipped(TestIdentifier.from(container), "container");

    assertThat(lines(report)).isEmpty();
  }

  @Test
  void theListenerIsRegisteredForEveryTestRunOfTheModule() throws IOException {
    Path services = Path.of("src", "test", "resources", "META-INF", "services", "org.junit.platform.launcher.TestExecutionListener");
    assertThat(Files.readAllLines(services, StandardCharsets.UTF_8)).contains(NotRunListener.class.getName());
  }
}
