package org.speckitty.missionstatus.perf;

import java.lang.reflect.Method;
import java.nio.file.Path;
import java.time.Clock;
import java.util.concurrent.Executors;
import java.util.concurrent.ScheduledExecutorService;
import org.speckitty.missionstatus.adapter.out.filesystem.AllowlistAccess;
import org.speckitty.missionstatus.adapter.out.filesystem.FilesystemMissionEventSource;
import org.speckitty.missionstatus.application.query.MissionStatusQueryService;
import org.speckitty.missionstatus.application.query.stream.StreamSettings;
import org.speckitty.missionstatus.testsupport.FilesystemFixtureFactory;
import org.speckitty.missionstatus.testsupport.LeakPatternsFile;
import org.speckitty.missionstatus.testsupport.http.HttpHarness;

/**
 * The production application over a project root with a REAL clock and a REAL scheduled feed executor (the stream tests use a
 * deterministic one; a performance hold needs the poll tick to run by itself). The service sits over a {@link CountingSource}, and the
 * reducer-invocation counter of its cache is read reflectively, so nothing in production code changes.
 */
public final class PerfServer implements AutoCloseable {

  private final HttpHarness http;
  private final ScheduledExecutorService executor;
  private final CountingSource source;
  private final MissionStatusQueryService service;
  private final Path root;

  private PerfServer(HttpHarness http, ScheduledExecutorService executor, CountingSource source, MissionStatusQueryService service, Path root) {
    this.http = http;
    this.executor = executor;
    this.source = source;
    this.service = service;
    this.root = root;
  }

  public static PerfServer start(Path root, String... properties) {
    CountingSource source = new CountingSource(new FilesystemMissionEventSource(root, AllowlistAccess.passThrough()));
    ScheduledExecutorService executor =
        Executors.newSingleThreadScheduledExecutor(
            task -> {
              Thread thread = new Thread(task, "perf-feed");
              thread.setDaemon(true);
              return thread;
            });
    MissionStatusQueryService service =
        new MissionStatusQueryService(source, Clock.systemUTC(), diagnostic -> {}, executor, StreamSettings.defaults(), LeakPatternsFile.load());
    // the handles are not needed: the harness only reads the root and the (optional) handles of the built record
    FilesystemFixtureFactory.Built built = new FilesystemFixtureFactory.Built(service, null, null, root);
    HttpHarness http = HttpHarness.startOver(built, service);
    return new PerfServer(http, executor, source, service, root);
  }

  public int port() {
    return http.port();
  }

  public Path root() {
    return root;
  }

  public CountingSource source() {
    return source;
  }

  /** How many times a ledger was reduced so far (the cache's own counter). */
  public int reductions() {
    try {
      Method cache = MissionStatusQueryService.class.getDeclaredMethod("cache");
      cache.setAccessible(true);
      Object projectionCache = cache.invoke(service);
      Method reductions = projectionCache.getClass().getDeclaredMethod("reductions");
      reductions.setAccessible(true);
      return (Integer) reductions.invoke(projectionCache);
    } catch (ReflectiveOperationException failure) {
      throw new IllegalStateException("the service no longer exposes its reducer counter", failure);
    }
  }

  @Override
  public void close() {
    http.close();
    executor.shutdownNow();
  }
}
