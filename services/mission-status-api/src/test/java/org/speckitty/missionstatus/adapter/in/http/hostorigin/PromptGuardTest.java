package org.speckitty.missionstatus.adapter.in.http.hostorigin;

import static org.assertj.core.api.Assertions.assertThat;

import java.io.IOException;
import java.nio.file.Files;
import java.nio.file.Path;
import java.util.List;
import org.junit.jupiter.api.AfterAll;
import org.junit.jupiter.api.BeforeAll;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.TestInstance;
import org.junit.jupiter.params.ParameterizedTest;
import org.junit.jupiter.params.provider.ValueSource;
import org.speckitty.missionstatus.application.query.detail.DetailRoute;
import org.speckitty.missionstatus.testsupport.http.RawClient;

/**
 * AC-9.3, the guard flow for the prompt variant (the multi-route AC that WP14 defers to this work package): {@code getWorkPackage?includePrompt=true}
 * is the one request that serves a Work Package body. Over the shared Host/Origin rig, a refused Host or Origin answers 403 {@code request_refused}
 * with no prompt byte in the reply and zero recorded reads (and the filter was entered once), while the accepted {@code 127.0.0.1:<port>} and
 * {@code localhost:<port>} Hosts get 200 with the {@code promptMarkdown} bytes. The prompt carries a marker that is found in the accepted replies,
 * so the absence in the refused ones is not vacuous.
 */
@TestInstance(TestInstance.Lifecycle.PER_CLASS)
class PromptGuardTest {

  private static final String MARKER = "PROMPT-BYTES-MARKER-18";

  private HostOriginRig server;

  @BeforeAll
  void start() throws IOException {
    server = HostOriginRig.start();
    Path mission = server.stream().built.root().resolve("kitty-specs").resolve("canary-mission");
    Files.createDirectories(mission.resolve("tasks"));
    Files.writeString(mission.resolve("tasks/WP01-guard.md"), DetailRoute.wpFile("WP01", "Guard") + "\nThe body holds " + MARKER + ".\n");
    server.stream().built.handles().allowlistRecorder().clear();
  }

  @AfterAll
  void stop() {
    server.close();
  }

  @ParameterizedTest(name = "foreign Host {0}")
  @ValueSource(strings = {"evil.example", "127.0.0.1", "localhost", "[::1]"})
  void aRefusedHostGetsNoPromptByteAndNoRead(String host) {
    int entriesBefore = server.counter.entries();
    int readsBefore = server.reads();
    String hostHeader = host.equals("127.0.0.1") || host.equals("localhost") ? host + ":" + (server.port() + 1) : host + ":" + server.port();

    RawClient.Reply reply = server.send("GET " + HostOriginRig.PROMPT_TARGET + " HTTP/1.1", "Host: " + hostHeader);

    assertThat(reply.status()).isEqualTo(403);
    assertThat(HostOriginRig.body(reply)).contains("\"code\":\"request_refused\"").doesNotContain(MARKER).doesNotContain("promptMarkdown");
    assertThat(reply.text()).doesNotContain(MARKER);
    assertThat(server.counter.entries() - entriesBefore).as("the filter was entered once").isEqualTo(1);
    assertThat(server.reads() - readsBefore).as("no recorded read and no port call").isZero();
  }

  @ParameterizedTest(name = "foreign Origin {0}")
  @ValueSource(strings = {"https://evil.example", "null", "http://127.0.0.1.evil.example"})
  void aRefusedOriginGetsNoPromptByteAndNoRead(String origin) {
    int entriesBefore = server.counter.entries();
    int readsBefore = server.reads();

    RawClient.Reply reply = server.send("GET " + HostOriginRig.PROMPT_TARGET + " HTTP/1.1", "Host: 127.0.0.1:" + server.port(), "Origin: " + origin);

    assertThat(reply.status()).isEqualTo(403);
    assertThat(reply.text()).doesNotContain(MARKER).doesNotContain("promptMarkdown");
    assertThat(server.counter.entries() - entriesBefore).isEqualTo(1);
    assertThat(server.reads() - readsBefore).isZero();
  }

  @ParameterizedTest(name = "accepted Host {0}")
  @ValueSource(strings = {"127.0.0.1", "localhost"})
  void theAcceptedHostsGet200WithThePromptBytes(String host) {
    RawClient.Reply reply = server.send("GET " + HostOriginRig.PROMPT_TARGET + " HTTP/1.1", "Host: " + host + ":" + server.port());

    assertThat(reply.status()).isEqualTo(200);
    assertThat(HostOriginRig.body(reply)).contains("\"promptMarkdown\"").contains(MARKER);
  }

  @Test
  void theControlTheSameRequestWithoutThePromptCarriesNoPromptEvenForAnAcceptedHost() {
    RawClient.Reply reply = server.send("GET " + HostOriginRig.MISSION + "/work-packages/WP01 HTTP/1.1", "Host: 127.0.0.1:" + server.port());

    assertThat(reply.status()).isEqualTo(200);
    assertThat(HostOriginRig.body(reply)).doesNotContain(MARKER).doesNotContain("promptMarkdown");
  }

  @Test
  void theTargetListHoldsTheFiveDetailRoutesAndThePromptVariant() {
    List<String> targets = HostOriginRig.TARGETS;
    assertThat(targets).hasSize(5 + 6).contains(HostOriginRig.PROMPT_TARGET);
    assertThat(targets.stream().filter(target -> target.startsWith(HostOriginRig.MISSION))).hasSize(6);
  }
}
