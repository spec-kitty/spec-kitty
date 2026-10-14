package org.speckitty.missionstatus.adapter.out.filesystem.codec;

import static org.assertj.core.api.Assertions.assertThat;
import static org.assertj.core.api.Assertions.assertThatThrownBy;

import java.nio.charset.StandardCharsets;
import java.util.List;
import java.util.Map;
import org.junit.jupiter.api.Test;
import org.speckitty.missionstatus.domain.model.Actor;
import org.speckitty.missionstatus.domain.model.HistoryRow;
import org.speckitty.missionstatus.domain.model.LedgerLine;
import org.speckitty.missionstatus.domain.model.Lane;
import org.speckitty.missionstatus.domain.model.LineKind;
import org.speckitty.missionstatus.domain.model.MalformedReason;
import org.speckitty.missionstatus.domain.model.ReviewOverrideRecord;
import org.speckitty.missionstatus.domain.model.ReviewResultRecord;
import org.speckitty.missionstatus.domain.model.StatusEvent;
import org.speckitty.missionstatus.domain.model.StatusEvent.SlotText;
import org.speckitty.missionstatus.domain.readmodel.reducer.AtThenEventId;
import org.speckitty.missionstatus.domain.readmodel.reducer.StatusReducer;
import org.speckitty.missionstatus.domain.readmodel.reducer.UnreducibleLedgerException;

/**
 * The members the decoder carries for the resolved Work Package state (FR-020, T033): what a status row and an annotation row give the
 * reducer, what a row gives {@code lifecycleTypes} and the history independently of its classification, and the three notes of the WP04
 * review (a present {@code event_type} key makes a row non-lane whatever its type; a missing key of a {@code review} object or a wrong key
 * set of a structured actor raises; annotation scalar slots are stored raw and stringified later).
 */
class LedgerLineDecoderResolvedMembersTest {

  private static String status(String extra) {
    return "{\"actor\":\"claude\",\"at\":\"2026-02-08T12:00:00+00:00\",\"event_id\":\"E1\",\"execution_mode\":\"worktree\",\"force\":false,"
        + "\"from_lane\":\"planned\",\"to_lane\":\"claimed\",\"wp_id\":\"WP01\"" + (extra.isEmpty() ? "" : "," + extra) + "}";
  }

  private static String annotation(String delta, String overrides) {
    return "{\"actor\":\"claude\",\"at\":\"2026-02-08T12:00:01+00:00\",\"delta\":" + delta + ",\"event_id\":\"01HXYZ0000000000000000000A\",\"kind\":\"annotation\",\"wp_id\":\"WP09\""
        + (overrides.isEmpty() ? "" : "," + overrides) + "}";
  }

  private static LedgerLine line(String text) {
    return LedgerLineDecoder.decodeLine(1, (text + "\n").getBytes(StandardCharsets.UTF_8));
  }

  private static StatusEvent event(String text) {
    return ((LineKind.Status) line(text).kind()).event();
  }

  private static LineKind.Annotation annotated(String text) {
    return (LineKind.Annotation) line(text).kind();
  }

  // ---- a status row ----------------------------------------------------------------------------------------------------------

  @Test
  void theClaimAgentIsWrittenOnlyWhenTruthyAndKeepsItsPythonTextWhateverItsType() {
    assertThat(event(status("\"policy_metadata\":{\"agent\":\"claude\"}")).claimAgentSlot()).isEqualTo(SlotText.of("claude"));
    assertThat(event(status("\"policy_metadata\":{\"agent\":123}")).claimAgentSlot()).isEqualTo(SlotText.of("123"));
    assertThat(event(status("\"policy_metadata\":{\"agent\":true}")).claimAgentSlot()).isEqualTo(SlotText.of("True"));
    assertThat(event(status("\"policy_metadata\":{\"agent\":[\"x\"]}")).claimAgentSlot()).isEqualTo(SlotText.UNSHOWN);
    assertThat(event(status("\"policy_metadata\":{\"agent\":{\"a\":1}}")).claimAgentSlot()).isEqualTo(SlotText.UNSHOWN);
    for (String falsy : List.of("\"\"", "0", "false", "null", "[]", "{}", "0.0")) {
      assertThat(event(status("\"policy_metadata\":{\"agent\":" + falsy + "}")).claimAgentSlot()).as(falsy).isNull();
    }
    assertThat(event(status("")).claimAgentSlot()).isNull();
    assertThat(event(status("\"policy_metadata\":\"x\"")).claimAgentSlot()).isNull();
  }

