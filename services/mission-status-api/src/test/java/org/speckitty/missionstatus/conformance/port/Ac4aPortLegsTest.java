package org.speckitty.missionstatus.conformance.port;

import static org.assertj.core.api.Assertions.assertThat;
import static org.assertj.core.api.Assertions.assertThatThrownBy;
import static org.speckitty.missionstatus.testsupport.Rows.id;

import java.util.List;
import java.util.function.Supplier;
import org.speckitty.missionstatus.application.query.port.in.MissionStatusQuery;
import org.speckitty.missionstatus.application.query.port.in.exceptions.MissionStatusUnavailable;
import org.speckitty.missionstatus.application.query.port.in.dto.PageRequest;
import org.speckitty.missionstatus.domain.readmodel.cursor.StreamCursor;
import org.speckitty.missionstatus.domain.model.Diagnostic;
import org.speckitty.missionstatus.domain.model.DiagnosticCode;
import org.speckitty.missionstatus.domain.readmodel.overview.LifecycleStatus;
import org.speckitty.missionstatus.domain.readmodel.overview.MissionOverview;
import org.speckitty.missionstatus.testsupport.Fixture;
import org.speckitty.missionstatus.testsupport.FixtureSpec;
import org.speckitty.missionstatus.testsupport.PortFixtures;
import org.speckitty.missionstatus.testsupport.PortLevelTest;
import org.speckitty.missionstatus.testsupport.PortSourceSelector;
import org.speckitty.missionstatus.testsupport.Rows;

/**
 * The port legs of AC-4a for rows L1, L3a, L3b, L4 and L4b: the typed result, or the typed {@link MissionStatusUnavailable} carrying
 * the row's diagnostic code. Every refusal is asserted to be a refusal (never a 200), and its diagnostic to carry the Mission's
 * {@code mid8}, the line number where the row has one, and no path or line text.
 */
public class Ac4aPortLegsTest {

  private static final String ALPHA_MID8 = Rows.ALPHA_ID.substring(0, 8);
  private static final String MOVES_TEXT = Rows.status(id(1), "2026-09-01T10:00:00Z", "WP01", "planned", "claimed") + Rows.status(id(2), "2026-09-01T10:05:00Z", "WP01", "claimed", "in_progress");

  /** Alpha (older) holds {@code alphaLedger}; beta (newer, so first in contract order) holds a healthy ledger. */
  private static Fixture pair(String alphaLedger) {
    return PortSourceSelector.open(
        FixtureSpec.of(
            PortFixtures.mission("alpha", Rows.ALPHA_ID, PortFixtures.CREATED, alphaLedger),
            PortFixtures.mission("beta", Rows.BETA_ID, "2026-09-03T10:00:00+00:00", Rows.status(id(20), "2026-09-01T10:00:00Z", "WP01", "planned", "claimed"))));
  }

  private static void assertRefused(Supplier<Object> route, DiagnosticCode code) {
    assertThatThrownBy(route::get).isInstanceOfSatisfying(MissionStatusUnavailable.class, refusal -> assertThat(refusal.code()).isEqualTo(code));
  }

  private static void assertRefusedFromBothReads(Fixture fixture, DiagnosticCode code) {
    MissionStatusQuery query = fixture.query();
    assertRefused(query::project, code);
    assertRefused(() -> query.missions(new PageRequest(null, null)), code);
  }

  @PortLevelTest("AC-4a/L1")
  public void l1AnAbsentLedgerIsADraftAtOffsetZeroWithNoDiagnostic() {
    Fixture fixture = pair(null);

    MissionOverview alpha = fixture.query().missions(new PageRequest(null, null)).items().stream().filter(item -> item.slug().equals("alpha")).findFirst().orElseThrow();

    assertThat(alpha.wpTotal()).isZero();
    assertThat(alpha.eventCount()).isZero();
    assertThat(alpha.lifecycleStatus()).isEqualTo(LifecycleStatus.DRAFT);
    assertThat(alpha.streamCursor()).isEqualTo(StreamCursor.start());
    assertThat(fixture.diagnostics()).as("a fresh Mission is a normal state").isEmpty();
  }

