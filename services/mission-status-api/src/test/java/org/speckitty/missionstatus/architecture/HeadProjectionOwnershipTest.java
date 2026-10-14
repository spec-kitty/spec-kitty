package org.speckitty.missionstatus.architecture;

import static com.tngtech.archunit.core.domain.JavaClass.Predicates.resideInAPackage;
import static com.tngtech.archunit.lang.syntax.ArchRuleDefinition.noClasses;
import static org.assertj.core.api.Assertions.assertThat;

import com.tngtech.archunit.base.DescribedPredicate;
import com.tngtech.archunit.core.domain.JavaClass;
import com.tngtech.archunit.core.domain.JavaClasses;
import com.tngtech.archunit.core.domain.JavaMethodCall;
import com.tngtech.archunit.core.importer.ClassFileImporter;
import com.tngtech.archunit.lang.ArchRule;
import com.tngtech.archunit.lang.EvaluationResult;
import java.util.List;
import java.util.Set;
import java.util.stream.StreamSupport;
import org.junit.jupiter.api.Test;
import org.speckitty.missionstatus.architecture.fixture.application.query.HeadBypass;
import org.speckitty.missionstatus.architecture.fixture.application.query.Service;

/**
 * The head projection has one owner (operator ruling A3 item 4, D-123): of the classes of {@code application.query}, only
 * {@code OverviewReader} and {@code MissionHeadProjection} call {@code OverviewDeriver#derive} or a method of
 * {@code MissionHeadProjection}. Everything else gets a Mission head through {@code OverviewReader#head}, so the list and the detail
 * routes share one derivation, one projection and one cache by construction. The rule is parameterised by the package root so that the
 * planted {@link HeadBypass} turns the same predicate red.
 */
class HeadProjectionOwnershipTest {

  private static final String DERIVER = "org.speckitty.missionstatus.domain.readmodel.overview.OverviewDeriver";
  private static final Set<String> OWNERS = Set.of("OverviewReader", "MissionHeadProjection");
  private static final String FIXTURE_ROOT = "org.speckitty.missionstatus.architecture.fixture";

  /** The top-level simple name of a class: {@code OverviewReader$Nested} counts as {@code OverviewReader}. */
  private static String topLevelName(JavaClass c) {
    String name = c.getName().substring(c.getPackageName().length() + 1);
    int nested = name.indexOf('$');
    return nested < 0 ? name : name.substring(0, nested);
  }

  private static DescribedPredicate<JavaClass> notAnOwner() {
    return DescribedPredicate.describe("not OverviewReader or MissionHeadProjection", (JavaClass c) -> !OWNERS.contains(topLevelName(c)));
  }

  private static DescribedPredicate<JavaMethodCall> derivesAHead() {
    return DescribedPredicate.describe(
        "derives a head: OverviewDeriver#derive or any method of MissionHeadProjection",
        (JavaMethodCall call) ->
            (call.getTargetOwner().getName().equals(DERIVER) && call.getName().equals("derive"))
                || topLevelName(call.getTargetOwner()).equals("MissionHeadProjection"));
  }

  static ArchRule rule(String root) {
    return noClasses()
        .that(resideInAPackage(root + ".application.query..").and(notAnOwner()))
        .should()
        .callMethodWhere(derivesAHead())
        .as("only OverviewReader and MissionHeadProjection derive a Mission head")
        .allowEmptyShould(true);
  }

  private static long scanned(JavaClasses classes, String root) {
    return StreamSupport.stream(classes.spliterator(), false).filter(resideInAPackage(root + ".application.query..").and(notAnOwner())).count();
  }

  @Test
  void noClassOutsideTheTwoOwnersDerivesAHeadAndTheScanIsNotEmpty() {
    JavaClasses main = ArchitectureRules.mainClasses();

    long subject = scanned(main, ArchitectureRules.ROOT);

    assertThat(subject).as("classes the rule scans (non-vacuity)").isGreaterThanOrEqualTo(3);
    for (String known : List.of("MissionStatusQueryService", "MissionLookup", "MissionReadModel")) {
      assertThat(main.contain(ArchitectureRules.ROOT + ".application.query." + known)).as(known + " is in the scanned set").isTrue();
    }
    EvaluationResult result = rule(ArchitectureRules.ROOT).evaluate(main);
    assertThat(result.hasViolation()).as("violations:%n%s", result.getFailureReport()).isFalse();
  }

  @Test
  void theOwnersThemselvesDoCallTheDeriverSoTheRuleExemptsSomethingReal() {
    JavaClasses main = ArchitectureRules.mainClasses();
    ArchRule everyone = noClasses().that(resideInAPackage(ArchitectureRules.ROOT + ".application.query..")).should().callMethodWhere(derivesAHead()).allowEmptyShould(true);

    assertThat(everyone.evaluate(main).hasViolation()).as("without the exemption the owners are red").isTrue();
  }

  @Test
  void aPlantedBypassTurnsTheSamePredicateRedAndOnlyOnTheBypass() {
    JavaClasses planted = new ClassFileImporter().importClasses(Service.class, HeadBypass.class);

    EvaluationResult result = rule(FIXTURE_ROOT).evaluate(planted);

    assertThat(scanned(planted, FIXTURE_ROOT)).isEqualTo(2);
    assertThat(result.hasViolation()).isTrue();
    assertThat(result.getFailureReport().getDetails()).isNotEmpty().allSatisfy(detail -> assertThat(detail).contains("HeadBypass"));
  }

  @Test
  void theConformingSkeletonAloneIsGreen() {
    JavaClasses skeleton = new ClassFileImporter().importClasses(Service.class);

    assertThat(rule(FIXTURE_ROOT).evaluate(skeleton).hasViolation()).isFalse();
  }
}
