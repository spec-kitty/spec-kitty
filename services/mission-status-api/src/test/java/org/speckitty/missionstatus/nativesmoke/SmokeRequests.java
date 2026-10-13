package org.speckitty.missionstatus.nativesmoke;

import java.io.IOException;
import java.io.InputStream;
import java.io.UncheckedIOException;
import java.nio.charset.StandardCharsets;
import java.nio.file.Files;
import java.nio.file.Path;
import java.util.ArrayList;
import java.util.HashSet;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;
import java.util.Optional;
import java.util.Set;
import org.speckitty.missionstatus.testsupport.CanonicalJson;
import org.speckitty.missionstatus.testsupport.ConformanceTree;
import org.speckitty.missionstatus.testsupport.ConformanceTree.TreeFixture;

/**
 * The literal request set of the native smoke ({@code nativesmoke/requests.json}): stages, groups and requests. A group is one
 * fixture tree and so one start of the binary (a tree whose whole read is refused cannot share a start with golden-backed requests).
 * Every expected status, Problem code and golden is written in the file; nothing is derived at run time.
 *
 * <p>An {@code expectedGolden} is {@code tree:<file>} (a file of the fixture's own {@code golden/} directory), {@code smoke:<file>}
 * (a file of {@code nativesmoke/golden/}) or {@code contract} (the bundled contract document the service ships).
 */
final class SmokeRequests {

  static final String RESOURCE = "/nativesmoke/requests.json";
  static final String CONTRACT = "contract";

  /** A stream round trip: open the stream, append {@code text} to {@code file} of the project, expect exactly one event with {@code expectedEventId}. */
  record Stream(String file, String append, String expectedEventId) {}

  record Request(
      String id,
      String method,
      String path,
      Map<String, String> headers,
      int expectedStatus,
      String expectedGolden,
      String expectedProblemCode,
      String expectedContentType,
      List<String> mustNotContain,
      Stream stream) {}

  record Group(String stage, String tree, List<Request> requests) {}

  record Stage(String name, int requestCountFloor) {}

  private final List<Stage> stages;
  private final List<Group> groups;
  private final List<String> parseProblems;

  private SmokeRequests(List<Stage> stages, List<Group> groups, List<String> parseProblems) {
    this.stages = stages;
    this.groups = groups;
    this.parseProblems = parseProblems;
  }

  static byte[] rawBytes() {
    try (InputStream in = SmokeRequests.class.getResourceAsStream(RESOURCE)) {
      if (in == null) {
        throw new IllegalStateException(RESOURCE + " is not on the test classpath");
      }
      return in.readAllBytes();
    } catch (IOException failure) {
      throw new UncheckedIOException(failure);
    }
  }

  static SmokeRequests load() {
    return parse(rawBytes());
  }

  /** Reads the file; a malformed one yields an instance whose {@link #problems()} say why (never an exception, so a test sees the reason). */
  @SuppressWarnings("unchecked")
  static SmokeRequests parse(byte[] bytes) {
    List<String> problems = new ArrayList<>();
    List<Stage> stages = new ArrayList<>();
    List<Group> groups = new ArrayList<>();
    Object root;
    try {
      root = CanonicalJson.parse(bytes);
    } catch (IllegalArgumentException notJson) {
      problems.add("requests.json is not JSON: " + notJson.getMessage());
      return new SmokeRequests(stages, groups, problems);
    }
    if (!(root instanceof Map<?, ?> top)) {
      problems.add("requests.json is not an object");
      return new SmokeRequests(stages, groups, problems);
    }
    if (top.get("stages") instanceof Map<?, ?> stageMap) {
      for (Map.Entry<?, ?> entry : stageMap.entrySet()) {
        Object floor = entry.getValue() instanceof Map<?, ?> body ? body.get("requestCountFloor") : null;
        if (floor instanceof CanonicalJson.Num number && number.text().matches("[0-9]+")) {
          stages.add(new Stage(entry.getKey().toString(), Integer.parseInt(number.text())));
        } else {
          problems.add("stage " + entry.getKey() + " has no integer requestCountFloor");
        }
      }
    } else {
      problems.add("no stages object");
    }
    if (top.get("groups") instanceof List<?> groupList) {
      for (Object rawGroup : groupList) {
        Map<String, Object> group = (Map<String, Object>) rawGroup;
        List<Request> requests = new ArrayList<>();
        for (Object rawRequest : (List<Object>) group.getOrDefault("requests", List.of())) {
          requests.add(request((Map<String, Object>) rawRequest, problems));
        }
        groups.add(new Group((String) group.get("stage"), (String) group.get("tree"), List.copyOf(requests)));
      }
    } else {
      problems.add("no groups array");
    }
    return new SmokeRequests(List.copyOf(stages), List.copyOf(groups), problems);
  }

