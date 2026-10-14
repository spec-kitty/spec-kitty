package org.speckitty.missionstatus.adapter.out.filesystem.codec;

import static org.assertj.core.api.Assertions.assertThat;

import java.nio.charset.StandardCharsets;
import org.junit.jupiter.api.Test;
import org.speckitty.missionstatus.domain.model.Lane;
import org.speckitty.missionstatus.domain.model.LineKind;
import org.speckitty.missionstatus.domain.model.MalformedReason;
import org.speckitty.missionstatus.domain.model.StatusEvent;
import org.speckitty.missionstatus.domain.model.StatusEvent.SlotText;

/**
 * Where the Java reading of a resolved-state member deliberately differs from the Python oracle (WP05 ruling 3: mirror Python except where
 * the mirrored value would be contract-invalid or leak-shaped, where the strict projection applies). Each test names the oracle's value;
 * each is a candidate {@code knownDivergence} entry of the conformance manifest (owned by WP07/WP08, see the design decision of WP05). They
 * pin the Java side so that a change of either is deliberate.
 */
class LedgerLineDecoderDivergencesTest {

  private static final String STATUS =
      "{\"actor\":\"claude\",\"at\":\"2026-02-08T12:00:00+00:00\",\"event_id\":\"E1\",\"execution_mode\":\"worktree\",\"force\":false,\"from_lane\":\"planned\",\"to_lane\":\"claimed\",\"wp_id\":\"WP01\"%s}";
  private static final String ANNOTATION =
      "{\"actor\":\"claude\",\"at\":\"2026-02-08T12:00:01+00:00\",\"delta\":%s,\"event_id\":\"01HXYZ0000000000000000000A\",\"kind\":\"annotation\",\"wp_id\":\"WP09\"}";

  private static LineKind kind(String line) {
    return LedgerLineDecoder.decodeLine(1, (line + "\n").getBytes(StandardCharsets.UTF_8)).kind();
  }

  @Test
  void aFloatAgentIsWrittenButNotShownWherePythonShowsItsReprIfItFitsAHandle() {
    // oracle: str(1.5) = "1.5", a handle, so agent = "1.5"; Java does not reproduce the float repr and shows null
    StatusEvent event = ((LineKind.Status) kind(STATUS.formatted(",\"policy_metadata\":{\"agent\":1.5}"))).event();
    assertThat(event.claimAgentSlot()).isEqualTo(SlotText.UNSHOWN);
    LineKind.Annotation annotation = (LineKind.Annotation) kind(ANNOTATION.formatted("{\"agent\":1.5}"));
    assertThat(annotation.delta().replaceSlots()).containsEntry("agent", SlotText.UNSHOWN);
  }

  @Test
  void aFloatActorGivesAnEmptyIdentityWherePythonHoldsTheReprOfTheFloat() {
    // oracle: the snapshot actor of "actor": 1.5 is "1.5" and the served actor.tool is "1.5"
    StatusEvent event = ((LineKind.Status) kind(STATUS.formatted("").replace("\"claude\"", "1.5"))).event();
    assertThat(event.actorIdentity()).isEmpty();
  }

  @Test
  void anAnnotationWhoseAtOrOverrideMemberIsAFloatListOrObjectIsUnusableWherePythonReadsItsRepr() {
    // the same rule as the float wp_id already pinned in LedgerLineOracleParityTest ("annotation-wp-id-float")
    LineKind unusable = new LineKind.Malformed(MalformedReason.UNUSABLE_ROW);
    assertThat(kind(ANNOTATION.formatted("{}").replace("\"at\":\"2026-02-08T12:00:01+00:00\"", "\"at\":1.5"))).isEqualTo(unusable);
    assertThat(kind(ANNOTATION.formatted("{}").replace("\"at\":\"2026-02-08T12:00:01+00:00\"", "\"at\":[1]"))).isEqualTo(unusable);
    assertThat(kind(ANNOTATION.formatted("{\"review\":{\"at\":1.5,\"actor\":\"b\",\"wp_id\":\"c\",\"reason\":\"d\"}}"))).isEqualTo(unusable);
    assertThat(kind(ANNOTATION.formatted("{\"review\":{\"at\":\"a\",\"actor\":[1],\"wp_id\":\"c\",\"reason\":\"d\"}}"))).isEqualTo(unusable);
    assertThat(kind(ANNOTATION.formatted("{\"review\":{\"at\":\"a\",\"actor\":\"b\",\"wp_id\":\"c\",\"reason\":{}}}"))).isEqualTo(unusable);
  }

  @Test
  void aSubtaskStatusOfANonDisplayLaneIsCarriedBecausePythonAcceptsItAndTheMapperRefusesItAsAnInvalidStatusLane() {
    // oracle: Status("genesis") is a valid Lane and str() gives "genesis"; the contract's StatusLane has nine display values
    LineKind.Annotation annotation = (LineKind.Annotation) kind(ANNOTATION.formatted("{\"subtasks\":{\"T1\":\"genesis\",\"T2\":\"uninitialized\"}}"));
    assertThat(annotation.delta().subtasks()).containsEntry("T1", Lane.GENESIS).containsEntry("T2", Lane.UNINITIALIZED);
    assertThat(Lane.GENESIS.isDisplay()).isFalse();
  }

  @Test
  void aNullOrNumericActorIsMirroredAsItsPythonTextNotAsNoActor() {
    // no divergence: the identity is Python's, "None" and "123" fit the handle shape and are contract-valid, so they are served as Python serves them
    assertThat(((LineKind.Status) kind(STATUS.formatted("").replace("\"claude\"", "null"))).event().actorIdentity()).isEqualTo("None");
    assertThat(((LineKind.Status) kind(STATUS.formatted("").replace("\"claude\"", "123"))).event().actorIdentity()).isEqualTo("123");
  }
}
