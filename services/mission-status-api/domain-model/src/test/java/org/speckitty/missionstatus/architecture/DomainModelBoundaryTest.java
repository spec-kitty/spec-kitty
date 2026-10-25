package org.speckitty.missionstatus.architecture;

import static com.tngtech.archunit.core.domain.JavaClass.Predicates.resideInAnyPackage;
import static com.tngtech.archunit.core.domain.JavaClass.Predicates.resideOutsideOfPackage;
import static com.tngtech.archunit.lang.syntax.ArchRuleDefinition.classes;
import static org.assertj.core.api.Assertions.assertThat;

import com.tngtech.archunit.core.domain.JavaClasses;
import com.tngtech.archunit.core.importer.ClassFileImporter;
import com.tngtech.archunit.lang.ArchRule;
import com.tngtech.archunit.lang.EvaluationResult;
import java.nio.file.Path;
import java.util.Arrays;
import java.util.List;
import org.junit.jupiter.api.Test;
import org.speckitty.missionstatus.architecture.fixture.ConcurrencyUsingType;
import org.speckitty.missionstatus.architecture.fixture.ConformingType;
import org.speckitty.missionstatus.architecture.fixture.FileReadingType;

/**
 * The domain-model boundary (#6192): the module is framework-free and uses no file API. Its classes depend only on the module's own package
 * and on the JDK packages the query service's rule 1b allows the domain (java.lang, java.util but not java.util.concurrent, java.time,
 * java.math, java.security, java.nio.charset). The allowlist keeps out every framework, JSON library, java.io and java.nio.file (it is
 * the root rule's set, so APIs inside those packages, such as java.util.zip, are not singled out).
 *
 * <p>Non-vacuity: the rule imports exactly this module's production classes (the {@code module.mainClasses} property the build sets)
 * and every type in {@link #EXTRACTED_TYPES} must be among them; planted violations prove it fires.
 */
class DomainModelBoundaryTest {

  /** The 18 top-level types this module held when it was extracted (#6192); each must still be imported and checked. */
  static final List<String> EXTRACTED_TYPES =
      List.of(
          "Actor", "CodePoints", "Diagnostic", "DiagnosticCode", "Lane", "LedgerLine", "LifecycleEvent", "LineKind", "MalformedReason",
          "MissionId", "MissionMeta", "PyText", "StatusEvent", "StatusSnapshot", "SupportedSchemaRange", "TailClassification", "Topology",
          "WpState");

  static final String MODEL = "org.speckitty.missionstatus.domain.model..";

  static final ArchRule BOUNDARY =
      classes().should().onlyDependOnClassesThat(
              resideInAnyPackage(MODEL, "java.lang..", "java.util..", "java.time..", "java.math..", "java.security..", "java.nio.charset..")
                  .and(resideOutsideOfPackage("java.util.concurrent..")))
          .as("domain-model depends only on itself and java.lang, java.util (not concurrent), java.time, java.math, java.security,"
              + " java.nio.charset (so no framework, JSON library, java.io or java.nio.file)");

  static JavaClasses moduleClasses() {
    String path = System.getProperty("module.mainClasses");
    assertThat(path).as("the module.mainClasses system property (set by this module's build script)").isNotBlank();
    List<Path> roots = Arrays.stream(path.split(java.io.File.pathSeparator)).map(Path::of).toList();
    return new ClassFileImporter().importPaths(roots);
  }

  @Test
  void theModuleClassesHoldTheBoundary() {
    JavaClasses classes = moduleClasses();
    for (String type : EXTRACTED_TYPES) {
      assertThat(classes.contain("org.speckitty.missionstatus.domain.model." + type)).as("%s is imported and checked", type).isTrue();
    }

    EvaluationResult result = BOUNDARY.evaluate(classes);
    assertThat(result.hasViolation()).as("violations:%n%s", result.getFailureReport()).isFalse();
  }

  @Test
  void aFileApiDependencyBreaksTheBoundary() {
    assertThat(BOUNDARY.evaluate(new ClassFileImporter().importClasses(FileReadingType.class)).hasViolation()).isTrue();
  }

  @Test
  void aConcurrencyDependencyBreaksTheBoundary() {
    assertThat(BOUNDARY.evaluate(new ClassFileImporter().importClasses(ConcurrencyUsingType.class)).hasViolation()).isTrue();
  }

  @Test
  void aConformingTypeHoldsTheBoundary() {
    assertThat(BOUNDARY.evaluate(new ClassFileImporter().importClasses(ConformingType.class)).hasViolation()).isFalse();
  }
}
