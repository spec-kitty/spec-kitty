package org.speckitty.missionstatus.application.query.stream;

import static org.assertj.core.api.Assertions.assertThat;
import static org.assertj.core.api.Assertions.assertThatThrownBy;
import static org.speckitty.missionstatus.application.query.StreamFx.ALPHA;

import java.time.Duration;
import java.util.Optional;
import org.junit.jupiter.api.Test;
import org.speckitty.missionstatus.application.query.Fx;
import org.speckitty.missionstatus.application.query.StreamFx;
import org.speckitty.missionstatus.application.query.port.in.MissionStatusQuery;
import org.speckitty.missionstatus.application.query.port.in.Subscription;
import org.speckitty.missionstatus.application.query.port.in.dto.StreamScope;
import org.speckitty.missionstatus.application.query.port.in.exceptions.MissionStatusUnavailable;
import org.speckitty.missionstatus.application.query.port.in.exceptions.StreamCapacityReached;
import org.speckitty.missionstatus.application.query.port.in.exceptions.StreamRefused;
import org.speckitty.missionstatus.application.query.port.out.exceptions.SourceFault;
import org.speckitty.missionstatus.domain.model.MissionId;
import org.speckitty.missionstatus.testsupport.InMemoryMissionEventSource.Op;

/**
 * Operator ruling A3 item 2, at the port and with no HTTP: the one cap on open streams belongs to the service, so every inbound adapter
 * draws from the same places. A refused call takes none, a failed connect gives its place back, a closed subscription gives it back once,
 * and {@code endStreams} ends everything and may be called again.
 */
class StreamAdmissionTest {

  private static final MissionId UNKNOWN = new MissionId("01JZZZZZZZZZZZZZZZZZZZZZZZ".replace('Z', '9'));

  private static Fx capped(int places) {
    return new Fx(StreamFx.twoMissions(), StreamSettings.defaults().withMaxConnections(places));
  }

  private static Subscription open(MissionStatusQuery query) {
    return query.subscribe(StreamScope.mission(ALPHA), Optional.empty());
  }

  @Test
  void theSubscribeOverTheCapIsRefusedWithStreamCapacityReached() {
    Fx fx = capped(2);

    try (Subscription first = open(fx.service);
        Subscription second = fx.service.subscribe(StreamScope.all(), Optional.empty())) {
      assertThatThrownBy(() -> open(fx.service)).isInstanceOf(StreamCapacityReached.class).hasMessage("stream capacity reached");
      assertThatThrownBy(() -> fx.service.subscribe(StreamScope.all(), Optional.empty())).isInstanceOf(StreamCapacityReached.class);
      assertThat(first).isNotNull();
      assertThat(second).isNotNull();
    }
  }

  @Test
  void aRefusedCallTakesNoPlaceAndLeavesNoSubscriptionInTheFeed() {
    Fx fx = capped(1);

    try (Subscription only = open(fx.service)) {
      for (int attempt = 0; attempt < 5; attempt++) {
        assertThatThrownBy(() -> open(fx.service)).isInstanceOf(StreamCapacityReached.class);
      }
      assertThat(fx.service.feed().subscriberCount()).as("the refused calls subscribed nothing").isEqualTo(1);
    }
    try (Subscription again = open(fx.service)) {
      assertThat(again).as("the place of the closed stream is free again").isNotNull();
    }
  }

  @Test
  void aClosedSubscriptionGivesBackItsPlaceOnce() {
    Fx fx = capped(2);
    Subscription first = open(fx.service);
    Subscription second = open(fx.service);

    first.close();
    first.close();
    first.close();

    try (Subscription third = open(fx.service)) {
      assertThatThrownBy(() -> open(fx.service)).as("closing twice gave back one place, not two").isInstanceOf(StreamCapacityReached.class);
      assertThat(third).isNotNull();
    }
    second.close();
  }

