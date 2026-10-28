package org.speckitty.missionstatus.architecture;

import static com.tngtech.archunit.core.domain.JavaClass.Predicates.resideInAPackage;
import static com.tngtech.archunit.core.domain.JavaClass.Predicates.resideInAnyPackage;
import static com.tngtech.archunit.core.domain.JavaClass.Predicates.resideOutsideOfPackage;
import static com.tngtech.archunit.lang.syntax.ArchRuleDefinition.classes;
import static org.assertj.core.api.Assertions.assertThat;

import com.tngtech.archunit.base.DescribedPredicate;
import com.tngtech.archunit.core.domain.JavaClass;
import com.tngtech.archunit.core.domain.JavaClasses;
import com.tngtech.archunit.core.importer.ClassFileImporter;
import com.tngtech.archunit.lang.ArchRule;
import com.tngtech.archunit.lang.EvaluationResult;
import java.nio.file.Path;
import java.util.Arrays;
import java.util.List;
import org.junit.jupiter.api.Test;
import org.speckitty.missionstatus.architecture.fixture.ConcurrentDecoder;
import org.speckitty.missionstatus.architecture.fixture.ConformingDecoder;
import org.speckitty.missionstatus.architecture.fixture.DataBindingDecoder;
import org.speckitty.missionstatus.architecture.fixture.FileReadingDecoder;
import org.speckitty.missionstatus.architecture.fixture.OutsidePackageDecoder;
import org.speckitty.missionstatus.architecture.fixture.ledger.ConformingLedgerFile;
import org.speckitty.missionstatus.architecture.fixture.ledger.DecodingLedgerFile;
import org.speckitty.missionstatus.architecture.fixture.reducer.ConformingFold;
import org.speckitty.missionstatus.architecture.fixture.reducer.ParsingFold;

/**
 * The event-log boundary (#6192). Among project code the module depends on domain-model only, and each of its three packages has its own
 * allowlist:
 *
 * <ul>
 *   <li>the codec ({@code adapter.out.filesystem.codec}, the line decoder and its byte rules) may use domain-model, the Jackson streaming
 *       parser ({@code tools.jackson.core}: no data binding, no reflection), {@code java.nio} buffers and the JDK packages the query
 *       service's rule 1b allows the domain. It decodes bytes it is handed and opens no file;
 *   <li>the reducer ({@code domain.readmodel.reducer}, the event ordering and fold) may use domain-model and the rule 1b JDK packages, and
 *       nothing else: no parser, no codec;
 *   <li>the ledger file mechanics ({@code adapter.out.ledger}: the ledger lock and the torn-tail repair, a #6193 follow-up)
 *       may use the JDK only. They open and lock files and move bytes, but read no row, so no parser, no codec and no domain-model.
 * </ul>
 *
 * The module holds those three packages only, so a new one needs its own rule here instead of slipping under a module-wide allowlist.
 *
 * <p>Non-vacuity: the rules import exactly this module's production classes (the {@code module.mainClasses} property the build sets)
 * and every type in {@link #EXTRACTED_TYPES} must be among them; planted violations prove each rule fires.
 */
class EventLogBoundaryTest {

  /** The 8 top-level types this module held when it was extracted (#6192); each must still be imported and checked. */
  static final List<String> EXTRACTED_TYPES =
      List.of(
          "adapter.out.filesystem.codec.LedgerLineDecoder", "adapter.out.filesystem.codec.PythonJson", "adapter.out.filesystem.codec.RowClassifier",
          "adapter.out.filesystem.codec.SeedKey", "domain.readmodel.reducer.AtThenEventId", "domain.readmodel.reducer.EventOrdering",
          "domain.readmodel.reducer.StatusReducer", "domain.readmodel.reducer.UnreducibleLedgerException");

  static final String ROOT = "org.speckitty.missionstatus";
  static final String MODEL = ROOT + ".domain.model..";
  static final String CODEC = ROOT + ".adapter.out.filesystem.codec..";
  static final String REDUCER = ROOT + ".domain.readmodel.reducer..";
  static final String LEDGER = ROOT + ".adapter.out.ledger..";

  /** The JDK packages of the query service's rule 1b: java.lang, java.util (not concurrent), java.time, java.math, java.security, java.nio.charset. */
  static final DescribedPredicate<JavaClass> RULE_1B_JDK =
      resideInAnyPackage("java.lang..", "java.util..", "java.time..", "java.math..", "java.security..", "java.nio.charset..")
          .and(resideOutsideOfPackage("java.util.concurrent.."));

  /** The codec rule over the package {@code codec}. */
  static ArchRule codecRule(String codec) {
    return classes().that().resideInAPackage(codec).should().onlyDependOnClassesThat(
            resideInAnyPackage(codec, MODEL, "tools.jackson.core..").or(resideInAPackage("java.nio")).or(RULE_1B_JDK))
        .as("the event-log codec depends only on itself, domain-model, the Jackson streaming parser, java.nio buffers and the rule 1b JDK"
            + " packages (so no framework, data binding, java.io or java.nio.file)");
  }

