package org.speckitty.missionstatus.adapter.out.filesystem.codec;

import static org.assertj.core.api.Assertions.assertThat;
import static org.assertj.core.api.Assertions.assertThatThrownBy;

import java.io.ByteArrayOutputStream;
import java.nio.charset.StandardCharsets;
import java.security.MessageDigest;
import java.util.HexFormat;
import java.util.List;
import org.junit.jupiter.api.Test;
import org.speckitty.missionstatus.domain.model.Actor;
import org.speckitty.missionstatus.domain.model.LedgerLine;
import org.speckitty.missionstatus.domain.model.Lane;
import org.speckitty.missionstatus.domain.model.LifecycleEvent;
import org.speckitty.missionstatus.domain.model.LineKind;
import org.speckitty.missionstatus.domain.model.MalformedReason;
import org.speckitty.missionstatus.domain.model.StatusEvent;
import org.speckitty.missionstatus.domain.model.TailClassification;

/**
 * Framing, hashing, tail classification and the decisions the codec took by reading Python. Test names cite the Python behaviour they
 * pin. Row shapes are in {@link LedgerLineOracleParityTest}. Synthetic ULIDs only.
 */
class LedgerLineDecoderTest {

  private static final String STATUS =
      "{\"actor\":\"claude\",\"at\":\"2026-02-08T12:00:00+00:00\",\"event_id\":\"01HXYZ0000000000000000000B\",\"evidence\":null,"
          + "\"execution_mode\":\"worktree\",\"force\":false,\"from_lane\":\"planned\",\"reason\":null,\"review_ref\":null,\"to_lane\":\"claimed\",\"wp_id\":\"WP01\"}";
  private static final String LIFECYCLE =
      "{\"aggregate_id\":\"x\",\"event_id\":\"01HXYZ0000000000000000000C\",\"event_type\":\"MissionCreated\",\"timestamp\":\"2026-02-08T11:00:00+00:00\"}";
  private static final String IGNORED = "{\"event_type\":\"DecisionPointOpened\"}";

  private static byte[] bytes(String text) {
    return text.getBytes(StandardCharsets.UTF_8);
  }

  private static String sha256(byte[] data) throws Exception {
    return HexFormat.of().formatHex(MessageDigest.getInstance("SHA-256").digest(data));
  }

  private static LineKind kindOf(String line) {
    return LedgerLineDecoder.decodeLine(1, bytes(line + "\n")).kind();
  }

  // ---- framing, numbering, digest ---------------------------------------------------------------------------------------

  @Test
  void anEmptyLedgerHasNoLinesAndNoTail() {
    LedgerLineDecoder.Decoded decoded = LedgerLineDecoder.decode(new byte[0]);
    assertThat(decoded.lines()).isEmpty();
    assertThat(decoded.tail()).isEqualTo(TailClassification.NONE);
  }

  @Test
  void linesAreNumberedFromOneAndCarryTheDigestAndLengthOfTheirRawBytesIncludingTheNewline() throws Exception {
    byte[] first = bytes(STATUS + "\n");
    byte[] second = bytes(LIFECYCLE + "\n");
    byte[] all = concat(first, second);
    LedgerLineDecoder.Decoded decoded = LedgerLineDecoder.decode(all);
    assertThat(decoded.tail()).isEqualTo(TailClassification.NONE);
    assertThat(decoded.lines()).hasSize(2);
    LedgerLine one = decoded.lines().get(0);
    LedgerLine two = decoded.lines().get(1);
    assertThat(one.lineNumber()).isEqualTo(1);
    assertThat(two.lineNumber()).isEqualTo(2);
    // The tail reader's invariant is sha256(chunk + b"\n"): the newline is part of the hashed line.
    assertThat(one.rawLineSha256()).isEqualTo(sha256(first));
    assertThat(two.rawLineSha256()).isEqualTo(sha256(second));
    assertThat(one.byteLength()).isEqualTo(first.length);
    assertThat(two.byteLength()).isEqualTo(second.length);
    assertThat(one.kind()).isInstanceOf(LineKind.Status.class);
    assertThat(two.kind()).isInstanceOf(LineKind.Lifecycle.class);
  }

  @Test
  void aWindowStartsAtTheLineNumberTheCallerGives() {
    LedgerLineDecoder.Decoded decoded = LedgerLineDecoder.decode(bytes(STATUS + "\n" + IGNORED + "\n"), 41);
    assertThat(decoded.lines()).extracting(LedgerLine::lineNumber).containsExactly(41L, 42L);
    assertThatThrownBy(() -> LedgerLineDecoder.decode(new byte[0], 0)).isInstanceOf(IllegalArgumentException.class);
  }

