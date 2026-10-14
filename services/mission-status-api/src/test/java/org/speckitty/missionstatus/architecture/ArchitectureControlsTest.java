package org.speckitty.missionstatus.architecture;

import static org.assertj.core.api.Assertions.assertThat;

import com.tngtech.archunit.core.domain.JavaClasses;
import com.tngtech.archunit.core.importer.ClassFileImporter;
import java.util.ArrayList;
import java.util.List;
import java.util.Set;
import java.util.TreeSet;
import java.util.stream.IntStream;
import java.util.stream.Stream;
import org.junit.jupiter.api.DynamicTest;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.TestFactory;
import org.speckitty.missionstatus.architecture.ArchitectureRules.Rule;
import org.speckitty.missionstatus.architecture.fixture.adapter.in.http.Controller;
import org.speckitty.missionstatus.architecture.fixture.adapter.in.http.H3aInternal;
import org.speckitty.missionstatus.architecture.fixture.adapter.in.http.H3bConfig;
import org.speckitty.missionstatus.architecture.fixture.adapter.in.http.H5UsesFs;
import org.speckitty.missionstatus.architecture.fixture.adapter.in.http.model.Dto;
import org.speckitty.missionstatus.architecture.fixture.adapter.out.filesystem.F4UsesHttp;
import org.speckitty.missionstatus.architecture.fixture.adapter.out.filesystem.FsSource;
import org.speckitty.missionstatus.architecture.fixture.adapter.out.filesystem.SafeFiles;
import org.speckitty.missionstatus.architecture.fixture.adapter.out.filesystem.codec.C12aSafeFiles;
import org.speckitty.missionstatus.architecture.fixture.adapter.out.filesystem.codec.C12bFiles;
import org.speckitty.missionstatus.architecture.fixture.adapter.out.filesystem.codec.Decoder;
import org.speckitty.missionstatus.architecture.fixture.application.A2aUsesAdapter;
import org.speckitty.missionstatus.architecture.fixture.application.A2bExecutors;
import org.speckitty.missionstatus.architecture.fixture.application.A6UsesConfig;
import org.speckitty.missionstatus.architecture.fixture.application.A8Jackson;
import org.speckitty.missionstatus.architecture.fixture.application.A9GeneratedModel;
import org.speckitty.missionstatus.architecture.fixture.application.query.P14UsesCommand;
import org.speckitty.missionstatus.architecture.fixture.application.query.Service;
import org.speckitty.missionstatus.architecture.fixture.application.query.port.in.P13aInClass;
import org.speckitty.missionstatus.architecture.fixture.application.query.port.in.Query;
import org.speckitty.missionstatus.architecture.fixture.application.query.port.out.P13bOutClass;
import org.speckitty.missionstatus.architecture.fixture.application.query.port.out.Source;
import org.speckitty.missionstatus.architecture.fixture.config.G10Process;
import org.speckitty.missionstatus.architecture.fixture.config.G11cUsesCodec;
import org.speckitty.missionstatus.architecture.fixture.config.G7Files;
import org.speckitty.missionstatus.architecture.fixture.config.Wiring;
import org.speckitty.missionstatus.architecture.fixture.conformance.golden.P11bGoldenImportsFs;
import org.speckitty.missionstatus.architecture.fixture.conformance.port.P11AdapterImport;
import org.speckitty.missionstatus.architecture.fixture.conformance.port.PortCase;
import org.speckitty.missionstatus.architecture.fixture.domain.D1aSpring;
import org.speckitty.missionstatus.architecture.fixture.domain.D1bConcurrent;
import org.speckitty.missionstatus.architecture.fixture.domain.D1cThread;
import org.speckitty.missionstatus.architecture.fixture.domain.aotTest.PlantB;
import org.speckitty.missionstatus.architecture.fixture.domain.Value;
import org.speckitty.missionstatus.architecture.fixture.testsupport.Support;

/**
 * The positive controls of FR-012: one planted violation per rule (a second for rules 1, 2, 3, 12 and 13), each shown to turn its rule red,
 * and a conforming skeleton shown to keep all fourteen green with every rule scanning at least one class. The rule definitions are the
 * very ones the production run uses ({@link ArchitectureRules#all}), parameterised by the fixture package root, so a control cannot
 * pass against a rule that the production test does not run.
 *
 * <p>Each control states the exact set of rules it turns red. A planted Spring import in the domain also breaks rule 8, a controller
 * reaching the filesystem adapter breaks rules 3 and 5, and so on: the plan's "exactly this rule" is the rule named as the target, and
 * the co-reds are the other rules that forbid the same edge. The set is pinned so that a rule which stops firing is caught here.
 */
class ArchitectureControlsTest {

  private static final String FIXTURE_ROOT = "org.speckitty.missionstatus.architecture.fixture";
  private static final List<String> FIXTURE_RULE_9_PACKAGES =
      List.of(FIXTURE_ROOT + ".adapter.in.http.api", FIXTURE_ROOT + ".adapter.in.http.model", FIXTURE_ROOT + ".adapter.in.http.dto");

  /** The conforming skeleton: one class (or more) in every package the rules name. */
  private static final List<Class<?>> SKELETON =
      List.of(Value.class, Query.class, Source.class, Service.class, Dto.class, Controller.class, Decoder.class, SafeFiles.class, FsSource.class, Wiring.class,
          Support.class, PortCase.class);

