package org.speckitty.missionstatus.adapter.out.filesystem;

import static com.tngtech.archunit.lang.syntax.ArchRuleDefinition.noClasses;
import static org.assertj.core.api.Assertions.assertThat;

import com.tngtech.archunit.base.DescribedPredicate;
import com.tngtech.archunit.core.domain.JavaClass;
import com.tngtech.archunit.core.domain.JavaClasses;
import com.tngtech.archunit.core.importer.ClassFileImporter;
import com.tngtech.archunit.lang.ArchRule;
import com.tngtech.archunit.lang.EvaluationResult;
import java.io.IOException;
import java.nio.file.Files;
import java.nio.file.Path;
import java.util.Set;
import org.junit.jupiter.api.Test;
import org.speckitty.missionstatus.architecture.ArchitectureRules;

/**
 * The recorder only sees reads that go through {@link AllowlistAccess}, so a direct {@code Files.readAllBytes} in the adapter would
 * pass the flow test (the reviewer's M21). This rule closes it: in the filesystem adapter's main code only the pass-through (and the
 * project-root check, a directory test) may touch {@code java.nio.file.Files}, {@code FileChannel} or a {@code java.io} file class;
 * everything else reads through the seam. It lives in the adapter's own test tree, beside what it guards.
 */
class FilesystemMissionEventSourceFileApiTest {

  private static final String PACKAGE = ArchitectureRules.ROOT + ".adapter.out.filesystem..";

  private static final Set<String> RAW_FILE_CLASSES =
      Set.of(
          Files.class.getName(),
          "java.nio.channels.FileChannel",
          "java.io.File",
          "java.io.FileInputStream",
          "java.io.FileOutputStream",
          "java.io.FileReader",
          "java.io.FileWriter",
          "java.io.RandomAccessFile");

  private static final DescribedPredicate<JavaClass> RAW_FILE_API = DescribedPredicate.describe("a raw file API (Files, FileChannel, java.io file classes)", c -> RAW_FILE_CLASSES.contains(c.getName()));

  private static final DescribedPredicate<JavaClass> MAY_USE_RAW_FILE_API =
      DescribedPredicate.describe("AllowlistPassThrough or ProjectRootCheck", c -> c.getName().matches(".*\\.(AllowlistPassThrough|ProjectRootCheck)(\\$.*)?"));

  static ArchRule rule() {
    return noClasses()
        .that()
        .resideInAPackage(PACKAGE)
        .and(DescribedPredicate.not(MAY_USE_RAW_FILE_API))
        .should()
        .dependOnClassesThat(RAW_FILE_API)
        .as("F6: in adapter.out.filesystem only AllowlistPassThrough and ProjectRootCheck use Files, FileChannel or java.io file classes; the rest reads through AllowlistAccess");
  }

  /** A class that bypasses the seam, the shape of M21. Test code, so the production import below never sees it. */
  static final class PlantedBypass {
    byte[] bypass(Path file) throws IOException {
      return Files.readAllBytes(file);
    }
  }

  @Test
  void onlyThePassThroughAndTheRootCheckTouchTheRawFileApis() {
    JavaClasses production = ArchitectureRules.mainClasses();
    assertThat(production.stream().filter(c -> c.getPackageName().startsWith(ArchitectureRules.ROOT + ".adapter.out.filesystem")).count()).as("the rule sees the adapter").isGreaterThan(10);
    rule().check(production);
  }

  @Test
  void thePassThroughReallyUsesThemSoTheAllowanceIsNotVacuous() {
    JavaClasses production = ArchitectureRules.mainClasses();
    assertThat(production.get(AllowlistPassThrough.class).getDirectDependenciesFromSelf()).anyMatch(d -> RAW_FILE_CLASSES.contains(d.getTargetClass().getName()));
  }

  @Test
  void aPlantedDirectReadIsCaught() {
    EvaluationResult result = rule().evaluate(new ClassFileImporter().importClasses(PlantedBypass.class));
    assertThat(result.hasViolation()).as("positive control: Files.readAllBytes outside the pass-through").isTrue();
  }
}
