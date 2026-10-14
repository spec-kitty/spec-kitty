package org.speckitty.missionstatus.build;

import static org.assertj.core.api.Assertions.assertThat;

import java.io.IOException;
import java.io.UncheckedIOException;
import java.nio.charset.StandardCharsets;
import java.nio.file.Files;
import java.nio.file.Path;
import java.util.HashMap;
import java.util.List;
import java.util.Map;
import java.util.stream.Stream;
import org.gradle.testkit.runner.BuildResult;
import org.gradle.testkit.runner.GradleRunner;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.Timeout;
import org.junit.jupiter.api.io.TempDir;

/**
 * D-101, the skipped-test report hook: a JUnit skip is green in {@code check}, so a test whose precondition is unmet appends a line
 * {@code not run: precondition unmet: <test id>} to {@code build/reports/not-run.txt}, and the {@code test} task copies that file to
 * the job summary ({@code GITHUB_STEP_SUMMARY}) or, without one, to standard output. A nested build of a COPY of the service build
 * inputs holds one test that writes the line and then skips by assumption. With the hook the line surfaces both ways; the control copy
 * of the build script WITHOUT the hook (the region between the two marker comments removed) prints nothing and writes nothing: the
 * red-first leg, since a hook that does nothing would pass the positive legs only if the line surfaced some other way.
 */
class SkipReportNestedBuildTest {

  private static final String LINE = "not run: precondition unmet: SkipProbeTest.needsAPrecondition";
  private static final String HOOK_BEGIN = "// BEGIN not-run report hook";
  private static final String HOOK_END = "// END not-run report hook";

  private static final String PROBE_TEST =
      """
      package org.speckitty.missionstatus.probe;

      import java.nio.file.Files;
      import java.nio.file.Path;
      import java.nio.file.StandardOpenOption;
      import org.junit.jupiter.api.Assumptions;
      import org.junit.jupiter.api.Test;

      class SkipProbeTest {
        @Test
        void needsAPrecondition() throws Exception {
          Path report = Path.of("build", "reports", "not-run.txt");
          Files.createDirectories(report.getParent());
          Files.writeString(report, "%s\\n", java.nio.charset.StandardCharsets.UTF_8, StandardOpenOption.CREATE, StandardOpenOption.APPEND);
          Assumptions.assumeTrue(false, "precondition unmet");
        }
      }
      """
          .formatted(LINE);

  @Test
  @Timeout(900)
  void theHookPrintsTheSkippedLineAndAppendsItToTheJobSummary(@TempDir Path workDir) throws IOException {
    Path copy = workDir.resolve("with-hook");
    copyBuildInputs(Path.of(requiredProperty("kit.projectDir")), copy, false);

    BuildResult printed = runner(copy, Map.of()).build();
    assertThat(printed.getOutput()).as("standard output with no summary file").contains(LINE);

    Path summary = workDir.resolve("summary.md");
    Files.writeString(summary, "# existing summary\n", StandardCharsets.UTF_8);
    Path again = workDir.resolve("with-hook-summary");
    copyBuildInputs(Path.of(requiredProperty("kit.projectDir")), again, false);
    BuildResult summarised = runner(again, Map.of("GITHUB_STEP_SUMMARY", summary.toString())).build();
    String summaryText = Files.readString(summary, StandardCharsets.UTF_8);
    assertThat(summaryText).as("the job summary file").startsWith("# existing summary\n").contains(LINE);
    assertThat(summarised.getOutput()).as("with a summary file the line goes there, not to standard output").doesNotContain(LINE);
  }

  @Test
  @Timeout(900)
  void withoutTheHookTheSkippedLineSurfacesNowhere(@TempDir Path workDir) throws IOException {
    Path copy = workDir.resolve("without-hook");
    copyBuildInputs(Path.of(requiredProperty("kit.projectDir")), copy, true);
    Path summary = workDir.resolve("summary.md");
    Files.writeString(summary, "# existing summary\n", StandardCharsets.UTF_8);

    BuildResult result = runner(copy, Map.of("GITHUB_STEP_SUMMARY", summary.toString())).build();

    assertThat(Files.readString(copy.resolve("build/reports/not-run.txt"), StandardCharsets.UTF_8)).as("the probe test did run and wrote its line").contains(LINE);
    assertThat(result.getOutput()).doesNotContain(LINE);
    assertThat(Files.readString(summary, StandardCharsets.UTF_8)).isEqualTo("# existing summary\n");
  }

