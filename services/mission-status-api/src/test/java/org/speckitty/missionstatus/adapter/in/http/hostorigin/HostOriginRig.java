package org.speckitty.missionstatus.adapter.in.http.hostorigin;

import java.util.ArrayList;
import java.util.List;
import org.speckitty.missionstatus.adapter.out.filesystem.RecordingAllowlistAccess;
import org.speckitty.missionstatus.testsupport.ConformanceTree;
import org.speckitty.missionstatus.testsupport.FilesystemFixtureFactory;
import org.speckitty.missionstatus.testsupport.http.RawClient;
import org.speckitty.missionstatus.testsupport.http.StreamRig;

/**
 * One server of the Host/Origin suites: the production application over the planted-canary tree on an ephemeral port (so every accepted
 * request is also the "configured port 0, own port from the bound server" control), the recording file seam, the spy over the inbound
 * port and the entry counter. Requests are literal bytes on a raw socket.
 */
final class HostOriginRig implements AutoCloseable {

  /** The Mission of the planted-canary tree, whose id the detail targets name. */
  static final String MISSION = "/api/v1/missions/01J6000000000000000000001W";

  /** The request path of the prompt variant (AC-9.3): the one request of the five detail routes that serves a Work Package body. */
  static final String PROMPT_TARGET = MISSION + "/work-packages/WP01?includePrompt=true";

  /** The five request targets of AC-9b/9c: three routes, the contract document and an unknown path (a refusal, never a 404). */
  static final List<String> OVERVIEW_TARGETS = List.of("/api/v1/project", "/api/v1/missions", "/api/v1/events", "/api/v1/openapi.yaml", "/api/v1/nowhere-at-all");

  /** The five detail routes and the prompt variant (WP18, AC-17.1, AC-9.3): the same refusals, the same zero reads. */
  static final List<String> DETAIL_TARGETS =
      List.of(
          MISSION,
          MISSION + "/work-packages/WP01",
          MISSION + "/work-packages/WP01/detail",
          MISSION + "/artifacts",
          MISSION + "/artifacts/content?path=spec.md",
          PROMPT_TARGET);

  /** Every request target of AC-9b/9c: the overview targets, then the detail ones. */
  static final List<String> TARGETS = java.util.stream.Stream.concat(OVERVIEW_TARGETS.stream(), DETAIL_TARGETS.stream()).toList();

  private final StreamRig rig;
  final EntryCounting.Counter counter;

  private HostOriginRig(StreamRig rig, EntryCounting.Counter counter) {
    this.rig = rig;
    this.counter = counter;
  }

  static HostOriginRig start(String... properties) {
    FilesystemFixtureFactory.Built built =
        FilesystemFixtureFactory.fromTree(ConformanceTree.root().resolve("secret-canaries").resolve("planted-canaries"), RecordingAllowlistAccess::new);
    String[] all = new String[properties.length + 1];
    all[0] = EntryCounting.SOURCE;
    System.arraycopy(properties, 0, all, 1, properties.length);
    StreamRig rig = StreamRig.over(built, all);
    EntryCounting.Counter counter = rig.http.context().getBean(EntryCounting.Counter.class);
    // a counter that wrapped nothing would read zero for everything
    if (counter.registrations() != 1) {
      rig.close();
      throw new IllegalStateException("the entry counter did not wrap the Host/Origin filter: " + counter.registrations());
    }
    rig.http.allowlistRecorder().clear();
    return new HostOriginRig(rig, counter);
  }

  int port() {
    return rig.http.port();
  }

  StreamRig stream() {
    return rig;
  }

  /** Reads of the Mission files and calls of the inbound port since the start, both of which must stay zero for a refusal. */
  int reads() {
    return rig.http.allowlistRecorder().accesses().size() + rig.spy.projectThreads().size() + rig.spy.missionsThreads().size() + rig.spy.totalSubscriptions();
  }

  /** A request as literal bytes: {@code requestLine}, the header lines (each a full {@code Name: value}) and the closing blank line. */
  RawClient.Reply send(String requestLine, String... headerLines) {
    StringBuilder text = new StringBuilder(requestLine).append("\r\n");
    for (String line : headerLines) {
      text.append(line).append("\r\n");
    }
    text.append("Connection: close\r\n\r\n");
    return RawClient.send(port(), text.toString());
  }

  /** The strings that must never appear in any reply: the fixture root, HOME, the home property and the planted markers. */
  List<String> secrets() {
    List<String> secrets = new ArrayList<>();
    secrets.add(rig.built.root().toString());
    secrets.add(System.getProperty("user.home"));
    if (System.getenv("HOME") != null && !System.getenv("HOME").isBlank()) {
      secrets.add(System.getenv("HOME"));
    }
    secrets.add("CANARY-NOT-A-SECRET");
    secrets.add("kitty-specs");
    return secrets;
  }

  @Override
  public void close() {
    rig.close();
  }

  /** The reply body (after the blank line), with a chunked transfer coding removed; the empty string when there is none. */
  static String body(RawClient.Reply reply) {
    int split = reply.text().indexOf("\r\n\r\n");
    if (split < 0) {
      return "";
    }
    String raw = reply.text().substring(split + 4);
    if (!reply.text().substring(0, split).toLowerCase().contains("transfer-encoding: chunked")) {
      return raw;
    }
    StringBuilder out = new StringBuilder();
    int at = 0;
    while (at < raw.length()) {
      int eol = raw.indexOf("\r\n", at);
      int size = Integer.parseInt(raw.substring(at, eol).strip(), 16);
      if (size == 0) {
        break;
      }
      out.append(raw, eol + 2, eol + 2 + size);
      at = eol + 2 + size + 2;
    }
    return out.toString();
  }
}
