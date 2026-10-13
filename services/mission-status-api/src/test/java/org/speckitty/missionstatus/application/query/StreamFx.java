package org.speckitty.missionstatus.application.query;

import static org.assertj.core.api.Assertions.assertThat;

import java.nio.charset.StandardCharsets;
import java.time.Duration;
import java.util.ArrayList;
import java.util.List;
import java.util.Optional;
import org.speckitty.missionstatus.application.query.port.in.dto.Change;
import org.speckitty.missionstatus.application.query.port.in.dto.StreamScope;
import org.speckitty.missionstatus.application.query.port.in.dto.StreamSignal;
import org.speckitty.missionstatus.application.query.port.in.Subscription;
import org.speckitty.missionstatus.domain.readmodel.cursor.StreamCursor;
import org.speckitty.missionstatus.domain.model.MissionId;
import org.speckitty.missionstatus.testsupport.FixtureSpec;
import org.speckitty.missionstatus.testsupport.Rows;

/** Helpers for the stream tests: two Missions, signal draining and the cursor after a given prefix of a ledger. */
public final class StreamFx {

  public static final MissionId ALPHA = new MissionId(Rows.ALPHA_ID);
  public static final MissionId BETA = new MissionId(Rows.BETA_ID);
  public static final String CREATED = "2026-09-02T10:00:00+00:00";

  private StreamFx() {}

  /** Alpha holds three rows already; beta holds one. */
  public static FixtureSpec twoMissions() {
    return FixtureSpec.of(Fx.mission("alpha", Rows.ALPHA_ID, CREATED, alphaHistory()), Fx.mission("beta", Rows.BETA_ID, "2026-09-03T10:00:00+00:00", betaHistory()));
  }

  public static String alphaHistory() {
    return Rows.lifecycle(Rows.id(1), "MissionCreated", Fx.T0) + Rows.status(Rows.id(2), Fx.T0, "WP01", "planned", "claimed") + Rows.status(Rows.id(3), Fx.T1, "WP01", "claimed", "in_progress");
  }

  public static String betaHistory() {
    return Rows.status(Rows.id(50), Fx.T0, "WP01", "planned", "claimed");
  }

  public static StreamSignal next(Subscription subscription) {
    try {
      return subscription.next(Duration.ZERO);
    } catch (InterruptedException interrupted) {
      throw new AssertionError(interrupted);
    }
  }

  /** Every signal available now, ending at the first {@code Idle}. */
  public static List<StreamSignal> drain(Subscription subscription) {
    List<StreamSignal> signals = new ArrayList<>();
    for (StreamSignal signal = next(subscription); !(signal instanceof StreamSignal.Idle); signal = next(subscription)) {
      signals.add(signal);
      if (signal instanceof StreamSignal.Closed) {
        break;
      }
    }
    return signals;
  }

  /** The changes of every Forwarded signal, in arrival order. */
  public static List<Change> changes(List<StreamSignal> signals) {
    List<Change> changes = new ArrayList<>();
    for (StreamSignal signal : signals) {
      if (signal instanceof StreamSignal.Forwarded forwarded) {
        changes.addAll(forwarded.batch().changes());
      }
    }
    return changes;
  }

  public static List<String> eventIds(List<Change> changes) {
    return changes.stream()
        .map(
            change ->
                switch (change.kind()) {
                  case org.speckitty.missionstatus.domain.model.LineKind.Status status -> status.event().eventId();
                  case org.speckitty.missionstatus.domain.model.LineKind.Lifecycle lifecycle -> lifecycle.event().eventId();
                  default -> throw new AssertionError();
                })
        .toList();
  }

  /** The cursor after the first {@code lines} terminated lines of the text. */
  public static StreamCursor cursorAfter(String ledger, int lines) {
    String[] parts = ledger.split("(?<=\n)");
    long offset = 0;
    String last = null;
    for (int i = 0; i < lines; i++) {
      offset += parts[i].getBytes(StandardCharsets.UTF_8).length;
      last = parts[i];
    }
    return new StreamCursor(offset, last == null ? StreamCursor.start().invariant() : StreamCursor.digestOf(last.getBytes(StandardCharsets.UTF_8)));
  }

  public static StreamScope scope(MissionId id) {
    return StreamScope.mission(id);
  }

  public static Optional<StreamCursor> from(StreamCursor cursor) {
    return Optional.of(cursor);
  }

  public static void assertIdle(Subscription subscription) {
    assertThat(next(subscription)).isInstanceOf(StreamSignal.Idle.class);
  }
}
