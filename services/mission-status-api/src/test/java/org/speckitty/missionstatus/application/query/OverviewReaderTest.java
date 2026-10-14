package org.speckitty.missionstatus.application.query;

import static org.assertj.core.api.Assertions.assertThat;
import static org.assertj.core.api.Assertions.assertThatThrownBy;

import java.util.ArrayList;
import java.util.Collections;
import java.util.List;
import java.util.Optional;
import org.junit.jupiter.api.Test;
import org.speckitty.missionstatus.adapter.out.filesystem.Allowlist.Access;
import org.speckitty.missionstatus.adapter.out.filesystem.Allowlist.OpenMode;
import org.speckitty.missionstatus.adapter.out.filesystem.Allowlist.PathClass;
import org.speckitty.missionstatus.adapter.out.filesystem.RecordingAllowlistAccess;
import org.speckitty.missionstatus.application.query.port.in.exceptions.MissionStatusUnavailable;
import org.speckitty.missionstatus.application.query.port.out.dto.MissionRef;
import org.speckitty.missionstatus.application.query.port.out.exceptions.SourceFault;
import org.speckitty.missionstatus.domain.model.Diagnostic;
import org.speckitty.missionstatus.domain.model.DiagnosticCode;
import org.speckitty.missionstatus.domain.model.MissionId;
import org.speckitty.missionstatus.domain.readmodel.overview.MissionOverview;
import org.speckitty.missionstatus.domain.readmodel.reducer.AtThenEventId;
import org.speckitty.missionstatus.domain.readmodel.reducer.StatusReducer;
import org.speckitty.missionstatus.testsupport.FilesystemFixtureFactory;
import org.speckitty.missionstatus.testsupport.FixtureSpec;
import org.speckitty.missionstatus.testsupport.InMemoryMissionEventSource.Op;
import org.speckitty.missionstatus.testsupport.InMemoryMissionEventSource;
import org.speckitty.missionstatus.testsupport.LeakPatternsFile;
import org.speckitty.missionstatus.testsupport.Rows;

/** The overview and the head over one derivation, and the meta-read arithmetic of AC-1.8(c) over the recording allowlist seam. */
class OverviewReaderTest {

  private static final String CREATED = "2026-09-02T10:00:00+00:00";

  private final List<Diagnostic> diagnostics = Collections.synchronizedList(new ArrayList<>());
  private final ProjectionCache cache = new ProjectionCache(new StatusReducer(new AtThenEventId()));

  private OverviewReader readerOver(InMemoryMissionEventSource source) {
    return new OverviewReader(source, diagnostics::add, cache, new MissionHeadProjection(LeakPatternsFile.load(), diagnostics::add));
  }

  private static InMemoryMissionEventSource alpha(String ledger) {
    return InMemoryMissionEventSource.from(FixtureSpec.of(Fx.mission("alpha", Rows.ALPHA_ID, CREATED, ledger)));
  }

  @Test
  void theOverviewIsTheHeadsOverview() {
    OverviewReader reader = readerOver(alpha(Fx.twoMoves("WP01", 1)));

    Optional<MissionOverview> overview = reader.overview(new MissionRef("alpha"));
    Optional<MissionHead> head = reader.head(new MissionRef("alpha"));

    assertThat(overview).isPresent();
    assertThat(head).isPresent();
    assertThat(head.get().overview()).isEqualTo(overview.get());
    assertThat(head.get().entry().snapshot().workPackages()).containsKey("WP01");
  }

  @Test
  void aMissionWhoseDirectoryVanishedIsLeftOutWithOneDiagnostic() {
    InMemoryMissionEventSource source = alpha(null);
    source.inject("alpha", Op.META, SourceFault.Kind.VANISHED);

    assertThat(readerOver(source).head(new MissionRef("alpha"))).isEmpty();
    assertThat(diagnostics).extracting(Diagnostic::code).containsExactly(DiagnosticCode.MISSION_VANISHED);
  }

  @Test
  void anUnparseableMetaRefusesTheReadWithItsRow() {
    InMemoryMissionEventSource source = alpha(null);
    source.inject("alpha", Op.META, SourceFault.Kind.META_UNPARSEABLE);

    assertThatThrownBy(() -> readerOver(source).head(new MissionRef("alpha"))).isInstanceOf(MissionStatusUnavailable.class);
    assertThat(diagnostics).extracting(Diagnostic::code).containsExactly(DiagnosticCode.META_UNPARSEABLE);
  }