  @Test
  void theTextOnlyClaimAgentOfTheImplementerProjectionIsUnchanged() {
    assertThat(event(status("\"policy_metadata\":{\"agent\":123}")).claimAgent()).isNull();
    assertThat(event(status("\"policy_metadata\":{\"agent\":\"claude\"}")).claimAgent()).isEqualTo("claude");
  }

  @Test
  void theActorIdentityIsActorIdentityStrOfTheRowsActor() {
    assertThat(event(status("")).actorIdentity()).isEqualTo("claude");
    assertThat(event(status("").replace("\"claude\"", "\"user@example.com\"")).actorIdentity()).as("verbatim, not a handle").isEqualTo("user@example.com");
    // Python str() of a null, an integer and a boolean; the snapshot slot then holds that text
    assertThat(event(status("").replace("\"claude\"", "null")).actorIdentity()).isEqualTo("None");
    assertThat(event(status("").replace("\"claude\"", "123")).actorIdentity()).isEqualTo("123");
    assertThat(event(status("").replace("\"claude\"", "true")).actorIdentity()).isEqualTo("True");
    String record = "{\"role\":\"r\",\"profile\":\"p\",\"tool\":\"t\",\"model\":\"m\"}";
    assertThat(event(status("").replace("\"claude\"", record)).actorIdentity()).isEqualTo("t");
    assertThat(event(status("").replace("\"claude\"", record.replace("\"t\"", "null"))).actorIdentity()).isEqualTo("r");
    assertThat(event(status("").replace("\"claude\"", record.replace("\"t\"", "\"\""))).actorIdentity()).isEqualTo("r");
    assertThat(event(status("").replace("\"claude\"", "{\"role\":null,\"profile\":null,\"tool\":null,\"model\":null}")).actorIdentity()).isEmpty();
  }

  @Test
  void theHandlesOfTheActorStayWhatTheyWereWhileTheIdentityKeepsTheRawText() {
    StatusEvent event = event(status("").replace("\"claude\"", "null"));
    assertThat(event.actor()).as("a null actor is no actor for the history entry").isEqualTo(Actor.NONE);
    assertThat(event.actorIdentity()).isEqualTo("None");
  }

  @Test
  void aPopulatedReviewResultIsCarriedAndAnEmptyOneIsNone() {
    assertThat(event(status("\"review_result\":{\"reviewer\":\"rev\",\"verdict\":\"approved\",\"reference\":\"cycle-1\",\"feedback_path\":\"/x\"}")).reviewResult())
        .isEqualTo(new ReviewResultRecord("rev", "approved", "cycle-1"));
    for (String none : List.of("{}", "null", "false", "0", "\"\"")) {
      assertThat(event(status("\"review_result\":" + none)).reviewResult()).as(none).isNull();
    }
    assertThat(event(status("")).reviewResult()).isNull();
  }

  @Test
  void aReviewResultMemberThatIsNotTextIsReadAsTheOracleDoes() {
    ReviewResultRecord record = event(status("\"review_result\":{\"reviewer\":5,\"verdict\":null,\"reference\":7}")).reviewResult();
    assertThat(record.reviewer()).as("handle of a non-text value is null").isNull();
    assertThat(record.verdict()).as("the contract allows only text, so nothing else is read").isNull();
    assertThat(record.reference()).as("human text is str() of the value").isEqualTo("7");
    assertThat(event(status("\"review_result\":{\"reviewer\":\"r\",\"verdict\":\"approved\",\"reference\":null}")).reviewResult().reference()).isNull();
  }