  @Test
  void aCrlfLedgerDiffersFromItsLfTwinInDigestAndLengthButNotInKindOrCount() throws Exception {
    byte[] lf = bytes(STATUS + "\n" + LIFECYCLE + "\n");
    byte[] crlf = bytes(STATUS + "\r\n" + LIFECYCLE + "\r\n");
    LedgerLineDecoder.Decoded lfDecoded = LedgerLineDecoder.decode(lf);
    LedgerLineDecoder.Decoded crlfDecoded = LedgerLineDecoder.decode(crlf);
    assertThat(crlfDecoded.lines()).hasSameSizeAs(lfDecoded.lines());
    for (int i = 0; i < lfDecoded.lines().size(); i++) {
      LedgerLine plain = lfDecoded.lines().get(i);
      LedgerLine windows = crlfDecoded.lines().get(i);
      assertThat(windows.kind()).isEqualTo(plain.kind());
      assertThat(windows.rawLineSha256()).isNotEqualTo(plain.rawLineSha256());
      assertThat(windows.byteLength()).isEqualTo(plain.byteLength() + 1);
    }
    // The digest is over the raw bytes including the carriage return.
    assertThat(crlfDecoded.lines().get(0).rawLineSha256()).isEqualTo(sha256(bytes(STATUS + "\r\n")));
  }

  @Test
  void aLoneCarriageReturnIsNotALineBreakHerePythonsUniversalNewlinesSplitAtIt() {
    // Python (read_text + splitlines) reads '{...}\r{...}\n' as two rows. A physical line is delimited by the newline byte only, which
    // is the stream cursor's definition, so this is one line that is not one JSON value. Decision D6, a known divergence.
    LedgerLineDecoder.Decoded decoded = LedgerLineDecoder.decode(bytes(IGNORED + "\r" + IGNORED + "\n"));
    assertThat(decoded.lines()).hasSize(1);
    assertThat(decoded.lines().get(0).kind()).isEqualTo(new LineKind.Malformed(MalformedReason.NOT_JSON));
  }

  @Test
  void aLineIsDecodedOnItsOwnWithItsGivenNumber() throws Exception {
    byte[] raw = bytes(STATUS + "\n");
    LedgerLine line = LedgerLineDecoder.decodeLine(7, raw);
    assertThat(line.lineNumber()).isEqualTo(7);
    assertThat(line.rawLineSha256()).isEqualTo(sha256(raw));
    assertThat(line.byteLength()).isEqualTo(raw.length);
    assertThatThrownBy(() -> LedgerLineDecoder.decodeLine(0, raw)).isInstanceOf(IllegalArgumentException.class);
    assertThatThrownBy(() -> LedgerLineDecoder.decodeLine(1, bytes(STATUS))).isInstanceOf(IllegalArgumentException.class);
    assertThatThrownBy(() -> LedgerLineDecoder.decodeLine(1, bytes(STATUS + "\n" + STATUS + "\n"))).isInstanceOf(IllegalArgumentException.class);
    assertThatThrownBy(() -> LedgerLineDecoder.decodeLine(1, new byte[0])).isInstanceOf(IllegalArgumentException.class);
  }

  // ---- the unterminated tail ---------------------------------------------------------------------------------------------

  @Test
  void anUnterminatedLastLineIsNotALineAndIsClassifiedByWhatItHolds() {
    // L4 (does not parse) and L4b (valid JSON) are both a non-whitespace tail: the application refuses both with ledger_torn_tail.
    LedgerLineDecoder.Decoded torn = LedgerLineDecoder.decode(bytes(STATUS + "\n{\"event_id\":"));
    assertThat(torn.lines()).hasSize(1);
    assertThat(torn.tail()).isEqualTo(TailClassification.NON_WHITESPACE);
    LedgerLineDecoder.Decoded complete = LedgerLineDecoder.decode(bytes(STATUS + "\n" + LIFECYCLE));
    assertThat(complete.lines()).hasSize(1);
    assertThat(complete.tail()).isEqualTo(TailClassification.NON_WHITESPACE);
  }

  @Test
  void aWhitespaceOnlyTailIsNeitherAnEventNorATear() {
    for (String tail : List.of(" ", "   ", "\t", "\r", " \r", "\u00a0", "\u3000", "\u0085", "\u001c")) {
      LedgerLineDecoder.Decoded decoded = LedgerLineDecoder.decode(bytes(STATUS + "\n" + tail));
      assertThat(decoded.lines()).as(tail).hasSize(1);
      assertThat(decoded.tail()).as(tail).isEqualTo(TailClassification.WHITESPACE);
    }
  }

