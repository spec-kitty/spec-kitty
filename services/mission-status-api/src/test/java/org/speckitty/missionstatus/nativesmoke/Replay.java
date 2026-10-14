package org.speckitty.missionstatus.nativesmoke;

import java.io.IOException;
import java.io.UncheckedIOException;
import java.net.InetAddress;
import java.net.ServerSocket;
import java.nio.charset.StandardCharsets;
import java.nio.file.Files;
import java.nio.file.Path;
import java.nio.file.StandardOpenOption;
import java.time.Duration;
import java.util.ArrayList;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;
import java.util.OptionalLong;
import org.speckitty.missionstatus.testsupport.CanonicalJson;
import org.speckitty.missionstatus.testsupport.ConformanceTree.TreeFixture;
import org.speckitty.missionstatus.testsupport.ProjectHeaderMaterialisation;
import org.speckitty.missionstatus.testsupport.ProvisionPlan;

/**
 * The replay: for every group, materialise its tree into a fresh project root, start the service on a free loopback port, send each
 * literal request through a raw socket, check status, Problem code and content type, and compare each 2xx RAW body with its golden
 * bytes through {@link CanonicalJson#assertBodyEqualsGolden} (the parsed tree only explains a mismatch). The bodies, refusals and the
 * stream frame included, are collected in order for the digest.
 */
final class Replay {

  /** The provisional bound for one appended row to reach a connected stream (ADR 2026-10-05-2: a miss is classified, never retried). */
  static final Duration EVENT_BOUND = Duration.ofSeconds(2);

  private static final Duration READY_BOUND = Duration.ofSeconds(30);
  private static final Duration QUIET_PERIOD = Duration.ofMillis(800);

  /** A started service: its port, a liveness check, an optional child-process count, and the stop. */
  interface Running extends AutoCloseable {
    /** Throws an {@link AssertionError} (path-free) when the service is no longer running. */
    void requireAlive();

    /** The number of child processes of the service, or empty when this platform cannot say. */
    OptionalLong childProcesses();

    @Override
    void close();
  }

  /** Starts the service over {@code projectRoot}, listening on {@code port}. */
  interface Launcher {
    Running start(Path projectRoot, int port);
  }

  record Exchange(String id, int status, byte[] body) {}

  /** What a whole replay produced: the exchanges in order and the per-stage request counts. */
  record Outcome(List<Exchange> exchanges, Map<String, Integer> requestsPerStage, int groupsStarted, int childrenSamples, int childrenUnmeasurable) {
    List<byte[]> bodies() {
      return exchanges.stream().map(Exchange::body).toList();
    }
  }

  private Replay() {}

  static Outcome replayAll(SmokeRequests requests, Launcher launcher) {
    List<String> problems = requests.problems();
    if (!problems.isEmpty()) {
      throw new AssertionError("requests.json is not usable: " + problems);
    }
    byte[] contract = SmokeRequests.contractBytes();
    List<Exchange> exchanges = new ArrayList<>();
    Map<String, Integer> perStage = new LinkedHashMap<>();
    int samples = 0;
    int unmeasurable = 0;
    for (SmokeRequests.Group group : requests.groups()) {
      TreeFixture tree = requests.tree(group.tree()).orElseThrow();
      Path scratch = scratchDirectory();
      try {
        Path projectRoot = Files.createDirectory(scratch.resolve("project"));
        ProjectHeaderMaterialisation.materialise(tree.dir(), projectRoot);
        // Modification times, links and the files assembled from fragments (a credential, a NUL file) exist only after the plan ran, so
        // the listing bytes agree on every leg. A leg that cannot make a link skips (never passes) and says so in the not-run report.
        ProvisionPlan.apply(tree.dir(), projectRoot);
        int port = freePort();
        try (Running running = launcher.start(projectRoot, port)) {
          awaitReady(port, running);
          OptionalLong before = running.childProcesses();
          for (SmokeRequests.Request request : group.requests()) {
            running.requireAlive();
            exchanges.add(replayOne(request, port, projectRoot, tree, contract));
            perStage.merge(group.stage(), 1, Integer::sum);
          }
          running.requireAlive();
          OptionalLong after = running.childProcesses();
          if (before.isPresent() && after.isPresent()) {
            samples++;
            // A child the service already had when it was ready (on Windows the console host of the harness-launched binary) is not a
            // process the replay started: the judgement is that the count did not move while the requests were served.
            if (after.getAsLong() != before.getAsLong()) {
              throw new AssertionError("group " + group.tree() + ": the service must start no process, but it had " + before.getAsLong() + " child process(es) before the replay and " + after.getAsLong() + " after");
            }
          } else {
            unmeasurable++;
          }
        }
      } catch (IOException failure) {
        throw new UncheckedIOException(failure);
      } finally {
        deleteTree(scratch);
      }
    }
    return new Outcome(List.copyOf(exchanges), perStage, requests.groups().size(), samples, unmeasurable);
  }

