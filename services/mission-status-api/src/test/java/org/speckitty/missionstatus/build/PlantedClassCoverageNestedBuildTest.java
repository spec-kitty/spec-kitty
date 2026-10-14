package org.speckitty.missionstatus.build;

import static org.assertj.core.api.Assertions.assertThat;

import java.io.IOException;
import java.io.UncheckedIOException;
import java.nio.charset.StandardCharsets;
import java.nio.file.Files;
import java.nio.file.Path;
import java.util.List;
import java.util.stream.Stream;
import org.gradle.testkit.runner.BuildResult;
import org.gradle.testkit.runner.GradleRunner;
import org.gradle.testkit.runner.TaskOutcome;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.Timeout;
import org.junit.jupiter.api.io.TempDir;

/**
 * AC-19.3, the planted untested class: the per-class JaCoCo floor must catch a class nobody tests. A nested build of a COPY of the
 * service build inputs, one small covered {@code domain} class with its test and one covered {@code application} class with its test,
 * passes {@code jacocoTestCoverageVerification}; the same copy with ONE planted untested class under {@code domain.*} (or under
 * {@code application.*}) fails it, naming the planted class. Modelled on {@link VerificationTamperTest}. If nothing were planted the
 * mutated leg would have no failure to find and the test would be red, so a verification rule that stopped applying cannot pass here.
 */
class PlantedClassCoverageNestedBuildTest {

  private static final String VERIFICATION = ":jacocoTestCoverageVerification";

  private static final String DOMAIN_COVERED =
      """
      package org.speckitty.missionstatus.domain.model;

      public final class Doubler {
        private Doubler() {}

        public static int twice(int value) {
          int doubled = value * 2;
          return doubled;
        }
      }
      """;

  private static final String APPLICATION_COVERED =
      """
      package org.speckitty.missionstatus.application.query;

      public final class Tripler {
        private Tripler() {}

        public static int thrice(int value) {
          int tripled = value * 3;
          return tripled;
        }
      }
      """;

  private static final String COVERING_TEST =
      """
      package org.speckitty.missionstatus.probe;

      import static org.junit.jupiter.api.Assertions.assertEquals;

      import org.junit.jupiter.api.Test;
      import org.speckitty.missionstatus.application.query.Tripler;
      import org.speckitty.missionstatus.domain.model.Doubler;

      class CoveringTest {
        @Test
        void callsTheCoveredClasses() {
          assertEquals(4, Doubler.twice(2));
          assertEquals(9, Tripler.thrice(3));
        }
      }
      """;

  private static final String PLANTED_TEMPLATE =
      """
      package %s;

      public final class Planted {
        private Planted() {}

        public static String describe(int value) {
          String first = "untested";
          String second = first + value;
          String third = second + "!";
          return third;
        }
      }
      """;

  @Test
  @Timeout(900)
  void theUnmutatedCopyPassesTheCoverageVerificationNonVacuously(@TempDir Path workDir) throws IOException {
    Path copy = workDir.resolve("control");
    copyInputs(Path.of(requiredProperty("kit.projectDir")), copy, null);

    BuildResult control = runner(copy).build();

    assertThat(control.task(VERIFICATION)).as("the verification task ran").isNotNull();
    assertThat(control.task(VERIFICATION).getOutcome()).isEqualTo(TaskOutcome.SUCCESS);
    assertThat(control.getOutput()).doesNotContain("Rule violated");
  }

  @Test
  @Timeout(900)
  void anUntestedClassPlantedUnderDomainFailsTheVerification(@TempDir Path workDir) throws IOException {
    Path copy = workDir.resolve("planted-domain");
    copyInputs(Path.of(requiredProperty("kit.projectDir")), copy, "org.speckitty.missionstatus.domain.model");

    BuildResult failed = runner(copy).buildAndFail();

    assertThat(failed.task(VERIFICATION)).isNotNull();
    assertThat(failed.task(VERIFICATION).getOutcome()).isEqualTo(TaskOutcome.FAILED);
    assertThat(failed.getOutput()).contains("Rule violated for class org.speckitty.missionstatus.domain.model.Planted").contains("lines covered ratio is 0.00");
  }

  @Test
  @Timeout(900)
  void anUntestedClassPlantedUnderApplicationFailsTheVerification(@TempDir Path workDir) throws IOException {
    Path copy = workDir.resolve("planted-application");
    copyInputs(Path.of(requiredProperty("kit.projectDir")), copy, "org.speckitty.missionstatus.application.query");

    BuildResult failed = runner(copy).buildAndFail();

    assertThat(failed.task(VERIFICATION)).isNotNull();
    assertThat(failed.task(VERIFICATION).getOutcome()).isEqualTo(TaskOutcome.FAILED);
    assertThat(failed.getOutput()).contains("Rule violated for class org.speckitty.missionstatus.application.query.Planted").contains("lines covered ratio is 0.00");
  }

  private static GradleRunner runner(Path copy) {
    return GradleRunner.create()
        .withProjectDir(copy.toFile())
        .withTestKitDir(Path.of(requiredProperty("kit.gradleUserHome")).toFile())
        // bundleContract needs the pre-built contract document; nothing here reads a resource, so it is left out
        .withArguments(List.of("--offline", "-PcontractRoot=" + requiredProperty("kit.contractRoot"), "test", "jacocoTestCoverageVerification", "-x", "bundleContract"));
  }

  /** The build inputs, two covered classes with their test, and, when {@code plantedPackage} is given, one untested class in it. */
  private static void copyInputs(Path original, Path copy, String plantedPackage) throws IOException {
    Files.createDirectories(copy);
    for (String name : List.of("build.gradle.kts", "settings.gradle.kts", "gradle.properties", "gradlew", "gradlew.bat")) {
      Files.copy(original.resolve(name), copy.resolve(name));
    }
    copyTree(original.resolve("gradle"), copy.resolve("gradle"));
    write(copy.resolve("src/main/java/org/speckitty/missionstatus/domain/model/Doubler.java"), DOMAIN_COVERED);
    write(copy.resolve("src/main/java/org/speckitty/missionstatus/application/query/Tripler.java"), APPLICATION_COVERED);
    write(copy.resolve("src/test/java/org/speckitty/missionstatus/probe/CoveringTest.java"), COVERING_TEST);
    if (plantedPackage != null) {
      write(copy.resolve("src/main/java/" + plantedPackage.replace('.', '/') + "/Planted.java"), PLANTED_TEMPLATE.formatted(plantedPackage));
    }
  }

  private static void write(Path file, String text) throws IOException {
    Files.createDirectories(file.getParent());
    Files.writeString(file, text, StandardCharsets.UTF_8);
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