  @Test
  void aTailThatIsNotValidUtf8IsNonWhitespace() {
    byte[] data = concat(bytes(STATUS + "\n"), new byte[] {(byte) 0xff, (byte) 0xfe});
    assertThat(LedgerLineDecoder.decode(data).tail()).isEqualTo(TailClassification.NON_WHITESPACE);
  }

  @Test
  void aZeroWidthSpaceTailIsNotWhitespaceToPython() {
    assertThat(LedgerLineDecoder.decode(bytes(STATUS + "\n\u200b")).tail()).isEqualTo(TailClassification.NON_WHITESPACE);
  }

  // ---- blanks ------------------------------------------------------------------------------------------------------------

  @Test
  void aBlankTerminatedLineIsBlankWhateverPythonStripCallsWhitespace() {
    LedgerLine plain = LedgerLineDecoder.decodeLine(3, bytes("\n"));
    assertThat(plain.kind()).isEqualTo(new LineKind.Blank());
    assertThat(plain.byteLength()).isEqualTo(1);
    for (String blank : List.of("   ", "\t\r", "\u00a0", "\u3000", "\u0085", "\u001c")) {
      assertThat(kindOf(blank)).as(blank).isEqualTo(new LineKind.Blank());
    }
  }

  // ---- non-UTF-8 ---------------------------------------------------------------------------------------------------------

  @Test
  void invalidUtf8IsMalformedPerLineAndTheNextLinesStillDecode() {
    for (byte[] bad :
        List.of(
            new byte[] {(byte) 0xff},
            new byte[] {(byte) 0xc3, (byte) 0x28},
            new byte[] {(byte) 0xc0, (byte) 0xaf},
            new byte[] {(byte) 0xed, (byte) 0xa0, (byte) 0x80},
            new byte[] {(byte) 0xe2, (byte) 0x82},
            new byte[] {(byte) 0xf8, (byte) 0x88, (byte) 0x80, (byte) 0x80, (byte) 0x80})) {
      byte[] ledger = concat(bytes(STATUS + "\n"), bad, bytes("\n" + LIFECYCLE + "\n"));
      LedgerLineDecoder.Decoded decoded = LedgerLineDecoder.decode(ledger);
      assertThat(decoded.lines()).hasSize(3);
      assertThat(decoded.lines().get(0).kind()).isInstanceOf(LineKind.Status.class);
      assertThat(decoded.lines().get(1).kind()).isEqualTo(new LineKind.Malformed(MalformedReason.NOT_UTF8));
      assertThat(decoded.lines().get(1).lineNumber()).isEqualTo(2);
      assertThat(decoded.lines().get(2).kind()).isInstanceOf(LineKind.Lifecycle.class);
    }
  }

  @Test
  void invalidUtf8InsideAnOtherwiseValidObjectIsStillNotUtf8() {
    byte[] raw = concat(bytes("{\"event_type\":\"X\",\"a\":\""), new byte[] {(byte) 0xff}, bytes("\"}\n"));
    assertThat(LedgerLineDecoder.decodeLine(1, raw).kind()).isEqualTo(new LineKind.Malformed(MalformedReason.NOT_UTF8));
  }

  @Test
  void validMultiByteTextIsFineAndHashedAsBytes() throws Exception {
    byte[] raw = bytes("{\"event_type\":\"X\",\"a\":\"\u00e9\u20ac\ud83d\ude00\"}\n");
    LedgerLine line = LedgerLineDecoder.decodeLine(1, raw);
    assertThat(line.kind()).isEqualTo(new LineKind.Ignored());
    assertThat(line.byteLength()).isEqualTo(raw.length);
    assertThat(line.rawLineSha256()).isEqualTo(sha256(raw));
  }

  // ---- decisions read from Python's json.loads --------------------------------------------------------------------------

  @Test
  void duplicateKeysTheLastOneWinsLikePythonJsonLoads() {
    String lastIsLifecycle = "{\"event_type\":\"X\",\"event_type\":\"MissionCreated\",\"event_id\":\"e1\",\"timestamp\":\"t1\"}";
    String firstIsLifecycle = "{\"event_type\":\"MissionCreated\",\"event_type\":\"X\",\"event_id\":\"e1\",\"timestamp\":\"t1\"}";
    assertThat(kindOf(lastIsLifecycle)).isEqualTo(new LineKind.Lifecycle(new LifecycleEvent("e1", "MissionCreated", "t1")));
    assertThat(kindOf(firstIsLifecycle)).isEqualTo(new LineKind.Ignored());
  }