  /** The reducer rule over the package {@code reducer}. */
  static ArchRule reducerRule(String reducer) {
    return classes().that().resideInAPackage(reducer).should().onlyDependOnClassesThat(resideInAnyPackage(reducer, MODEL).or(RULE_1B_JDK))
        .as("the event-log reducer depends only on itself, domain-model and the rule 1b JDK packages (no parser, no codec, no IO)");
  }

  /** The ledger rule over the package {@code ledger}. */
  static ArchRule ledgerRule(String ledger) {
    return classes().that().resideInAPackage(ledger).should().onlyDependOnClassesThat(resideInAnyPackage(ledger, "java.."))
        .as("the event-log ledger file mechanics depend only on themselves and the JDK (no parser, no codec, no domain-model)");
  }

  static final ArchRule ONLY_THE_THREE_PACKAGES =
      classes().should().resideInAnyPackage(CODEC, REDUCER, LEDGER)
          .as("event-log holds the codec, the reducer and the ledger file mechanics only; a new package needs its own boundary rule here");

  static JavaClasses moduleClasses() {
    String path = System.getProperty("module.mainClasses");
    assertThat(path).as("the module.mainClasses system property (set by this module's build script)").isNotBlank();
    List<Path> roots = Arrays.stream(path.split(java.io.File.pathSeparator)).map(Path::of).toList();
    return new ClassFileImporter().importPaths(roots);
  }

  private static void assertHolds(ArchRule rule, JavaClasses classes) {
    EvaluationResult result = rule.evaluate(classes);
    assertThat(result.hasViolation()).as("violations:%n%s", result.getFailureReport()).isFalse();
  }

  @Test
  void theModuleClassesHoldTheBoundary() {
    JavaClasses classes = moduleClasses();
    for (String type : EXTRACTED_TYPES) {
      assertThat(classes.contain(ROOT + "." + type)).as("%s is imported and checked", type).isTrue();
    }
    assertThat(classes.contain(ROOT + ".domain.model.Lane")).as("domain-model classes are not this module's").isFalse();

    assertHolds(codecRule(CODEC), classes);
    assertHolds(reducerRule(REDUCER), classes);
    assertHolds(ledgerRule(LEDGER), classes);
    assertHolds(ONLY_THE_THREE_PACKAGES, classes);
    assertThat(classes.contain(ROOT + ".adapter.out.ledger.TornTailRepair")).as("the ledger package is imported and checked").isTrue();
  }

  private static final String FIXTURE = ROOT + ".architecture.fixture";

  @Test
  void aFileApiDependencyBreaksTheCodecRule() {
    assertThat(codecRule(FIXTURE).evaluate(new ClassFileImporter().importClasses(FileReadingDecoder.class)).hasViolation()).isTrue();
  }

  @Test
  void aDependencyOutsideTheAllowlistBreaksTheCodecRule() {
    assertThat(codecRule(FIXTURE).evaluate(new ClassFileImporter().importClasses(OutsidePackageDecoder.class)).hasViolation()).isTrue();
  }

  @Test
  void aDataBindingDependencyBreaksTheCodecRule() {
    assertThat(codecRule(FIXTURE).evaluate(new ClassFileImporter().importClasses(DataBindingDecoder.class)).hasViolation()).isTrue();
  }

  @Test
  void aConcurrencyDependencyBreaksTheCodecRule() {
    assertThat(codecRule(FIXTURE).evaluate(new ClassFileImporter().importClasses(ConcurrentDecoder.class)).hasViolation()).isTrue();
  }

  @Test
  void aConformingDecoderHoldsTheCodecRule() {
    assertHolds(codecRule(FIXTURE), new ClassFileImporter().importClasses(ConformingDecoder.class));
  }

  @Test
  void aParserDependencyBreaksTheReducerRule() {
    assertThat(reducerRule(FIXTURE + ".reducer").evaluate(new ClassFileImporter().importClasses(ParsingFold.class)).hasViolation()).isTrue();
  }

  @Test
  void aConformingFoldHoldsTheReducerRule() {
    assertHolds(reducerRule(FIXTURE + ".reducer"), new ClassFileImporter().importClasses(ConformingFold.class));
  }

  @Test
  void aParserDependencyBreaksTheLedgerRule() {
    assertThat(ledgerRule(FIXTURE + ".ledger").evaluate(new ClassFileImporter().importClasses(DecodingLedgerFile.class)).hasViolation()).isTrue();
  }

  @Test
  void conformingLedgerFileMechanicsHoldTheLedgerRule() {
    assertHolds(ledgerRule(FIXTURE + ".ledger"), new ClassFileImporter().importClasses(ConformingLedgerFile.class));
  }

  @Test
  void aClassOutsideTheThreePackagesBreaksTheModuleRule() {
    assertThat(ONLY_THE_THREE_PACKAGES.evaluate(new ClassFileImporter().importClasses(ConformingDecoder.class)).hasViolation()).isTrue();
  }
}