  @Test
  void aStructuredActorWithoutExactlyTheFourKeysRaisesWhenReduced() {
    for (String bad : List.of("{\"role\":\"a\"}", "{\"role\":\"a\",\"profile\":\"b\",\"tool\":\"c\",\"model\":\"d\",\"x\":\"e\"}")) {
      String row = status("").replace("\"claude\"", bad);
      assertThat(line(row).kind()).as(bad).isEqualTo(new LineKind.Malformed(MalformedReason.UNUSABLE_ROW));
      assertThatThrownBy(() -> reduce(row)).as(bad).isInstanceOf(UnreducibleLedgerException.class);
      String annotated = annotation("{}", "").replace("\"claude\"", bad);
      assertThatThrownBy(() -> reduce(annotated)).as(bad).isInstanceOf(UnreducibleLedgerException.class);
    }
  }

  private static void reduce(String... rows) {
    byte[] bytes = (String.join("\n", rows) + "\n").getBytes(StandardCharsets.UTF_8);
    new StatusReducer(new AtThenEventId()).reduceLines(LedgerLineDecoder.decode(bytes).lines());
  }

  // ---- an annotation row -----------------------------------------------------------------------------------------------------

  @Test
  void anAnnotationCarriesItsSortKeysStrCoercedAndItsActorIdentity() {
    LineKind.Annotation plain = annotated(annotation("{}", ""));
    assertThat(plain.at()).isEqualTo("2026-02-08T12:00:01+00:00");
    assertThat(plain.eventId()).isEqualTo("01HXYZ0000000000000000000A");
    assertThat(plain.actorIdentity()).isEqualTo("claude");
    assertThat(plain.delta()).isEqualTo(LineKind.Annotation.Delta.NONE);

    assertThat(annotated(annotation("{}", "").replace("\"at\":\"2026-02-08T12:00:01+00:00\"", "\"at\":5")).at()).isEqualTo("5");
    assertThat(annotated(annotation("{}", "").replace("\"at\":\"2026-02-08T12:00:01+00:00\"", "\"at\":null")).at()).isEqualTo("None");
    assertThat(annotated(annotation("{}", "").replace("\"at\":\"2026-02-08T12:00:01+00:00\"", "\"at\":true")).at()).isEqualTo("True");
    assertThat(annotated(annotation("{}", "").replace("\"claude\"", "null")).actorIdentity()).isEqualTo("None");
  }

  @Test
  void theReplaceSlotsAreStoredRawAndStringifiedLaterAndABlankOrNullIsNoWrite() {
    LineKind.Annotation.Delta delta =
        annotated(annotation("{\"agent\":5,\"assignee\":true,\"role\":[1],\"model\":{\"a\":1},\"provider\":0,\"agent_profile\":\"\",\"agent_profile_version\":null,\"zzz\":1,\"shell_pid\":12}", "")).delta();

    assertThat(delta.replaceSlots())
        .containsOnly(
            Map.entry("agent", SlotText.of("5")),
            Map.entry("assignee", SlotText.of("True")),
            Map.entry("role", SlotText.UNSHOWN),
            Map.entry("model", SlotText.UNSHOWN),
            Map.entry("provider", SlotText.of("0")));
  }

  @Test
  void theReleaseFlagIsPythonTruthinessOfTheValue() {
    assertThat(annotated(annotation("{\"release_runtime_claim\":true}", "")).delta().releaseRuntimeClaim()).isTrue();
    assertThat(annotated(annotation("{\"release_runtime_claim\":\"no\"}", "")).delta().releaseRuntimeClaim()).isTrue();
    assertThat(annotated(annotation("{\"release_runtime_claim\":\"\"}", "")).delta().releaseRuntimeClaim()).isFalse();
    assertThat(annotated(annotation("{\"release_runtime_claim\":0}", "")).delta().releaseRuntimeClaim()).isFalse();
    assertThat(annotated(annotation("{}", "")).delta().releaseRuntimeClaim()).isFalse();
  }

