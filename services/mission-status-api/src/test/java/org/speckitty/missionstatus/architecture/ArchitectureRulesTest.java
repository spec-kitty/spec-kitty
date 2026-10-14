package org.speckitty.missionstatus.architecture;

import static org.assertj.core.api.Assertions.assertThat;

import com.tngtech.archunit.core.domain.JavaClass;
import com.tngtech.archunit.core.domain.JavaClasses;
import com.tngtech.archunit.lang.EvaluationResult;
import java.util.List;
import java.util.Map;
import java.util.TreeMap;
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
 * The sixteen architecture rules of FR-012 over the real classes. Production rules import main classes only
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

  @Test
  void theRuleSetDefinesEveryRuleOfThePlanTableWithContiguousIds() {
    List<Rule> rules = ArchitectureRules.production();

    assertThat(rules).hasSize(ArchitectureRules.DEFINED_RULE_COUNT);
    assertThat(rules).extracting(Rule::id).containsExactlyElementsOf(IntStream.rangeClosed(1, ArchitectureRules.DEFINED_RULE_COUNT).boxed().toList());
  }

  /**
   * Pins the discovered inbound adapters of the production import (not in the rule: the fixture root legitimately holds
   * {@code adapter.in.other}). The first MCP adapter must add its own entry and its own count here.
   */
  @Test
  void theDiscoveredInboundAdaptersAreExactlyHttpWithClasses() {
    Map<String, Long> bySegment = new TreeMap<>();
    for (JavaClass c : MAIN) {
      if (c.getPackageName().startsWith(ArchitectureRules.ROOT + ".adapter.in.")) {
        bySegment.merge(ArchitectureRules.adapterSegment(ArchitectureRules.ROOT, c), 1L, Long::sum);
      }
    }

    assertThat(bySegment.keySet()).containsExactly("http");
    assertThat(bySegment.get("http")).as("classes in adapter.in.http").isGreaterThan(0);
  }

  /** Rule 3b: the production floor is five annotated classes in adapter.in.. plus the allow-listed error controller, which must still exist. */
  @Test
  void ruleThreeBSeesTheFiveAnnotatedControllersAndTheAllowListedOneStillExists() {
    String allowListed = ArchitectureRules.controllerAllowList(ArchitectureRules.ROOT);
    long inAdapter =
        MAIN.stream().filter(ArchitectureRules.CONTROLLER_ANNOTATED).filter(c -> c.getPackageName().startsWith(ArchitectureRules.ROOT + ".adapter.in.")).count();

    assertThat(inAdapter).as("annotated controller classes in adapter.in..").isGreaterThanOrEqualTo(5);
    assertThat(MAIN.contain(allowListed)).as("stale allow-list entry: %s no longer exists", allowListed).isTrue();
    assertThat(MAIN.get(allowListed)).as("the allow-listed class is a controller").matches(ArchitectureRules.CONTROLLER_ANNOTATED);
  }

  /** Rule 13 must scan each of the two roots and the four subpackages, or one of them could be vacuously green. */
  @Test
  void ruleThirteenScansBothPortRootsAndAllFourSubpackages() {
    String port = ArchitectureRules.ROOT + ".application.query.port.";
    for (String sub : List.of("in", "out", "in.dto", "in.exceptions", "out.dto", "out.exceptions")) {
      long count = MAIN.stream().filter(c -> c.getPackageName().equals(port + sub)).count();
      assertThat(count).as("classes in application.query.port.%s", sub).isGreaterThan(0);
    }
  }

  /** Rule 15 must scan the shared HTTP pieces of the detail operations: with no controller yet, {@code RawQuery} and {@code IncludePrompt} are its subject. */
  @Test
  void ruleFifteenScansTheSharedDetailPieces() {
    String detail = ArchitectureRules.ROOT + ".adapter.in.http.detail.";

    assertThat(MAIN.contain(detail + "RawQuery")).isTrue();
    assertThat(MAIN.contain(detail + "IncludePrompt")).isTrue();
    assertThat(MAIN.stream().filter(c -> c.getPackageName().equals(detail.substring(0, detail.length() - 1))).count()).isGreaterThanOrEqualTo(2);
  }

  /** Rule 16 clause c reads the four detail interfaces: exactly those, besides the stream port, sit directly in port.in. */
  @Test
  void ruleSixteenReadsTheFourDetailInterfacesAndTheDetailRecords() {
    String port = ArchitectureRules.ROOT + ".application.query.port.in";
    List<String> interfaces =
        MAIN.stream().filter(c -> c.getPackageName().equals(port) && c.isInterface()).map(JavaClass::getSimpleName).sorted().toList();

    assertThat(interfaces).containsExactly("ArtifactQuery", "MissionDetailQuery", "MissionStatusQuery", "Subscription", "WorkPackageDetailQuery", "WorkPackageQuery");
    assertThat(MAIN.stream().filter(c -> c.getPackageName().equals(ArchitectureRules.ROOT + ".domain.readmodel.detail")).count()).isGreaterThanOrEqualTo(21);
  }

  /** Rule 14's target does not exist in production by design: the planted control, not production, shows the rule bites. */
  @Test
  void noApplicationCommandPackageExistsInProduction() {
    assertThat(MAIN.stream().filter(c -> c.getPackageName().startsWith(ArchitectureRules.ROOT + ".application.command"))).isEmpty();
  }

  /** The rule-count guard: the number of rules RUN equals the number defined. It fails when a rule is deleted from the set. */
  @AfterAll
  static void ruleCountGuard() {
    assertThat(RULES_RUN.get()).as("rules run by everyRuleHoldsOverTheRealClasses").isEqualTo(ArchitectureRules.DEFINED_RULE_COUNT);
  }
}