  @Test
  void nanAndInfinityAreAcceptedLikePythonJsonLoadsButTheOtherSpellingsAreNot() {
    for (String accepted : List.of("NaN", "Infinity", "-Infinity")) {
      assertThat(kindOf("{\"event_type\":\"X\",\"a\":" + accepted + "}")).as(accepted).isEqualTo(new LineKind.Ignored());
    }
    for (String rejected : List.of("+Infinity", "INF", "-INF", "+INF", "nan", "infinity", "-NaN", "+NaN")) {
      assertThat(kindOf("{\"event_type\":\"X\",\"a\":" + rejected + "}")).as(rejected).isEqualTo(new LineKind.Malformed(MalformedReason.NOT_JSON));
    }
  }

  @Test
  void numberFormsFollowPythonsGrammarAndLargeValuesAreFine() {
    for (String accepted : List.of("0", "-0", "1e5", "1E+2", "1.5e-3", "123456789012345678901234567890", "1e999", "-1.0")) {
      assertThat(kindOf("{\"event_type\":\"X\",\"a\":" + accepted + "}")).as(accepted).isEqualTo(new LineKind.Ignored());
    }
    for (String rejected : List.of("01", "1.", ".5", "+1", "0x1", "1e", "--1", "1_0")) {
      assertThat(kindOf("{\"event_type\":\"X\",\"a\":" + rejected + "}")).as(rejected).isEqualTo(new LineKind.Malformed(MalformedReason.NOT_JSON));
    }
  }

  @Test
  void stringsAcceptEscapedLoneSurrogatesButNotRawControlCharactersLikePythonsStrictMode() {
    assertThat(kindOf("{\"event_type\":\"X\",\"a\":\"\\ud800\"}")).isEqualTo(new LineKind.Ignored());
    assertThat(kindOf("{\"event_type\":\"X\",\"a\":\"\\ud83d\\ude00\"}")).isEqualTo(new LineKind.Ignored());
    assertThat(kindOf("{\"event_type\":\"X\",\"a\":\"\\u0000\"}")).isEqualTo(new LineKind.Ignored());
    assertThat(kindOf("{\"event_type\":\"X\",\"a\":\"\t\"}")).isEqualTo(new LineKind.Malformed(MalformedReason.NOT_JSON));
    assertThat(kindOf("{\"event_type\":\"X\",\"a\":\"\\x\"}")).isEqualTo(new LineKind.Malformed(MalformedReason.NOT_JSON));
    assertThat(kindOf("{\"event_type\":\"X\",\"a\":\"\\u12G4\"}")).isEqualTo(new LineKind.Malformed(MalformedReason.NOT_JSON));
  }

  @Test
  void aByteOrderMarkIsNotWhitespaceToPythonSoTheLineIsNotJson() {
    assertThat(LedgerLineDecoder.decodeLine(1, bytes("\ufeff{\"event_type\":\"X\"}\n")).kind()).isEqualTo(new LineKind.Malformed(MalformedReason.NOT_JSON));
    assertThat(LedgerLineDecoder.decodeLine(1, concat(new byte[] {(byte) 0xef, (byte) 0xbb, (byte) 0xbf}, bytes("{\"event_type\":\"X\"}\n"))).kind())
        .isEqualTo(new LineKind.Malformed(MalformedReason.NOT_JSON));
  }

  @Test
  void aNonObjectJsonValueIsMalformedAsNotObjectAndATextThatIsNoJsonIsNotJson() {
    for (String value : List.of("[]", "1", "\"s\"", "null", "true", "NaN", "[{}]")) {
      assertThat(kindOf(value)).as(value).isEqualTo(new LineKind.Malformed(MalformedReason.NOT_OBJECT));
    }
    for (String text : List.of("{", "abc", "{'a':1}", "{\"a\":1} x", "{\"a\":1}{\"b\":2}", "{\"a\":1,}")) {
      assertThat(kindOf(text)).as(text).isEqualTo(new LineKind.Malformed(MalformedReason.NOT_JSON));
    }
  }

  @Test
  void nestingOfAHundredLevelsParses() {
    String nested = "{\"event_type\":\"X\",\"a\":" + "[".repeat(100) + "]".repeat(100) + "}";
    assertThat(kindOf(nested)).isEqualTo(new LineKind.Ignored());
  }

  @Test
  void aRidiculouslyDeepNestingIsRefusedNotACrash() {
    String nested = "{\"event_type\":\"X\",\"a\":" + "[".repeat(5000) + "]".repeat(5000) + "}";
    assertThat(kindOf(nested)).isEqualTo(new LineKind.Malformed(MalformedReason.NOT_JSON));
  }

  // ---- what a decoded row carries ---------------------------------------------------------------------------------------

