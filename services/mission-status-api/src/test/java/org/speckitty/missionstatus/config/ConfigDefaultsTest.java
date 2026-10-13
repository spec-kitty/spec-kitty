package org.speckitty.missionstatus.config;

import static org.assertj.core.api.Assertions.assertThat;

import java.net.InetAddress;
import java.nio.file.Path;
import java.time.Duration;
import java.util.Arrays;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.extension.ExtendWith;
import org.speckitty.missionstatus.application.query.MissionStatusQueryService;
import org.speckitty.missionstatus.application.query.port.in.MissionStatusQuery;
import org.speckitty.missionstatus.domain.redaction.LeakClasses;
import org.speckitty.missionstatus.testsupport.FilesystemFixtureFactory;
import org.speckitty.missionstatus.testsupport.LeakPatternsFile;
import org.speckitty.missionstatus.testsupport.http.HttpHarness;
import org.springframework.boot.test.system.CapturedOutput;
import org.springframework.boot.test.system.OutputCaptureExtension;
import org.springframework.boot.web.server.WebServer;
import org.springframework.boot.web.server.context.WebServerApplicationContext;
import org.springframework.core.env.EnumerablePropertySource;
import org.springframework.web.filter.ForwardedHeaderFilter;

/**
 * The effective configuration of the running application (AC-9a read-back, T057 step 4): loopback bind, no proxy trust, the wiring
 * beans, the heartbeat key and the path-free diagnostics line.
 */
@ExtendWith(OutputCaptureExtension.class)
class ConfigDefaultsTest {

  private static HttpHarness server() {
    return HttpHarness.startWired(FilesystemFixtureFactory.fromSpec(org.speckitty.missionstatus.testsupport.FixtureSpec.of()).root());
  }

  @Test
  void theEffectiveAddressIsLoopbackAndTheConnectorIsBoundToIt() throws Exception {
    try (HttpHarness server = server()) {
      assertThat(server.context().getEnvironment().getProperty("server.address")).isEqualTo("127.0.0.1");
      WebServer webServer = ((WebServerApplicationContext) server.context()).getWebServer();
      assertThat(BindGuard.configuredAddress(webServer)).isEqualTo(InetAddress.getByName("127.0.0.1"));
      assertThat(BindGuard.connectorRefusal(BindGuard.configuredAddress(webServer))).isEmpty();
    }
  }

  @Test
  void noProxyHeaderIsTrusted() {
    try (HttpHarness server = server()) {
      assertThat(server.context().getEnvironment().getProperty("server.forward-headers-strategy")).isEqualTo("none");
      assertThat(server.context().getBeanNamesForType(ForwardedHeaderFilter.class)).isEmpty();
      long remoteIp =
          server.context().getEnvironment().getPropertySources().stream()
              .filter(EnumerablePropertySource.class::isInstance)
              .flatMap(source -> Arrays.stream(((EnumerablePropertySource<?>) source).getPropertyNames()))
              .filter(name -> name.startsWith("server.tomcat.remoteip"))
              .count();
      assertThat(remoteIp).isZero();
    }
  }

  @Test
  void theWiringBeansExistAndTheStreamKeysHaveTheirDefaults() {
    try (HttpHarness server = server()) {
      assertThat(server.context().getBean(MissionStatusQuery.class)).isInstanceOf(MissionStatusQueryService.class);
      MissionStatusProperties properties = server.context().getBean(MissionStatusProperties.class);
      assertThat(properties.stream().queueCapacity()).isEqualTo(1024);
      assertThat(properties.stream().heartbeatInterval()).isEqualTo(Duration.ofSeconds(30));
      assertThat(server.context().getEnvironment().getProperty("spring.threads.virtual.enabled")).isEqualTo("true");
    }
  }

  @Test
  void theLeakClassesComeFromTheCommittedFileThroughTheOneCompiler() {
    try (HttpHarness server = server()) {
      LeakClasses wired = server.context().getBean(LeakClasses.class);
      LeakClasses expected = LeakPatternsFile.load();
      assertThat(wired.strictHostPaths()).extracting(java.util.regex.Pattern::pattern).isEqualTo(expected.strictHostPaths().stream().map(java.util.regex.Pattern::pattern).toList());
      assertThat(wired.humanHostPaths()).extracting(java.util.regex.Pattern::pattern).isEqualTo(expected.humanHostPaths().stream().map(java.util.regex.Pattern::pattern).toList());
      assertThat(wired.secrets()).extracting(java.util.regex.Pattern::pattern).isEqualTo(expected.secrets().stream().map(java.util.regex.Pattern::pattern).toList());
      assertThat(wired.email().pattern()).isEqualTo(expected.email().pattern());
      assertThat(wired.emailAnchored().pattern()).isEqualTo(expected.emailAnchored().pattern());
    }
  }

  @Test
  void aDiagnosticIsOneLineWithTheCodeAndMid8AndNoPathOrLineText(CapturedOutput output) {
    try (HttpHarness server = server()) {
      @SuppressWarnings("unchecked")
      java.util.function.Consumer<org.speckitty.missionstatus.domain.model.Diagnostic> diagnostics =
          (java.util.function.Consumer<org.speckitty.missionstatus.domain.model.Diagnostic>) server.context().getBean("diagnosticsLine");
      diagnostics.accept(new org.speckitty.missionstatus.domain.model.Diagnostic(org.speckitty.missionstatus.domain.model.DiagnosticCode.LEDGER_UNPARSEABLE, "01J01000", 3));
      String line = output.getAll().lines().filter(l -> l.contains("ledger_unparseable")).findFirst().orElseThrow();
      assertThat(line).contains("01J01000").contains("3").doesNotContain("/").doesNotContain("kitty-specs");
    }
  }
}
