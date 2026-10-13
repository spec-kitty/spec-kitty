package org.speckitty.missionstatus.testsupport;

import static org.assertj.core.api.Assertions.assertThat;
import static org.assertj.core.api.Assertions.assertThatCode;
import static org.assertj.core.api.Assertions.assertThatThrownBy;

import java.nio.charset.StandardCharsets;
import java.util.HexFormat;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;
import org.junit.jupiter.api.Test;

/**
 * The comparator of the golden suite (AC-8a, AC-8d, NFR-005, post-analyze ruling ANL-003). The raw bytes decide; the parsed tree only
 * names the difference in the failure message.
 */
class CanonicalJsonTest {

  /**
   * Written by Python: {@code json.dumps(document, sort_keys=True, ensure_ascii=False, separators=(",", ":")) + "\n"} of a document
   * holding a non-ASCII string (Latin, a symbol, CJK and a supplementary character), escaped controls and fractional percentages.
   */
  private static final byte[] PYTHON_BYTES =
      HexFormat.of()
          .parseHex(
              "7b22667269656e646c794e616d65223a22436166c3a920e2988320e697a5e69cac20f09f90b1222c226e6f7465223a227461625c74686572655c6e6c696e65205c22715c22205c5c205c7530303031222c2270726f6772657373223a7b22646f6e6550657263656e74616765223a33332e333333332c22776569676874656450657263656e74616765223a36332e333333332c2278223a302e307d7d0a");

  private static Object tree() {
    Map<String, Object> progress = new LinkedHashMap<>();
    progress.put("weightedPercentage", new CanonicalJson.Num("63.3333"));
    progress.put("x", new CanonicalJson.Num("0.0"));
    progress.put("donePercentage", new CanonicalJson.Num("33.3333"));
    Map<String, Object> document = new LinkedHashMap<>();
    document.put("progress", progress);
    document.put("note", "tab\there\nline \"q\" \\ \u0001");
    document.put("friendlyName", new String(HexFormat.of().parseHex("436166c3a920e2988320e697a5e69cac20f09f90b1"), StandardCharsets.UTF_8));
    return document;
  }

  @Test
  void theIgnoreListIsOneNamedEmptyConstant() {
    assertThat(CanonicalJson.IGNORED_MEMBERS).isEmpty();
  }

  @Test
  void identicalBytesPassWithoutParsing() {
    byte[] notJson = "not json at all\n".getBytes(StandardCharsets.UTF_8);

    assertThatCode(() -> CanonicalJson.assertBodyEqualsGolden(notJson, notJson.clone())).doesNotThrowAnyException();
  }

  @Test
  void theCanonicalFormOfTheTreeIsTheBytesPythonWrote() {
    assertThat(CanonicalJson.toBytes(tree())).isEqualTo(PYTHON_BYTES);
  }

  @Test
  void aNonAsciiStringIsWrittenUnescapedAndAFractionalNumberKeepsItsText() {
    String text = new String(CanonicalJson.toBytes(tree()), StandardCharsets.UTF_8);

    assertThat(text).contains("Caf\u00e9").doesNotContain("\\u00e9").contains("33.3333").contains("\"x\":0.0").contains("\\u0001");
    assertThatCode(() -> CanonicalJson.assertBodyEqualsGolden(PYTHON_BYTES, PYTHON_BYTES.clone())).doesNotThrowAnyException();
  }

  @Test
  void aBodyEqualAsADocumentButDifferentInKeyOrderWhitespaceOrEscapeFails() {
    String golden = "{\"a\":\"\u00e9\",\"b\":1}\n";
    byte[] goldenBytes = golden.getBytes(StandardCharsets.UTF_8);
    for (String variant :
        List.of(
            "{\"b\":1,\"a\":\"\u00e9\"}\n", // key order
            "{\"a\": \"\u00e9\",\"b\":1}\n", // whitespace
            "{\"a\":\"\\u00e9\",\"b\":1}\n", // an ASCII escape of the same character
            "{\"a\":\"\u00e9\",\"b\":1}")) { // the trailing newline
      assertThatThrownBy(() -> CanonicalJson.assertBodyEqualsGolden(variant.getBytes(StandardCharsets.UTF_8), goldenBytes))
          .as(variant)
          .isInstanceOf(AssertionError.class)
          .hasMessageContaining("bytes differ");
    }
  }

  @Test
  void aDifferingMemberIsNamedInTheFailureMessage() {
    byte[] golden = "{\"items\":[{\"lastActivityAt\":\"2026-09-01T10:00:00Z\",\"slug\":\"a\"}],\"pageInfo\":{\"pageSize\":50}}\n".getBytes(StandardCharsets.UTF_8);
    byte[] actual = "{\"items\":[{\"lastActivityAt\":\"2026-09-01T10:00:01Z\",\"slug\":\"a\"}],\"pageInfo\":{\"pageSize\":50}}\n".getBytes(StandardCharsets.UTF_8);

    assertThatThrownBy(() -> CanonicalJson.assertBodyEqualsGolden(actual, golden))
        .isInstanceOf(AssertionError.class)
        .hasMessageContaining("items[0].lastActivityAt")
        .hasMessageContaining("member lastActivityAt");
  }

  @Test
  void aMissingAndAnExtraMemberAreNamed() {
    byte[] golden = "{\"a\":1,\"b\":2}\n".getBytes(StandardCharsets.UTF_8);

    assertThatThrownBy(() -> CanonicalJson.assertBodyEqualsGolden("{\"a\":1}\n".getBytes(StandardCharsets.UTF_8), golden)).hasMessageContaining("member b").hasMessageContaining("missing");
    assertThatThrownBy(() -> CanonicalJson.assertBodyEqualsGolden("{\"a\":1,\"b\":2,\"c\":3}\n".getBytes(StandardCharsets.UTF_8), golden)).hasMessageContaining("member c").hasMessageContaining("extra");
  }

  @Test
  void aBodyThatIsNotJsonFailsWithoutAnException() {
    assertThatThrownBy(() -> CanonicalJson.assertBodyEqualsGolden("{oops".getBytes(StandardCharsets.UTF_8), "{}\n".getBytes(StandardCharsets.UTF_8)))
        .isInstanceOf(AssertionError.class)
        .hasMessageContaining("not JSON");
  }

  @Test
  void theCanonicalFormSortsKeysByCodePoint() {
    Map<String, Object> document = new LinkedHashMap<>();
    document.put("\uFF5E", "bmp-high");
    document.put("\uD83D\uDC31", "supplementary");
    document.put("b", 1);
    document.put("B", 2);

    // code point order: B, b, U+FF5E, U+1F431 (UTF-16 order would put the supplementary pair before U+FF5E)
    assertThat(new String(CanonicalJson.toBytes(document), StandardCharsets.UTF_8))
        .isEqualTo("{\"B\":2,\"b\":1,\"\uFF5E\":\"bmp-high\",\"\uD83D\uDC31\":\"supplementary\"}\n");
  }
}