  @Test
  @Timeout(900)
  void theHookIsInTheBuildScriptBetweenItsMarkers() throws IOException {
    String script = Files.readString(Path.of(requiredProperty("kit.projectDir")).resolve("build.gradle.kts"), StandardCharsets.UTF_8);
    assertThat(script).contains(HOOK_BEGIN).contains(HOOK_END).contains("GITHUB_STEP_SUMMARY").contains("reports/not-run.txt");
    assertThat(script.indexOf(HOOK_BEGIN)).isLessThan(script.indexOf(HOOK_END));
  }

  private static GradleRunner runner(Path copy, Map<String, String> extraEnvironment) {
    Map<String, String> environment = new HashMap<>(System.getenv());
    environment.remove("GITHUB_STEP_SUMMARY");
    environment.putAll(extraEnvironment);
    return GradleRunner.create()
        .withProjectDir(copy.toFile())
        .withTestKitDir(Path.of(requiredProperty("kit.gradleUserHome")).toFile())
        .withEnvironment(environment)
        // bundleContract needs the pre-built contract document; the probe test reads no resource, so it is left out
        .withArguments(List.of("--offline", "-PcontractRoot=" + requiredProperty("kit.contractRoot"), "test", "-x", "bundleContract", "-x", "jacocoTestReport", "--tests", "*SkipProbeTest"));
  }

  /** The build inputs, a minimal main source set and the probe test (outside the `build` package, which the kit source set owns); optionally the build script with the hook region removed. */
  private static void copyBuildInputs(Path original, Path copy, boolean withoutHook) throws IOException {
    Files.createDirectories(copy);
    for (String name : List.of("settings.gradle.kts", "gradle.properties", "gradlew", "gradlew.bat")) {
      Files.copy(original.resolve(name), copy.resolve(name));
    }
    String script = Files.readString(original.resolve("build.gradle.kts"), StandardCharsets.UTF_8);
    if (withoutHook) {
      int begin = script.indexOf(HOOK_BEGIN);
      int end = script.indexOf(HOOK_END);
      assertThat(begin).as("hook begin marker").isGreaterThanOrEqualTo(0);
      assertThat(end).as("hook end marker").isGreaterThan(begin);
      String without = script.substring(0, begin) + script.substring(end + HOOK_END.length());
      assertThat(without).as("the control script has no hook").doesNotContain("GITHUB_STEP_SUMMARY");
      script = without;
    }
    Files.writeString(copy.resolve("build.gradle.kts"), script, StandardCharsets.UTF_8);
    copyTree(original.resolve("gradle"), copy.resolve("gradle"));
    Path main = copy.resolve("src/main/java/org/speckitty/missionstatus/Nested.java");
    Files.createDirectories(main.getParent());
    Files.writeString(main, "package org.speckitty.missionstatus;\n\nfinal class Nested {}\n", StandardCharsets.UTF_8);
    Path test = copy.resolve("src/test/java/org/speckitty/missionstatus/probe/SkipProbeTest.java");
    Files.createDirectories(test.getParent());
    Files.writeString(test, PROBE_TEST, StandardCharsets.UTF_8);
  }

  private static void copyTree(Path from, Path to) throws IOException {
    try (Stream<Path> paths = Files.walk(from)) {
      for (Path path : (Iterable<Path>) paths::iterator) {
        Path target = to.resolve(from.relativize(path).toString());
        if (Files.isDirectory(path)) {
          Files.createDirectories(target);
        } else {
          Files.copy(path, target);
        }
      }
    } catch (UncheckedIOException e) {
      throw e.getCause();
    }
  }

  private static String requiredProperty(String name) {
    String value = System.getProperty(name);
    assertThat(value).as("system property %s (set by the kitTest task)", name).isNotBlank();
    return value;
  }
}