  @Test
  void theSubtasksKeepTheirOrderAndTheirLane() {
    LineKind.Annotation.Delta delta = annotated(annotation("{\"subtasks\":{\"T2\":\"done\",\"T1\":\"planned\",\"T3\":\"blocked\"}}", "")).delta();
    assertThat(delta.subtasks()).containsExactly(Map.entry("T2", Lane.DONE), Map.entry("T1", Lane.PLANNED), Map.entry("T3", Lane.BLOCKED));
    assertThat(annotated(annotation("{\"subtasks\":{}}", "")).delta().subtasks()).isEmpty();
    assertThat(annotated(annotation("{\"subtasks\":null}", "")).delta().subtasks()).isNull();
  }

  @Test
  void theReviewOverrideFieldsAreStrCoercedAndTheReleaseSentinelIsRecognised() {
    assertThat(annotated(annotation("{\"review\":{\"at\":\"a\",\"actor\":\"b\",\"wp_id\":\"c\",\"reason\":\"d\"}}", "")).delta().review()).isEqualTo(new ReviewOverrideRecord("a", "b", "c", "d"));
    ReviewOverrideRecord nulls = annotated(annotation("{\"review\":{\"at\":null,\"actor\":null,\"wp_id\":null,\"reason\":null}}", "")).delta().review();
    assertThat(nulls).as("a JSON null is the text None, which is a value").isEqualTo(new ReviewOverrideRecord("None", "None", "None", "None"));
    assertThat(nulls.complete()).isTrue();
    ReviewOverrideRecord sentinel = annotated(annotation("{\"review\":{\"at\":\"\",\"actor\":\"\",\"wp_id\":\"\",\"reason\":\"\"}}", "")).delta().review();
    assertThat(sentinel.releaseSentinel()).isTrue();
    assertThat(annotated(annotation("{\"review\":{\"at\":5,\"actor\":true,\"wp_id\":6,\"reason\":7}}", "")).delta().review()).isEqualTo(new ReviewOverrideRecord("5", "True", "6", "7"));
    assertThat(annotated(annotation("{\"review\":null}", "")).delta().review()).isNull();
  }

  @Test
  void aReviewObjectMissingAnyOfItsFourKeysRaisesWhenReduced() {
    String[] keys = {"at", "actor", "wp_id", "reason"};
    for (String missing : keys) {
      StringBuilder review = new StringBuilder("{");
      for (String key : keys) {
        if (!key.equals(missing)) {
          review.append(review.length() > 1 ? "," : "").append('"').append(key).append("\":\"v\"");
        }
      }
      String row = annotation("{\"review\":" + review + "}}", "");
      assertThat(line(row).kind()).as(missing).isEqualTo(new LineKind.Malformed(MalformedReason.UNUSABLE_ROW));
      assertThatThrownBy(() -> reduce(row)).as(missing).isInstanceOf(UnreducibleLedgerException.class);
    }
  }

  // ---- lifecycleTypes and history, independent of the classification --------------------------------------------------------

  @Test
  void aMarkerRowWithoutAnEventIdOrATimestampIsIgnoredAsALineButItsEventTypeIsStillCarried() {
    LedgerLine marker = line("{\"event_type\":\"PlanStarted\"}");
    assertThat(marker.kind()).isEqualTo(new LineKind.Ignored());
    assertThat(marker.eventType()).isEqualTo("PlanStarted");
    assertThat(line("{\"event_type\":\"SpecifyStarted\",\"event_id\":5,\"timestamp\":\"t\"}").eventType()).isEqualTo("SpecifyStarted");
    assertThat(line("{\"event_type\":\"DecisionPointOpened\",\"event_id\":\"x\",\"timestamp\":\"t\"}").eventType()).isEqualTo("DecisionPointOpened");
    LedgerLine lifecycle = line("{\"event_type\":\"MissionCreated\",\"event_id\":\"x\",\"timestamp\":\"t\"}");
    assertThat(lifecycle.kind()).isInstanceOf(LineKind.Lifecycle.class);
    assertThat(lifecycle.eventType()).isEqualTo("MissionCreated");
  }

