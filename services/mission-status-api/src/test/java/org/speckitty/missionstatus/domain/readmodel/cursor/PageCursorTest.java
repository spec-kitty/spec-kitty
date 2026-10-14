package org.speckitty.missionstatus.domain.readmodel.cursor;

import static org.assertj.core.api.Assertions.assertThat;
import static org.assertj.core.api.Assertions.assertThatThrownBy;

import java.nio.charset.StandardCharsets;
import java.util.Base64;
import org.junit.jupiter.api.Test;

class PageCursorTest {

  private static final String PINNED = "v1.MjAyNi0wOS0wMlQxMDowMDowMCswMDowMAowMUowMTAwMDAwMDAwMDAwMDAwMDAwMDAwMQpmaXh0dXJlLWRpcg";
  private static final String CREATED = "2026-09-02T10:00:00+00:00";
  private static final String ID = "01J01000000000000000000001";
  private static final String DIRECTORY = "fixture-dir";

  private static String forged(String body) {
    return "v1." + Base64.getUrlEncoder().withoutPadding().encodeToString(body.getBytes(StandardCharsets.UTF_8));
  }

  private static void assertRefused(String cursor, InvalidPageCursor.Reason reason) {
    assertThatThrownBy(() -> PageCursor.decode(cursor)).isInstanceOfSatisfying(InvalidPageCursor.class, e -> assertThat(e.reason()).isEqualTo(reason));
  }

  @Test
  void encodingIsStatelessAndPinnedToTheSpecifiedForm() {
    assertThat(PageCursor.encode(CREATED, ID, DIRECTORY)).isEqualTo(PINNED);
    assertThat(PageCursor.encode(CREATED, ID, DIRECTORY)).isEqualTo(PageCursor.encode(CREATED, ID, DIRECTORY));
  }

  @Test
  void aCursorFromARealPositionRoundTrips() {
    PageCursor decoded = PageCursor.decode(PageCursor.encode(CREATED, ID, DIRECTORY));
    assertThat(decoded.createdAt()).isEqualTo(CREATED);
    assertThat(decoded.missionId()).isEqualTo(ID);
    assertThat(decoded.directory()).isEqualTo(DIRECTORY);
    assertThat(PageCursor.decode(PINNED)).isEqualTo(decoded);
  }

  @Test
  void theEmptyStringIsRefused() {
    assertRefused("", InvalidPageCursor.Reason.EMPTY);
    assertRefused(null, InvalidPageCursor.Reason.EMPTY);
  }

  @Test
  void aCursorThatIsNotTheV1FormIsRefused() {
    assertRefused("abc", InvalidPageCursor.Reason.NOT_V1);
    assertRefused("v2." + PINNED.substring(3), InvalidPageCursor.Reason.NOT_V1);
  }

  @Test
  void textThatIsNotBase64IsRefused() {
    assertRefused("v1.!!!not-base64!!!", InvalidPageCursor.Reason.NOT_BASE64);
    assertRefused("v1." + PINNED.substring(3) + "=", InvalidPageCursor.Reason.NOT_BASE64); // padded, so not the canonical form
    
  }

  @Test
  void aV1PrefixWithNothingAfterItHasNoSeparator() {
    assertRefused("v1.", InvalidPageCursor.Reason.NO_SEPARATOR);
  }

  @Test
  void bytesThatAreNotUtf8AreRefused() {
    String body = Base64.getUrlEncoder().withoutPadding().encodeToString(new byte[] {(byte) 0xC3, (byte) 0x28, 0x0A, 0x41});
    assertRefused("v1." + body, InvalidPageCursor.Reason.NOT_UTF8);
  }

  @Test
  void validBase64OfBytesWithNoLineFeedIsRefused() {
    assertRefused(forged(CREATED + ID), InvalidPageCursor.Reason.NO_SEPARATOR);
    // the two-field form of the first draft names no directory and is refused
    assertRefused(forged(CREATED + "\n" + ID), InvalidPageCursor.Reason.NO_SEPARATOR);
  }

  @Test
  void aValueOverFiveHundredAndTwelveCharactersIsRefused() {
    assertRefused("v1." + "A".repeat(597), InvalidPageCursor.Reason.TOO_LONG); // 600 characters
    String atLimit = forged("x".repeat(200) + "\n" + "y".repeat(100) + "\nd");
    assertThat(atLimit.length()).isLessThanOrEqualTo(512);
    assertThat(PageCursor.decode(atLimit).missionId()).hasSize(100);
    String over = forged("x".repeat(300) + "\n" + "y".repeat(100) + "\nd");
    assertThat(over.length()).isGreaterThan(512);
    assertRefused(over, InvalidPageCursor.Reason.TOO_LONG);
  }
}