  @Test
  void aStatusRowCarriesTheMembersTheReducerReads() {
    LineKind kind =
        kindOf(
            "{\"actor\":\"a\",\"at\":\"2026-02-08T12:00:00+00:00\",\"event_id\":\"E1\",\"execution_mode\":\"worktree\",\"force\":true,"
                + "\"from_lane\":\"in_review\",\"to_lane\":\"canceled\",\"wp_id\":\"WP02\",\"reason\":\"because\",\"review_ref\":\"feedback://x\","
                + "\"reason_source\":\"operator\",\"policy_metadata\":{\"agent\":\"claude\"}}");
    assertThat(kind)
        .isEqualTo(new LineKind.Status(new StatusEvent("E1", "2026-02-08T12:00:00+00:00", "WP02", Lane.IN_REVIEW, Lane.CANCELED, true, "feedback://x", "because", "operator", "claude", new Actor("a", null, null))));
  }

  @Test
  void forceFollowsPythonTruthinessAndOptionalMembersDefaultToNull() {
    String base = STATUS.replace("\"force\":false", "\"force\":%s");
    assertThat(((LineKind.Status) kindOf(base.formatted("true"))).event().force()).isTrue();
    assertThat(((LineKind.Status) kindOf(base.formatted("1"))).event().force()).isTrue();
    assertThat(((LineKind.Status) kindOf(base.formatted("\"yes\""))).event().force()).isTrue();
    assertThat(((LineKind.Status) kindOf(base.formatted("[0]"))).event().force()).isTrue();
    assertThat(((LineKind.Status) kindOf(base.formatted("1.5"))).event().force()).isTrue();
    assertThat(((LineKind.Status) kindOf(base.formatted("NaN"))).event().force()).isTrue();
    for (String falsy : List.of("false", "0", "0.0", "\"\"", "[]", "{}", "null")) {
      assertThat(((LineKind.Status) kindOf(base.formatted(falsy))).event().force()).as(falsy).isFalse();
    }
    StatusEvent event = ((LineKind.Status) kindOf(STATUS)).event();
    assertThat(event.reviewRef()).isNull();
    assertThat(event.reason()).isNull();
    assertThat(event.reasonSource()).isNull();
    assertThat(event.claimAgent()).isNull();
  }

  @Test
  void optionalMembersOfTheWrongTypeDoNotRefuseTheLine() {
    // Python reads them with .get() and accepts any value; only 'is not None' is ever asked of review_ref. Decision D7: a non-text
    // review_ref keeps the line (and counts as present), the others read as absent.
    StatusEvent event =
        ((LineKind.Status)
                kindOf(STATUS.replace("\"review_ref\":null", "\"review_ref\":5,\"reason_source\":5,\"policy_metadata\":{\"agent\":5}").replace("\"reason\":null", "\"reason\":5")))
            .event();
    assertThat(event.reviewRef()).isNotNull();
    assertThat(event.reason()).isNull();
    assertThat(event.reasonSource()).isNull();
    assertThat(event.claimAgent()).isNull();
    StatusEvent notAnObject = ((LineKind.Status) kindOf(STATUS.replace("\"review_ref\":null", "\"policy_metadata\":\"x\""))).event();
    assertThat(notAnObject.claimAgent()).isNull();
  }

  @Test
  void aTimestampThatDoesNotParseIsKeptAsTextLikeParseDiaryDoes() {
    // DD-79: parse_diary never parses 'at'; the reducer orders it as text. The instant is parsed only where lastActivityAt is derived
    // (domain.readmodel.overview.Instants), which refuses it there. The codec keeps the text.
    LineKind kind = kindOf(STATUS.replace("2026-02-08T12:00:00+00:00", "not-a-date"));
    assertThat(((LineKind.Status) kind).event().at()).isEqualTo("not-a-date");
    assertThat(kindOf(STATUS.replace("2026-02-08T12:00:00+00:00", ""))).isInstanceOf(LineKind.Status.class);
    assertThat(kindOf(LIFECYCLE.replace("2026-02-08T11:00:00+00:00", "garbage"))).isEqualTo(new LineKind.Lifecycle(new LifecycleEvent("01HXYZ0000000000000000000C", "MissionCreated", "garbage")));
  }