  @Test
  void anEventTypeThatIsNotTextMakesTheRowNonLaneButIsNotCounted() {
    for (String notText : List.of("5", "null", "true", "[\"x\"]", "{}")) {
      String row = status("").replace("{", "{\"event_type\":" + notText + ",");
      LedgerLine line = line(row);
      assertThat(line.kind()).as(notText).isEqualTo(new LineKind.Ignored());
      assertThat(line.eventType()).as(notText).isNull();
    }
    assertThat(line(status("")).eventType()).isNull();
  }

  @Test
  void anAnnotationRowWithATextEventTypeIsCounted() {
    LedgerLine line = line(annotation("{}", "\"event_type\":\"WeirdAnnotation\""));
    assertThat(line.kind()).isInstanceOf(LineKind.Annotation.class);
    assertThat(line.eventType()).isEqualTo("WeirdAnnotation");
  }

  @Test
  void everyRowWithAToLaneKeyAndAStringWorkPackageGetsAHistoryRowWhateverItsClassification() {
    HistoryRow fromStatus = line(status("\"reason\":\"why\",\"review_result\":{\"reviewer\":\"r\",\"verdict\":\"approved\",\"reference\":\"x\"}")).historyRow();
    assertThat(fromStatus).isEqualTo(new HistoryRow("WP01", "E1", "2026-02-08T12:00:00+00:00", "planned", "claimed", Actor.ofText("claude"), false, "why", "approved", "x", 1L));

    LedgerLine nonLane = line(status("").replace("{", "{\"event_type\":\"DecisionX\","));
    assertThat(nonLane.kind()).isEqualTo(new LineKind.Ignored());
    assertThat(nonLane.historyRow()).isNotNull();
    assertThat(nonLane.historyRow().wpId()).isEqualTo("WP01");

    assertThat(line(annotation("{}", "")).historyRow()).as("no to_lane key").isNull();
    assertThat(line(status("").replace("\"WP01\"", "5")).historyRow()).as("wp_id is not a string").isNull();
    assertThat(line(status("").replace("\"WP01\"", "null")).historyRow()).isNull();
    assertThat(line("{\"to_lane\":\"claimed\"}").historyRow()).as("no wp_id").isNull();
    assertThat(line("{\"to_lane\":null,\"wp_id\":\"WP01\"}").historyRow().toLane()).as("the key is what counts").isNull();
  }

  @Test
  void forceIsTrueOnlyForTheLiteralTrue() {
    assertThat(line(status("").replace("\"force\":false", "\"force\":true")).historyRow().force()).isTrue();
    for (String truthy : List.of("1", "\"true\"", "\"yes\"", "[1]", "1.0")) {
      assertThat(line(status("").replace("\"force\":false", "\"force\":" + truthy)).historyRow().force()).as(truthy).isFalse();
    }
  }

  @Test
  void theHistoryRowKeepsTheRowsOwnActorAndStoredTexts() {
    String record = "{\"role\":\"dev\",\"profile\":\"jenny\",\"tool\":\"claude\",\"model\":\"m\"}";
    assertThat(line(status("").replace("\"claude\"", record)).historyRow().actor()).isEqualTo(new Actor("claude", "dev", "jenny"));
    assertThat(line(status("").replace("\"claude\"", "null")).historyRow().actor()).isEqualTo(Actor.NONE);
    HistoryRow genesis = line(status("").replace("\"planned\"", "\"genesis\"")).historyRow();
    assertThat(genesis.fromLane()).as("stored text; the mapper shows or refuses it").isEqualTo("genesis");
    assertThat(line(status("").replace("\"at\":\"2026-02-08T12:00:00+00:00\"", "\"at\":5")).historyRow().at()).isEqualTo("5");
  }

  @Test
  void aLineWithNeitherAnEventTypeNorAHistoryRowIsAsItWas() {
    LedgerLine blank = LedgerLineDecoder.decodeLine(1, "\n".getBytes(StandardCharsets.UTF_8));
    assertThat(blank.eventType()).isNull();
    assertThat(blank.historyRow()).isNull();
    assertThat(line("not json").eventType()).isNull();
    assertThat(new LedgerLine(1, "0".repeat(64), 1, new LineKind.Blank()).historyRow()).isNull();
  }
}
