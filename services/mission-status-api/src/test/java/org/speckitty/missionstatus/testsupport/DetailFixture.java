package org.speckitty.missionstatus.testsupport;

import java.nio.file.Path;
import java.util.List;
import org.speckitty.missionstatus.adapter.out.filesystem.FilesystemTextSource;
import org.speckitty.missionstatus.adapter.out.filesystem.NameEncoding;
import org.speckitty.missionstatus.adapter.out.filesystem.RecordingAllowlistAccess;
import org.speckitty.missionstatus.application.query.MissionReadModel;
import org.speckitty.missionstatus.application.query.port.out.dto.LedgerRead;
import org.speckitty.missionstatus.application.query.port.out.dto.MissionRef;
import org.speckitty.missionstatus.domain.model.Diagnostic;
import org.speckitty.missionstatus.domain.model.StatusSnapshot;
import org.speckitty.missionstatus.domain.readmodel.reducer.AtThenEventId;
import org.speckitty.missionstatus.domain.readmodel.reducer.StatusReducer;

/**
 * The bundle every detail route test builds its service on (PLAN-FRESH4-004): one fixture, provisioned once, with the pieces a route
 * needs already wired to the <em>one</em> recording seam. It composes an already built {@link FilesystemFixtureFactory.Built} (which
 * keeps the one scratch-tree and materialisation path) with a real {@link FilesystemTextSource} over the same project root and the very
 * recorder the event source reads through ({@code FixtureHandles#allowlistRecorder()}), so the accesses of a listing and those of a
 * text read land in one record; and a {@link MissionReadModel} over the built event source and the diagnostics recorder of the
 * fixture. It edits none of the types it composes. No decoder is built here: each route phase builds its own service on the fixture.
 */
public record DetailFixture(FilesystemFixtureFactory.Built built, FilesystemTextSource textSource, MissionReadModel readModel) {

  /**
   * A committed conformance fixture, copied, materialised and provisioned: {@link ProvisionPlan} runs on the scratch copy before any
   * read, with the plan read from the source directory (OO-4).
   */
  public static DetailFixture of(Path fixtureDir) {
    FilesystemFixtureFactory.Built built = FilesystemFixtureFactory.fromTreeRecording(fixtureDir);
    ProvisionPlan.apply(fixtureDir, built.root());
    return over(built);
  }

  /** The bundle over an already built (and, if it needs it, provisioned) fixture that has the recording seam installed. */
  public static DetailFixture over(FilesystemFixtureFactory.Built built) {
    RecordingAllowlistAccess recorder = built.handles().allowlistRecorder();
    if (recorder == null) {
      throw new IllegalArgumentException("a detail fixture needs the recording file seam: build it with fromTreeRecording");
    }
    FilesystemTextSource text = new FilesystemTextSource(built.root(), recorder, NameEncoding.host());
    MissionReadModel model = new MissionReadModel(built.source(), built.handles().recorder(), LeakPatternsFile.load());
    return new DetailFixture(built, text, model);
  }

  /** The one recorder: the event source and the text source both read through it. */
  public RecordingAllowlistAccess recorder() {
    return built.handles().allowlistRecorder();
  }

  /** The project root of the scratch copy. */
  public Path root() {
    return built.root();
  }

  /** The diagnostics the service wrote so far. */
  public List<Diagnostic> diagnostics() {
    return built.diagnostics();
  }

  /**
   * The reduction of one Mission's ledger by the production reducer, through the event source of the fixture: the resolved state a
   * detail route will serve. A ledger the codec refuses raises what the source raises.
   */
  public StatusSnapshot reduce(String missionDirectory) {
    MissionRef ref = new MissionRef(missionDirectory);
    LedgerRead ledger = built.source().readLedger(ref, built.source().stampLedger(ref));
    return new StatusReducer(new AtThenEventId()).reduceLines(ledger.lines());
  }
}
