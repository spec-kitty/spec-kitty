package org.speckitty.missionstatus.adapter.out.filesystem;

import static org.assertj.core.api.Assertions.assertThat;

import java.nio.charset.StandardCharsets;
import java.nio.file.Files;
import java.nio.file.Path;
import java.util.Arrays;
import java.util.List;
import java.util.Map;
import java.util.stream.Stream;
import org.junit.jupiter.api.io.TempDir;
import org.junit.jupiter.params.ParameterizedTest;
import org.junit.jupiter.params.provider.Arguments;
import org.junit.jupiter.params.provider.MethodSource;
import org.speckitty.missionstatus.application.query.port.out.dto.LedgerStamp;
import org.speckitty.missionstatus.application.query.port.out.dto.LedgerWindow;
import org.speckitty.missionstatus.application.query.port.out.dto.MissionRef;
import org.speckitty.missionstatus.domain.model.TailClassification;
import org.speckitty.missionstatus.testsupport.Rows;

/**
 * The cursor facts of the adapter against the oracle's {@code tail_reader}: for each byte pattern the digest of the line ending at
 * every line boundary is {@code _content_invariant_at} (a backward scan from {@code offset - 1}), and the terminated length and the
 * last-line digest of the stamp are the offset and invariant that {@code poll_once} returns from the start (the cursor lands after the
 * last complete line and leaves any unterminated tail unconsumed). The table below is the output of an oracle probe that calls
 * {@code tail_reader} on these bytes (recorded in the WP19 tracer); the patterns are rebuilt here from the same bytes.
 */
class FilesystemMissionEventSourceOracleParityTest {

  record Poll(long offset, String invariant) {}

  /** One pattern: its size, its line boundaries with the oracle digest of the line ending there, and poll_once from the start (null when it raises). */
  record Oracle(String name, long size, long[] offsets, String[] digests, Poll poll) {}

  private static final byte[] ROW1 = bytes("{\"event_id\":\"E1\",\"a\":1}\n");
  private static final byte[] ROW2 = bytes("{\"event_id\":\"E2\",\"a\":2}\r\n");

  private static final Map<String, byte[]> PATTERNS =
      Map.ofEntries(
          Map.entry("empty", new byte[0]),
          Map.entry("one-row", ROW1),
          Map.entry("two-rows", join(ROW1, ROW2)),
          Map.entry("crlf-row", ROW2),
          Map.entry("blank-last", join(ROW1, bytes("\n"))),
          Map.entry("blank-only", bytes("\n")),
          Map.entry("torn-tail", join(ROW1, bytes("{\"half"))),
          Map.entry("valid-json-tail", join(ROW1, bytes("{\"b\":2}"))),
          Map.entry("whitespace-tail", join(ROW1, bytes("   "))),
          Map.entry("no-newline", bytes("{\"a\":1}")),
          Map.entry("long-line", join(ROW1, bytes("{\"pad\":\"" + "x".repeat(200000) + "\"}\n"), ROW1)),
          Map.entry("multibyte", join(bytes("{\"n\":\"café\"}\n"), ROW1)));

  private static final Map<String, TailClassification> TAILS =
      Map.of(
          "torn-tail", TailClassification.NON_WHITESPACE,
          "valid-json-tail", TailClassification.NON_WHITESPACE,
          "whitespace-tail", TailClassification.WHITESPACE,
          "no-newline", TailClassification.NON_WHITESPACE);

  private static final List<Oracle> ORACLE =
      List.of(
          new Oracle("empty", 0L, new long[] {0L}, new String[] {"e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855"}, new Poll(0L, "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855")),
          new Oracle("one-row", 24L, new long[] {0L, 24L}, new String[] {"e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855", "aa74be068f72ee9a2115542ab3c32e2a571fbcbe23e7ea764840df889bf9ed10"}, new Poll(24L, "aa74be068f72ee9a2115542ab3c32e2a571fbcbe23e7ea764840df889bf9ed10")),
          new Oracle("two-rows", 49L, new long[] {0L, 24L, 49L}, new String[] {"e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855", "aa74be068f72ee9a2115542ab3c32e2a571fbcbe23e7ea764840df889bf9ed10", "fbf00275f9ed8e78a1257924425f612a21bb967bf11b34939acfb1944c6fa1f7"}, new Poll(49L, "fbf00275f9ed8e78a1257924425f612a21bb967bf11b34939acfb1944c6fa1f7")),
          new Oracle("crlf-row", 25L, new long[] {0L, 25L}, new String[] {"e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855", "fbf00275f9ed8e78a1257924425f612a21bb967bf11b34939acfb1944c6fa1f7"}, new Poll(25L, "fbf00275f9ed8e78a1257924425f612a21bb967bf11b34939acfb1944c6fa1f7")),
          new Oracle("blank-last", 25L, new long[] {0L, 24L, 25L}, new String[] {"e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855", "aa74be068f72ee9a2115542ab3c32e2a571fbcbe23e7ea764840df889bf9ed10", "01ba4719c80b6fe911b091a7c05124b64eeece964e09c058ef8f9805daca546b"}, null),
          new Oracle("blank-only", 1L, new long[] {0L, 1L}, new String[] {"e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855", "01ba4719c80b6fe911b091a7c05124b64eeece964e09c058ef8f9805daca546b"}, null),
          new Oracle("torn-tail", 30L, new long[] {0L, 24L}, new String[] {"e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855", "aa74be068f72ee9a2115542ab3c32e2a571fbcbe23e7ea764840df889bf9ed10"}, new Poll(24L, "aa74be068f72ee9a2115542ab3c32e2a571fbcbe23e7ea764840df889bf9ed10")),
          new Oracle("valid-json-tail", 31L, new long[] {0L, 24L}, new String[] {"e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855", "aa74be068f72ee9a2115542ab3c32e2a571fbcbe23e7ea764840df889bf9ed10"}, new Poll(24L, "aa74be068f72ee9a2115542ab3c32e2a571fbcbe23e7ea764840df889bf9ed10")),
          new Oracle("whitespace-tail", 27L, new long[] {0L, 24L}, new String[] {"e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855", "aa74be068f72ee9a2115542ab3c32e2a571fbcbe23e7ea764840df889bf9ed10"}, new Poll(24L, "aa74be068f72ee9a2115542ab3c32e2a571fbcbe23e7ea764840df889bf9ed10")),
          new Oracle("no-newline", 7L, new long[] {0L}, new String[] {"e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855"}, new Poll(0L, "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855")),
          new Oracle("long-line", 200059L, new long[] {0L, 24L, 200035L, 200059L}, new String[] {"e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855", "aa74be068f72ee9a2115542ab3c32e2a571fbcbe23e7ea764840df889bf9ed10", "269b2e4078844bb5271e846c8bbaeb424fee3054e6837d29aa1bdd1354c4e4d5", "aa74be068f72ee9a2115542ab3c32e2a571fbcbe23e7ea764840df889bf9ed10"}, new Poll(200059L, "aa74be068f72ee9a2115542ab3c32e2a571fbcbe23e7ea764840df889bf9ed10")),
          new Oracle("multibyte", 38L, new long[] {0L, 14L, 38L}, new String[] {"e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855", "09a994814a8e1bd4f4ef6d43cd5fc38930853e63920a3f223e5e4bebfd0a51d0", "aa74be068f72ee9a2115542ab3c32e2a571fbcbe23e7ea764840df889bf9ed10"}, new Poll(38L, "aa74be068f72ee9a2115542ab3c32e2a571fbcbe23e7ea764840df889bf9ed10")),
          new Oracle("", 0L, new long[0], new String[0], null));

