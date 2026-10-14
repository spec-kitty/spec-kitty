package org.speckitty.missionstatus.application.query.port.in.dto;

import static org.assertj.core.api.Assertions.assertThat;
import static org.assertj.core.api.Assertions.assertThatThrownBy;

import java.util.Optional;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.params.ParameterizedTest;
import org.junit.jupiter.params.provider.CsvSource;
import org.speckitty.missionstatus.application.query.port.in.exceptions.StreamRefused;
import org.speckitty.missionstatus.domain.model.MissionId;
import org.speckitty.missionstatus.domain.readmodel.cursor.StreamCursor;
import org.speckitty.missionstatus.testsupport.Rows;

/**
 * {@code StreamRequest.parse} fixes the order of the connect-time decisions once for every adapter: a cursor text without a Mission, then
 * the cursor text, then the scope. A request that is wrong in more than one way is refused for the first reason only.
 */
class StreamRequestTest {

  private static final String CURSOR = "107:b1d594537c90f3bcff0ab6fb7777af9b65b246cac14067a309276efff8faed95";

  @Test
  void noMissionAndNoCursorIsEveryMissionLive() {
    StreamRequest request = StreamRequest.parse(null, null);

    assertThat(request.scope()).isEqualTo(StreamScope.all());
    assertThat(request.cursor()).isEmpty();
  }

  @Test
  void aMissionWithoutACursorIsThatMissionLive() {
    StreamRequest request = StreamRequest.parse(Rows.ALPHA_ID, null);

    assertThat(request.scope()).isEqualTo(StreamScope.mission(new MissionId(Rows.ALPHA_ID)));
    assertThat(request.cursor()).isEmpty();
  }

  @Test
  void aMissionWithACursorResumesFromIt() {
    StreamRequest request = StreamRequest.parse(Rows.ALPHA_ID, CURSOR);

    assertThat(request.cursor()).contains(StreamCursor.parse(CURSOR));
    assertThat(request.scope()).isEqualTo(StreamScope.mission(new MissionId(Rows.ALPHA_ID)));
  }

  /** Each row is wrong in the ways its columns say; the refusal named is the first of: cursor without Mission, cursor text, scope. */
  @ParameterizedTest(name = "{index}: mission={0} cursor={1} -> {2}")
  @CsvSource(
      nullValues = "NULL",
      value = {
        // a cursor without a Mission wins over an unparseable cursor text
        "NULL, garbage, CURSOR_WITHOUT_MISSION",
        "NULL, " + CURSOR + ", CURSOR_WITHOUT_MISSION",
        // an unparseable cursor text wins over a Mission id that is no ULID
        "not-a-ulid, garbage, MISALIGNED",
        "not-a-ulid, -5:zz, MISALIGNED",
        "not-a-ulid, -5:b1d594537c90f3bcff0ab6fb7777af9b65b246cac14067a309276efff8faed95, NEGATIVE",
        // the scope is decided last
        "not-a-ulid, NULL, UNKNOWN_MISSION",
        "not-a-ulid, " + CURSOR + ", UNKNOWN_MISSION"
      })
  void theFirstWrongDecisionIsTheRefusal(String mission, String cursor, StreamRefused.Kind expected) {
    assertThatThrownBy(() -> StreamRequest.parse(mission, cursor)).isInstanceOfSatisfying(StreamRefused.class, refused -> assertThat(refused.kind()).isEqualTo(expected));
  }

  @Test
  void aRequestRefusesNulls() {
    assertThatThrownBy(() -> new StreamRequest(null, Optional.empty())).isInstanceOf(NullPointerException.class);
    assertThatThrownBy(() -> new StreamRequest(StreamScope.all(), null)).isInstanceOf(NullPointerException.class);
  }
}
