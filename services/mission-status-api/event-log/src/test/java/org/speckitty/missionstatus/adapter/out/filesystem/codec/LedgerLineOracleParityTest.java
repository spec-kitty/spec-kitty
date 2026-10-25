package org.speckitty.missionstatus.adapter.out.filesystem.codec;

import static org.assertj.core.api.Assertions.assertThat;

import java.nio.charset.StandardCharsets;
import java.util.List;
import java.util.Map;
import org.junit.jupiter.api.DynamicTest;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.TestFactory;
import org.speckitty.missionstatus.domain.model.LedgerLine;
import org.speckitty.missionstatus.domain.model.LineKind;

/**
 * The codec against live Python, line shape by line shape. {@link OracleCases} holds the verdict the CLI's event-stream partition gave
 * for each line. The Java verdict must equal it, except for the shapes in {@link #DIVERGENCES}, each with the reason and the decision.
 *
 * <p>Python's two classes of "not an event object" stay apart: a JSON value that is not an object is {@code NOT_OBJECT}, and an object that
 * is no usable row (a missing key, an unknown lane or kind, a bad nested value, or a shape on which Python crashes) is
 * {@code UNUSABLE_ROW}. A stream stops on the first and skips the second (Python's {@code poll_once} raises only on the first); a request
 * route refuses both.
 */
class LedgerLineOracleParityTest {

  /** Case name to the Java verdict where it differs from the oracle, on purpose. */
  private static final Map<String, String> DIVERGENCES = divergences();

  private static Map<String, String> divergences() {
    java.util.HashMap<String, String> map = new java.util.HashMap<>();
    // D1. Required text members must be text: the reducer orders by (at, event_id) as text and the domain records are typed, while
    // Python accepts any JSON value and only fails later, if two different types are ever compared. The codec refuses the line.
    for (String name : List.of("status-event-id-int", "status-event-id-null", "status-at-int", "status-at-null", "status-wp-id-int", "status-wp-id-null")) {
      map.put(name, "malformed:unusable_row");
    }
    // D2. An annotation's wp_id is str()-coerced by Python (a float or a list gets its repr); the codec coerces text, integers,
    // booleans and null the way Python does and refuses the rest rather than reproduce Python's float and container repr.
    map.put("annotation-wp-id-float", "malformed:unusable_row");
    map.put("annotation-wp-id-list", "malformed:unusable_row");
    // D3. A lifecycle row the contract could not forward (no text event_id or no text timestamp) is ignored; Python's partition
    // accepts it and the oracle would forward a null id.
    for (String name :
        List.of("lifecycle-no-event-id", "lifecycle-no-timestamp", "lifecycle-timestamp-int", "lifecycle-event-id-null", "lifecycle-with-at-not-timestamp")) {
      map.put(name, "ignored");
    }
    // D4 is not listed: Python CRASHES (AttributeError, not a StoreError) on an annotation delta or subtasks value that is not an object;
    // the oracle verdict "crash:*" is read as a refused line, which is what the codec answers.
    // D5. Python's str.splitlines() also splits at U+2028 and similar separators, so a ledger holding one inside a string reads as
    // two lines there; a physical line here ends at the newline byte only (the stream cursor's definition). The line is valid JSON.
    map.put("not-json-raw-newline-in-string", "malformed:unusable_row");
    // D6. A truthy slug that is not text (an int, a float, true, a list, an object) or a slug over 255 characters makes Python's partition
    // path raise (an AttributeError, a StoreError or an OSError from the path it builds), so materialize_snapshot fails on the ledger.
    // The codec serves the line: the slug is not part of a status event's identity here, and the domain does not read it. Live count: 0.
    for (String tag : List.of("feature", "mission")) {
      for (String shape : List.of("int", "float", "true", "list", "object", "256-chars")) {
        map.put("status-" + tag + "-" + shape, "status");
      }
    }
    // D7. materialize_snapshot reads the ledger with two readers that frame lines differently (str.splitlines() splits at a lone CR, at
    // U+0085 and at U+2028 and U+2029; a text-mode reader does not), so one of those characters inside an otherwise valid row makes it fail
    // there. A physical line here ends at the newline byte only, so the line is read whole: a CR between tokens is JSON whitespace, and
    // U+0085 or U+2028 inside a string is an ordinary string character (D5 is the same shape on a row that is not valid JSON). A raw CR
    // inside a string, and U+0085 or U+2028 between tokens, are not JSON, so both sides refuse them (pinned as agreeing cases). Live count: 0.
    for (String name : List.of("status-lone-cr-between-tokens", "status-nel-in-string", "status-line-separator-in-string")) {
      map.put(name, "status");
    }
    return Map.copyOf(map);
  }

  @TestFactory
  List<DynamicTest> everyLineShapeGetsTheVerdictOfLivePython() {
    return OracleCases.all().stream()
        .map(
            testCase ->
                DynamicTest.dynamicTest(
                    testCase.name(),
                    () -> {
                      String expected = DIVERGENCES.getOrDefault(testCase.name(), normalised(testCase.oracle()));
                      assertThat(verdict(testCase.line())).as(testCase.name()).isEqualTo(expected);
                    }))
        .toList();
  }

  @Test
  void everyDivergenceReallyDiffersFromTheOracleSoNoneIsStale() {
    for (OracleCases.Case testCase : OracleCases.all()) {
      String decision = DIVERGENCES.get(testCase.name());
      if (decision != null) {
        assertThat(decision).as(testCase.name()).isNotEqualTo(normalised(testCase.oracle()));
      }
    }
  }

  @Test
  void theOracleTableCoversEveryShapeGroupAndEveryDivergenceNamesARealCase() {
    List<String> names = OracleCases.all().stream().map(OracleCases.Case::name).toList();
    assertThat(names).hasSizeGreaterThan(250).doesNotHaveDuplicates();
    assertThat(names).containsAll(DIVERGENCES.keySet());
    for (String prefix : List.of("blank-", "not-json-", "not-object-", "json-", "status-", "annotation-", "lifecycle-", "retro-", "kind-")) {
      assertThat(names).as(prefix).anyMatch(name -> name.startsWith(prefix));
    }
    // Every verdict class of the oracle occurs, so the table is not vacuous.
    List<String> verdicts = OracleCases.all().stream().map(OracleCases.Case::oracle).toList();
    assertThat(verdicts).contains("status", "lifecycle", "ignored", "blank", "malformed:not_json", "malformed:not_object", "malformed:invalid_row");
    assertThat(verdicts).anyMatch(v -> v.startsWith("annotation:"));
  }

  private static String normalised(String oracle) {
    return oracle.equals("malformed:invalid_row") || oracle.startsWith("crash:") ? "malformed:unusable_row" : oracle;
  }

  /** The verdict string of the decoder for one line, in the oracle's vocabulary. */
  static String verdict(String line) {
    LedgerLine decoded = LedgerLineDecoder.decodeLine(1, (line + "\n").getBytes(StandardCharsets.UTF_8));
    return switch (decoded.kind()) {
      case LineKind.Status status -> "status";
      case LineKind.Lifecycle lifecycle -> "lifecycle";
      case LineKind.Annotation annotation -> "annotation:" + annotation.wpId();
      case LineKind.Ignored ignored -> "ignored";
      case LineKind.Blank blank -> "blank";
      case LineKind.Malformed malformed -> "malformed:" + malformed.reason().name().toLowerCase(java.util.Locale.ROOT);
    };
  }
}
