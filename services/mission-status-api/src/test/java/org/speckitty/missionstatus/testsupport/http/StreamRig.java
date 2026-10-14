package org.speckitty.missionstatus.testsupport.http;

import java.io.IOException;
import java.io.UncheckedIOException;
import java.nio.charset.StandardCharsets;
import java.nio.file.Files;
import java.nio.file.Path;
import java.nio.file.StandardOpenOption;
import java.time.Duration;
import org.speckitty.missionstatus.application.query.stream.StreamSettings;
import org.speckitty.missionstatus.domain.readmodel.cursor.StreamCursor;
import org.speckitty.missionstatus.testsupport.FilesystemFixtureFactory;
import org.speckitty.missionstatus.testsupport.FixtureSpec;

/**
 * The server of one stream test: the production application over a fixture tree on port 0, with the fixture's own service (injected clock,
 * deterministic executor, recording diagnostics) behind a {@link SpyQuery}. A test changes the tree and calls {@link #tick()}; nothing waits for
 * a poll interval, so the only waits left are the bounded reads of the client.
 */
public final class StreamRig implements AutoCloseable {

  /** The provisional ceiling of every delivery and close the spec bounds at 2 seconds (ADR 2026-10-05-2: a ceiling, never a measurement). */
  public static final Duration BOUND = Duration.ofSeconds(2);

  /** How long "nothing arrives" is watched for. */
  public static final Duration QUIET = Duration.ofMillis(300);

  /** A heartbeat interval long enough that no test sees one unless it asks for it. */
  public static final String NO_HEARTBEAT = "mission-status.stream.heartbeat-interval=PT10M";

  public final FilesystemFixtureFactory.Built built;
  public final SpyQuery spy;
  public final HttpHarness http;

  private StreamRig(FilesystemFixtureFactory.Built built, SpyQuery spy, HttpHarness http) {
    this.built = built;
    this.spy = spy;
    this.http = http;
  }

  public static StreamRig of(FixtureSpec spec, String... properties) {
    // the fixture's service, not the controller, owns the stream cap, so the property is handed to it as well as to the application
    StreamSettings settings = StreamSettings.defaults();
    for (String property : properties) {
      String key = "mission-status.stream.max-connections=";
      if (property.startsWith(key)) {
        settings = settings.withMaxConnections(Integer.parseInt(property.substring(key.length())));
      }
    }
    FilesystemFixtureFactory.Built built = FilesystemFixtureFactory.fromSpec(spec, settings);
    return over(built, properties);
  }

  public static StreamRig over(FilesystemFixtureFactory.Built built, String... properties) {
    SpyQuery spy = new SpyQuery(built.query());
    String[] all = new String[properties.length + 1];
    all[0] = NO_HEARTBEAT;
    System.arraycopy(properties, 0, all, 1, properties.length);
    // a property given later wins over the default one
    HttpHarness http = HttpHarness.startOver(built, spy, all);
    return new StreamRig(built, spy, http);
  }

  /** The same fixture served by a service with the given subscriber queue capacity (the overflow check). */
  public static StreamRig withQueueCapacity(FixtureSpec spec, int capacity) {
    FilesystemFixtureFactory.Built base = FilesystemFixtureFactory.fromSpec(spec);
    org.speckitty.missionstatus.application.query.port.in.MissionStatusQuery service =
        new org.speckitty.missionstatus.application.query.MissionStatusQueryService(
            base.source(),
            base.handles().clock(),
            base.handles().recorder(),
            base.handles().executor(),
            org.speckitty.missionstatus.application.query.stream.StreamSettings.defaults().withQueueCapacity(capacity),
            org.speckitty.missionstatus.testsupport.LeakPatternsFile.load());
    FilesystemFixtureFactory.Built built = new FilesystemFixtureFactory.Built(service, base.source(), base.handles(), base.root());
    return over(built);
  }

  public Path missionDir(String slug) {
    return built.root().resolve("kitty-specs").resolve(slug);
  }

  public Path ledger(String slug) {
    return missionDir(slug).resolve("status.events.jsonl");
  }

  /** Appends text to a ledger (creating it when absent). */
  public void append(String slug, String text) {
    try {
      Files.writeString(ledger(slug), text, StandardCharsets.UTF_8, StandardOpenOption.CREATE, StandardOpenOption.APPEND);
    } catch (IOException failure) {
      throw new UncheckedIOException(failure);
    }
  }

  public void replace(String slug, String text) {
    try {
      Files.writeString(ledger(slug), text, StandardCharsets.UTF_8);
    } catch (IOException failure) {
      throw new UncheckedIOException(failure);
    }
  }

  public String read(String slug) {
    try {
      return Files.readString(ledger(slug), StandardCharsets.UTF_8);
    } catch (IOException failure) {
      throw new UncheckedIOException(failure);
    }
  }

  /** Replaces the ledger by a symbolic link to a readable file elsewhere: the symlink rule (AC-10d, row L2) makes it unreadable. */
  public void swapLedgerForSymlink(String slug) {
    try {
      Path target = Files.createTempFile(built.root().getParent(), "elsewhere", ".jsonl");
      Files.delete(ledger(slug));
      Files.createSymbolicLink(ledger(slug), target);
    } catch (IOException failure) {
      throw new UncheckedIOException(failure);
    }
  }

  /** Removes a directory and everything under it. */
  public void removeTree(Path directory) {
    try (var walk = Files.walk(directory)) {
      for (Path path : walk.sorted(java.util.Comparator.reverseOrder()).toList()) {
        Files.delete(path);
      }
    } catch (IOException failure) {
      throw new UncheckedIOException(failure);
    }
  }

  /** Diagnostics recorded for the service so far with this code. */
  public java.util.List<org.speckitty.missionstatus.domain.model.Diagnostic> diagnostics(org.speckitty.missionstatus.domain.model.DiagnosticCode code) {
    return built.handles().diagnostics().stream().filter(diagnostic -> diagnostic.code() == code).toList();
  }

  /** One poll tick of the feed: the clock moves past the re-list interval and every scheduled task runs once. */
  public void tick() {
    built.handles().clock().advance(Duration.ofSeconds(2));
    built.handles().executor().tick();
  }

  public SseClient scoped(String missionId, String... headers) {
    return SseClient.open(http, "/api/v1/events?missionId=" + missionId, headers);
  }

  public SseClient scopedFrom(String missionId, StreamCursor cursor) {
    return SseClient.open(http, "/api/v1/events?missionId=" + missionId + "&streamCursor=" + cursor.toText());
  }

  public SseClient unscoped() {
    return SseClient.open(http, "/api/v1/events");
  }

  @Override
  public void close() {
    http.close();
  }
}
