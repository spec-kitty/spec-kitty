package org.speckitty.missionstatus.domain.readmodel.cursor;

import static org.assertj.core.api.Assertions.assertThat;
import static org.assertj.core.api.Assertions.assertThatThrownBy;

import java.nio.charset.StandardCharsets;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.params.ParameterizedTest;
import org.junit.jupiter.params.provider.ValueSource;

class StreamCursorTest {

  private static final String EMPTY_DIGEST = "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855";

  @Test
  void theStartCursorIsOffsetZeroWithTheEmptyDigest() {
    assertThat(StreamCursor.start().offset()).isZero();
    assertThat(StreamCursor.start().invariant()).isEqualTo(EMPTY_DIGEST);
    assertThat(StreamCursor.start().toText()).isEqualTo("0:" + EMPTY_DIGEST);
    assertThat(StreamCursor.digestOf(new byte[0])).isEqualTo(EMPTY_DIGEST);
  }

  @Test
  void theInvariantIsTheSha256OfTheLastLineIncludingItsLineEnding() {
    String lf = StreamCursor.digestOf("{\"a\":1}\n".getBytes(StandardCharsets.UTF_8));
    String crlf = StreamCursor.digestOf("{\"a\":1}\r\n".getBytes(StandardCharsets.UTF_8));
    assertThat(lf).isEqualTo("e346432021b04179518d9614f3560ccd71354a4ee101ddcb893d6959a9d6301c");
    assertThat(crlf).isNotEqualTo(lf);
  }

  @Test
  void textFormRoundTripsAndIsDeterministic() {
    StreamCursor cursor = new StreamCursor(2555, "3d2a9d4d7b706cd619dc97806ccbc5797d383f027b7670256e79a67e8764a01e");
    assertThat(cursor.toText()).isEqualTo("2555:3d2a9d4d7b706cd619dc97806ccbc5797d383f027b7670256e79a67e8764a01e");
    assertThat(StreamCursor.parse(cursor.toText())).isEqualTo(cursor);
    assertThat(cursor.toText().getBytes(StandardCharsets.UTF_8)).isEqualTo(new StreamCursor(2555, cursor.invariant()).toText().getBytes(StandardCharsets.UTF_8));
    assertThat(StreamCursor.parse("0:" + EMPTY_DIGEST)).isEqualTo(StreamCursor.start());
  }

  @Test
  void aNegativeOffsetIsRefusedAsNegative() {
    assertThatThrownBy(() -> new StreamCursor(-1, EMPTY_DIGEST)).isInstanceOfSatisfying(StreamCursorException.class, e -> assertThat(e.reason()).isEqualTo(StreamCursorException.Reason.NEGATIVE));
    assertThatThrownBy(() -> StreamCursor.parse("-5:" + EMPTY_DIGEST)).isInstanceOfSatisfying(StreamCursorException.class, e -> assertThat(e.reason()).isEqualTo(StreamCursorException.Reason.NEGATIVE));
  }

  @ParameterizedTest
  @ValueSource(strings = {"", "abc", "5", "5:", ":e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855", "05:e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855", "5:E3B0C44298FC1C149AFBF4C8996FB92427AE41E4649B934CA495991B7852B855", "5:abc", "x:e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855", "99999999999999999999:e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855"})
  void malformedTextIsRefusedAsMalformed(String text) {
    assertThatThrownBy(() -> StreamCursor.parse(text)).isInstanceOfSatisfying(StreamCursorException.class, e -> assertThat(e.reason()).isEqualTo(StreamCursorException.Reason.MALFORMED));
  }

  @Test
  void aMalformedInvariantAndANullTextAreRefused() {
    assertThatThrownBy(() -> new StreamCursor(1, "short")).isInstanceOf(StreamCursorException.class);
    assertThatThrownBy(() -> StreamCursor.parse(null)).isInstanceOfSatisfying(StreamCursorException.class, e -> assertThat(e.reason()).isEqualTo(StreamCursorException.Reason.MALFORMED));
  }
}
