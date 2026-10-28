package org.speckitty.missionstatus.architecture;

import static org.assertj.core.api.Assertions.assertThat;

import com.tngtech.archunit.core.domain.JavaClass;
import java.util.List;
import org.junit.jupiter.api.Test;

/**
 * Rule 7 exempts {@code adapter.out.ledger} by package name. The exemption is meant for event-log's ledger file mechanics only, so every
 * production class in that package must come from the event-log module: a query-service class placed there would otherwise get file APIs.
 */
class LedgerExemptionScopeTest {

  @Test
  void onlyEventLogClassesSitInTheExemptedLedgerPackage() {
    List<JavaClass> ledger =
        ArchitectureRules.mainClasses().stream().filter(c -> c.getPackageName().startsWith(ArchitectureRules.ROOT + ".adapter.out.ledger")).toList();
    assertThat(ledger).as("the ledger package is on the classpath (non-vacuous)").isNotEmpty();
    assertThat(ledger)
        .allSatisfy(c -> assertThat(c.getSource().orElseThrow().getUri().toString()).as(c.getName()).contains("event-log"));
  }
}