  @Test
  void aLifecycleRowKeepsItsTimestampAsItsInstant() {
    assertThat(kindOf(LIFECYCLE)).isEqualTo(new LineKind.Lifecycle(new LifecycleEvent("01HXYZ0000000000000000000C", "MissionCreated", "2026-02-08T11:00:00+00:00")));
    for (String type : List.of("MissionCreated", "SpecifyStarted", "SpecifyCompleted", "PlanStarted", "PlanCompleted", "TasksStarted", "TasksCompleted")) {
      assertThat(kindOf(LIFECYCLE.replace("MissionCreated", type))).as(type).isInstanceOf(LineKind.Lifecycle.class);
    }
    assertThat(kindOf(LIFECYCLE.replace("MissionCreated", "WPCreated"))).isEqualTo(new LineKind.Ignored());
  }

  @Test
  void anEventTypeRowThatAlsoHasLaneFieldsIsNonLaneToPythonsPartitionAndSoNotAStatusRow() {
    // parse_diary / the CLI partition skip any row with an 'event_type' key before reading lanes. The oracle's stream builder looks at
    // 'to_lane' first, so for this odd shape the two halves of Python disagree; the codec follows the reducer's partition.
    assertThat(kindOf(STATUS.replace("{", "{\"event_type\":\"DecisionPointOpened\","))).isEqualTo(new LineKind.Ignored());
    assertThat(kindOf(STATUS.replace("{", "{\"event_type\":\"MissionCreated\",\"timestamp\":\"t\","))).isEqualTo(new LineKind.Lifecycle(new LifecycleEvent("01HXYZ0000000000000000000B", "MissionCreated", "t")));
  }

  // ---- annotation rows (operator ruling 2026-10-11) ----------------------------------------------------------------------

  private static String annotation(String wpId, String delta) {
    return "{\"actor\":\"claude\",\"at\":\"2026-02-08T12:00:01+00:00\",\"delta\":" + delta + ",\"event_id\":\"01HXYZ0000000000000000000A\",\"kind\":\"annotation\",\"wp_id\":" + wpId + "}";
  }

  @Test
  void anAnnotationRowIsAKindAnnotationRowAndItsWorkPackageIsItsWpId() {
    assertThat(kindOf(annotation("\"WP09\"", "{\"note\":\"hello\"}"))).isEqualTo(new LineKind.Annotation("WP09"));
    assertThat(kindOf(annotation("\"WP09\"", "{}"))).isEqualTo(new LineKind.Annotation("WP09"));
  }

  @Test
  void anAnnotationsWpIdIsStrCoercedLikePythonsStrOfTheValue() {
    assertThat(kindOf(annotation("5", "{}"))).isEqualTo(new LineKind.Annotation("5"));
    assertThat(kindOf(annotation("null", "{}"))).isEqualTo(new LineKind.Annotation("None"));
    assertThat(kindOf(annotation("true", "{}"))).isEqualTo(new LineKind.Annotation("True"));
    assertThat(kindOf(annotation("false", "{}"))).isEqualTo(new LineKind.Annotation("False"));
    assertThat(kindOf(annotation("123456789012345678901234567890", "{}"))).isEqualTo(new LineKind.Annotation("123456789012345678901234567890"));
  }

  @Test
  void aKindOnARowThatIsNotAnnotationIsAnUnknownKindWhateverItsType() {
    for (String kind : List.of("\"decision\"", "\"\"", "\"ANNOTATION\"", "0", "false", "[]", "{}")) {
      assertThat(kindOf(STATUS.replace("{", "{\"kind\":" + kind + ","))).as(kind).isEqualTo(new LineKind.Malformed(MalformedReason.UNUSABLE_ROW));
    }
    // A null kind is no kind: the row is read as a status row.
    assertThat(kindOf(STATUS.replace("{", "{\"kind\":null,"))).isInstanceOf(LineKind.Status.class);
  }

  @Test
  void anAnnotationEventIdIsAUlidAndPythonsDollarAcceptsOneTrailingNewline() {
    String ok = annotation("\"WP09\"", "{}");
    assertThat(kindOf(ok.replace("01HXYZ0000000000000000000A", "01HXYZ0000000000000000000A\\n"))).isEqualTo(new LineKind.Annotation("WP09"));
    for (String bad : List.of("01hxyz0000000000000000000a", "01HXYZ", "01HXYZ0000000000000000000AA", "IIIIIIIIIIIIIIIIIIIIIIIIII", "LLLLLLLLLLLLLLLLLLLLLLLLLL", "OOOOOOOOOOOOOOOOOOOOOOOOOO", "UUUUUUUUUUUUUUUUUUUUUUUUUU", "01HXYZ0000000000000000000A\\n\\n")) {
      assertThat(kindOf(ok.replace("01HXYZ0000000000000000000A", bad))).as(bad).isEqualTo(new LineKind.Malformed(MalformedReason.UNUSABLE_ROW));
    }
    assertThat(kindOf(ok.replace("\"01HXYZ0000000000000000000A\"", "5"))).isEqualTo(new LineKind.Malformed(MalformedReason.UNUSABLE_ROW));
    assertThat(kindOf(ok.replace("\"01HXYZ0000000000000000000A\"", "null"))).isEqualTo(new LineKind.Malformed(MalformedReason.UNUSABLE_ROW));
  }

