package org.speckitty.missionstatus.architecture;

import static com.tngtech.archunit.core.domain.JavaClass.Predicates.resideInAPackage;
import static com.tngtech.archunit.core.domain.JavaClass.Predicates.resideInAnyPackage;
import static com.tngtech.archunit.core.domain.JavaClass.Predicates.resideOutsideOfPackage;
import static com.tngtech.archunit.core.domain.JavaClass.Predicates.resideOutsideOfPackages;
import static com.tngtech.archunit.lang.syntax.ArchRuleDefinition.classes;
import static com.tngtech.archunit.lang.syntax.ArchRuleDefinition.noClasses;

import com.tngtech.archunit.base.DescribedPredicate;
import com.tngtech.archunit.core.domain.Dependency;
import com.tngtech.archunit.core.domain.JavaClass;
import com.tngtech.archunit.core.domain.JavaClasses;
import com.tngtech.archunit.core.domain.JavaConstructorCall;
import com.tngtech.archunit.core.domain.JavaMethod;
import com.tngtech.archunit.core.domain.JavaModifier;
import com.tngtech.archunit.core.domain.JavaMethodCall;
import com.tngtech.archunit.core.importer.ClassFileImporter;
import com.tngtech.archunit.core.importer.ImportOption;
import com.tngtech.archunit.core.importer.Location;
import com.tngtech.archunit.lang.ArchCondition;
import com.tngtech.archunit.lang.ArchRule;
import com.tngtech.archunit.lang.CompositeArchRule;
import com.tngtech.archunit.lang.ConditionEvents;
import com.tngtech.archunit.lang.SimpleConditionEvent;
import java.util.List;
import java.util.Set;
import java.util.stream.StreamSupport;

