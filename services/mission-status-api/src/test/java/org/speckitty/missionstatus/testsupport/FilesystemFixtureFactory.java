package org.speckitty.missionstatus.testsupport;

import java.io.IOException;
import java.io.UncheckedIOException;
import java.nio.file.Files;
import java.nio.file.Path;
import java.lang.reflect.Constructor;
import java.time.Clock;
import java.time.Instant;
import java.util.List;
import java.util.concurrent.ScheduledExecutorService;
import java.util.function.Consumer;
import java.util.function.Function;
import org.speckitty.missionstatus.adapter.out.filesystem.AllowlistAccess;
import org.speckitty.missionstatus.adapter.out.filesystem.FilesystemMissionEventSource;
import org.speckitty.missionstatus.adapter.out.filesystem.ReadDirResolver;
import org.speckitty.missionstatus.adapter.out.filesystem.RecordingAllowlistAccess;
import org.speckitty.missionstatus.adapter.out.filesystem.SafeFiles;
import org.speckitty.missionstatus.application.query.MissionStatusQueryService;
import org.speckitty.missionstatus.application.query.stream.StreamSettings;
import org.speckitty.missionstatus.application.query.port.in.MissionStatusQuery;
import org.speckitty.missionstatus.application.query.port.out.MissionEventSource;
import org.speckitty.missionstatus.domain.model.Diagnostic;
import org.speckitty.missionstatus.domain.redaction.LeakClasses;
import org.speckitty.missionstatus.domain.readmodel.reducer.EventOrdering;
import org.speckitty.missionstatus.domain.readmodel.reducer.StatusReducer;
import org.speckitty.missionstatus.testsupport.ConformanceTree.TreeFixture;

/**
 * Realises a fixture on disk and builds the real {@link MissionStatusQueryService} over the real {@link FilesystemMissionEventSource}, with
 * a fixed clock, a recording diagnostics consumer, a deterministic scheduled executor and the leak classes read from the committed
 * {@code leak-patterns.json}. It is the only class of the test support that imports the real adapter.
 *
 * <p>A committed tree is COPIED into a scratch directory first and materialised by {@link ProjectHeaderMaterialisation}; the fixtures
 * themselves are never read in place, and no git repository is ever provisioned.
 */
public final class FilesystemFixtureFactory {

  /** The built fixture: the inbound port, the source, the handles and the project root of the scratch copy. */
  public record Built(MissionStatusQuery query, FilesystemMissionEventSource source, FixtureHandles handles, Path root) implements Fixture {

    @Override
    public List<Diagnostic> diagnostics() {
      return handles.diagnostics();
    }
  }

  private FilesystemFixtureFactory() {}

  /** A committed conformance fixture tree, served with no recorder. */
  public static Built fromTree(Path fixtureDir) {
    return fromTree(fixtureDir, null);
  }

  /**
   * A committed conformance fixture tree. {@code access} builds the file seam over the scratch root (for example
   * {@code RecordingAllowlistAccess::new}); a recorder it returns is exposed through {@link FixtureHandles#allowlistRecorder()}.
   */
  public static Built fromTree(Path fixtureDir, Function<Path, AllowlistAccess> access) {
    Path root = projectRoot();
    ProjectHeaderMaterialisation.materialise(fixtureDir, root);
    return over(root, access);
  }

  /** A committed tree with the recording file seam installed; {@link FixtureHandles#allowlistViolations()} reads it back. */
  public static Built fromTreeRecording(Path fixtureDir) {
    return fromTree(fixtureDir, RecordingAllowlistAccess::new);
  }

  public static Built fromTree(TreeFixture fixture) {
    return fromTree(fixture.dir());
  }

  /**
   * A committed tree served by a service whose reducer uses {@code ordering} instead of the production one (AC-8a: a wrong ordering
   * must turn the conformance suite red). The service keeps its cache and its constructor package-private, so this reaches them
   * reflectively; nothing in production code is touched.
   */
  public static Built fromTreeWithOrdering(Path fixtureDir, EventOrdering ordering) {
    Path root = projectRoot();
    ProjectHeaderMaterialisation.materialise(fixtureDir, root);
    AllowlistAccess seam = AllowlistAccess.passThrough();
    FilesystemMissionEventSource source = new FilesystemMissionEventSource(root, seam);
    FixtureHandles handles = new FixtureHandles(new MutableClock(Instant.parse("2026-10-01T12:00:00Z")));
    try {
      Class<?> cacheType = Class.forName("org.speckitty.missionstatus.application.query.ProjectionCache");
      Constructor<?> cacheConstructor = cacheType.getDeclaredConstructor(StatusReducer.class);
      cacheConstructor.setAccessible(true);
      Object cache = cacheConstructor.newInstance(new StatusReducer(ordering));
      Constructor<MissionStatusQueryService> serviceConstructor =
          MissionStatusQueryService.class.getDeclaredConstructor(
              MissionEventSource.class, Clock.class, Consumer.class, ScheduledExecutorService.class, StreamSettings.class, LeakClasses.class, cacheType);
      serviceConstructor.setAccessible(true);
      MissionStatusQuery query =
          serviceConstructor.newInstance(source, handles.clock(), handles.recorder(), handles.executor(), StreamSettings.defaults(), LeakPatternsFile.load(), cache);
      return new Built(query, source, handles, root);
    } catch (ReflectiveOperationException failure) {
      throw new IllegalStateException("the service no longer takes an injected reducer cache", failure);
    }
  }

  /** A source-neutral spec, written as a tree. This is what the selector installs for the second leg of the port-level subset. */
  public static Built fromSpec(FixtureSpec spec) {
    return fromSpec(spec, StreamSettings.defaults());
  }

  /** A source-neutral spec served by a service with these stream settings (the service, not the controller, owns the stream cap). */
  public static Built fromSpec(FixtureSpec spec, StreamSettings settings) {
    Path root = projectRoot();
    FixtureTrees.write(spec, root);
    return over(root, null, settings);
  }

  /** The service over an existing project root. */
  public static Built over(Path root, Function<Path, AllowlistAccess> access) {
    return over(root, access, StreamSettings.defaults());
  }

  /** The service over an existing project root with these stream settings. */
  public static Built over(Path root, Function<Path, AllowlistAccess> access, StreamSettings settings) {
    AllowlistAccess seam = access == null ? AllowlistAccess.passThrough() : access.apply(root);
    RecordingAllowlistAccess recorder = seam instanceof RecordingAllowlistAccess recording ? recording : null;
    FilesystemMissionEventSource source = new FilesystemMissionEventSource(root, seam);
    FixtureHandles handles = new FixtureHandles(new MutableClock(Instant.parse("2026-10-01T12:00:00Z")), recorder);
    MissionStatusQuery query = new MissionStatusQueryService(source, handles.clock(), handles.recorder(), handles.executor(), settings, LeakPatternsFile.load());
    return new Built(query, source, handles, root);
  }

  /** {@code own} or {@code coord}: the read directory class the resolver chooses for a Mission of a materialised tree. */
  public static String readDirectoryClass(Path root, String missionName) {
    ReadDirResolver resolver = new ReadDirResolver(new SafeFiles(root, AllowlistAccess.passThrough()));
    return resolver.resolve(missionName).readClass() == ReadDirResolver.ReadClass.COORD ? "coord" : "own";
  }

  private static Path projectRoot() {
    try {
      return Files.createDirectories(ScratchDirs.create().resolve("project"));
    } catch (IOException failure) {
      throw new UncheckedIOException(failure);
    }
  }
}
