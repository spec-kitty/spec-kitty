package org.speckitty.missionstatus.config;

import static org.assertj.core.api.Assertions.assertThat;

import java.util.ArrayList;
import java.util.List;
import java.util.Map;
import org.junit.jupiter.api.Test;
import org.speckitty.missionstatus.application.query.AdmissionGate;
import org.speckitty.missionstatus.application.query.index.WorkPackageIndex;
import org.speckitty.missionstatus.application.query.port.in.ArtifactQuery;
import org.speckitty.missionstatus.application.query.port.in.MissionDetailQuery;
import org.speckitty.missionstatus.application.query.port.in.WorkPackageDetailQuery;
import org.speckitty.missionstatus.application.query.port.in.WorkPackageQuery;
import org.speckitty.missionstatus.application.query.port.out.FrontmatterDecoder;
import org.speckitty.missionstatus.application.query.port.out.LanesDecoder;
import org.speckitty.missionstatus.application.query.port.out.TextSource;
import org.speckitty.missionstatus.testsupport.FilesystemFixtureFactory;
import org.speckitty.missionstatus.testsupport.FixtureSpec;
import org.speckitty.missionstatus.testsupport.http.HttpHarness;
import org.springframework.beans.factory.ListableBeanFactory;
import org.springframework.boot.test.context.runner.ApplicationContextRunner;
import org.springframework.context.annotation.Bean;
import org.springframework.context.annotation.Configuration;

/**
 * The single-owner guard for the shared beans (TASKS-FRESH2-001): over the full production application, exactly one bean of each shared type.
 * A wiring class other than the owner that declares a second one makes the same assertion helper fail; the control plants one in a throwaway
 * context. Owners: {@code WorkPackageIndex} (WP13), {@code TextSource} and {@code AdmissionGate} (WP12), the two decoders (WP11), and one
 * query per route family.
 */
class SharedBeansUniqueTest {

  /** The shared types of the guard. */
  static final List<Class<?>> SHARED =
      List.of(
          WorkPackageIndex.class,
          TextSource.class,
          AdmissionGate.class,
          FrontmatterDecoder.class,
          LanesDecoder.class,
          MissionDetailQuery.class,
          WorkPackageQuery.class,
          WorkPackageDetailQuery.class,
          ArtifactQuery.class);

  /** The types that do not have exactly one bean in this factory, with how many they have. */
  static Map<Class<?>, Integer> notUnique(ListableBeanFactory factory) {
    Map<Class<?>, Integer> bad = new java.util.LinkedHashMap<>();
    for (Class<?> type : SHARED) {
      int count = factory.getBeansOfType(type).size();
      if (count != 1) {
        bad.put(type, count);
      }
    }
    return bad;
  }

  @Test
  void theFullApplicationHoldsExactlyOneBeanOfEachSharedType() {
    assertThat(SHARED).hasSize(9);
    try (HttpHarness server = HttpHarness.startWired(FilesystemFixtureFactory.fromSpec(FixtureSpec.of()).root())) {
      assertThat(notUnique(server.context())).isEmpty();
    }
  }

  /** A second definition of a shared bean, as a wiring class other than the owner would declare it. */
  @Configuration(proxyBeanMethods = false)
  static class SecondAdmissionGate {
    @Bean
    AdmissionGate first() {
      return new AdmissionGate();
    }

    @Bean
    AdmissionGate second() {
      return new AdmissionGate();
    }
  }

  @Test
  void controlASecondDefinitionOfASharedBeanFailsTheSameHelper() {
    List<Map<Class<?>, Integer>> seen = new ArrayList<>();
    new ApplicationContextRunner().withUserConfiguration(SecondAdmissionGate.class).run(context -> seen.add(notUnique(context)));

    assertThat(seen).hasSize(1);
    assertThat(seen.get(0)).containsEntry(AdmissionGate.class, 2);
  }
}
