package org.speckitty.missionstatus.architecture;

import static com.tngtech.archunit.core.domain.JavaClass.Predicates.resideInAPackage;
import static com.tngtech.archunit.core.domain.JavaClass.Predicates.resideInAnyPackage;
import static com.tngtech.archunit.core.domain.JavaClass.Predicates.resideOutsideOfPackage;
import static com.tngtech.archunit.core.domain.JavaClass.Predicates.resideOutsideOfPackages;
import static com.tngtech.archunit.lang.syntax.ArchRuleDefinition.classes;
import static com.tngtech.archunit.lang.syntax.ArchRuleDefinition.noClasses;

import com.tngtech.archunit.base.DescribedPredicate;
import com.tngtech.archunit.core.domain.JavaClass;
import com.tngtech.archunit.core.domain.JavaClasses;
import com.tngtech.archunit.core.domain.JavaConstructorCall;
import com.tngtech.archunit.core.domain.JavaMethodCall;
import com.tngtech.archunit.core.importer.ClassFileImporter;
import com.tngtech.archunit.core.importer.ImportOption;
import com.tngtech.archunit.core.importer.Location;
import com.tngtech.archunit.lang.ArchRule;
import com.tngtech.archunit.lang.CompositeArchRule;
import java.util.List;
import java.util.Set;
import java.util.stream.StreamSupport;

/**
 * The fourteen rules (the twelve of plan section 13, FR-012, AC-12, AC-13b, and two for the CQRS layout), parameterised by the package root so the same definitions run over the
 * production classes and over the planted violations of the positive controls. Which classes a rule is about (its {@link Rule#subject})
 * is separate from what it forbids, so a test can count the classes a rule scans (AC-12b).
 */
public final class ArchitectureRules {

  /** The production package root. */
  public static final String ROOT = "org.speckitty.missionstatus";

  /**
   * Rule 9's package list, pinned as literals: hand mode has no {@code apiPackage}/{@code modelPackage} in the build script. Generated
   * mode fills the first two, hand mode the third; the rule covers all three whichever is populated.
   */
  public static final List<String> RULE_9_PACKAGES =
      List.of(
          "org.speckitty.missionstatus.adapter.in.http.api",
          "org.speckitty.missionstatus.adapter.in.http.model",
          "org.speckitty.missionstatus.adapter.in.http.dto");

  /** How many rules the plan table defines. The guard compares the rules actually built and run with this literal. */
  public static final int DEFINED_RULE_COUNT = 14;

  /** Where a rule looks: production rules import main classes only; rule 11 imports test classes. */
  public enum Scope {
    MAIN,
    TEST
  }

  /** One numbered rule: what it forbids, which classes it is about, and the class set it must be evaluated over. */
  public record Rule(int id, String name, Scope scope, ArchRule rule, DescribedPredicate<JavaClass> subject) {

    /** The classes this rule scans among {@code classes}. */
    public long scanned(JavaClasses classes) {
      return StreamSupport.stream(classes.spliterator(), false).filter(subject).count();
    }

    public boolean violatedBy(JavaClasses classes) {
      return rule.evaluate(classes).hasViolation();
    }
  }

  private static final String[] SPRING = {"org.springframework.."};
  private static final String[] HTTP = {"jakarta.servlet..", "org.apache.catalina..", "org.apache.coyote..", "java.net.."};
  /** The packages of every JSON (and YAML) library the build can see; rule 8 and rules 1 and 2 share the list. */
  private static final String[] JSON = {
    "tools.jackson..", "com.fasterxml.jackson..", "org.openapitools.jackson..", "com.google.gson..", "org.json..", "jakarta.json..", "javax.json..",
    "org.yaml..", "org.snakeyaml.."
  };

  private static final Set<String> JAVA_IO_FILE_CLASSES =
      Set.of(
          "java.io.File", "java.io.FileInputStream", "java.io.FileOutputStream", "java.io.FileReader", "java.io.FileWriter", "java.io.RandomAccessFile",
          "java.io.FileDescriptor", "java.io.FileFilter", "java.io.FilenameFilter", "java.nio.channels.FileChannel");

  /** The file APIs of rules 7 and 12: {@code java.nio.file}, the {@code java.io} file classes, and {@code FileChannel}. */
  static final DescribedPredicate<JavaClass> FILE_API =
      resideInAPackage("java.nio.file..").or(DescribedPredicate.describe("java.io file classes", (JavaClass c) -> JAVA_IO_FILE_CLASSES.contains(c.getName())));

