package org.speckitty.missionstatus.application.query;

import static org.assertj.core.api.Assertions.assertThat;
import static org.assertj.core.api.Assertions.assertThatThrownBy;

import org.junit.jupiter.api.Test;
import org.speckitty.missionstatus.application.query.port.out.dto.MissionRef;
import org.speckitty.missionstatus.application.query.port.out.exceptions.SourceFault;
import org.speckitty.missionstatus.domain.model.MissionId;
import org.speckitty.missionstatus.testsupport.FixtureSpec;
import org.speckitty.missionstatus.testsupport.InMemoryMissionEventSource;
import org.speckitty.missionstatus.testsupport.InMemoryMissionEventSource.Op;
import org.speckitty.missionstatus.testsupport.Rows;

/** The probe-free lookup of a Mission by id: first readable wins, the first fault is remembered, the continuation finds a duplicate. */
class MissionLookupTest {

  private static final String CREATED = "2026-09-02T10:00:00+00:00";

  private static InMemoryMissionEventSource sourceOf(FixtureSpec.Mission... missions) {
    return InMemoryMissionEventSource.from(FixtureSpec.of(missions));
  }

  private static FixtureSpec.Mission mission(String name, String id) {
    return Fx.mission(name, id, CREATED, null);
  }

  @Test
  void theFirstReadableMissionWithTheIdWinsAndNeverStampsALedger() {
    InMemoryMissionEventSource source = sourceOf(mission("alpha", Rows.ALPHA_ID), mission("beta", Rows.BETA_ID));

    MissionLookup.Scan scan = new MissionLookup(source).find(new MissionId(Rows.BETA_ID));

    assertThat(scan.found().ref()).isEqualTo(new MissionRef("beta"));
    assertThat(scan.found().mid8()).isEqualTo(new MissionId(Rows.BETA_ID).mid8());
    assertThat(scan.firstFault()).isNull();
    assertThat(source.calls("stampLedger")).as("the lookup is probe-free").isZero();
    assertThat(source.calls("readLedger")).isZero();
  }

  @Test
  void aFaultedSiblingBeforeTheMatchDoesNotStopTheLookupAndTheFirstFaultIsRemembered() {
    InMemoryMissionEventSource source = sourceOf(mission("a-bad", Rows.ALPHA_ID), mission("b-bad", Rows.GAMMA_ID), mission("c-good", Rows.BETA_ID));
    source.inject("a-bad", Op.META, SourceFault.Kind.META_UNPARSEABLE);
    source.inject("b-bad", Op.META, SourceFault.Kind.DIR_UNREADABLE);

    MissionLookup.Scan scan = new MissionLookup(source).find(new MissionId(Rows.BETA_ID));

    assertThat(scan.found().ref()).isEqualTo(new MissionRef("c-good"));
    assertThat(scan.firstFault()).isEqualTo(SourceFault.Kind.META_UNPARSEABLE);
  }

  @Test
  void whenNothingMatchesTheFirstFaultDecidesAndAVanishedDirectoryIsNotAFault() {
    InMemoryMissionEventSource source = sourceOf(mission("a-gone", Rows.ALPHA_ID), mission("b-bad", Rows.GAMMA_ID), mission("c-bad", Rows.BETA_ID));
    source.inject("a-gone", Op.META, SourceFault.Kind.VANISHED);
    source.inject("b-bad", Op.META, SourceFault.Kind.PATH_REFUSED);
    source.inject("c-bad", Op.META, SourceFault.Kind.DIR_UNREADABLE);

    MissionLookup.Scan scan = new MissionLookup(source).find(new MissionId("01J09000000000000000000009"));

    assertThat(scan.found()).isNull();
    assertThat(scan.firstFault()).isEqualTo(SourceFault.Kind.PATH_REFUSED);
    assertThat(scan.unscanned()).isEmpty();
  }

  @Test
  void aListingFaultPropagatesToTheCaller() {
    InMemoryMissionEventSource source = sourceOf(mission("alpha", Rows.ALPHA_ID));
    source.failListing(SourceFault.Kind.DIR_UNREADABLE);

    assertThatThrownBy(() -> new MissionLookup(source).find(new MissionId(Rows.ALPHA_ID))).isInstanceOf(SourceFault.class);
  }

  @Test
  void theContinuationFindsASecondReadableDirectoryCarryingTheId() {
    InMemoryMissionEventSource source = sourceOf(mission("a-first", Rows.ALPHA_ID), mission("b-other", Rows.BETA_ID), mission("c-copy", Rows.ALPHA_ID));
    MissionLookup lookup = new MissionLookup(source);

    MissionLookup.Scan scan = lookup.find(new MissionId(Rows.ALPHA_ID));

    assertThat(scan.found().ref()).as("the first readable directory wins").isEqualTo(new MissionRef("a-first"));
    assertThat(scan.unscanned()).containsExactly(new MissionRef("b-other"), new MissionRef("c-copy"));
    assertThat(lookup.hasDuplicate(scan)).isTrue();
  }

  @Test
  void theContinuationReadsEachLaterMetaOnceAndIgnoresAFaultedSibling() {
    InMemoryMissionEventSource source = sourceOf(mission("a-first", Rows.ALPHA_ID), mission("b-bad", Rows.GAMMA_ID), mission("c-other", Rows.BETA_ID));
    source.inject("b-bad", Op.META, SourceFault.Kind.META_UNPARSEABLE);
    MissionLookup lookup = new MissionLookup(source);
    MissionLookup.Scan scan = lookup.find(new MissionId(Rows.ALPHA_ID));
    int afterFind = source.calls("readMeta");

    boolean duplicate = lookup.hasDuplicate(scan);

    assertThat(duplicate).isFalse();
    assertThat(source.calls("readMeta") - afterFind).as("one read per later Mission").isEqualTo(2);
  }

  @Test
  void anUnmatchedScanHasNoDuplicate() {
    InMemoryMissionEventSource source = sourceOf(mission("alpha", Rows.ALPHA_ID));
    MissionLookup lookup = new MissionLookup(source);

    assertThat(lookup.hasDuplicate(lookup.find(new MissionId(Rows.BETA_ID)))).isFalse();
  }
}
