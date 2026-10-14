package org.speckitty.missionstatus.application.query.port.in.dto;

import static org.assertj.core.api.Assertions.assertThat;
import static org.assertj.core.api.Assertions.assertThatThrownBy;

import org.junit.jupiter.api.Test;
import org.junit.jupiter.params.ParameterizedTest;
import org.junit.jupiter.params.provider.ValueSource;
import org.speckitty.missionstatus.application.query.port.in.exceptions.StreamRefused;
import org.speckitty.missionstatus.domain.readmodel.cursor.StreamCursor;

/** The cursor text of the contract: a negative offset is {@code negative}; every other text that does not parse is {@code misaligned} with the fixed detail. */
class StreamCursorTextTest {

  private static final String DIGEST = "b1d594537c90f3bcff0ab6fb7777af9b65b246cac14067a309276efff8faed95";

  @Test
  void aParseableTextIsTheCursor() {
    assertThat(StreamCursorText.parse("107:" + DIGEST)).isEqualTo(new StreamCursor(107, DIGEST));
    assertThat(StreamCursorText.parse(StreamCursor.start().toText())).isEqualTo(StreamCursor.start());
  }

  @Test
  void aNegativeOffsetIsNegativeWithTheKindsOwnDetail() {
    assertThatThrownBy(() -> StreamCursorText.parse("-5:" + DIGEST))
        .isInstanceOfSatisfying(
            StreamRefused.class,
            refused -> {
              assertThat(refused.kind()).isEqualTo(StreamRefused.Kind.NEGATIVE);
              assertThat(refused.detail()).isEmpty();
            });
  }

  @ParameterizedTest
  @ValueSource(strings = {"", "nocolon", "5", "5:zz", "-5:zz", "5:gggggggggggggggggggggggggggggggggggggggggggggggggggggggggggggggg", "99999999999999999999:" + DIGEST, ":", "5:", "a:" + DIGEST})
  void everyOtherTextIsMisalignedWithTheFixedUnparseableDetail(String text) {
    assertThatThrownBy(() -> StreamCursorText.parse(text))
        .isInstanceOfSatisfying(
            StreamRefused.class,
            refused -> {
              assertThat(refused.kind()).isEqualTo(StreamRefused.Kind.MISALIGNED);
              assertThat(refused.detail()).contains(StreamCursorText.UNPARSEABLE_DETAIL);
            });
  }

  @Test
  void theUnparseableDetailIsTheFixedSentence() {
    assertThat(StreamCursorText.UNPARSEABLE_DETAIL).isEqualTo("The stream cursor did not parse.");
  }
}
