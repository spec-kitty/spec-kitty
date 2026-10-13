package org.speckitty.missionstatus.config.nativetags;

import static org.assertj.core.api.Assertions.assertThat;

import java.net.URI;
import java.net.http.HttpClient;
import java.net.http.HttpRequest;
import java.net.http.HttpResponse;
import java.nio.file.Path;
import org.junit.jupiter.api.Tag;
import org.junit.jupiter.api.Test;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.boot.test.context.SpringBootTest;
import org.springframework.core.io.Resource;
import org.springframework.core.io.ResourceLoader;
import org.springframework.test.context.DynamicPropertyRegistry;
import org.springframework.test.context.DynamicPropertySource;
import org.speckitty.missionstatus.config.MissionStatusApplication;

/** The classpath resources the code reads by name are present in the native image and are the bytes the service serves. */
@Tag("native")
@SpringBootTest(classes = MissionStatusApplication.class, webEnvironment = SpringBootTest.WebEnvironment.RANDOM_PORT)
class NativeContractResourceTest {

  private static final Path ROOT = NativeProject.create();

  @DynamicPropertySource
  static void project(DynamicPropertyRegistry registry) {
    registry.add("mission-status.project-root", ROOT::toString);
  }

  @Value("${local.server.port}")
  int port;

  @Autowired ResourceLoader resourceLoader;

  @Test
  void theBundledContractAndTheLeakPatternsAreReadableAndTheDocumentIsServedUnchanged() throws Exception {
    Resource contract = resourceLoader.getResource("classpath:contract/openapi.yaml");
    Resource patterns = resourceLoader.getResource("classpath:leak-patterns.json");
    assertThat(contract.exists()).isTrue();
    assertThat(patterns.exists()).isTrue();

    HttpResponse<byte[]> served =
        HttpClient.newHttpClient().send(HttpRequest.newBuilder(URI.create("http://127.0.0.1:" + port + "/api/v1/openapi.yaml")).GET().build(), HttpResponse.BodyHandlers.ofByteArray());

    assertThat(served.statusCode()).isEqualTo(200);
    assertThat(served.body()).isEqualTo(contract.getContentAsByteArray());
  }
}
