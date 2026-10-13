package org.speckitty.missionstatus.adapter.in.http.hostorigin;

import static org.assertj.core.api.Assertions.assertThat;

import jakarta.servlet.DispatcherType;
import java.util.EnumSet;
import java.util.Map;
import org.junit.jupiter.api.AfterAll;
import org.junit.jupiter.api.BeforeAll;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.TestInstance;
import org.speckitty.missionstatus.adapter.in.http.OwnPortSource;
import org.springframework.boot.web.servlet.FilterRegistrationBean;
import org.springframework.core.Ordered;

/**
 * Where the guard sits. Every request meets a servlet filter before it meets the dispatcher servlet, so the order among filters is not
 * visible from outside; it is pinned here on the registration instead (the highest precedence, every path, one pass per request), and
 * the own-port seam is the bound port of the server.
 */
@TestInstance(TestInstance.Lifecycle.PER_CLASS)
class RegistrationTest {

  private HostOriginRig server;

  @BeforeAll
  void start() {
    server = HostOriginRig.start();
  }

  @AfterAll
  void stop() {
    server.close();
  }

  @Test
  @SuppressWarnings("rawtypes")
  void theGuardIsRegisteredAtTheHighestPrecedenceOnEveryPathForTheRequestDispatch() {
    Map<String, FilterRegistrationBean> registrations = server.stream().http.context().getBeansOfType(FilterRegistrationBean.class);
    FilterRegistrationBean guard = registrations.get("hostOriginFilter");
    assertThat(guard).as("the registration bean").isNotNull();
    assertThat(guard.getOrder()).isEqualTo(Ordered.HIGHEST_PRECEDENCE);
    assertThat(guard.getUrlPatterns()).containsExactly("/*");
    assertThat(guard.isEnabled()).isTrue();
    assertThat(guard.determineDispatcherTypes()).isEqualTo(EnumSet.of(DispatcherType.REQUEST, DispatcherType.ERROR));
    assertThat(registrations.values()).as("no other registration precedes the guard").allSatisfy(other -> assertThat(other.getOrder()).isGreaterThanOrEqualTo(guard.getOrder()));
  }

  @Test
  void theOwnPortIsTheBoundPortOfTheServer() {
    OwnPortSource source = server.stream().http.context().getBean(OwnPortSource.class);
    assertThat(source.port()).isEqualTo(server.port()).isPositive();
  }
}
