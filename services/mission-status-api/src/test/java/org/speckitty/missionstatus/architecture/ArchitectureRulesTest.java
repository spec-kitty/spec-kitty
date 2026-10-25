package org.speckitty.missionstatus.architecture;

import static org.assertj.core.api.Assertions.assertThat;

import com.tngtech.archunit.core.domain.JavaClasses;
import com.tngtech.archunit.lang.EvaluationResult;
import java.util.List;
import java.util.concurrent.atomic.AtomicInteger;
import java.util.stream.IntStream;
import java.util.stream.Stream;
import org.junit.jupiter.api.AfterAll;
import org.junit.jupiter.api.DynamicTest;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.TestFactory;
import org.speckitty.missionstatus.architecture.ArchitectureRules.Rule;
import org.speckitty.missionstatus.architecture.ArchitectureRules.Scope;

/**
 * The fourteen architecture rules of FR-012 over the real classes. Production rules import main classes only
 * ({@code DoNotIncludeTests}, generated classes included); rule 11 imports test classes. Non-vacuity has three parts (AC-12b): every
 * rule scans more than zero classes, every rule has a positive control ({@link ArchitectureControlsTest}), and the rule-count guard
 * below fails when the number of rules run differs from the number defined.
 */
class ArchitectureRulesTest {

  private static final JavaClasses MAIN = ArchitectureRules.mainClasses();
  private static final JavaClasses TESTS = ArchitectureRules.testClasses();

  private static final AtomicInteger RULES_RUN = new AtomicInteger();

  private static JavaClasses classesFor(Rule rule) {
    return rule.scope() == Scope.MAIN ? MAIN : TESTS;
  }

  @TestFactory
  Stream<DynamicTest> everyRuleHoldsOverTheRealClasses() {
    return ArchitectureRules.production().stream()
        .map(
            rule ->
                DynamicTest.dynamicTest(
                    "rule %02d: %s".formatted(rule.id(), rule.name()),
                    () -> {
                      RULES_RUN.incrementAndGet();
                      JavaClasses classes = classesFor(rule);
                      long scanned = rule.scanned(classes);
                      System.out.println("[architecture] rule %02d scans %d classes".formatted(rule.id(), scanned));
                      assertThat(scanned).as("classes rule %d scans (AC-12b non-vacuity)", rule.id()).isGreaterThan(0);

                      EvaluationResult result = rule.rule().evaluate(classes);
                      assertThat(result.hasViolation()).as("rule %d violations:%n%s", rule.id(), result.getFailureReport()).isFalse();
                    }));
  }

  @Test
  void theMainImportHoldsNoTestClassAndTheTestImportOnlyTestClasses() {
    assertThat(MAIN.contain("org.speckitty.missionstatus.testsupport.FixtureFactory")).as("main import holds a test class").isFalse();
    assertThat(MAIN.contain("org.speckitty.missionstatus.architecture.ArchitectureRulesTest")).as("main import holds a test class").isFalse();
    assertThat(MAIN.contain("org.speckitty.missionstatus.application.query.MissionStatusQueryService")).as("main import holds main code").isTrue();
    assertThat(TESTS.contain("org.speckitty.missionstatus.testsupport.FixtureFactory")).as("test import holds test classes").isTrue();
    assertThat(TESTS.contain("org.speckitty.missionstatus.application.query.MissionStatusQueryService")).as("test import holds no main class").isFalse();
  }

  /**
   * The domain-model and event-log libraries (#6192) reach the production import through the classpath, so rules 1, 4, 7 and 12 keep
   * covering the classes moved out of this module. An import option that dropped library jars would make those rules vacuous for them.
   */
  @Test
  void theMainImportHoldsTheExtractedLibraryClasses() {
    assertThat(MAIN.contain("org.speckitty.missionstatus.domain.model.Lane")).as("a domain-model class in the main import").isTrue();
    assertThat(MAIN.contain("org.speckitty.missionstatus.adapter.out.filesystem.codec.LedgerLineDecoder")).as("an event-log class in the main import").isTrue();
    assertThat(MAIN.contain("org.speckitty.missionstatus.domain.readmodel.reducer.StatusReducer")).as("an event-log class in the main import").isTrue();
  }

  @Test
  void theRuleSetDefinesTheFourteenRulesOfThePlanTableWithContiguousIds() {
    List<Rule> rules = ArchitectureRules.production();

    assertThat(rules).hasSize(ArchitectureRules.DEFINED_RULE_COUNT);
    assertThat(rules).extracting(Rule::id).containsExactlyElementsOf(IntStream.rangeClosed(1, ArchitectureRules.DEFINED_RULE_COUNT).boxed().toList());
  }

  /** The rule-count guard: the number of rules RUN equals the number defined. It fails when a rule is deleted from the set. */
  @AfterAll
  static void ruleCountGuard() {
    assertThat(RULES_RUN.get()).as("rules run by everyRuleHoldsOverTheRealClasses").isEqualTo(ArchitectureRules.DEFINED_RULE_COUNT);
  }
}
