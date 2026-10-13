package org.speckitty.missionstatus.adapter.in.http.contractdoc;

import static org.assertj.core.api.Assertions.assertThat;
import static org.junit.jupiter.api.Assumptions.assumeTrue;

import java.io.IOException;
import java.nio.file.Files;
import java.nio.file.Path;
import java.util.concurrent.TimeUnit;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.io.TempDir;
import org.springframework.core.io.ClassPathResource;
import org.speckitty.missionstatus.testsupport.FilesystemFixtureFactory;
import org.speckitty.missionstatus.testsupport.http.HttpHarness;
import org.speckitty.missionstatus.adapter.in.http.rest.ContractRoutes;

/**
 * AC-11d (E-11, contract first): GET /api/v1/openapi.yaml answers the committed contract document with the bytes UNCHANGED. A document
 * generated from controllers, a hand-copied stale copy, or one altered byte is red: the bytes served must equal what the contract tooling
 * (bundle.py, run into a directory outside the repository) writes for the same commit.
 */
class ContractDocumentTest {

  @Test
  void theRouteServesTheBundledResourceByteForByteWithAnYamlType() throws IOException {
    byte[] bundled = new ClassPathResource("contract/openapi.yaml").getContentAsByteArray();
    assertThat(bundled).isNotEmpty();
    try (HttpHarness server = HttpHarness.start(ContractRoutes.anyFixture())) {
      HttpHarness.Response response = server.get("/api/v1/openapi.yaml");
      assertThat(response.status()).isEqualTo(200);
      assertThat(response.header("Content-Type")).containsIgnoringCase("yaml");
      assertThat(response.body()).isEqualTo(bundled);
    }
  }

  @Test
  void theServedBytesEqualTheBundleTheContractToolingWritesForThisCommit(@TempDir Path out) throws Exception {
    Path contractRoot = Path.of(System.getProperty("user.dir")).resolve("../../contracts").normalize();
    boolean tooling = Files.isRegularFile(contractRoot.resolve("tools/bundle.py"));
    boolean python = false;
    if (tooling) {
      try {
        Process probe = new ProcessBuilder("python3", "-c", "import yaml").redirectErrorStream(true).start();
        python = probe.waitFor(60, TimeUnit.SECONDS) && probe.exitValue() == 0;
      } catch (IOException noInterpreter) {
        python = false;
      }
    }
    if (System.getenv("CI") != null) {
      // Under CI the comparison is the AC-11d proof: a missing tool is a failure, never a skip.
      assertThat(tooling && python).as("AC-11d under CI needs the contract tooling and python3 with PyYAML").isTrue();
    }
    assumeTrue(tooling && python, "the contract tooling and python3 with PyYAML are available");
    Process bundler =
        new ProcessBuilder("python3", contractRoot.resolve("tools/bundle.py").toString(), "--root", contractRoot.toString(), "--out", out.toString(), "--module", "mission-status", "--bundle-only")
            .redirectErrorStream(true)
            .start();
    String log = new String(bundler.getInputStream().readAllBytes());
    assertThat(bundler.waitFor(300, TimeUnit.SECONDS)).as("bundler finished").isTrue();
    assertThat(bundler.exitValue()).as(log).isZero();
    byte[] written = Files.readAllBytes(out.resolve("bundle/mission-status/openapi.yaml"));
    try (HttpHarness server = HttpHarness.start(ContractRoutes.anyFixture())) {
      assertThat(server.get("/api/v1/openapi.yaml").body()).as("served bytes against the freshly bundled document").isEqualTo(written);
    }
  }

  @Test
  void aWrongMethodOrPathVariantIsNotTheDocument() {
    try (HttpHarness server = HttpHarness.start(ContractRoutes.anyFixture())) {
      assertThat(server.get("/api/v1/openapi.json").status()).isEqualTo(404);
      assertThat(server.get("/openapi.yaml").status()).isEqualTo(404);
    }
  }
}