  /** A planted violation: the class, the rule it targets and the full set of rules it turns red. */
  private record Control(int target, Class<?> planted, Set<Integer> red) {}

  private static final List<Control> CONTROLS =
      List.of(
          new Control(1, D1aSpring.class, Set.of(1, 8)),
          new Control(1, D1bConcurrent.class, Set.of(1)),
          new Control(1, PlantB.class, Set.of(1)),
          new Control(1, D1cThread.class, Set.of(1)),
          new Control(2, A2aUsesAdapter.class, Set.of(2)),
          new Control(2, A2bExecutors.class, Set.of(2)),
          new Control(3, H3aInternal.class, Set.of(3)),
          new Control(3, H3bConfig.class, Set.of(3, 6)),
          new Control(4, F4UsesHttp.class, Set.of(4, 5)),
          new Control(5, H5UsesFs.class, Set.of(3, 5)),
          new Control(6, A6UsesConfig.class, Set.of(2, 6)),
          new Control(7, G7Files.class, Set.of(7)),
          new Control(8, A8Jackson.class, Set.of(2, 8)),
          new Control(9, A9GeneratedModel.class, Set.of(2, 9)),
          new Control(10, G10Process.class, Set.of(10)),
          new Control(11, P11AdapterImport.class, Set.of(11)),
          new Control(11, P11bGoldenImportsFs.class, Set.of(11)),
          new Control(11, G11cUsesCodec.class, Set.of(11, 12)),
          new Control(12, C12aSafeFiles.class, Set.of(12)),
          new Control(12, C12bFiles.class, Set.of(7, 12)),
          new Control(13, P13aInClass.class, Set.of(13)),
          new Control(13, P13bOutClass.class, Set.of(13)),
          new Control(14, P14UsesCommand.class, Set.of(14)));

  private static List<Rule> fixtureRules() {
    return ArchitectureRules.all(FIXTURE_ROOT, FIXTURE_RULE_9_PACKAGES);
  }

  private static JavaClasses import_(List<Class<?>> classes) {
    return new ClassFileImporter().importClasses(classes.toArray(Class<?>[]::new));
  }

  private static Set<Integer> redRules(JavaClasses classes) {
    Set<Integer> red = new TreeSet<>();
    for (Rule rule : fixtureRules()) {
      if (rule.violatedBy(classes)) {
        red.add(rule.id());
      }
    }
    return red;
  }

  @TestFactory
  Stream<DynamicTest> everyPlantedViolationTurnsItsRuleRed() {
    return CONTROLS.stream()
        .map(
            control ->
                DynamicTest.dynamicTest(
                    "rule %02d control %s".formatted(control.target(), control.planted().getSimpleName()),
                    () -> {
                      List<Class<?>> classes = new ArrayList<>(SKELETON);
                      classes.add(control.planted());

                      Set<Integer> red = redRules(import_(classes));

                      assertThat(red).as("rules turned red by %s", control.planted().getSimpleName()).containsAll(Set.of(control.target()));
                      assertThat(red).as("the full red set of %s", control.planted().getSimpleName()).isEqualTo(control.red());
                    }));
  }

  @Test
  void theConformingSkeletonKeepsAllFourteenRulesGreenAndEveryRuleScansAClass() {
    JavaClasses skeleton = import_(SKELETON);

    for (Rule rule : fixtureRules()) {
      assertThat(rule.scanned(skeleton)).as("classes scanned by rule %d over the skeleton", rule.id()).isGreaterThan(0);
      assertThat(rule.violatedBy(skeleton)).as("rule %d over the skeleton", rule.id()).isFalse();
    }
  }

  @Test
  void everyRuleHasAControlAndRulesOneTwoThreeTwelveAndThirteenHaveASecond() {
    List<Integer> targets = CONTROLS.stream().map(Control::target).toList();

    assertThat(new TreeSet<>(targets)).containsExactlyElementsOf(IntStream.rangeClosed(1, ArchitectureRules.DEFINED_RULE_COUNT).boxed().toList());
    for (int withSecond : List.of(1, 2, 3, 12, 13)) {
      assertThat(targets.stream().filter(target -> target == withSecond).count()).as("controls of rule %d", withSecond).isGreaterThanOrEqualTo(2);
    }
    assertThat(fixtureRules()).hasSize(ArchitectureRules.DEFINED_RULE_COUNT);
  }

  @Test
  void theAotExclusionMatchesTheGradleOutputDirectoryOnlyNotAPackageNamedAotTest() throws Exception {
    var option = ArchitectureRules.NO_GENERATED_AOT_TEST_CLASSES;
    String base = "file:/w/services/mission-status-api/build/classes/java/";

    assertThat(option.includes(com.tngtech.archunit.core.importer.Location.of(java.net.URI.create(base + "aotTest/org/x/Y__TestContext001.class")))).isFalse();
    assertThat(option.includes(com.tngtech.archunit.core.importer.Location.of(java.net.URI.create(base + "main/org/speckitty/missionstatus/domain/aotTest/PlantB.class")))).isTrue();
  }

  @Test
  void theFixturePackagesAreNeverPartOfTheProductionImport() {
    JavaClasses main = ArchitectureRules.mainClasses();

    assertThat(main.stream().filter(c -> c.getPackageName().startsWith(FIXTURE_ROOT))).isEmpty();
  }
}