/**
 * The sixteen rules (the twelve of plan section 13, FR-012, AC-12, AC-13b, two for the CQRS layout and two for the inbound side of the detail operations), parameterised by the package root so the same definitions run over the
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
  public static final int DEFINED_RULE_COUNT = 16;

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
  /** The packages of every JSON (and YAML) library the build can see; rule 8 uses the list. */
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

  /** All sixteen rules over the package root {@code root}, with {@code rule9Packages} as rule 9's DTO package list. */
  public static List<Rule> all(String root, List<String> rule9Packages) {
    return List.of(
        rule1(root), rule2(root), rule3(root), rule4(root), rule5(root), rule6(root), rule7(root),
        rule8(root), rule9(root, rule9Packages), rule10(), rule11(root), rule12(root), rule13(root), rule14(root), rule15(root), rule16(root, rule9Packages));
  }

  /** Rule 1: the domain. */
  private static Rule rule1(String root) {
    String domain = p(root, "domain..");
    // The allowlist below also keeps Spring, HTTP, JSON, java.nio.file and java.io out of the domain (an allowlist subsumes that denylist).
    ArchRule r1b =
        classes().that().resideInAPackage(domain).should().onlyDependOnClassesThat(
                resideInAnyPackage(domain, "java.lang", "java.util..", "java.time..", "java.math..", "java.security..", "java.nio.charset..").and(resideOutsideOfPackage("java.util.concurrent..")))
            .as("rule 1b: domain depends only on domain and java.lang (not java.lang.reflect or java.lang.invoke), java.util (not concurrent), java.time, java.math, java.security, java.nio.charset"
                + " (so no Spring, HTTP, JSON, java.nio.file or java.io)");
    ArchRule r1c =
        noClasses().that().resideInAPackage(domain).should().callMethodWhere(threadCreatingMethodCall())
            .orShould().callConstructorWhere(threadCreatingConstructorCall())
            .as("rule 1c: domain creates no thread (java.lang is allowed by 1b, so Thread itself needs its own rule)");
    ArchRule r1d =
        noClasses().that().resideInAPackage(domain).should().callMethodWhere(REFLECTIVE_LOADING_CALL)
            .as("rule 1d: domain loads no class reflectively (no Class.forName, ClassLoader.loadClass or Class.get*Method/Constructor/Field)");
    return new Rule(1, "domain is framework-, JSON-, file- and concurrency-free", Scope.MAIN, CompositeArchRule.of(rule(r1b)).and(rule(r1c)).and(rule(r1d)), resideInAPackage(domain));
  }

  /** Rule 2: the application. */
  private static Rule rule2(String root) {
    String domain = p(root, "domain..");
    String application = p(root, "application..");
    // As in the domain, the allowlist of 2b subsumes the denylist of Spring, HTTP, JSON, java.io and java.nio.file.
    ArchRule r2b =
        classes().that().resideInAPackage(application).should().onlyDependOnClassesThat(
                resideInAnyPackage(application, domain, "java.lang", "java.util..", "java.time..", "java.math..", "java.security..", "java.nio.charset.."))
            .as("rule 2b: application depends only on application, domain and the JDK packages, java.lang.reflect and java.lang.invoke excluded (adapter and config, Spring, HTTP, JSON and file APIs excluded)");
    ArchRule r2c =
        noClasses().that().resideInAPackage(application).should().callMethodWhere(threadCreatingMethodCall())
            .orShould().callConstructorWhere(threadCreatingConstructorCall())
            .as("rule 2c: application creates no thread (the executor is injected)");
    ArchRule r2d =
        noClasses().that().resideInAPackage(application).should().callMethodWhere(REFLECTIVE_LOADING_CALL)
            .as("rule 2d: application loads no class reflectively (no Class.forName, ClassLoader.loadClass or Class.get*Method/Constructor/Field)");
    return new Rule(2, "application is technology-free and creates no thread", Scope.MAIN, CompositeArchRule.of(rule(r2b)).and(rule(r2c)).and(rule(r2d)), resideInAPackage(application));
  }

  /**
   * Rule 3: every inbound adapter {@code adapter.in.<x>} reaches, among project packages, only the inbound port, the domain and itself (a
   * sibling {@code adapter.in.<y>} is a violation), and a controller annotation lives only in {@code adapter.in..} (rule 3b).
   *
   * <p>Rule 3b allow-lists {@code config.ProblemErrorController} by fully qualified name. This is a permanent structural exception, not
   * transient debt, and it has no expiry: the container dispatches an error to {@code /error}, outside the {@code /api/v1} prefix that
   * applies to {@code adapter.in.http}, so the error controller cannot live there without changing the path. The entry must match a class
   * in the production import ({@code ArchitectureRulesTest} guards the stale entry).
   */
  private static Rule rule3(String root) {
    String in = p(root, "adapter.in");
    ArchRule r3a =
        classes().that().resideInAPackage(in + "..").should(onlyReachPortDomainAndOwnAdapter(root))
            .as("rule 3: every adapter.in.<x> depends, among project packages, only on application.query.port.in, domain and itself");
    ArchRule r3b =
        classes().that(CONTROLLER_ANNOTATED).and().doNotHaveFullyQualifiedName(controllerAllowList(root)).should().resideInAPackage(in + "..")
            .as("rule 3b: a controller annotation (@RestController, @Controller, @RestControllerAdvice, @ControllerAdvice) only in adapter.in.., except config.ProblemErrorController");
    return new Rule(3, "every adapter.in.<x> reaches only the inbound port; controllers only in adapter.in", Scope.MAIN, both(r3a, r3b), resideInAPackage(in + ".."));
  }

  /** The one allow-listed controller outside {@code adapter.in..}, by fully qualified name. */
  static String controllerAllowList(String root) {
    return p(root, "config.ProblemErrorController");
  }

  private static final Set<String> CONTROLLER_ANNOTATIONS =
      Set.of(
          "org.springframework.web.bind.annotation.RestController", "org.springframework.stereotype.Controller",
          "org.springframework.web.bind.annotation.RestControllerAdvice", "org.springframework.web.bind.annotation.ControllerAdvice");

  static final DescribedPredicate<JavaClass> CONTROLLER_ANNOTATED =
      DescribedPredicate.describe("annotated with a controller annotation", (JavaClass c) -> CONTROLLER_ANNOTATIONS.stream().anyMatch(c::isAnnotatedWith));

  /** A nested class is judged by its outermost class. */
  static JavaClass outermost(JavaClass c) {
    JavaClass top = c;
    while (top.getEnclosingClass().isPresent()) {
      top = top.getEnclosingClass().get();
    }
    return top;
  }

  /** The first package segment below {@code adapter.in}: the name of the inbound adapter a class belongs to ({@code ""} for the package itself). */
  static String adapterSegment(String root, JavaClass c) {
    String prefix = p(root, "adapter.in");
    String pkg = c.getPackageName();
    if (!pkg.startsWith(prefix + ".")) {
      return "";
    }
    String rest = pkg.substring(prefix.length() + 1);
    int dot = rest.indexOf('.');
    return dot < 0 ? rest : rest.substring(0, dot);
  }

  private static boolean inPackageOrBelow(String pkg, String base) {
    return pkg.equals(base) || pkg.startsWith(base + ".");
  }

  private static ArchCondition<JavaClass> onlyReachPortDomainAndOwnAdapter(String root) {
    return new ArchCondition<>("depend, among project packages, only on application.query.port.in, domain and their own adapter.in.<x>") {
      @Override
      public void check(JavaClass c, ConditionEvents events) {
        String segment = adapterSegment(root, c);
        String own = segment.isEmpty() ? p(root, "adapter.in") : p(root, "adapter.in." + segment);
        for (Dependency d : c.getDirectDependenciesFromSelf()) {
          String target = d.getTargetClass().getPackageName();
          boolean project = inPackageOrBelow(target, root);
          boolean allowed =
              inPackageOrBelow(target, p(root, "application.query.port.in")) || inPackageOrBelow(target, p(root, "domain")) || inPackageOrBelow(target, own);
          if (project && !allowed) {
            events.add(SimpleConditionEvent.violated(d, d.getDescription()));
          }
        }
      }
    };
  }

  /** Calls that load a class or look up a member by name at run time: the hole a package exclusion alone leaves open (D-124). */
  static final DescribedPredicate<JavaMethodCall> REFLECTIVE_LOADING_CALL =
      DescribedPredicate.describe(
          "a call of Class.forName, ClassLoader.loadClass or Class.getMethod(s)/getConstructor(s)/getField(s)/getDeclared*",
          (JavaMethodCall call) -> {
            String owner = call.getTargetOwner().getName();
            String name = call.getName();
            if (owner.equals("java.lang.Class")) {
              return name.equals("forName")
                  || name.equals("getMethod") || name.equals("getMethods") || name.equals("getConstructor") || name.equals("getConstructors")
                  || name.equals("getField") || name.equals("getFields") || name.startsWith("getDeclared");
            }
            return owner.equals("java.lang.ClassLoader") && name.equals("loadClass");
          });

  /** Rule 4: the filesystem adapter reaches only the outbound port and the domain. */
  private static Rule rule4(String root) {
    String filesystem = p(root, "adapter.out.filesystem..");
    ArchRule r4 =
        noClasses().that().resideInAPackage(filesystem).should().dependOnClassesThat(
                resideInAPackage(root + "..").and(resideOutsideOfPackages(filesystem, p(root, "application.query.port.out.."), p(root, "domain.."))))
            .as("rule 4: adapter.out.filesystem (codec included) depends, among project packages, only on application.query.port.out, domain and itself");
    return new Rule(4, "adapter.out.filesystem reaches only the outbound port and domain", Scope.MAIN, rule(r4), resideInAPackage(filesystem));
  }

  /** Rule 5: no adapter-to-adapter dependency. */
  private static Rule rule5(String root) {
    ArchRule r5a =
        noClasses().that().resideInAPackage(p(root, "adapter.in..")).should().dependOnClassesThat().resideInAPackage(p(root, "adapter.out.."))
            .as("rule 5a: no inbound-adapter dependency on an outbound adapter");
    ArchRule r5b =
        noClasses().that().resideInAPackage(p(root, "adapter.out..")).should().dependOnClassesThat().resideInAPackage(p(root, "adapter.in.."))
            .as("rule 5b: no outbound-adapter dependency on an inbound adapter");
    return new Rule(5, "no adapter-to-adapter dependency", Scope.MAIN, both(r5a, r5b), resideInAPackage(p(root, "adapter..")));
  }

  /** Rule 6: nothing depends on config. */
  private static Rule rule6(String root) {
    String config = p(root, "config..");
    ArchRule r6 =
        noClasses().that().resideOutsideOfPackage(config).should().dependOnClassesThat().resideInAPackage(config)
            .as("rule 6: nothing outside config depends on config");
    return new Rule(6, "nothing depends on config", Scope.MAIN, rule(r6), resideOutsideOfPackage(config));
  }

  /** Rule 7: file APIs only in the filesystem adapter, codec excluded. */
  private static Rule rule7(String root) {
    DescribedPredicate<JavaClass> outsideFilesystemOrCodec = inFilesystemOutsideCodecComplement(root);
    ArchRule r7 = noClasses().that(outsideFilesystemOrCodec).should().dependOnClassesThat(FILE_API).as("rule 7: file APIs only in adapter.out.filesystem, its codec sub-package excluded");
    return new Rule(7, "file APIs only in the filesystem adapter, codec excluded", Scope.MAIN, rule(r7), outsideFilesystemOrCodec);
  }

  private static DescribedPredicate<JavaClass> inFilesystemOutsideCodecComplement(String root) {
    return resideOutsideOfPackage(p(root, "adapter.out.filesystem..")).or(resideInAPackage(p(root, "adapter.out.filesystem.codec..")));
  }

  /** Rule 8: JSON libraries and Spring only in adapters and config. */
  private static Rule rule8(String root) {
    String config = p(root, "config..");
    ArchRule r8 =
        noClasses().that().resideOutsideOfPackages(p(root, "adapter.."), config).should().dependOnClassesThat()
            .resideInAnyPackage(concat(SPRING, JSON))
            .as("rule 8: JSON libraries and Spring only in adapter and config");
    return new Rule(8, "JSON libraries and Spring only in adapters and config", Scope.MAIN, rule(r8), resideOutsideOfPackages(p(root, "adapter.."), config));
  }

  /** Rule 9: the contract DTO packages only in the inbound HTTP adapter. */
  private static Rule rule9(String root, List<String> rule9Packages) {
    String http = p(root, "adapter.in.http..");
    ArchRule r9 =
        noClasses().that().resideOutsideOfPackage(http).should().dependOnClassesThat().resideInAnyPackage(rule9Packages.toArray(String[]::new))
            .as("rule 9: generated and hand contract DTO packages only in adapter.in.http");
    return new Rule(9, "contract DTO packages only in adapter.in.http", Scope.MAIN, rule(r9), resideOutsideOfPackage(http));
  }

  /** Rule 10: no process creation. */
  private static Rule rule10() {
    ArchRule r10 =
        noClasses().should().dependOnClassesThat(DescribedPredicate.describe("ProcessBuilder", (JavaClass c) -> c.getName().equals("java.lang.ProcessBuilder")))
            .orShould().callMethodWhere(DescribedPredicate.describe("Runtime.exec", (JavaMethodCall c) -> c.getTargetOwner().getName().equals("java.lang.Runtime") && c.getName().equals("exec")))
            .as("rule 10: no ProcessBuilder and no Runtime.exec");
    return new Rule(10, "no process creation", Scope.MAIN, rule(r10), DescribedPredicate.alwaysTrue());
  }

  /** Rule 11: the port-level subset (test classes). */
  private static Rule rule11(String root) {
    String filesystem = p(root, "adapter.out.filesystem..");
    String codec = p(root, "adapter.out.filesystem.codec..");
    String testsupport = p(root, "testsupport..");
    ArchRule r11a =
        noClasses().that().resideInAPackage(p(root, "conformance.port..")).should().dependOnClassesThat().resideInAPackage(p(root, "adapter.."))
            .as("rule 11a: port-level classes depend on no adapter class");
    ArchRule r11b =
        noClasses().that().resideInAnyPackage(p(root, "conformance.port.."), p(root, "conformance.golden.."))
            .should().dependOnClassesThat().resideInAPackage(p(root, "adapter.."))
            .as("rule 11b: of the conformance trees, only testsupport imports an adapter class");
    ArchRule r11c =
        noClasses().that().resideOutsideOfPackages(testsupport, filesystem).should().dependOnClassesThat().resideInAPackage(codec)
            .as("rule 11c: of the test classes, only testsupport and adapter.out.filesystem itself use the codec");
    return new Rule(11, "the port-level subset is source-neutral", Scope.TEST, CompositeArchRule.of(rule(r11a)).and(rule(r11b)).and(rule(r11c)), resideInAPackage(p(root, "conformance.port..")));
  }

  /** Rule 12: the codec is pure decoding. */
  private static Rule rule12(String root) {
    String domain = p(root, "domain..");
    String filesystem = p(root, "adapter.out.filesystem..");
    String codec = p(root, "adapter.out.filesystem.codec..");
    String testsupport = p(root, "testsupport..");
    ArchRule r12a =
        noClasses().that().resideInAPackage(codec).should().dependOnClassesThat(
                resideInAPackage(root + "..").and(resideOutsideOfPackages(domain, codec)))
            .as("rule 12a: the codec depends, among project packages, only on domain and itself");
    ArchRule r12b =
        noClasses().that().resideInAPackage(codec).should().dependOnClassesThat(FILE_API).as("rule 12b: the codec uses no file API");
    ArchRule r12c =
        noClasses().that().resideOutsideOfPackages(filesystem, testsupport).should().dependOnClassesThat().resideInAPackage(codec)
            .as("rule 12c: the codec is used only by adapter.out.filesystem and testsupport");
    return new Rule(12, "the codec is pure decoding", Scope.MAIN, CompositeArchRule.of(rule(r12a)).and(rule(r12b)).and(rule(r12c)), resideInAPackage(codec));
  }

  /**
   * Rule 13: the query ports are interfaces only. Each class is judged by its outermost class, so a nested enum of an exception is judged as
   * the exception it sits in: (a) a class directly in {@code port.in} or {@code port.out} is an interface; (b) a class in a {@code dto}
   * package is not a Throwable; (c) a class in an {@code exceptions} package is a Throwable; (d) no other {@code port..} subpackage exists.
   */
  private static Rule rule13(String root) {
    String port = p(root, "application.query.port");
    ArchRule r13 =
        classes().that().resideInAPackage(port + "..").should(portLayout(port))
            .as("rule 13: ports are interfaces only (data in dto, exceptions in exceptions, nothing else under port)");
    return new Rule(13, "ports are interfaces only", Scope.MAIN, rule(r13), resideInAPackage(port + ".."));
  }

  private static ArchCondition<JavaClass> portLayout(String port) {
    return new ArchCondition<>("keep ports as interfaces, data in dto and exceptions in exceptions") {
      @Override
      public void check(JavaClass c, ConditionEvents events) {
        if (c.getSimpleName().equals("package-info")) {
          return;
        }
        JavaClass top = outermost(c);
        boolean throwable = top.isAssignableTo("java.lang.Throwable");
        String pkg = c.getPackageName();
        String problem = null;
        if (pkg.equals(port + ".in") || pkg.equals(port + ".out")) {
          if (!top.isInterface()) {
            problem = "is not an interface although it sits directly in " + pkg;
          }
        } else if (pkg.equals(port + ".in.dto") || pkg.equals(port + ".out.dto")) {
          if (throwable) {
            problem = "is a Throwable in a dto package";
          }
        } else if (pkg.equals(port + ".in.exceptions") || pkg.equals(port + ".out.exceptions")) {
          if (!throwable) {
            problem = "is not a Throwable in an exceptions package";
          }
        } else {
          problem = "sits in a port subpackage that is neither port.in, port.out nor their dto or exceptions";
        }
        if (problem != null) {
          events.add(SimpleConditionEvent.violated(c, c.getName() + " (outermost " + top.getName() + ") " + problem));
        }
      }
    };
  }

  /** Rule 14: the query side does not reach the command side. */
  private static Rule rule14(String root) {
    ArchRule r14 =
        noClasses().that().resideInAPackage(p(root, "application.query..")).should().dependOnClassesThat().resideInAPackage(p(root, "application.command.."))
            .as("rule 14: nothing in application.query depends on application.command");
    return new Rule(14, "the query side does not reach the command side", Scope.MAIN, rule(r14), resideInAPackage(p(root, "application.query..")));
  }

  /**
   * Rule 15: the controllers and mappers of the detail operations reach, among project packages, only the inbound port, the records and enums
   * of the read model they return and their own adapter. A non-record class of {@code domain.model} or {@code domain.readmodel.overview}
   * ({@code CodePoints}, {@code PyText}, {@code SupportedSchemaRange}, a deriver) is out: ordering, text and range work happens in the
   * application layer.
   */
  private static Rule rule15(String root) {
    String detail = p(root, "adapter.in.http.detail..");
    ArchRule r15 =
        classes().that().resideInAPackage(detail).should(onlyReachPortRecordsAndOwnAdapter(root))
            .as("rule 15: the detail adapter depends, among project packages, only on application.query.port.in, the records and enums of domain.model, domain.readmodel.overview and domain.readmodel.detail, and adapter.in.http");
    return new Rule(15, "the detail adapter reaches only the inbound port and read-model records", Scope.MAIN, rule(r15), resideInAPackage(detail));
  }

  private static ArchCondition<JavaClass> onlyReachPortRecordsAndOwnAdapter(String root) {
    return new ArchCondition<>("depend, among project packages, only on the inbound port, read-model records and enums, and adapter.in.http") {
      @Override
      public void check(JavaClass c, ConditionEvents events) {
        for (Dependency d : c.getDirectDependenciesFromSelf()) {
          JavaClass target = d.getTargetClass();
          String pkg = target.getPackageName();
          if (!inPackageOrBelow(pkg, root)) {
            continue;
          }
          boolean valueType = target.isRecord() || target.isEnum();
          boolean allowed =
              inPackageOrBelow(pkg, p(root, "application.query.port.in"))
                  || inPackageOrBelow(pkg, p(root, "adapter.in.http"))
                  || (valueType
                      && (pkg.equals(p(root, "domain.model")) || pkg.equals(p(root, "domain.readmodel.overview")) || pkg.equals(p(root, "domain.readmodel.detail"))));
          if (!allowed) {
            events.add(SimpleConditionEvent.violated(d, d.getDescription()));
          }
        }
      }
    };
  }

  /** The two inbound interfaces that predate the detail operations: the stream port may declare a checked exception, and is not a detail operation. */
  private static final Set<String> RULE_16_EXEMPT_FROM_B_AND_C = Set.of("MissionStatusQuery", "Subscription");

  /**
   * Rule 16: the inbound interfaces of the detail operations and the result types they return stay free of transport. Clause a: no Spring,
   * Jakarta, OpenAPI or generated package, in every class of {@code application.query.port.in..} (the stream vocabulary included) and
   * {@code domain.readmodel.detail..}. Clause b: no public method of those classes declares a checked exception (except the stream port:
   * {@code Subscription#next} declares {@code InterruptedException}). Clause c: no parameter of a public method of an interface directly
   * in {@code port.in} (the stream port excepted) is a {@code String}: an identifier is a typed value.
   */
  private static Rule rule16(String root, List<String> rule9Packages) {
    String port = p(root, "application.query.port.in..");
    String detail = p(root, "domain.readmodel.detail..");
    String portRoot = p(root, "application.query.port.in");
    String[] transport = concat(SPRING, new String[] {"jakarta..", "org.openapitools.."}, rule9Packages.toArray(String[]::new));
    DescribedPredicate<JavaClass> subject = resideInAnyPackage(port, detail);
    ArchRule r16a =
        noClasses().that().resideInAnyPackage(port, detail).should().dependOnClassesThat().resideInAnyPackage(transport)
            .as("rule 16a: no Spring, Jakarta, OpenAPI or generated package in the inbound port (stream vocabulary included) or the detail records");
    ArchRule r16b =
        classes().that(subject).and(DescribedPredicate.describe("not the stream port", (JavaClass c) -> !RULE_16_EXEMPT_FROM_B_AND_C.contains(outermost(c).getSimpleName())))
            .should(declareNoCheckedException())
            .as("rule 16b: no public method of the inbound port or the detail records declares a checked exception (the stream port excepted)");
    ArchRule r16c =
        classes().that().resideInAPackage(portRoot).and().areInterfaces()
            .and(DescribedPredicate.describe("not the stream port", (JavaClass c) -> !RULE_16_EXEMPT_FROM_B_AND_C.contains(c.getSimpleName())))
            .should(takeNoStringParameter())
            .as("rule 16c: no parameter of a public method of a detail inbound interface is a String");
    return new Rule(16, "the inbound detail ports are transport-free, unchecked and typed", Scope.MAIN, CompositeArchRule.of(rule(r16a)).and(rule(r16b)).and(rule(r16c)), subject);
  }

  private static ArchCondition<JavaClass> declareNoCheckedException() {
    return new ArchCondition<>("declare no checked exception on a public method") {
      @Override
      public void check(JavaClass c, ConditionEvents events) {
        for (JavaMethod method : c.getMethods()) {
          if (!method.getModifiers().contains(JavaModifier.PUBLIC)) {
            continue;
          }
          for (JavaClass thrown : method.getThrowsClause().getTypes()) {
            if (!thrown.isAssignableTo(RuntimeException.class) && !thrown.isAssignableTo(Error.class)) {
              events.add(SimpleConditionEvent.violated(method, method.getFullName() + " declares the checked exception " + thrown.getName()));
            }
          }
        }
      }
    };
  }

  private static ArchCondition<JavaClass> takeNoStringParameter() {
    return new ArchCondition<>("take no String parameter on a public method") {
      @Override
      public void check(JavaClass c, ConditionEvents events) {
        for (JavaMethod method : c.getMethods()) {
          if (!method.getModifiers().contains(JavaModifier.PUBLIC)) {
            continue;
          }
          for (JavaClass parameter : method.getRawParameterTypes()) {
            if (parameter.getName().equals("java.lang.String")) {
              events.add(SimpleConditionEvent.violated(method, method.getFullName() + " takes a String parameter"));
            }
          }
        }
      }
    };
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
        "a call of Executors.*, Thread.ofVirtual/ofPlatform/startVirtualThread, ForkJoinPool.commonPool, a CompletableFuture *Async method"
            + " without an executor, parallelStream() or BaseStream.parallel()",
        (JavaMethodCall call) -> {
          String owner = call.getTargetOwner().getName();
          String name = call.getName();
          return owner.equals("java.util.concurrent.Executors")
              || (owner.equals("java.lang.Thread") && THREAD_OWNER_METHODS.contains(name))
              || (owner.equals("java.util.concurrent.ForkJoinPool") && name.equals("commonPool"))
              || (owner.equals("java.util.concurrent.CompletableFuture") && name.endsWith("Async") && !takesAnExecutor(call))
              || name.equals("parallelStream")
              || (call.getTargetOwner().isAssignableTo(java.util.stream.BaseStream.class) && name.equals("parallel"));
        });
  }

  /** The async variants of CompletableFuture run on the common pool unless the call passes an executor. */
  private static boolean takesAnExecutor(JavaMethodCall call) {
    return call.getTarget().getRawParameterTypes().stream().anyMatch(type -> type.isAssignableTo(java.util.concurrent.Executor.class));
  }

  private static DescribedPredicate<JavaConstructorCall> threadCreatingConstructorCall() {
    return DescribedPredicate.describe(
        "the construction of a Thread, ThreadPoolExecutor, ForkJoinPool or Timer",
        (JavaConstructorCall call) ->
            call.getTargetOwner().isAssignableTo(Thread.class)
                || call.getTargetOwner().isAssignableTo(java.util.concurrent.ThreadPoolExecutor.class)
                || call.getTargetOwner().isAssignableTo(java.util.concurrent.ForkJoinPool.class)
                || call.getTargetOwner().isAssignableTo(java.util.Timer.class));
  }
}