  /** The guards against a vacuous replay: some request ran and some body was compared. */
  static void requireCounts(int requestsReplayed, int bodiesCompared) {
    if (requestsReplayed == 0) {
      throw new AssertionError("no request was replayed");
    }
    if (bodiesCompared == 0) {
      throw new AssertionError("no body was compared");
    }
  }

  /** Every stage of the file must have been replayed at least {@code requestCountFloor} times. */
  static void requireFloors(SmokeRequests requests, Map<String, Integer> replayedPerStage) {
    for (String stage : requests.stageNames()) {
      int replayed = replayedPerStage.getOrDefault(stage, 0);
      if (replayed < requests.floor(stage)) {
        throw new AssertionError("stage " + stage + " replayed " + replayed + " request(s), below its floor of " + requests.floor(stage));
      }
    }
  }

  /** The RAW body must equal the golden bytes; the parsed documents are used only by the comparator to say where they differ. */
  static void compareToGolden(String id, byte[] rawBody, byte[] goldenBytes) {
    try {
      CanonicalJson.assertBodyEqualsGolden(rawBody, goldenBytes);
    } catch (AssertionError mismatch) {
      throw new AssertionError("request " + id + ": " + mismatch.getMessage(), mismatch);
    }
  }

  private static Exchange replayOne(SmokeRequests.Request request, int port, Path projectRoot, TreeFixture tree, byte[] contract) {
    if (request.stream() != null) {
      return replayStream(request, port, projectRoot, tree, contract);
    }
    RawHttp.Response response = RawHttp.exchange(port, request.method(), withPort(request.path(), port), withPort(request.headers(), port));
    checkStatus(request, response.status());
    checkContentType(request, response.header("content-type"));
    checkProblemCode(request, response.body());
    checkBody(request, response.body(), tree, contract);
    return new Exchange(request.id(), response.status(), response.body());
  }

  /** Fills the {@code <port>} placeholder of a request target with the port the service was started on. */
  static String withPort(String text, int port) {
    return text.replace("<port>", Integer.toString(port));
  }

  /** Fills the {@code <port>} placeholder in the header VALUES (names are literal): a Host or Origin of the hostOrigin stage names the bound port. */
  static Map<String, String> withPort(Map<String, String> headers, int port) {
    Map<String, String> filled = new LinkedHashMap<>();
    headers.forEach((name, value) -> filled.put(name, withPort(value, port)));
    return filled;
  }

  private static Exchange replayStream(SmokeRequests.Request request, int port, Path projectRoot, TreeFixture tree, byte[] contract) {
    try (RawHttp.EventStream stream = RawHttp.openStream(port, withPort(request.path(), port), withPort(request.headers(), port))) {
      checkStatus(request, stream.status());
      checkContentType(request, stream.header("content-type"));
      Path ledger = projectRoot.resolve(request.stream().file());
      try {
        Files.writeString(ledger, request.stream().append(), StandardCharsets.UTF_8, StandardOpenOption.APPEND);
      } catch (IOException failure) {
        throw new UncheckedIOException(failure);
      }
      byte[] frame = stream.nextEvent(EVENT_BOUND);
      if (frame == null) {
        throw new AssertionError("request " + request.id() + ": no event within " + EVENT_BOUND.toSeconds() + " s of the appended row (classify the miss under ADR 2026-10-05-2; it is not retried)");
      }
      String text = new String(frame, StandardCharsets.UTF_8);
      String expectedId = request.stream().expectedEventId();
      if (!text.contains("\nid:" + expectedId + "\n") && !text.contains("\nid: " + expectedId + "\n") && !text.startsWith("id:" + expectedId + "\n")) {
        throw new AssertionError("request " + request.id() + ": the event does not carry the id " + expectedId);
      }
      if (stream.nextEvent(QUIET_PERIOD) != null) {
        throw new AssertionError("request " + request.id() + ": more than one event arrived for one appended row");
      }
      checkBody(request, frame, tree, contract);
      return new Exchange(request.id(), stream.status(), frame);
    }
  }

