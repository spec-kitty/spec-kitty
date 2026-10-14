package org.speckitty.missionstatus.testsupport.http;

import java.io.IOException;
import java.net.URI;
import java.net.http.HttpClient;
import java.net.http.HttpRequest;
import java.net.http.HttpResponse;
import java.nio.charset.StandardCharsets;
import java.nio.file.Path;
import java.util.ArrayList;
import java.util.List;
import java.util.Map;
import org.springframework.boot.builder.SpringApplicationBuilder;
import org.speckitty.missionstatus.application.query.port.in.MissionStatusQuery;
import org.speckitty.missionstatus.config.MissionStatusApplication;
import org.speckitty.missionstatus.testsupport.FilesystemFixtureFactory;
import org.speckitty.missionstatus.testsupport.FixtureHandles;
import org.speckitty.missionstatus.testsupport.RouteMarker;
import org.speckitty.missionstatus.adapter.out.filesystem.RecordingAllowlistAccess;
import org.springframework.context.ConfigurableApplicationContext;
import org.springframework.context.support.GenericApplicationContext;

/**
 * A real-socket server over a built filesystem fixture: the production application (controllers, mapper, advice) on port 0, with the
 * fixture's own {@link MissionStatusQuery} installed as the primary inbound port so the recording allowlist seam of the fixture stays
 * in the path. The caller keeps the fixture root and may change the tree while the server runs. Requests carry the accepted Host form
 * ({@code 127.0.0.1:<bound port>}).
 */
public final class HttpHarness implements AutoCloseable {

  /** A response as received. */
  public record Response(int status, java.net.http.HttpHeaders headers, byte[] body) {
    public String text() {
      return new String(body, StandardCharsets.UTF_8);
    }

    public String header(String name) {
      return headers.firstValue(name).orElse(null);
    }
  }

  private static final HttpClient CLIENT = HttpClient.newHttpClient();

  private final ConfigurableApplicationContext context;
  private final int port;
  private final FixtureHandles handles;

  private HttpHarness(ConfigurableApplicationContext context, int port, FixtureHandles handles) {
    this.context = context;
    this.port = port;
    this.handles = handles;
  }

  /** Starts the production application over the fixture; its query is the fixture's own. */
  public static HttpHarness start(FilesystemFixtureFactory.Built built, String... properties) {
    MissionStatusQuery query = built.query();
    return run(built.root(), built.handles(), query, properties);
  }

  /** Starts the production application over the fixture with {@code query} (a wrapper of the fixture's own, or a different service) installed instead. */
  public static HttpHarness startOver(FilesystemFixtureFactory.Built built, MissionStatusQuery query, String... properties) {
    return run(built.root(), built.handles(), query, properties);
  }

  /** Starts the production application with its own wiring over a project root (no fixture query installed). */
  public static HttpHarness startWired(Path root, String... properties) {
    return run(root, null, null, properties);
  }

  /**
   * Starts the production application over the fixture (its own query installed, as {@link #start} does) and registers each of
   * {@code inbound} as a primary bean under its map key. The key is a plain {@code Class<?>}, so this harness names no inbound
   * interface of a later work package: the route tests of PR B pass theirs, a test of this phase passes one it declares itself.
   * Every instance must be an instance of its key.
   */
  public static HttpHarness startWith(FilesystemFixtureFactory.Built built, Map<Class<?>, Object> inbound, String... properties) {
    return run(built.root(), built.handles(), built.query(), inbound, properties);
  }

  /**
   * As {@link #startWith(FilesystemFixtureFactory.Built, Map, String...)}, and the recorder of the fixture notes the route of
   * {@code marker} for every access from now on (a test sets the marker before the request it makes).
   */
  public static HttpHarness startWith(FilesystemFixtureFactory.Built built, Map<Class<?>, Object> inbound, RouteMarker marker, String... properties) {
    if (built.handles().allowlistRecorder() != null) {
      built.handles().allowlistRecorder().routeSupplier(marker.supplier());
    }
    return run(built.root(), built.handles(), built.query(), inbound, properties);
  }

