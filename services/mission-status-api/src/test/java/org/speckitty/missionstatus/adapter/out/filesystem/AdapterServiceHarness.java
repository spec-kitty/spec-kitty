package org.speckitty.missionstatus.adapter.out.filesystem;

import java.io.IOException;
import java.io.UncheckedIOException;
import java.nio.charset.StandardCharsets;
import java.nio.file.Files;
import java.nio.file.Path;
import java.time.Instant;
import java.util.ArrayList;
import java.util.Collections;
import java.util.List;
import org.speckitty.missionstatus.application.query.MissionStatusQueryService;
import org.speckitty.missionstatus.application.query.stream.StreamSettings;
import org.speckitty.missionstatus.application.query.port.in.MissionStatusQuery;
import org.speckitty.missionstatus.application.query.port.in.dto.PageRequest;
import org.speckitty.missionstatus.domain.model.Diagnostic;
import org.speckitty.missionstatus.domain.readmodel.overview.MissionOverview;
import org.speckitty.missionstatus.testsupport.DeterministicExecutor;
import org.speckitty.missionstatus.testsupport.FixtureFactory;
import org.speckitty.missionstatus.testsupport.MutableClock;
import org.speckitty.missionstatus.testsupport.Rows;

/**
 * The real {@link MissionStatusQueryService} over the real {@link FilesystemMissionEventSource}, on a tree built by the test, with the
 * recording {@link AllowlistAccess}, a fixed clock, a recording diagnostics consumer and a deterministic executor. It is a helper of the
 * adapter-level cases; it names no WP09 fixture type. Package-local, so no {@code testsupport} path is touched.
 */
final class AdapterServiceHarness {

  static final String ALPHA = "alpha-01J01000";
  static final String BETA = "beta-01J02000";

  final Path root;
  final RecordingAllowlistAccess recorder;
  final FilesystemMissionEventSource source;
  final MutableClock clock = new MutableClock(Instant.parse("2026-10-01T12:00:00Z"));
  final DeterministicExecutor executor = new DeterministicExecutor();
  final List<Diagnostic> diagnostics = Collections.synchronizedList(new ArrayList<>());
  final MissionStatusQuery query;

  AdapterServiceHarness(Path root) {
    this.root = root;
    this.recorder = new RecordingAllowlistAccess(root);
    this.source = new FilesystemMissionEventSource(root, recorder);
    this.query = new MissionStatusQueryService(source, clock, diagnostics::add, executor, StreamSettings.defaults(), FixtureFactory.leakClasses());
  }

  // ---- tree builders ----------------------------------------------------------------------------------------------------------

  /** A healthy project: configuration slug, metadata and a {@code .git/HEAD} on {@code main}. */
  static void healthyProject(Path root) {
    write(root.resolve(".kittify/config.yaml"), "project:\n  slug: fixture-project\n");
    write(root.resolve(".kittify/metadata.yaml"), "spec_kitty:\n  version: 3.2.7\n  schema_version: 3\n");
    write(root.resolve(".git/HEAD"), "ref: refs/heads/main\n");
  }

  /** A Mission directory with {@code meta.json} and (when {@code ledger} is not null) a ledger. */
  static Path mission(Path root, String name, String id, String createdAt, String ledger) {
    Path dir = root.resolve("kitty-specs").resolve(name);
    write(dir.resolve("meta.json"), Rows.meta(id, name, createdAt));
    if (ledger != null) {
      write(dir.resolve("status.events.jsonl"), ledger);
    }
    return dir;
  }

  static void write(Path file, String text) {
    writeBytes(file, text.getBytes(StandardCharsets.UTF_8));
  }

  static void writeBytes(Path file, byte[] bytes) {
    try {
      Files.createDirectories(file.getParent());
      Files.write(file, bytes);
    } catch (IOException failure) {
      throw new UncheckedIOException(failure);
    }
  }

  static String laneRow(int n, String wp, String from, String to) {
    return Rows.status(Rows.id(n), String.format("2026-09-01T10:00:%02d+00:00", n), wp, from, to);
  }

  // ---- reads through the inbound port -----------------------------------------------------------------------------------------

  List<MissionOverview> overviews() {
    return query.missions(new PageRequest(200, null)).items();
  }
}