  @SuppressWarnings("unchecked")
  private static Request request(Map<String, Object> raw, List<String> problems) {
    Map<String, String> headers = new LinkedHashMap<>();
    if (raw.get("headers") instanceof Map<?, ?> map) {
      map.forEach((name, value) -> headers.put(name.toString(), value.toString()));
    }
    int status = raw.get("expectedStatus") instanceof CanonicalJson.Num number ? Integer.parseInt(number.text()) : -1;
    if (status < 0) {
      problems.add("request " + raw.get("id") + " has no integer expectedStatus");
    }
    List<String> forbidden = raw.get("mustNotContain") instanceof List<?> list ? list.stream().map(Object::toString).toList() : List.of();
    Stream stream = null;
    if (raw.get("stream") instanceof Map<?, ?> map) {
      stream = new Stream((String) map.get("file"), (String) map.get("append"), (String) map.get("expectedEventId"));
    }
    return new Request(
        (String) raw.get("id"),
        (String) raw.get("method"),
        (String) raw.get("path"),
        Map.copyOf(headers),
        status,
        (String) raw.get("expectedGolden"),
        (String) raw.get("expectedProblemCode"),
        (String) raw.get("expectedContentType"),
        forbidden,
        stream);
  }

  List<Group> groups() {
    return groups;
  }

  List<String> stageNames() {
    return stages.stream().map(Stage::name).toList();
  }

  List<Request> allRequests() {
    return groups.stream().flatMap(group -> group.requests().stream()).toList();
  }

  int floor(String stage) {
    return stages.stream().filter(s -> s.name().equals(stage)).mapToInt(Stage::requestCountFloor).findFirst().orElseThrow(() -> new IllegalArgumentException("no stage " + stage));
  }

  /** The sum of the floors of the stages in the file: what the gate's {@code --request-floor} must equal. */
  int floorSum() {
    return stages.stream().mapToInt(Stage::requestCountFloor).sum();
  }

  int requestCount(String stage) {
    return groups.stream().filter(group -> stage.equals(group.stage())).mapToInt(group -> group.requests().size()).sum();
  }

  Optional<TreeFixture> tree(String id) {
    return ConformanceTree.fixtures().stream().filter(fixture -> fixture.key().equals(id)).findFirst();
  }

  /** The golden bytes an {@code expectedGolden} names, or null when the file is absent. */
  static byte[] golden(String spec, TreeFixture tree, byte[] contractBytes) {
    try {
      if (spec.equals(CONTRACT)) {
        return contractBytes;
      }
      if (spec.startsWith("tree:")) {
        return tree == null ? null : ConformanceTree.golden(tree, spec.substring("tree:".length()));
      }
      if (spec.startsWith("smoke:")) {
        try (InputStream in = SmokeRequests.class.getResourceAsStream("/nativesmoke/golden/" + spec.substring("smoke:".length()))) {
          return in == null ? null : in.readAllBytes();
        }
      }
      return null;
    } catch (IOException failure) {
      throw new UncheckedIOException(failure);
    }
  }

  /** The bytes of the bundled contract document the service ships, from the main resources on the test classpath. */
  static byte[] contractBytes() {
    try (InputStream in = SmokeRequests.class.getResourceAsStream("/contract/openapi.yaml")) {
      if (in == null) {
        throw new IllegalStateException("contract/openapi.yaml is not on the test classpath");
      }
      return in.readAllBytes();
    } catch (IOException failure) {
      throw new UncheckedIOException(failure);
    }
  }

  /** Everything that is wrong with the file: parse problems, missing stages, duplicate ids, unknown trees, absent goldens. */
  List<String> problems() {
    List<String> problems = new ArrayList<>(parseProblems);
    if (groups.isEmpty()) {
      problems.add("the file has no group");
    }
    if (allRequests().isEmpty()) {
      problems.add("the file has no request");
    }
    Set<String> ids = new HashSet<>();
    Set<String> stageNames = new HashSet<>(stageNames());
    for (Group group : groups) {
      if (!stageNames.contains(group.stage())) {
        problems.add("a group names the undeclared stage " + group.stage());
      }
      TreeFixture tree = tree(String.valueOf(group.tree())).orElse(null);
      if (tree == null) {
        problems.add("the group tree " + group.tree() + " is not in the conformance manifest");
      }
      if (group.requests().isEmpty()) {
        problems.add("the group " + group.tree() + " has no request");
      }
      for (Request request : group.requests()) {
        if (request.id() == null || request.method() == null || request.path() == null) {
          problems.add("a request of " + group.tree() + " lacks id, method or path");
          continue;
        }
        if (!ids.add(request.id())) {
          problems.add("duplicate request id " + request.id());
        }
        if (request.expectedStatus() >= 200 && request.expectedStatus() < 300 && request.expectedGolden() == null) {
          problems.add("request " + request.id() + " expects a 2xx and names no golden");
        }
        if (request.expectedGolden() != null) {
          byte[] golden = request.expectedGolden().equals(CONTRACT) ? new byte[0] : golden(request.expectedGolden(), tree, null);
          if (golden == null) {
            problems.add("request " + request.id() + ": the golden " + request.expectedGolden() + " does not exist");
          }
        }
      }
    }
    return problems;
  }

  /** Reads a file as UTF-8 text (a helper for resources the harness shares). */
  static String text(Path file) {
    try {
      return Files.readString(file, StandardCharsets.UTF_8);
    } catch (IOException failure) {
      throw new UncheckedIOException(failure);
    }
  }
}
