package org.speckitty.missionstatus.adapter.out.filesystem.codec;

import static org.assertj.core.api.Assertions.assertThat;

import com.tngtech.archunit.core.domain.JavaClass;
import com.tngtech.archunit.core.domain.JavaClasses;
import java.util.List;
import java.util.Set;
import java.util.stream.Collectors;
import java.util.stream.StreamSupport;
import org.junit.jupiter.api.Test;
import org.speckitty.missionstatus.architecture.ArchitectureRules;
import org.speckitty.missionstatus.architecture.ArchitectureRules.Rule;

/**
 * AC-6.5 (c), the codec half: rules 4, 7 and 12 over the production decoder classes added by FR-006, with a non-zero scanned count that
 * names them. The planted violations of the same rules are the controls {@code C12aPortOut} and {@code A12cUsesCodec} of
 * {@code ArchitectureControlsTest}.
 */
class LanesCodecRulesTest {

  private static final String FILESYSTEM = ArchitectureRules.ROOT + ".adapter.out.filesystem.";
  private static final Set<String> CODEC_CLASSES = Set.of(FILESYSTEM + "codec.WpFrontmatterCodec", FILESYSTEM + "codec.ReviewCycleCodec", FILESYSTEM + "codec.LanesCodec");
  private static final Set<String> ADAPTER_CLASSES = Set.of(FILESYSTEM + "YamlFrontmatterDecoder", FILESYSTEM + "JsonLanesDecoder");

  private static final JavaClasses MAIN = ArchitectureRules.mainClasses();

  private static Rule rule(int id) {
    return ArchitectureRules.production().stream().filter(candidate -> candidate.id() == id).findFirst().orElseThrow();
  }

  private static Set<String> scannedNames(Rule rule) {
    return StreamSupport.stream(MAIN.spliterator(), false).filter(rule.subject()).map(JavaClass::getName).collect(Collectors.toSet());
  }

  @Test
  void rule12TheCodecIsPureDecodingHoldsAndScansTheThreeCodecs() {
    Rule rule = rule(12);
    assertThat(rule.violatedBy(MAIN)).isFalse();
    assertThat(rule.scanned(MAIN)).isGreaterThan(0);
    assertThat(scannedNames(rule)).containsAll(CODEC_CLASSES);
  }

  @Test
  void rule4TheFilesystemAdapterReachesOnlyThePortAndDomainHoldsAndScansTheCodecsAndTheTwoDecoders() {
    Rule rule = rule(4);
    assertThat(rule.violatedBy(MAIN)).isFalse();
    assertThat(scannedNames(rule)).containsAll(CODEC_CLASSES).containsAll(ADAPTER_CLASSES);
  }

  @Test
  void rule7NoFileApiOutsideTheFilesystemAdapterHoldsAndScansTheCodecs() {
    Rule rule = rule(7);
    assertThat(rule.violatedBy(MAIN)).isFalse();
    assertThat(scannedNames(rule)).containsAll(CODEC_CLASSES);
  }

  @Test
  void theImplementingClassesSitDirectlyInTheFilesystemPackageAndNotInTheCodecPackage() {
    for (String name : ADAPTER_CLASSES) {
      JavaClass decoder = MAIN.get(name);
      assertThat(decoder.getPackageName()).isEqualTo(ArchitectureRules.ROOT + ".adapter.out.filesystem");
      assertThat(decoder.getRawInterfaces()).extracting(JavaClass::getPackageName).containsExactly(ArchitectureRules.ROOT + ".application.query.port.out");
    }
    List<String> codecDependencies =
        CODEC_CLASSES.stream()
            .flatMap(name -> MAIN.get(name).getDirectDependenciesFromSelf().stream())
            .map(dependency -> dependency.getTargetClass().getPackageName())
            .filter(pkg -> pkg.startsWith(ArchitectureRules.ROOT))
            .distinct()
            .toList();
    assertThat(codecDependencies).allMatch(pkg -> pkg.startsWith(ArchitectureRules.ROOT + ".domain") || pkg.equals(ArchitectureRules.ROOT + ".adapter.out.filesystem.codec"));
  }
}
