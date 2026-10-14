package org.speckitty.missionstatus.domain.model;

import static org.assertj.core.api.Assertions.assertThat;

import java.util.List;
import java.util.Optional;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.params.ParameterizedTest;
import org.junit.jupiter.params.provider.NullAndEmptySource;
import org.junit.jupiter.params.provider.ValueSource;

/** {@code MissionId.parse} is the lenient factory the adapters call: an empty result for anything that is no ULID, never an exception (E-5, D-150). */
class MissionIdParseTest {

  private static final String ULID = "01M4S6D5ABCDEFGHJKMNPQRSTV";

  @Test
  void aUlidParsesToTheSameValueAsTheStrictConstructor() {
    assertThat(MissionId.parse(ULID)).isEqualTo(Optional.of(new MissionId(ULID)));
  }

  @ParameterizedTest
  @NullAndEmptySource
  @ValueSource(
      strings = {
        "01m4s6d5abcdefghjkmnpqrstv",
        "01M4S6D5ABCDEFGHJKMNPQRST",
        "01M4S6D5ABCDEFGHJKMNPQRSTVW",
        "01M4S6D5",
        "my-mission-slug",
        "957",
        "01M4S6D5ABCDEFGHJKMNPQRSTI",
        "01M4S6D5ABCDEFGHJKMNPQRSTL",
        "01M4S6D5ABCDEFGHJKMNPQRSTO",
        "01M4S6D5ABCDEFGHJKMNPQRSTU",
        "01M4S6D5ABCDEFGHJKMNPQRSTV\n",
        " 01M4S6D5ABCDEFGHJKMNPQRSTV",
        "01M4S6D5ABCDEFGHJKMNPQRSTÉ"
      })
  void anythingElseIsEmptyAndNothingThrows(String raw) {
    assertThat(MissionId.parse(raw)).isEmpty();
  }

  @Test
  void aMid8AndASlugAndANumberAreNotUlids() {
    for (String raw : List.of(ULID.substring(0, 8), "mission-status-read-api", "5533")) {
      assertThat(MissionId.parse(raw)).as(raw).isEmpty();
    }
  }
}
