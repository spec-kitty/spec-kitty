package org.speckitty.missionstatus.application.query.index;

import static org.assertj.core.api.Assertions.assertThat;

import com.tngtech.archunit.core.domain.JavaClass;
import com.tngtech.archunit.core.domain.JavaClasses;
import java.util.Set;
import java.util.stream.Collectors;
import java.util.stream.StreamSupport;
import org.junit.jupiter.api.Test;
import org.speckitty.missionstatus.architecture.ArchitectureRules;
import org.speckitty.missionstatus.architecture.ArchitectureRules.Rule;

/**
 * AC-6.5 (c), the application half: rules 2, 4, 7, 12 and 13 over the production {@code WorkPackageIndex}. The index calls the decoder
 * port and never the codec (rule 12c), and the application layer stays technology-free (rule 2).
 */
class WorkPackageIndexRulesTest {

  private static final String INDEX = ArchitectureRules.ROOT + ".application.query.index.WorkPackageIndex";
  private static final JavaClasses MAIN = ArchitectureRules.mainClasses();

  private static Rule rule(int id) {
    return ArchitectureRules.production().stream().filter(candidate -> candidate.id() == id).findFirst().orElseThrow();
  }

  private static Set<String> scannedNames(Rule rule) {
    return StreamSupport.stream(MAIN.spliterator(), false).filter(rule.subject()).map(JavaClass::getName).collect(Collectors.toSet());
  }

  @Test
  void rulesTwoFourSevenTwelveAndThirteenHoldAndTheIndexIsInTheClassesTheyScan() {
    for (int id : new int[] {2, 7, 13}) {
      Rule rule = rule(id);
      assertThat(rule.violatedBy(MAIN)).as("rule %d", id).isFalse();
      assertThat(rule.scanned(MAIN)).as("rule %d scans classes", id).isGreaterThan(0);
    }
    assertThat(scannedNames(rule(2))).contains(INDEX);
    assertThat(scannedNames(rule(7))).contains(INDEX);
    assertThat(rule(4).violatedBy(MAIN)).isFalse();
    assertThat(rule(12).violatedBy(MAIN)).isFalse();
  }

  @Test
  void theIndexReferencesTheDecoderPortAndNoCodecOrAdapterClass() {
    JavaClass index = MAIN.get(INDEX);
    Set<String> targets = index.getDirectDependenciesFromSelf().stream().map(dependency -> dependency.getTargetClass().getName()).collect(Collectors.toSet());
    assertThat(targets).contains(ArchitectureRules.ROOT + ".application.query.port.out.FrontmatterDecoder", ArchitectureRules.ROOT + ".application.query.port.out.TextSource");
    assertThat(targets).noneMatch(name -> name.contains(".adapter."));
    assertThat(targets).noneMatch(name -> name.startsWith("org.yaml"));
  }

  @Test
  void theTwoDecoderPortsAreInterfacesDirectlyInThePortPackage() {
    for (String name : Set.of("FrontmatterDecoder", "LanesDecoder")) {
      JavaClass port = MAIN.get(ArchitectureRules.ROOT + ".application.query.port.out." + name);
      assertThat(port.isInterface()).isTrue();
    }
  }
}