  @Test
  void anAnnotationMissingARequiredKeyIsMalformed() {
    String ok = annotation("\"WP09\"", "{}");
    for (String key : List.of("actor", "at", "delta", "event_id", "wp_id")) {
      String without = ok.replace("\"" + key + "\":", "\"" + key + "X\":");
      assertThat(without).doesNotContain("\"" + key + "\":");
      assertThat(kindOf(without)).as(key).isEqualTo(new LineKind.Malformed(MalformedReason.UNUSABLE_ROW));
    }
  }

  @Test
  void anAnnotationActorMustBeAScalarOrAFullStructuredBinding() {
    String ok = annotation("\"WP09\"", "{}");
    String full = "{\"role\":\"a\",\"profile\":\"b\",\"tool\":\"c\",\"model\":\"d\"}";
    assertThat(kindOf(ok.replace("\"claude\"", full))).isEqualTo(new LineKind.Annotation("WP09"));
    assertThat(kindOf(ok.replace("\"claude\"", "{\"role\":null,\"profile\":null,\"tool\":null,\"model\":null}"))).isEqualTo(new LineKind.Annotation("WP09"));
    assertThat(kindOf(ok.replace("\"claude\"", "5"))).isEqualTo(new LineKind.Annotation("WP09"));
    assertThat(kindOf(ok.replace("\"claude\"", "null"))).isEqualTo(new LineKind.Annotation("WP09"));
    for (String bad : List.of("{\"role\":\"a\"}", "{\"role\":\"a\",\"profile\":\"b\",\"tool\":\"c\",\"model\":\"d\",\"x\":\"e\"}", "{\"role\":1,\"profile\":\"b\",\"tool\":\"c\",\"model\":\"d\"}")) {
      assertThat(kindOf(ok.replace("\"claude\"", bad))).as(bad).isEqualTo(new LineKind.Malformed(MalformedReason.UNUSABLE_ROW));
    }
  }

  @Test
  void anAnnotationDeltaIsValidatedLikeWPInnerStateDeltaFromDict() {
    for (String ok : List.of("{}", "{\"subtasks\":{\"T001\":\"done\"}}", "{\"subtasks\":null}", "{\"review\":{\"at\":\"a\",\"actor\":\"b\",\"wp_id\":\"c\",\"reason\":\"d\"}}", "{\"review\":null}", "{\"review\":{\"at\":null,\"actor\":null,\"wp_id\":null,\"reason\":null}}",
        "{\"shell_pid\":12}", "{\"shell_pid\":\"12\"}", "{\"shell_pid\":\" +1_2 \"}", "{\"shell_pid\":1.5}", "{\"shell_pid\":true}", "{\"shell_pid\":null}", "{\"shell_pid\":\"\u0661\u0662\"}",
        "{\"tracker_refs\":[\"a\"]}", "{\"tracker_refs\":\"ab\"}", "{\"tracker_refs\":{\"a\":1}}", "{\"tracker_refs_replace\":[]}", "{\"release_runtime_claim\":\"no\"}", "{\"agent\":5,\"role\":[1],\"model\":{\"a\":1}}", "{\"zzz\":1}")) {
      assertThat(kindOf(annotation("\"WP09\"", ok))).as(ok).isEqualTo(new LineKind.Annotation("WP09"));
    }
    for (String bad : List.of("{\"subtasks\":{\"T001\":\"finished\"}}", "{\"subtasks\":[\"a\"]}", "{\"subtasks\":\"x\"}", "{\"review\":{}}", "{\"review\":{\"at\":\"a\",\"actor\":\"b\",\"wp_id\":\"c\"}}", "{\"review\":\"x\"}",
        "{\"shell_pid\":\"abc\"}", "{\"shell_pid\":\"1__2\"}", "{\"shell_pid\":\"_12\"}", "{\"shell_pid\":\"\"}", "{\"shell_pid\":[]}", "{\"shell_pid\":{}}", "{\"shell_pid\":NaN}", "{\"shell_pid\":Infinity}",
        "{\"tracker_refs\":5}", "{\"tracker_refs\":true}", "{\"tracker_refs_replace\":5}", "{\"tracker_refs\":1.5}", "5", "null", "[]", "\"x\"")) {
      assertThat(kindOf(annotation("\"WP09\"", bad))).as(bad).isEqualTo(new LineKind.Malformed(MalformedReason.UNUSABLE_ROW));
    }
  }