  @TempDir Path sandbox;

  static Stream<Arguments> patterns() {
    return ORACLE.stream().filter(o -> !o.name().isEmpty()).map(o -> Arguments.of(o.name(), o));
  }

  private static byte[] bytes(String text) {
    return text.getBytes(StandardCharsets.UTF_8);
  }

  private static byte[] join(byte[]... parts) {
    return Arrays.stream(parts)
        .reduce(
            new byte[0],
            (a, b) -> {
              byte[] joined = Arrays.copyOf(a, a.length + b.length);
              System.arraycopy(b, 0, joined, a.length, b.length);
              return joined;
            });
  }

  private FilesystemMissionEventSource sourceWith(byte[] ledger) throws Exception {
    Path root = Files.createDirectory(sandbox.resolve("p"));
    AdapterServiceHarness.healthyProject(root);
    Path dir = AdapterServiceHarness.mission(root, AdapterServiceHarness.ALPHA, Rows.ALPHA_ID, "2026-09-01T09:00:00+00:00", null);
    AdapterServiceHarness.writeBytes(dir.resolve("status.events.jsonl"), ledger);
    return new FilesystemMissionEventSource(root);
  }

  @ParameterizedTest(name = "{0}")
  @MethodSource("patterns")
  void theDigestAtEveryLineBoundaryIsTheOraclesContentInvariant(String name, Oracle oracle) throws Exception {
    byte[] ledger = PATTERNS.get(name);
    assertThat((long) ledger.length).isEqualTo(oracle.size());
    FilesystemMissionEventSource source = sourceWith(ledger);
    MissionRef ref = new MissionRef(AdapterServiceHarness.ALPHA);
    for (int i = 0; i < oracle.offsets().length; i++) {
      LedgerWindow window = source.readLedgerFrom(ref, oracle.offsets()[i]);
      assertThat(window.aligned()).as(name + " @" + oracle.offsets()[i]).isTrue();
      assertThat(window.precedingLineSha256()).as(name + " @" + oracle.offsets()[i]).isEqualTo(oracle.digests()[i]);
      assertThat(window.size()).isEqualTo(oracle.size());
    }
  }

  @ParameterizedTest(name = "{0}")
  @MethodSource("patterns")
  void theStampCarriesTheOraclesCursorAfterPollOnceAndTheTailClassIsRight(String name, Oracle oracle) throws Exception {
    FilesystemMissionEventSource source = sourceWith(PATTERNS.get(name));
    MissionRef ref = new MissionRef(AdapterServiceHarness.ALPHA);
    LedgerStamp stamp = source.stampLedger(ref);
    long lastBoundary = oracle.offsets()[oracle.offsets().length - 1];
    String lastDigest = oracle.digests()[oracle.digests().length - 1];
    assertThat(stamp.parts().get(3)).as("terminated length").isEqualTo(lastBoundary);
    assertThat(stamp.parts().get(4)).as("digest of the last terminated line").isEqualTo(lastDigest);
    if (oracle.poll() != null) {
      assertThat(lastBoundary).as("poll_once offset").isEqualTo(oracle.poll().offset());
      assertThat(lastDigest).as("poll_once invariant").isEqualTo(oracle.poll().invariant());
    }
    assertThat(source.readLedger(ref, stamp).tail()).isEqualTo(TAILS.getOrDefault(name, TailClassification.NONE));
    assertThat(source.readLedgerFrom(ref, lastBoundary).tail()).isEqualTo(TAILS.getOrDefault(name, TailClassification.NONE));
  }
}
