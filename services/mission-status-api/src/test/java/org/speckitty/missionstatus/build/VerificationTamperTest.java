package org.speckitty.missionstatus.build;

import static org.assertj.core.api.Assertions.assertThat;

import java.io.IOException;
import java.io.UncheckedIOException;
import java.nio.charset.StandardCharsets;
import java.nio.file.Files;
import java.nio.file.Path;
import java.util.List;
import java.util.regex.Matcher;
import java.util.regex.Pattern;
import java.util.stream.Stream;
import org.gradle.testkit.runner.BuildResult;
import org.gradle.testkit.runner.GradleRunner;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.Timeout;
import org.junit.jupiter.api.io.TempDir;

/**
 * AC-14a, the standing tamper test: a nested build of a COPY of the build inputs resolves strictly against
 * gradle/verification-metadata.xml. The unmutated copy builds; the copy with one altered checksum fails with a dependency
 * verification error. Modelled on contracts/tools/tamper_check.py, written for the service tree. It runs offline against the real
 * Gradle user home (TestKit's own home is empty), so the outer build must have resolved the compile classpath first (kitTest
 * depends on compileJava). It never touches the original tree and never uses the network.
 */
class VerificationTamperTest {

  /** The library modules settings.gradle.kts includes (#6117 decision 12, #6192); a nested build needs each one's directory. */
  private static final List<String> LIBRARY_MODULES = List.of("domain-model", "event-log");

  private static final String VERIFICATION_FAILURE = "Dependency verification failed for configuration";
  private static final Pattern A_JAR_CHECKSUM =
      Pattern.compile("(<artifact name=\"jackson-annotations-[^\"]+\\.jar\">\\s*<sha256 value=\")([0-9a-f]{8})");

  @Test
  @Timeout(900)
  void anAlteredChecksumFailsTheNestedBuildWhileTheUnmutatedCopyBuilds(@TempDir Path workDir) throws IOException {
    Path original = Path.of(requiredProperty("kit.projectDir"));
    Path copy = workDir.resolve("copy");
    copyBuildInputs(original, copy);
    Path metadata = copy.resolve("gradle/verification-metadata.xml");
    String text = Files.readString(metadata, StandardCharsets.UTF_8);

    // (b) non-vacuity: zero checksums fails the test.
    assertThat(count(text, "<sha256 value=\"")).as("sha256 entries in the copy's verification metadata").isGreaterThan(100);

    // (c) positive control: the unmutated copy resolves offline and the nested build succeeds.
    BuildResult control = runner(copy).build();
    assertThat(control.getOutput()).as("control build output").doesNotContain(VERIFICATION_FAILURE);

    // (d) alter the leading eight hex characters of ONE checksum in the copy (a deadbeef prefix, as tamper_check.py does).
    Matcher matcher = A_JAR_CHECKSUM.matcher(text);
    assertThat(matcher.find()).as("a jackson-annotations jar checksum to alter").isTrue();
    String replacement = matcher.group(2).equals("deadbeef") ? "cafebabe" : "deadbeef";
    String tampered = text.substring(0, matcher.start(2)) + replacement + text.substring(matcher.end(2));
    assertThat(tampered).isNotEqualTo(text);
    Files.writeString(metadata, tampered, StandardCharsets.UTF_8);

    BuildResult failure = runner(copy).buildAndFail();
    assertThat(failure.getOutput()).contains(VERIFICATION_FAILURE);
  }

  private static GradleRunner runner(Path copy) {
    Path gradleUserHome = Path.of(requiredProperty("kit.gradleUserHome"));
    return GradleRunner.create()
        .withProjectDir(copy.toFile())
        .withTestKitDir(gradleUserHome.toFile())
        .withArguments(List.of("--offline", "-PcontractRoot=" + requiredProperty("kit.contractRoot"), "compileJava"));
  }

  /** The files a nested build needs (never the sources, never build output) plus a minimal main source set. */
  private static void copyBuildInputs(Path original, Path copy) throws IOException {
    Files.createDirectories(copy);
    for (String name : List.of("build.gradle.kts", "settings.gradle.kts", "gradle.properties", "gradlew", "gradlew.bat")) {
      Files.copy(original.resolve(name), copy.resolve(name));
    }
    copyTree(original.resolve("gradle"), copy.resolve("gradle"));
    // settings.gradle.kts includes the library modules (#6192): their build scripts, with no sources, keep the nested build whole.
    for (String library : LIBRARY_MODULES) {
      Files.createDirectories(copy.resolve(library));
      Files.copy(original.resolve(library).resolve("build.gradle.kts"), copy.resolve(library).resolve("build.gradle.kts"));
    }
    Path source = copy.resolve("src/main/java/org/speckitty/missionstatus/Nested.java");
    Files.createDirectories(source.getParent());
    Files.writeString(source, "package org.speckitty.missionstatus;\n\nfinal class Nested {}\n", StandardCharsets.UTF_8);
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

  private static int count(String text, String needle) {
    int count = 0;
    for (int at = text.indexOf(needle); at >= 0; at = text.indexOf(needle, at + needle.length())) {
      count++;
    }
    return count;
  }

  private static String requiredProperty(String name) {
    String value = System.getProperty(name);
    assertThat(value).as("system property %s (set by the kitTest task)", name).isNotBlank();
    return value;
  }
}
