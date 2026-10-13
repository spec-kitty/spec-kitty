package org.speckitty.missionstatus.adapter.in.http.contractdoc;

import static org.assertj.core.api.Assertions.assertThat;
import static org.assertj.core.api.Assertions.assertThatThrownBy;

import org.junit.jupiter.api.Test;
import org.junit.jupiter.params.ParameterizedTest;
import org.junit.jupiter.params.provider.ValueSource;
import org.speckitty.missionstatus.adapter.in.http.rest.ContractRoutes;
import org.speckitty.missionstatus.testsupport.http.HttpHarness;
import org.springframework.core.env.ConfigurableEnvironment;
import org.springframework.core.env.EnumerablePropertySource;

/** E-11: no springdoc anywhere. The documentation routes are not served, and no springdoc class or property exists at runtime. */
class SpringdocAbsentTest {

  @ParameterizedTest
  @ValueSource(strings = {"/v3/api-docs", "/v3/api-docs.yaml", "/swagger-ui.html", "/swagger-ui/index.html", "/api/v1/v3/api-docs"})
  void theGeneratedDocumentationRoutesAnswer404(String path) {
    try (HttpHarness server = HttpHarness.start(ContractRoutes.anyFixture())) {
      assertThat(server.get(path).status()).isEqualTo(404);
    }
  }

  @Test
  void noSpringdocClassIsOnTheRuntimeClasspath() {
    assertThatThrownBy(() -> Class.forName("org.springdoc.core.configuration.SpringDocConfiguration")).isInstanceOf(ClassNotFoundException.class);
    assertThatThrownBy(() -> Class.forName("org.springdoc.webmvc.ui.SwaggerConfig")).isInstanceOf(ClassNotFoundException.class);
  }

  @Test
  void noSpringdocPropertyIsInTheEffectiveEnvironment() {
    try (HttpHarness server = HttpHarness.start(ContractRoutes.anyFixture())) {
      ConfigurableEnvironment environment = server.context().getEnvironment();
      long keys =
          environment.getPropertySources().stream()
              .filter(EnumerablePropertySource.class::isInstance)
              .flatMap(source -> java.util.Arrays.stream(((EnumerablePropertySource<?>) source).getPropertyNames()))
              .filter(name -> name.startsWith("springdoc"))
              .count();
      assertThat(keys).isZero();
    }
  }
}
