package org.speckitty.missionstatus.architecture;

import static com.tngtech.archunit.lang.syntax.ArchRuleDefinition.classes;
import static com.tngtech.archunit.lang.syntax.ArchRuleDefinition.noClasses;
import static org.assertj.core.api.Assertions.assertThat;

import com.tngtech.archunit.core.domain.JavaClass;
import com.tngtech.archunit.core.domain.JavaClasses;
import java.lang.reflect.Method;
import java.lang.reflect.Modifier;
import java.util.Arrays;
import java.util.List;
import java.util.Set;
import java.util.TreeSet;
import java.util.stream.Collectors;
import java.util.stream.StreamSupport;
import org.junit.jupiter.api.Test;
import org.speckitty.missionstatus.testsupport.PortLevelIds;
import org.speckitty.missionstatus.testsupport.PortLevelIds.Entry;
import org.speckitty.missionstatus.testsupport.PortLevelTest;

/**
 * AC-13b, the scan half (the import half is rule 11 and its controls): the classes of {@code ..conformance.port..} are exactly the
 * classes the id list names, every one of them obtains its query from the one selector, none names a source, and every id is carried by
 * the method it names. The scan is non-empty.
 */
class PortLevelClassSetTest {

  private static final JavaClasses TESTS = ArchitectureRules.testClasses();
  private static final String PORT = PortLevelIds.PORT_PACKAGE;

  private static Set<String> topLevelPortClasses(JavaClasses classes) {
    return StreamSupport.stream(classes.spliterator(), false)
        .filter(c -> inPortTree(c) && c.getEnclosingClass().isEmpty())
        .map(JavaClass::getName)
        .collect(Collectors.toCollection(TreeSet::new));
  }

  private static boolean inPortTree(JavaClass c) {
    return c.getPackageName().equals(PORT) || c.getPackageName().startsWith(PORT + ".");
  }

  /** What differs between the scanned classes and the named ones: the empty set when they are equal. */
  static Set<String> differences(Set<String> scanned, Set<String> named) {
    Set<String> differences = new TreeSet<>();
    scanned.stream().filter(name -> !named.contains(name)).forEach(name -> differences.add("scanned but not named: " + name));
    named.stream().filter(name -> !scanned.contains(name)).forEach(name -> differences.add("named but not scanned: " + name));
    return differences;
  }

  @Test
  void theScannedPortLevelClassesAreNonEmptyAndEqualTheClassesTheIdListNames() {
    Set<String> scanned = topLevelPortClasses(TESTS);
    Set<String> named = new TreeSet<>(PortLevelIds.classNames(PortLevelIds.load()));

    assertThat(scanned).as("the scan of ..conformance.port.. is non-empty").isNotEmpty();
    assertThat(differences(scanned, named)).isEmpty();
  }

  @Test
  void theEqualityCheckCatchesAStrayClassAndAMissingOne() {
    Set<String> named = new TreeSet<>(PortLevelIds.classNames(PortLevelIds.load()));
    Set<String> withStray = new TreeSet<>(named);
    withStray.add(PORT + ".StrayHelper");
    Set<String> withMissing = new TreeSet<>(named);
    withMissing.remove(named.iterator().next());

    assertThat(differences(withStray, named)).containsExactly("scanned but not named: " + PORT + ".StrayHelper");
    assertThat(differences(withMissing, named)).hasSize(1).first().asString().startsWith("named but not scanned");
  }

  @Test
  void thePortLevelPackageHoldsNoNestedClass() {
    assertThat(StreamSupport.stream(TESTS.spliterator(), false).filter(c -> inPortTree(c) && c.getEnclosingClass().isPresent()).map(JavaClass::getName)).isEmpty();
  }

  @Test
  void everyPortLevelClassAsksTheSelectorAndNoneNamesASource() {
    String selectorHolders = "org.speckitty.missionstatus.testsupport.PortSourceSelector";
    String fixtureHelper = "org.speckitty.missionstatus.testsupport.PortFixtures";

    classes().that().resideInAPackage(PORT).should().dependOnClassesThat().haveFullyQualifiedName(selectorHolders)
        .orShould().dependOnClassesThat().haveFullyQualifiedName(fixtureHelper)
        .as("every port-level class obtains its query through the selector (directly or through PortFixtures, which only calls it)")
        .check(TESTS);

    noClasses().that().resideInAPackage(PORT).should().dependOnClassesThat().haveSimpleNameEndingWith("FixtureFactory")
        .orShould().dependOnClassesThat().haveSimpleNameStartingWith("InMemory")
        .orShould().dependOnClassesThat().haveFullyQualifiedName("org.speckitty.missionstatus.application.query.MissionStatusQueryService")
        .as("no port-level class constructs a factory, a service or a source")
        .check(TESTS);
  }

  @Test
  void theFixtureHelperOnlyReachesTheSourceThroughTheSelector() {
    noClasses().that().haveFullyQualifiedName("org.speckitty.missionstatus.testsupport.PortFixtures")
        .should().dependOnClassesThat().haveSimpleNameEndingWith("FixtureFactory")
        .orShould().dependOnClassesThat().haveSimpleNameStartingWith("InMemory")
        .check(TESTS);
  }

  @Test
  void everyIdIsCarriedByTheMethodItNamesAndNoAnnotatedMethodIsUnlisted() throws ClassNotFoundException {
    List<Entry> entries = PortLevelIds.load();
    Set<String> annotated = new TreeSet<>();

    for (String className : PortLevelIds.classNames(entries)) {
      Class<?> type = Class.forName(className);
      assertThat(Modifier.isPublic(type.getModifiers())).as("%s is public", type.getSimpleName()).isTrue();
      assertThat(type.getDeclaredConstructors()).as("%s has one public no-arg constructor", type.getSimpleName()).allSatisfy(c -> {
        assertThat(c.getParameterCount()).isZero();
        assertThat(Modifier.isPublic(c.getModifiers())).isTrue();
      });
      for (Method method : type.getDeclaredMethods()) {
        assertThat(Arrays.stream(method.getAnnotations()).map(a -> a.annotationType().getSimpleName()))
            .as("%s#%s is a plain method: no lifecycle or parameterised-test annotation", type.getSimpleName(), method.getName())
            .noneMatch(name -> Set.of("BeforeEach", "AfterEach", "BeforeAll", "AfterAll", "ParameterizedTest", "RepeatedTest", "TestFactory", "Nested").contains(name));
        PortLevelTest marker = method.getAnnotation(PortLevelTest.class);
        if (marker != null) {
          assertThat(method.getParameterCount()).as("%s#%s takes no parameter", type.getSimpleName(), method.getName()).isZero();
          assertThat(Modifier.isPublic(method.getModifiers())).isTrue();
          annotated.add(marker.value() + " " + type.getSimpleName() + "#" + method.getName());
        }
      }
    }

    Set<String> listed = entries.stream().map(e -> e.id() + " " + e.className() + "#" + e.method()).collect(Collectors.toCollection(TreeSet::new));
    assertThat(annotated).as("annotated methods versus the lines of portlevel-tests.txt").isEqualTo(listed);
  }
}