  private static final Set<String> THREAD_OWNER_METHODS = Set.of("ofVirtual", "ofPlatform", "startVirtualThread");

  private ArchitectureRules() {}

  /**
   * Excludes the Spring AOT test-context classes ({@code build/classes/java/aotTest}, matched on that output directory so a package named {@code aotTest} is still scanned; generated from the {@code @SpringBootTest} classes):
   * they are neither production nor hand-written test classes and call Spring and config internals by construction.
   */
  static final ImportOption NO_GENERATED_AOT_TEST_CLASSES = (Location location) -> !location.contains("/classes/java/aotTest/");

  /** The production class set: main classes only (generated classes included), never test classes. */
  public static JavaClasses mainClasses() {
    return new ClassFileImporter()
        .withImportOption(ImportOption.Predefined.DO_NOT_INCLUDE_TESTS)
        .withImportOption(NO_GENERATED_AOT_TEST_CLASSES)
        .importPackages(ROOT);
  }

  /** The test class set, for rule 11: hand-written test classes only. */
  public static JavaClasses testClasses() {
    return new ClassFileImporter()
        .withImportOption(new ImportOption.OnlyIncludeTests())
        .withImportOption(NO_GENERATED_AOT_TEST_CLASSES)
        .importPackages(ROOT);
  }

  private static String p(String root, String suffix) {
    return root + "." + suffix;
  }

  private static DescribedPredicate<JavaClass> inFilesystemWithoutCodec(String root) {
    return resideInAPackage(p(root, "adapter.out.filesystem..")).and(resideOutsideOfPackage(p(root, "adapter.out.filesystem.codec..")));
  }

  private static ArchRule rule(ArchRule rule) {
    // Emptiness is checked explicitly by the non-vacuity tests (the subject count), so a control over a partial class set evaluates.
    return rule.allowEmptyShould(true);
  }

