package org.speckitty.missionstatus.nativesmoke;

import static org.assertj.core.api.Assertions.assertThat;

import java.nio.charset.StandardCharsets;
import java.nio.file.Files;
import java.nio.file.Path;
import java.util.List;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.io.TempDir;

/** The per-leg digest (T066): the SHA-256 of the concatenated RAW bodies and nothing else. */
class DigestTest {

  private static byte[] bytes(String text) {
    return text.getBytes(StandardCharsets.UTF_8);
  }

  @Test
  void twoIdenticalBodyListsHaveTheSameDigest() {
    assertThat(Digest.sha256(List.of(bytes("{\"a\":1}\n"), bytes("{\"b\":2}\n")))).isEqualTo(Digest.sha256(List.of(bytes("{\"a\":1}\n"), bytes("{\"b\":2}\n"))));
  }

  @Test
  void aReorderedListAndAListWithOneByteChangedDiffer() {
    String original = Digest.sha256(List.of(bytes("{\"a\":1}\n"), bytes("{\"b\":2}\n")));
    assertThat(Digest.sha256(List.of(bytes("{\"b\":2}\n"), bytes("{\"a\":1}\n")))).isNotEqualTo(original);
    assertThat(Digest.sha256(List.of(bytes("{\"a\":1}\n"), bytes("{\"b\":3}\n")))).isNotEqualTo(original);
  }

  @Test
  void aBodyIsHashedAsReceivedNeverCanonicalised() {
    String plain = Digest.sha256(List.of(bytes("{\"a\":1}\n")));
    assertThat(Digest.sha256(List.of(bytes("{\"a\":1}")))).as("the trailing newline counts").isNotEqualTo(plain);
    assertThat(Digest.sha256(List.of(bytes("{ \"a\": 1 }\n")))).as("whitespace counts").isNotEqualTo(plain);
    assertThat(Digest.sha256(List.of(bytes("{\"a\":1.0}\n")))).as("a number's spelling counts").isNotEqualTo(plain);
    assertThat(Digest.sha256(List.of(bytes("{\"a\":1}\r\n")))).as("a line ending counts").isNotEqualTo(plain);
  }

  @Test
  void aFractionalAndAUnicodeBodyHashToTheValueSha256sumGivesForTheSameBytes() {
    // built from code points so the source stays ASCII; the expected value comes from sha256sum over the same bytes, not from this code
    String text = new String(Character.toChars(0xE9)) + new String(Character.toChars(0x2615));
    byte[] body = bytes("{\"p\":5.0,\"t\":\"2026-09-01T11:00:00.123456Z\",\"u\":\"" + text + "\"}\n");
    assertThat(Digest.sha256(List.of(body))).isEqualTo("3d4c24b634ec2f11990e9849846fde60fce570f1321a5f24847eee81d038dda9");
  }

  @Test
  void theEmptyListIsRefusedBecauseAnEmptyReplayMustNotProduceADigest() {
    org.junit.jupiter.api.Assertions.assertThrows(IllegalArgumentException.class, () -> Digest.sha256(List.of()));
  }

  @Test
  void osAndArchNeverEnterTheHashButNameTheFile(@TempDir Path dir) throws Exception {
    String sha = Digest.sha256(List.of(bytes("x\n")));
    Path linux = Digest.write(dir, "linux", "x64", 4, 4, sha);
    Path mac = Digest.write(dir, "macos", "arm64", 4, 4, sha);
    assertThat(linux.getFileName().toString()).isEqualTo("digest-linux-x64.json");
    assertThat(mac.getFileName().toString()).isEqualTo("digest-macos-arm64.json");
    assertThat(Files.readString(linux)).contains("\"sha256\":\"" + sha + "\"");
    assertThat(Files.readString(mac)).contains("\"sha256\":\"" + sha + "\"");
  }

  @Test
  void theFileHoldsExactlyTheKeysTheGateHelperReads(@TempDir Path dir) throws Exception {
    Path file = Digest.write(dir, "windows", "x64", 31, 31, "ab".repeat(32));
    assertThat(Files.readString(file, StandardCharsets.UTF_8))
        .isEqualTo("{\"os\":\"windows\",\"arch\":\"x64\",\"requestCount\":31,\"bodyCount\":31,\"sha256\":\"" + "ab".repeat(32) + "\"}\n");
  }

  @Test
  void theNamesAreNormalisedToTheFourTargetsTokens() {
    assertThat(Digest.osToken("Linux")).isEqualTo("linux");
    assertThat(Digest.osToken("Mac OS X")).isEqualTo("macos");
    assertThat(Digest.osToken("Windows Server 2025")).isEqualTo("windows");
    assertThat(Digest.archToken("amd64")).isEqualTo("x64");
    assertThat(Digest.archToken("x86_64")).isEqualTo("x64");
    assertThat(Digest.archToken("aarch64")).isEqualTo("arm64");
    org.junit.jupiter.api.Assertions.assertThrows(IllegalArgumentException.class, () -> Digest.osToken("Plan 9"));
    org.junit.jupiter.api.Assertions.assertThrows(IllegalArgumentException.class, () -> Digest.archToken("riscv64"));
  }
}
