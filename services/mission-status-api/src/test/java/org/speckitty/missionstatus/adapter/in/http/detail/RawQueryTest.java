package org.speckitty.missionstatus.adapter.in.http.detail;

import static org.assertj.core.api.Assertions.assertThat;

import java.util.List;
import org.junit.jupiter.api.Test;
import org.speckitty.missionstatus.application.query.port.in.dto.ArtifactPathInput;

/** The raw query string of an artifact request: every {@code path} value, percent-decoded once and strictly (AC-5.2). */
class RawQueryTest {

  private static ArtifactPathInput.Values values(String... values) {
    return new ArtifactPathInput.Values(List.of(values));
  }

  @Test
  void aSingleValueIsDecoded() {
    assertThat(RawQuery.path("path=spec.md")).isEqualTo(values("spec.md"));
    assertThat(RawQuery.path("path=tasks%2FWP01.md")).isEqualTo(values("tasks/WP01.md"));
  }

  @Test
  void anEncodedDotDotSlashIsDecodedNotRefusedHere() {
    assertThat(RawQuery.path("path=..%2fx")).isEqualTo(values("../x"));
  }

  @Test
  void aDoubleEncodedSequenceDecodesOnceToTheLiteralPercentText() {
    assertThat(RawQuery.path("path=%252e%252e")).isEqualTo(values("%2e%2e"));
  }

  @Test
  void aRepeatedParameterIsSeenNotJoined() {
    assertThat(RawQuery.path("path=a&path=b")).isEqualTo(values("a", "b"));
    assertThat(RawQuery.path("path=spec.md&path=plan.md")).isEqualTo(values("spec.md", "plan.md"));
  }

  @Test
  void aMissingParameterIsNoValueAndAnEmptyOneIsOneEmptyValue() {
    assertThat(RawQuery.path(null)).isEqualTo(values());
    assertThat(RawQuery.path("")).isEqualTo(values());
    assertThat(RawQuery.path("other=1")).isEqualTo(values());
    assertThat(RawQuery.path("path=")).isEqualTo(values(""));
    assertThat(RawQuery.path("path")).isEqualTo(values(""));
  }

  @Test
  void otherParametersAreIgnoredAndOrderIsKept() {
    assertThat(RawQuery.path("includePrompt=true&path=b&x=1&path=a")).isEqualTo(values("b", "a"));
  }

  @Test
  void invalidUtf8IsUndecodableNeverReplaced() {
    assertThat(RawQuery.path("path=%ff")).isEqualTo(new ArtifactPathInput.Undecodable());
    assertThat(RawQuery.path("path=%c0%af")).isEqualTo(new ArtifactPathInput.Undecodable());
    assertThat(RawQuery.path("path=%e2%82")).isEqualTo(new ArtifactPathInput.Undecodable());
    assertThat(RawQuery.path("path=%ed%a0%80")).as("an encoded surrogate").isEqualTo(new ArtifactPathInput.Undecodable());
    assertThat(RawQuery.path("path=ok&path=%ff")).as("one bad value spoils the input").isEqualTo(new ArtifactPathInput.Undecodable());
  }

  @Test
  void aBrokenPercentSequenceIsUndecodable() {
    assertThat(RawQuery.path("path=%zz")).isEqualTo(new ArtifactPathInput.Undecodable());
    assertThat(RawQuery.path("path=a%2")).isEqualTo(new ArtifactPathInput.Undecodable());
    assertThat(RawQuery.path("path=a%")).isEqualTo(new ArtifactPathInput.Undecodable());
  }

  @Test
  void onlyAsciiHexDigitsFollowAPercentSign() {
    assertThat(RawQuery.path("path=%２e%２e/x")).as("fullwidth digit 2").isEqualTo(new ArtifactPathInput.Undecodable());
    assertThat(RawQuery.path("path=a%١b")).as("Arabic-Indic digit one").isEqualTo(new ArtifactPathInput.Undecodable());
    assertThat(RawQuery.path("path=a%Ａ1")).as("fullwidth hex letter A").isEqualTo(new ArtifactPathInput.Undecodable());
    assertThat(RawQuery.path("path=a%4")).as("one digit only").isEqualTo(new ArtifactPathInput.Undecodable());
    assertThat(RawQuery.path("path=%4A%4a")).as("ASCII hex of both cases").isEqualTo(values("JJ"));
  }

  @Test
  void aPlusIsALiteralPlus() {
    assertThat(RawQuery.path("path=a+b.md")).isEqualTo(values("a+b.md"));
  }

  @Test
  void multiByteUtf8IsDecoded() {
    assertThat(RawQuery.path("path=caf%c3%a9.md")).isEqualTo(values("café.md"));
    assertThat(RawQuery.path("path=%e2%82%ac")).isEqualTo(values("€"));
  }

  @Test
  void anEncodedParameterNameIsDecoded() {
    assertThat(RawQuery.path("%70ath=spec.md")).isEqualTo(values("spec.md"));
  }
}