  private static HttpHarness run(Path root, FixtureHandles handles, MissionStatusQuery override, String... properties) {
    return run(root, handles, override, Map.of(), properties);
  }

  private static HttpHarness run(Path root, FixtureHandles handles, MissionStatusQuery override, Map<Class<?>, Object> inbound, String... properties) {
    List<String> all = new ArrayList<>(List.of("server.port=0", "mission-status.project-root=" + root));
    all.addAll(List.of(properties));
    SpringApplicationBuilder builder = new SpringApplicationBuilder(MissionStatusApplication.class).web(org.springframework.boot.WebApplicationType.SERVLET);
    if (override != null) {
      builder.initializers(
          (ConfigurableApplicationContext context) ->
              ((GenericApplicationContext) context).registerBean("fixtureQuery", MissionStatusQuery.class, () -> override, definition -> definition.setPrimary(true)));
    }
    if (!inbound.isEmpty()) {
      builder.initializers(
          (ConfigurableApplicationContext context) -> inbound.forEach((type, instance) -> registerPrimary((GenericApplicationContext) context, type, instance)));
    }
    // command-line arguments: the highest precedence, so a test key wins over the packaged application.properties
    ConfigurableApplicationContext context = builder.run(arguments(all));
    int port = Integer.parseInt(context.getEnvironment().getProperty("local.server.port"));
    return new HttpHarness(context, port, handles);
  }

  private static <T> void registerPrimary(GenericApplicationContext context, Class<T> type, Object instance) {
    T typed = type.cast(instance);
    context.registerBean("inbound-" + type.getName(), type, () -> typed, definition -> definition.setPrimary(true));
  }

  /** The properties as command-line arguments; a key given twice keeps its last value (repeated arguments would be merged into a list). */
  private static String[] arguments(List<String> properties) {
    java.util.Map<String, String> byKey = new java.util.LinkedHashMap<>();
    for (String property : properties) {
      int equals = property.indexOf('=');
      byKey.put(property.substring(0, equals), property.substring(equals + 1));
    }
    return byKey.entrySet().stream().map(entry -> "--" + entry.getKey() + "=" + entry.getValue()).toArray(String[]::new);
  }

  public int port() {
    return port;
  }

  public String host() {
    return "127.0.0.1:" + port;
  }

  /** The fixture handles the server was started over (null for {@link #startWired}). */
  public FixtureHandles handles() {
    return handles;
  }

  /** The recording allowlist seam of the fixture, or null when it was built without one. */
  public RecordingAllowlistAccess allowlistRecorder() {
    return handles == null ? null : handles.allowlistRecorder();
  }

  public ConfigurableApplicationContext context() {
    return context;
  }

  public Response get(String pathAndQuery) {
    return get(pathAndQuery, null);
  }

  public Response get(String pathAndQuery, String accept) {
    try {
      HttpRequest.Builder request = HttpRequest.newBuilder(URI.create("http://127.0.0.1:" + port + pathAndQuery)).GET();
      if (accept != null) {
        request.header("Accept", accept);
      }
      HttpResponse<byte[]> response = CLIENT.send(request.build(), HttpResponse.BodyHandlers.ofByteArray());
      return new Response(response.statusCode(), response.headers(), response.body());
    } catch (IOException failure) {
      throw new java.io.UncheckedIOException(failure);
    } catch (InterruptedException interrupted) {
      Thread.currentThread().interrupt();
      throw new IllegalStateException(interrupted);
    }
  }

  /** Sends literal request bytes on a fresh socket (see {@link RawClient}). */
  public RawClient.Reply raw(String requestBytes) {
    return RawClient.send(port, requestBytes);
  }

  @Override
  public void close() {
    context.close();
  }
}