  @PortLevelTest("AC-4a/L1/discarded")
  public void l1WithDiscardedAtIsDiscardedNotDraft() {
    String meta = Rows.metaWith(Rows.ALPHA_ID, "alpha", PortFixtures.CREATED, "\"discarded_at\":\"2026-09-05T10:00:00+00:00\"");
    Fixture fixture = PortSourceSelector.open(FixtureSpec.of(FixtureSpec.Mission.of("alpha", meta, null)));

    MissionOverview alpha = fixture.query().missions(new PageRequest(null, null)).items().getFirst();

    assertThat(alpha.lifecycleStatus()).isEqualTo(LifecycleStatus.DISCARDED);
    assertThat(fixture.diagnostics()).isEmpty();
  }

  @PortLevelTest("AC-4a/L3a")
  public void l3aABadTerminatedLineRefusesTheProjectHeader() {
    String bad = MOVES_TEXT + "this is not json\n" + Rows.status(id(4), "2026-09-01T10:10:00Z", "WP01", "in_progress", "for_review");
    Fixture fixture = pair(bad);

    assertRefused(fixture.query()::project, DiagnosticCode.LEDGER_UNPARSEABLE);

    assertThat(fixture.diagnostics()).containsExactly(new Diagnostic(DiagnosticCode.LEDGER_UNPARSEABLE, ALPHA_MID8, 3));
  }

  @PortLevelTest("AC-4a/L3b")
  public void l3bABadTerminatedLineRefusesTheMissionListWhicheverPageIsRequested() {
    Fixture fixture = pair(MOVES_TEXT + "[1,2,3]\n");
    MissionStatusQuery query = fixture.query();

    // Alpha is older, so with page size 1 it is not on the first page; the whole read is refused all the same.
    assertRefused(() -> query.missions(new PageRequest(1, null)), DiagnosticCode.LEDGER_UNPARSEABLE);
    assertRefused(() -> query.missions(new PageRequest(null, null)), DiagnosticCode.LEDGER_UNPARSEABLE);

    assertThat(fixture.diagnostics()).isNotEmpty().allSatisfy(diagnostic -> assertThat(diagnostic).isEqualTo(new Diagnostic(DiagnosticCode.LEDGER_UNPARSEABLE, ALPHA_MID8, 3)));
  }

  @PortLevelTest("AC-4a/L4")
  public void l4AnUnparseableTornTailRefusesBothReads() {
    Fixture fixture = pair(MOVES_TEXT + "{\"actor\":\"claude\",\"at\":\"2026-09-01T10:10:");

    assertRefusedFromBothReads(fixture, DiagnosticCode.LEDGER_TORN_TAIL);

    assertThat(fixture.diagnostics()).hasSize(2).allSatisfy(diagnostic -> assertThat(diagnostic).isEqualTo(new Diagnostic(DiagnosticCode.LEDGER_TORN_TAIL, ALPHA_MID8, null)));
  }

  @PortLevelTest("AC-4a/L4b")
  public void l4bAParseableUnterminatedTailRefusesBothReads() {
    String parseableRow = Rows.status(id(3), "2026-09-01T10:10:00Z", "WP01", "in_progress", "for_review").stripTrailing();
    Fixture fixture = pair(MOVES_TEXT + parseableRow);

    assertRefusedFromBothReads(fixture, DiagnosticCode.LEDGER_TORN_TAIL);

    List<Diagnostic> diagnostics = fixture.diagnostics();
    assertThat(diagnostics).hasSize(2).allSatisfy(diagnostic -> assertThat(diagnostic).isEqualTo(new Diagnostic(DiagnosticCode.LEDGER_TORN_TAIL, ALPHA_MID8, null)));
  }
}
