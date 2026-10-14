package org.speckitty.missionstatus.architecture;

import static com.tngtech.archunit.core.domain.JavaClass.Predicates.belongToAnyOf;
import static com.tngtech.archunit.core.domain.JavaClass.Predicates.resideInAPackage;
import static com.tngtech.archunit.lang.syntax.ArchRuleDefinition.noClasses;
import static org.assertj.core.api.Assertions.assertThat;

import com.tngtech.archunit.core.domain.JavaClasses;
import com.tngtech.archunit.core.importer.ClassFileImporter;
import com.tngtech.archunit.lang.ArchRule;
import java.util.List;
import java.util.stream.Stream;
import org.junit.jupiter.api.DynamicTest;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.TestFactory;
import org.speckitty.missionstatus.architecture.fixture.application.query.port.in.LeakyLedgerLine;
import org.speckitty.missionstatus.architecture.fixture.application.query.port.in.LeakyLifecycleEvent;
import org.speckitty.missionstatus.architecture.fixture.application.query.port.in.LeakyQuery;
import org.speckitty.missionstatus.architecture.fixture.application.query.port.in.LeakyStatusEvent;
import org.speckitty.missionstatus.domain.model.LedgerLine;
import org.speckitty.missionstatus.domain.model.LifecycleEvent;
import org.speckitty.missionstatus.domain.model.LineKind;
import org.speckitty.missionstatus.domain.model.StatusEvent;

/**
 * Ruling item 1, enforced for types: the inbound port exposes no raw ledger row. No class of {@code application.query.port.in..}
 * depends on {@code LineKind}, {@code StatusEvent}, {@code LifecycleEvent} or {@code LedgerLine}. The planted {@link LeakyQuery} shows the
 * predicate bites, so the production result is not a vacuous green.
 */
class PortExposesNoLedgerRowTest {

  /** The production port.in classes read off the tip (24 classes measured, nested included); a floor, never an equality, so later phases can add port classes. */
  private static final long PRODUCTION_PORT_IN_CLASS_FLOOR = 24;

  private static ArchRule portExposesNoLedgerRow(String portInPackage) {
    return noClasses().that(resideInAPackage(portInPackage + "..")).should().dependOnClassesThat(belongToAnyOf(LineKind.class, StatusEvent.class, LifecycleEvent.class, LedgerLine.class))
        .as("the inbound port exposes no raw ledger row (LineKind, StatusEvent, LifecycleEvent, LedgerLine)")
        .allowEmptyShould(true);
  }

  private static long scanned(JavaClasses classes, String portInPackage) {
    return classes.stream().filter(resideInAPackage(portInPackage + "..")).count();
  }

  @Test
  void theProductionInboundPortExposesNoLedgerRow() {
    JavaClasses main = ArchitectureRules.mainClasses();
    String portIn = ArchitectureRules.ROOT + ".application.query.port.in";

    assertThat(scanned(main, portIn)).as("classes scanned in application.query.port.in..").isGreaterThanOrEqualTo(PRODUCTION_PORT_IN_CLASS_FLOOR);
    assertThat(portExposesNoLedgerRow(portIn).evaluate(main).hasViolation()).as(portExposesNoLedgerRow(portIn).evaluate(main).getFailureReport().toString()).isFalse();
  }

  @TestFactory
  Stream<DynamicTest> aPortMethodReturningEachBannedTypeIsReported() {
    String portIn = "org.speckitty.missionstatus.architecture.fixture.application.query.port.in";
    return List.<Class<?>>of(LeakyQuery.class, LeakyStatusEvent.class, LeakyLifecycleEvent.class, LeakyLedgerLine.class).stream()
        .map(
            leaky ->
                DynamicTest.dynamicTest(
                    leaky.getSimpleName(),
                    () -> {
                      JavaClasses planted = new ClassFileImporter().importClasses(leaky);

                      assertThat(scanned(planted, portIn)).isGreaterThan(0);
                      assertThat(portExposesNoLedgerRow(portIn).evaluate(planted).hasViolation()).isTrue();
                    }));
  }
}