  /** All fourteen rules over the package root {@code root}, with {@code rule9Packages} as rule 9's DTO package list. */
  public static List<Rule> all(String root, List<String> rule9Packages) {
    String domain = p(root, "domain..");
    String application = p(root, "application..");
    String http = p(root, "adapter.in.http..");
    String filesystem = p(root, "adapter.out.filesystem..");
    String codec = p(root, "adapter.out.filesystem.codec..");
    String config = p(root, "config..");
    String testsupport = p(root, "testsupport..");

    DescribedPredicate<JavaClass> anyClass = DescribedPredicate.alwaysTrue();

    // 1: domain
    ArchRule r1a =
        noClasses().that().resideInAPackage(domain).should().dependOnClassesThat()
            .resideInAnyPackage(concat(SPRING, HTTP, JSON, new String[] {"java.nio.file..", "java.io.."}))
            .as("rule 1a: domain references no Spring, HTTP, JSON, java.nio.file or java.io");
    ArchRule r1b =
        classes().that().resideInAPackage(domain).should().onlyDependOnClassesThat(
                resideInAnyPackage(domain, "java.lang..", "java.util..", "java.time..", "java.math..", "java.security..", "java.nio.charset..").and(resideOutsideOfPackage("java.util.concurrent..")))
            .as("rule 1b: domain depends only on domain and java.lang, java.util (not concurrent), java.time, java.math, java.security, java.nio.charset");

    // 2: application
    ArchRule r2a =
        noClasses().that().resideInAPackage(application).should().dependOnClassesThat()
            .resideInAnyPackage(concat(SPRING, HTTP, JSON, new String[] {"java.nio.file..", "java.io.."}))
            .as("rule 2a: application references no Spring, HTTP, JSON, java.io or java.nio.file");
    ArchRule r2b =
        classes().that().resideInAPackage(application).should().onlyDependOnClassesThat(
                resideInAnyPackage(application, domain, "java.lang..", "java.util..", "java.time..", "java.math..", "java.security..", "java.nio.charset.."))
            .as("rule 2b: application depends only on application, domain and the JDK packages (adapter and config excluded)");
    ArchRule r2c =
        noClasses().that().resideInAPackage(application).should().callMethodWhere(threadCreatingMethodCall())
            .orShould().callConstructorWhere(threadCreatingConstructorCall())
            .as("rule 2c: application creates no thread (the executor is injected)");

    // 3, 4, 5: adapters
    ArchRule r3 =
        noClasses().that().resideInAPackage(http).should().dependOnClassesThat(
                resideInAPackage(root + "..").and(resideOutsideOfPackages(http, p(root, "application.query.port.in.."), domain)))
            .as("rule 3: adapter.in.http depends, among project packages, only on application.query.port.in, domain and itself");
    ArchRule r4 =
        noClasses().that().resideInAPackage(filesystem).should().dependOnClassesThat(
                resideInAPackage(root + "..").and(resideOutsideOfPackages(filesystem, p(root, "application.query.port.out.."), domain)))
            .as("rule 4: adapter.out.filesystem (codec included) depends, among project packages, only on application.query.port.out, domain and itself");
    ArchRule r5a =
        noClasses().that().resideInAPackage(p(root, "adapter.in..")).should().dependOnClassesThat().resideInAPackage(p(root, "adapter.out.."))
            .as("rule 5a: no inbound-adapter dependency on an outbound adapter");
    ArchRule r5b =
        noClasses().that().resideInAPackage(p(root, "adapter.out..")).should().dependOnClassesThat().resideInAPackage(p(root, "adapter.in.."))
            .as("rule 5b: no outbound-adapter dependency on an inbound adapter");

    // 6: config
    ArchRule r6 =
        noClasses().that().resideOutsideOfPackage(config).should().dependOnClassesThat().resideInAPackage(config)
            .as("rule 6: nothing outside config depends on config");

    // 7, 8, 9, 10: technology confinement
    ArchRule r7 =
        noClasses().that(resideOutsideOfPackage(filesystem).or(resideInAPackage(codec))).should().dependOnClassesThat(FILE_API)
            .as("rule 7: file APIs only in adapter.out.filesystem, its codec sub-package excluded");
    ArchRule r8 =
        noClasses().that().resideOutsideOfPackages(p(root, "adapter.."), config).should().dependOnClassesThat()
            .resideInAnyPackage(concat(SPRING, JSON))
            .as("rule 8: JSON libraries and Spring only in adapter and config");
    ArchRule r9 =
        noClasses().that().resideOutsideOfPackage(http).should().dependOnClassesThat().resideInAnyPackage(rule9Packages.toArray(String[]::new))
            .as("rule 9: generated and hand contract DTO packages only in adapter.in.http");
    ArchRule r10 =
        noClasses().should().dependOnClassesThat(DescribedPredicate.describe("ProcessBuilder", (JavaClass c) -> c.getName().equals("java.lang.ProcessBuilder")))
            .orShould().callMethodWhere(DescribedPredicate.describe("Runtime.exec", (JavaMethodCall c) -> c.getTargetOwner().getName().equals("java.lang.Runtime") && c.getName().equals("exec")))
            .as("rule 10: no ProcessBuilder and no Runtime.exec");

    // 11: the port-level subset (test classes)
    ArchRule r11a =
        noClasses().that().resideInAPackage(p(root, "conformance.port..")).should().dependOnClassesThat().resideInAPackage(p(root, "adapter.."))
            .as("rule 11a: port-level classes depend on no adapter class");
    ArchRule r11b =
        noClasses().that().resideInAnyPackage(p(root, "conformance.port.."), p(root, "conformance.golden.."))
            .should().dependOnClassesThat().resideInAPackage(filesystem)
            .as("rule 11b: of the conformance trees, only testsupport imports adapter.out.filesystem");
    ArchRule r11c =
        noClasses().that().resideOutsideOfPackages(testsupport, filesystem).should().dependOnClassesThat().resideInAPackage(codec)
            .as("rule 11c: of the test classes, only testsupport and adapter.out.filesystem itself use the codec");

    // 12: the codec
    ArchRule r12a =
        noClasses().that().resideInAPackage(codec).should().dependOnClassesThat(
                resideInAPackage(root + "..").and(resideOutsideOfPackages(domain, codec)))
            .as("rule 12a: the codec depends, among project packages, only on domain and itself");
    ArchRule r12b =
        noClasses().that().resideInAPackage(codec).should().dependOnClassesThat(FILE_API).as("rule 12b: the codec uses no file API");
    ArchRule r12c =
        noClasses().that().resideOutsideOfPackages(filesystem, testsupport).should().dependOnClassesThat().resideInAPackage(codec)
            .as("rule 12c: the codec is used only by adapter.out.filesystem and testsupport");

    // 13, 14: the CQRS query side
    ArchRule r13 =
        classes().that().resideInAnyPackage(p(root, "application.query.port.in"), p(root, "application.query.port.out")).should().beInterfaces()
            .as("rule 13: a class residing directly in application.query.port.in or application.query.port.out is an interface (types go to dto or exceptions)");
    ArchRule r14 =
        noClasses().that().resideInAPackage(p(root, "application.query..")).should().dependOnClassesThat().resideInAPackage(p(root, "application.command.."))
            .as("rule 14: nothing in application.query depends on application.command");

    return List.of(
        new Rule(1, "domain is framework-, JSON-, file- and concurrency-free", Scope.MAIN, both(r1a, r1b), resideInAPackage(domain)),
        new Rule(2, "application is technology-free and creates no thread", Scope.MAIN, CompositeArchRule.of(rule(r2a)).and(rule(r2b)).and(rule(r2c)), resideInAPackage(application)),
        new Rule(3, "adapter.in.http reaches only the inbound port", Scope.MAIN, rule(r3), resideInAPackage(http)),
        new Rule(4, "adapter.out.filesystem reaches only the outbound port and domain", Scope.MAIN, rule(r4), resideInAPackage(filesystem)),
        new Rule(5, "no adapter-to-adapter dependency", Scope.MAIN, both(r5a, r5b), resideInAPackage(p(root, "adapter.."))),
        new Rule(6, "nothing depends on config", Scope.MAIN, rule(r6), resideOutsideOfPackage(config)),
        new Rule(7, "file APIs only in the filesystem adapter, codec excluded", Scope.MAIN, rule(r7), resideOutsideOfPackage(filesystem).or(resideInAPackage(codec))),
        new Rule(8, "JSON libraries and Spring only in adapters and config", Scope.MAIN, rule(r8), resideOutsideOfPackages(p(root, "adapter.."), config)),
        new Rule(9, "contract DTO packages only in adapter.in.http", Scope.MAIN, rule(r9), resideOutsideOfPackage(http)),
        new Rule(10, "no process creation", Scope.MAIN, rule(r10), anyClass),
        new Rule(11, "the port-level subset is source-neutral", Scope.TEST, CompositeArchRule.of(rule(r11a)).and(rule(r11b)).and(rule(r11c)), resideInAPackage(p(root, "conformance.port.."))),
        new Rule(12, "the codec is pure decoding", Scope.MAIN, CompositeArchRule.of(rule(r12a)).and(rule(r12b)).and(rule(r12c)), resideInAPackage(codec)),
        new Rule(13, "the query ports hold interfaces only", Scope.MAIN, rule(r13), resideInAnyPackage(p(root, "application.query.port.in"), p(root, "application.query.port.out"))),
        new Rule(14, "the query side does not reach the command side", Scope.MAIN, rule(r14), resideInAPackage(p(root, "application.query.."))));
  }