  @Test
  void anAnnotationWithAnEventTypeKeyIsStillAnAnnotationBecauseTheKindIsReadFirst() {
    assertThat(kindOf(withFirst(annotation("\"WP09\"", "{}"), "\"event_type\":\"MissionCreated\","))).isEqualTo(new LineKind.Annotation("WP09"));
    assertThat(kindOf(withFirst(annotation("\"WP09\"", "{}"), "\"event_name\":\"retrospective.x\","))).isEqualTo(new LineKind.Annotation("WP09"));
  }

  // ---- evidence and review_result of a status row ------------------------------------------------------------------------

  @Test
  void anEvidenceValueIsValidatedOnlyWhenTruthyLikeStatusEventFromDict() {
    String review = "{\"review\":{\"reviewer\":\"r\",\"verdict\":\"approved\",\"reference\":\"ref\"}";
    for (String ok : List.of("null", "{}", "[]", "0", "\"\"", "false", review + "}", review + ",\"repos\":[{\"repo\":\"a\",\"branch\":\"b\",\"commit\":\"c\"}]}", review + ",\"repos\":[]}", review + ",\"repos\":{}}", review + ",\"repos\":\"\"}",
        review + ",\"verification\":[{\"command\":\"c\",\"result\":\"pass\",\"summary\":\"s\"}]}")) {
      assertThat(kindOf(STATUS.replace("\"evidence\":null", "\"evidence\":" + ok))).as(ok).isInstanceOf(LineKind.Status.class);
    }
    for (String bad : List.of("\"x\"", "5", "true", "[1]", "{\"repos\":[]}", "{\"review\":null}", "{\"review\":\"x\"}", "{\"review\":{\"reviewer\":\"r\",\"verdict\":\"v\"}}", review + ",\"repos\":null}", review + ",\"repos\":[{\"repo\":\"a\",\"branch\":\"b\"}]}",
        review + ",\"repos\":[\"abc\"]}", review + ",\"repos\":{\"a\":1}}", review + ",\"repos\":\"abc\"}", review + ",\"repos\":5}", review + ",\"verification\":[{\"command\":\"c\"}]}", review + ",\"verification\":null}")) {
      assertThat(kindOf(STATUS.replace("\"evidence\":null", "\"evidence\":" + bad))).as(bad).isEqualTo(new LineKind.Malformed(MalformedReason.UNUSABLE_ROW));
    }
  }

  @Test
  void aReviewResultIsValidatedOnlyWhenTruthy() {
    String ok = "{\"reviewer\":\"r\",\"verdict\":\"approved\",\"reference\":\"ref\"}";
    for (String good : List.of("{}", ok, "{\"reviewer\":\"r\",\"verdict\":\"v\",\"reference\":\"x\",\"feedback_path\":\"p\"}", "null", "0", "[]")) {
      assertThat(kindOf(STATUS.replace("\"evidence\":null", "\"review_result\":" + good + ",\"evidence\":null"))).as(good).isInstanceOf(LineKind.Status.class);
    }
    for (String bad : List.of("{\"reviewer\":\"r\"}", "\"x\"", "5", "true", "[1]")) {
      assertThat(kindOf(STATUS.replace("\"evidence\":null", "\"review_result\":" + bad + ",\"evidence\":null"))).as(bad).isEqualTo(new LineKind.Malformed(MalformedReason.UNUSABLE_ROW));
    }
  }

  // ---- plumbing ----------------------------------------------------------------------------------------------------------

  @Test
  void theDecoderIsAUtilityClass() throws Exception {
    java.lang.reflect.Constructor<LedgerLineDecoder> constructor = LedgerLineDecoder.class.getDeclaredConstructor();
    assertThat(java.lang.reflect.Modifier.isPrivate(constructor.getModifiers())).isTrue();
    assertThat(LedgerLineDecoder.Decoded.class).isNotNull();
    assertThatThrownBy(() -> new LedgerLineDecoder.Decoded(null, TailClassification.NONE)).isInstanceOf(NullPointerException.class);
    assertThatThrownBy(() -> new LedgerLineDecoder.Decoded(List.of(), null)).isInstanceOf(NullPointerException.class);
  }

  /** The row with extra members written right after its opening brace. */
  private static String withFirst(String row, String members) {
    return "{" + members + row.substring(1);
  }

  private static byte[] concat(byte[]... parts) {
    ByteArrayOutputStream out = new ByteArrayOutputStream();
    for (byte[] part : parts) {
      out.writeBytes(part);
    }
    return out.toByteArray();
  }
}