  @Test
  void aFailedConnectGivesItsPlaceBack() {
    Fx fx = capped(1);

    assertThatThrownBy(() -> fx.service.subscribe(StreamScope.mission(UNKNOWN), Optional.empty())).isInstanceOf(StreamRefused.class);
    fx.source.inject("alpha", Op.META, SourceFault.Kind.DIR_UNREADABLE);
    assertThatThrownBy(() -> open(fx.service)).isInstanceOf(MissionStatusUnavailable.class);

    try (Subscription connected = fx.service.subscribe(StreamScope.all(), Optional.empty())) {
      assertThat(connected).as("neither refusal kept the one place").isNotNull();
    }
  }

  @Test
  void aCursorWithoutAMissionIsRefusedAfterTheAdmissionAndGivesThePlaceBack() {
    Fx fx = capped(1);

    assertThatThrownBy(() -> fx.service.subscribe(StreamScope.all(), Optional.of(StreamFx.cursorAfter(StreamFx.alphaHistory(), 1)))).isInstanceOf(StreamRefused.class);

    try (Subscription connected = open(fx.service)) {
      assertThat(connected).isNotNull();
    }
  }

  @Test
  void theCapIsCheckedBeforeTheMissionIsLookedUp() {
    Fx fx = capped(1);

    try (Subscription only = open(fx.service)) {
      assertThatThrownBy(() -> fx.service.subscribe(StreamScope.mission(UNKNOWN), Optional.empty()))
          .as("a full service refuses on capacity, without costing a lookup")
          .isInstanceOf(StreamCapacityReached.class);
    }
  }

  @Test
  void endStreamsEndsEveryOpenSubscriptionAndIsIdempotent() throws Exception {
    Fx fx = capped(3);
    Subscription scoped = open(fx.service);
    Subscription unscoped = fx.service.subscribe(StreamScope.all(), Optional.empty());

    fx.service.endStreams();
    fx.service.endStreams();

    assertThatThrownBy(() -> scoped.next(Duration.ZERO)).isInstanceOf(IllegalStateException.class);
    assertThatThrownBy(() -> unscoped.next(Duration.ZERO)).isInstanceOf(IllegalStateException.class);
    assertThat(fx.service.feed().subscriberCount()).isZero();
    // both places are back: three fresh subscriptions fit and the fourth does not
    Subscription a = open(fx.service);
    Subscription b = open(fx.service);
    Subscription c = open(fx.service);
    assertThatThrownBy(() -> open(fx.service)).isInstanceOf(StreamCapacityReached.class);
    scoped.close();
    unscoped.close();
    assertThatThrownBy(() -> open(fx.service)).as("closing an ended subscription again gives back nothing").isInstanceOf(StreamCapacityReached.class);
    a.close();
    b.close();
    c.close();
  }

  @Test
  void endStreamsWithNothingOpenIsHarmless() {
    Fx fx = capped(1);

    fx.service.endStreams();

    try (Subscription connected = open(fx.service)) {
      assertThat(connected).isNotNull();
    }
  }

  @Test
  void anUnscopedAndAScopedStreamDrawFromTheSamePlaces() {
    Fx fx = capped(2);

    try (Subscription unscoped = fx.service.subscribe(StreamScope.all(), Optional.empty());
        Subscription scoped = open(fx.service)) {
      assertThatThrownBy(() -> fx.service.subscribe(StreamScope.all(), Optional.empty())).isInstanceOf(StreamCapacityReached.class);
      assertThat(unscoped).isNotNull();
      assertThat(scoped).isNotNull();
    }
  }

  // ---- the admission on its own ------------------------------------------------------------------------------------------------

  @Test
  void theAdmissionCountsPlacesAndRefusesAtItsCapacity() {
    StreamAdmission admission = new StreamAdmission(2);

    admission.admit();
    admission.admit();
    assertThat(admission.open()).isEqualTo(2);
    assertThatThrownBy(admission::admit).isInstanceOf(StreamCapacityReached.class);
    assertThat(admission.open()).as("the refused call took none").isEqualTo(2);
    admission.release();
    assertThat(admission.open()).isEqualTo(1);
    admission.admit();
    assertThat(admission.open()).isEqualTo(2);
  }

  @Test
  void theAdmissionNeedsAtLeastOnePlace() {
    assertThatThrownBy(() -> new StreamAdmission(0)).isInstanceOf(IllegalArgumentException.class);
  }
}
