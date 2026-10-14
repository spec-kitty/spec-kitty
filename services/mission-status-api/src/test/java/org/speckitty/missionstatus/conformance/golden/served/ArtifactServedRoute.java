package org.speckitty.missionstatus.conformance.golden.served;

import java.net.URLEncoder;
import java.nio.charset.StandardCharsets;
import java.util.LinkedHashMap;
import java.util.Map;
import java.util.Set;
import java.util.concurrent.ConcurrentHashMap;
import org.speckitty.missionstatus.application.query.AdmissionGate;
import org.speckitty.missionstatus.application.query.ArtifactQueryService;
import org.speckitty.missionstatus.application.query.port.in.ArtifactQuery;
import org.speckitty.missionstatus.conformance.golden.ServedRoute;
import org.speckitty.missionstatus.conformance.golden.ServedRoutes;
import org.speckitty.missionstatus.domain.redaction.TextScreen;
import org.speckitty.missionstatus.testsupport.CanonicalJson;
import org.speckitty.missionstatus.testsupport.ConformanceTree;
import org.speckitty.missionstatus.testsupport.ConformanceTree.TreeFixture;
import org.speckitty.missionstatus.testsupport.DetailFixture;
import org.speckitty.missionstatus.testsupport.LeakPatternsFile;
import org.speckitty.missionstatus.testsupport.Utf8Host;
import org.speckitty.missionstatus.testsupport.http.HttpHarness;

/**
 * The provider of {@code list-artifacts.json} and {@code get-artifact-content.json} (WP16). It serves each request key over a real socket
 * through the whole production stack (controller, port, service, mapper and canonical writer) and answers the canonical bytes of the
 * golden's value: {@code {"body": <served body>, "status": <status>}}. The raw served body must itself be in the canonical form, or the
 * answer is an error. The fixtures that carry the goldens are WP07's; none is written here. {@code artifacts-links} has no golden and is
 * Java-only.
 *
 * <p>One server per fixture is started on first use and shared by every instance of the provider in the JVM (the registry creates a
 * provider for each lookup); they are closed by a shutdown hook, because the provider interface has no close.
 */
public final class ArtifactServedRoute implements ServedRoute {

  private static final String LISTING = "list-artifacts.json";
  private static final String CONTENT = "get-artifact-content.json";
  private static final String BASE = "/api/v1/missions/00000000000000000000000001/artifacts";

  private static final Map<String, HttpHarness> SERVERS = new ConcurrentHashMap<>();

  static {
    Runtime.getRuntime().addShutdownHook(new Thread(() -> SERVERS.values().forEach(HttpHarness::close)));
  }

  @Override
  public Set<String> goldenFiles() {
    return Set.of(LISTING, CONTENT);
  }

  @Override
  public Set<Entry> served() {
    return ServedRoutes.expectedEntries(goldenFiles());
  }

  @Override
  public byte[] body(Entry entry, String requestKey) {
    Utf8Host.assumeUtf8("ArtifactServedRoute " + entry.fixtureKey());
    HttpHarness server = SERVERS.computeIfAbsent(entry.fixtureKey(), ArtifactServedRoute::start);
    String url = entry.goldenFile().equals(LISTING) ? BASE : BASE + "/content?path=" + encode(requestKey);
    HttpHarness.Response response = server.get(url);
    CanonicalJson.assertBodyEqualsGolden(response.body(), CanonicalJson.toBytes(CanonicalJson.parse(response.body())));
    Map<String, Object> envelope = new LinkedHashMap<>();
    envelope.put("body", CanonicalJson.parse(response.body()));
    envelope.put("status", new CanonicalJson.Num(Integer.toString(response.status())));
    return CanonicalJson.toBytes(envelope);
  }

  private static HttpHarness start(String fixtureKey) {
    TreeFixture tree = ConformanceTree.detailFixtures().stream().filter(candidate -> candidate.key().equals(fixtureKey)).findFirst().orElseThrow();
    DetailFixture fixture = DetailFixture.of(tree.dir());
    ArtifactQuery query = new ArtifactQueryService(fixture.readModel(), fixture.textSource(), new AdmissionGate(), fixture.built().handles().recorder(), new TextScreen(LeakPatternsFile.load()));
    return HttpHarness.startWith(fixture.built(), Map.of(ArtifactQuery.class, query));
  }

  /** The request key as the query value, percent-encoded once (a space as {@code %20}, a plus sign as {@code %2B}). */
  private static String encode(String key) {
    return URLEncoder.encode(key, StandardCharsets.UTF_8).replace("+", "%20").replace("%2F", "/");
  }
}
