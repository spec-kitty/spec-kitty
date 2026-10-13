package org.speckitty.missionstatus.config.nativetags;

import static org.assertj.core.api.Assertions.assertThat;

import java.nio.file.Path;
import java.time.Duration;
import org.junit.jupiter.api.Tag;
import org.junit.jupiter.api.Test;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.beans.factory.config.BeanPostProcessor;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.boot.test.context.SpringBootTest;
import org.springframework.boot.test.context.TestConfiguration;
import org.springframework.context.annotation.Bean;
import org.springframework.context.annotation.Import;
import org.springframework.test.context.DynamicPropertyRegistry;
import org.springframework.test.context.DynamicPropertySource;
import org.speckitty.missionstatus.application.query.port.in.MissionStatusQuery;
import org.speckitty.missionstatus.config.MissionStatusApplication;
import org.speckitty.missionstatus.testsupport.http.SpyQuery;
import org.speckitty.missionstatus.testsupport.http.SseClient;

/**
 * AC-9h (native-tagged; runs on the JVM in {@code test} and natively through {@code nativeTest}): a test-profile probe records
 * {@code Thread.currentThread().isVirtual()} in the handler of {@code /api/v1/missions}, in the handler of the event stream and on the
 * connection's own thread. Fails if any records false.
 */
@Tag("native")
@SpringBootTest(classes = MissionStatusApplication.class, webEnvironment = SpringBootTest.WebEnvironment.RANDOM_PORT)
@Import(NativeVirtualThreadProbeTest.Probe.class)
class NativeVirtualThreadProbeTest {

  private static final Path ROOT = NativeProject.create();

  @DynamicPropertySource
  static void project(DynamicPropertyRegistry registry) {
    registry.add("mission-status.project-root", ROOT::toString);
  }

  /** Wraps the service in the recording seam; the controllers receive the wrapper. */
  @TestConfiguration(proxyBeanMethods = false)
  static class Probe {
    @Bean
    static BeanPostProcessor probeAroundTheQuery() {
      return new BeanPostProcessor() {
        @Override
        public Object postProcessAfterInitialization(Object bean, String beanName) {
          return bean instanceof MissionStatusQuery query && !(bean instanceof SpyQuery) ? new SpyQuery(query) : bean;
        }
      };
    }
  }

  @Value("${local.server.port}")
  int port;

  @Autowired MissionStatusQuery query;

  @Test
  void theMissionsHandlerTheStreamHandlerAndTheConnectionThreadAreVirtual() throws Exception {
    SpyQuery spy = (SpyQuery) query;
    java.net.http.HttpResponse<String> page =
        java.net.http.HttpClient.newHttpClient()
            .send(java.net.http.HttpRequest.newBuilder(java.net.URI.create("http://127.0.0.1:" + port + "/api/v1/missions")).GET().build(), java.net.http.HttpResponse.BodyHandlers.ofString());
    assertThat(page.statusCode()).isEqualTo(200);

    try (SseClient client = SseClient.open(port, "/api/v1/events?missionId=" + NativeProject.MISSION_ID)) {
      assertThat(client.status()).isEqualTo(200);
      long deadline = System.nanoTime() + Duration.ofSeconds(10).toNanos();
      while (spy.nextThreads().isEmpty() && System.nanoTime() < deadline) {
        Thread.sleep(20);
      }
    }

    assertThat(spy.missionsThreads()).as("the probe saw the missions handler").isNotEmpty().containsOnly(true);
    assertThat(spy.subscribeThreads()).as("the probe saw the stream handler").isNotEmpty().containsOnly(true);
    assertThat(spy.nextThreads()).as("the probe saw the connection's thread").isNotEmpty().containsOnly(true);
  }
}