  @Test
  void anUnreadableLedgerServesAnEmptyHeadWithOneDiagnostic() {
    InMemoryMissionEventSource source = alpha(Fx.twoMoves("WP01", 1));
    source.inject("alpha", Op.STAMP, SourceFault.Kind.LEDGER_UNREADABLE);

    Optional<MissionHead> head = readerOver(source).head(new MissionRef("alpha"));

    assertThat(head).isPresent();
    assertThat(head.get().entry().snapshot().workPackages()).isEmpty();
    assertThat(diagnostics).extracting(Diagnostic::code).containsExactly(DiagnosticCode.LEDGER_UNREADABLE);
  }

  @Test
  void aSecondHeadOfAnUnchangedLedgerIsACacheHit() {
    InMemoryMissionEventSource source = alpha(Fx.twoMoves("WP01", 1));
    OverviewReader reader = readerOver(source);

    reader.head(new MissionRef("alpha"));
    reader.head(new MissionRef("alpha"));
    reader.overview(new MissionRef("alpha"));

    assertThat(cache.reductions()).isEqualTo(1);
    assertThat(source.calls("readLedger")).isEqualTo(1);
  }

  // ---- AC-1.8(c): the meta.json reads of the matched Mission, over the recording allowlist seam -------------------------------

  private static long metaReads(RecordingAllowlistAccess recorder) {
    return recorder.accesses().stream().filter(OverviewReaderTest::isMetaRead).count();
  }

  private static boolean isMetaRead(Access access) {
    return access.pathClass() == PathClass.MISSION_META && access.mode() == OpenMode.READ;
  }

  private record Recorded(OverviewReader reader, MissionLookup lookup, RecordingAllowlistAccess recorder) {}

  private static Recorded recorded() {
    FixtureSpec spec = FixtureSpec.of(Fx.mission("alpha", Rows.ALPHA_ID, CREATED, Fx.twoMoves("WP01", 1)));
    FilesystemFixtureFactory.Built tree = FilesystemFixtureFactory.fromSpec(spec);
    FilesystemFixtureFactory.Built built = FilesystemFixtureFactory.over(tree.root(), RecordingAllowlistAccess::new);
    RecordingAllowlistAccess recorder = built.handles().allowlistRecorder();
    ProjectionCache cache = new ProjectionCache(new StatusReducer(new AtThenEventId()));
    OverviewReader reader = new OverviewReader(built.source(), built.handles().recorder(), cache, new MissionHeadProjection(LeakPatternsFile.load(), built.handles().recorder()));
    return new Recorded(reader, new MissionLookup(built.source()), recorder);
  }

  @Test
  void overviewReadsTheMatchedMetaTwiceWarmAndThreeTimesCold() {
    Recorded r = recorded();

    r.reader().overview(new MissionRef("alpha"));
    long cold = metaReads(r.recorder());
    r.recorder().clear();
    r.reader().overview(new MissionRef("alpha"));
    long warm = metaReads(r.recorder());

    assertThat(cold).as("cold: the meta read plus the stamp and the ledger read").isEqualTo(3);
    assertThat(warm).as("warm: the meta read plus the stamp").isEqualTo(2);
  }

  @Test
  void headReadsTheSameMetaTotalsAsOverview() {
    Recorded r = recorded();

    r.reader().head(new MissionRef("alpha"));
    long cold = metaReads(r.recorder());
    r.recorder().clear();
    r.reader().head(new MissionRef("alpha"));
    long warm = metaReads(r.recorder());

    assertThat(cold).isEqualTo(3);
    assertThat(warm).isEqualTo(2);
  }

  @Test
  void findFollowedByHeadReadsTheMatchedMetaThreeTimesWarmAndFourTimesCold() {
    Recorded r = recorded();

    r.lookup().find(new MissionId(Rows.ALPHA_ID));
    r.reader().head(new MissionRef("alpha"));
    long cold = metaReads(r.recorder());
    r.recorder().clear();
    r.lookup().find(new MissionId(Rows.ALPHA_ID));
    r.reader().head(new MissionRef("alpha"));
    long warm = metaReads(r.recorder());

    assertThat(cold).isEqualTo(4);
    assertThat(warm).isEqualTo(3);
  }
}