  private static void checkStatus(SmokeRequests.Request request, int status) {
    if (status != request.expectedStatus()) {
      throw new AssertionError("request " + request.id() + ": status " + status + ", expected " + request.expectedStatus());
    }
  }

  private static void checkContentType(SmokeRequests.Request request, String contentType) {
    if (request.expectedContentType() != null && (contentType == null || !contentType.startsWith(request.expectedContentType()))) {
      throw new AssertionError("request " + request.id() + ": content type " + contentType + ", expected " + request.expectedContentType());
    }
  }

  private static void checkProblemCode(SmokeRequests.Request request, byte[] body) {
    if (request.expectedProblemCode() == null) {
      return;
    }
    Object document;
    try {
      document = CanonicalJson.parse(body);
    } catch (IllegalArgumentException notJson) {
      throw new AssertionError("request " + request.id() + ": a Problem body was expected and the body is not JSON");
    }
    Object code = document instanceof Map<?, ?> map ? map.get("code") : null;
    if (!request.expectedProblemCode().equals(code)) {
      throw new AssertionError("request " + request.id() + ": Problem code " + code + ", expected " + request.expectedProblemCode());
    }
  }

  private static void checkBody(SmokeRequests.Request request, byte[] body, TreeFixture tree, byte[] contract) {
    if (request.expectedGolden() != null) {
      byte[] golden = SmokeRequests.golden(request.expectedGolden(), tree, contract);
      if (golden == null) {
        throw new AssertionError("request " + request.id() + ": the golden " + request.expectedGolden() + " does not exist");
      }
      compareToGolden(request.id(), body, golden);
    }
    String text = new String(body, StandardCharsets.UTF_8);
    for (String forbidden : request.mustNotContain()) {
      if (text.contains(forbidden)) {
        throw new AssertionError("request " + request.id() + ": the body contains the forbidden text " + forbidden);
      }
    }
  }

  private static void awaitReady(int port, Running running) {
    long deadline = System.nanoTime() + READY_BOUND.toNanos();
    while (System.nanoTime() < deadline) {
      running.requireAlive();
      int status = RawHttp.probe(port, "/api/v1/project");
      // 403 is the Host/Origin filter before the server knows its own port; any other HTTP answer (a refusal included) means serving
      if (status != 0 && status != 403) {
        return;
      }
      try {
        Thread.sleep(100);
      } catch (InterruptedException interrupted) {
        Thread.currentThread().interrupt();
        throw new AssertionError("interrupted while waiting for the service");
      }
    }
    throw new AssertionError("the service did not answer within " + READY_BOUND.toSeconds() + " s");
  }

  static int freePort() {
    try (ServerSocket socket = new ServerSocket(0, 1, InetAddress.getLoopbackAddress())) {
      return socket.getLocalPort();
    } catch (IOException failure) {
      throw new UncheckedIOException(failure);
    }
  }

  private static Path scratchDirectory() {
    try {
      return Files.createTempDirectory("mission-status-smoke-");
    } catch (IOException failure) {
      throw new UncheckedIOException(failure);
    }
  }

  /** Deletes a scratch tree without following links; a leftover is cleaned by the operating system's temporary directory. */
  private static void deleteTree(Path root) {
    try {
      Files.walkFileTree(
          root,
          new java.nio.file.SimpleFileVisitor<>() {
            @Override
            public java.nio.file.FileVisitResult visitFile(Path file, java.nio.file.attribute.BasicFileAttributes attributes) throws IOException {
              Files.delete(file);
              return java.nio.file.FileVisitResult.CONTINUE;
            }

            @Override
            public java.nio.file.FileVisitResult postVisitDirectory(Path dir, IOException failure) throws IOException {
              Files.delete(dir);
              return java.nio.file.FileVisitResult.CONTINUE;
            }
          });
    } catch (IOException ignored) {
      // best effort
    }
  }
}