  /** The production rule set. */
  public static List<Rule> production() {
    return all(ROOT, RULE_9_PACKAGES);
  }

  private static ArchRule both(ArchRule first, ArchRule second) {
    return CompositeArchRule.of(rule(first)).and(rule(second));
  }

  private static String[] concat(String[]... parts) {
    return java.util.Arrays.stream(parts).flatMap(java.util.Arrays::stream).toArray(String[]::new);
  }

  private static DescribedPredicate<JavaMethodCall> threadCreatingMethodCall() {
    return DescribedPredicate.describe(
        "a call of Executors.* or Thread.ofVirtual/ofPlatform/startVirtualThread",
        (JavaMethodCall call) ->
            call.getTargetOwner().getName().equals("java.util.concurrent.Executors")
                || (call.getTargetOwner().getName().equals("java.lang.Thread") && THREAD_OWNER_METHODS.contains(call.getName())));
  }

  private static DescribedPredicate<JavaConstructorCall> threadCreatingConstructorCall() {
    return DescribedPredicate.describe(
        "the construction of a Thread, ThreadPoolExecutor or ForkJoinPool",
        (JavaConstructorCall call) ->
            call.getTargetOwner().isAssignableTo(Thread.class)
                || call.getTargetOwner().isAssignableTo(java.util.concurrent.ThreadPoolExecutor.class)
                || call.getTargetOwner().isAssignableTo(java.util.concurrent.ForkJoinPool.class));
  }
}
