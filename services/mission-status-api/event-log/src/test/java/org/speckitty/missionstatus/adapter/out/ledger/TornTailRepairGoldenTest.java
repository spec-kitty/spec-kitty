package org.speckitty.missionstatus.adapter.out.ledger;

import static org.assertj.core.api.Assertions.assertThat;

import java.io.ByteArrayOutputStream;
import java.io.IOException;
import java.io.InputStream;
import java.nio.file.Files;
import java.nio.file.Path;
import java.time.Duration;
import java.util.ArrayList;
import java.util.HexFormat;
import java.util.List;
import java.util.Optional;
import java.util.stream.Stream;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.io.TempDir;
import org.junit.jupiter.params.ParameterizedTest;
import org.junit.jupiter.params.provider.MethodSource;
import tools.jackson.databind.JsonNode;
import tools.jackson.databind.json.JsonMapper;

/**
 * {@link TornTailRepair} against the goldens of {@code torn-tail/repair-cases.json}, which record what the glossary's Python repair
 * ({@code glossary.events._repair_torn_tail}) leaves in a ledger and in its {@code <ledger>.torn} quarantine file.
 * {@code tests/glossary/test_torn_tail_repair_goldens.py} re-checks Python against the same file, so the two cannot drift apart.
 */
class TornTailRepairGoldenTest {

  private static final String GOLDENS = "/torn-tail/repair-cases.json";

  @TempDir Path dir;

  record Golden(String name, byte[] ledger, byte[] tornBefore, boolean repaired, byte[] expectedLedger, byte[] expectedTorn) {
    @Override
    public String toString() {
      return name;
    }
  }

  static Stream<Golden> goldens() throws IOException {
    JsonNode cases;
    try (InputStream in = TornTailRepairGoldenTest.class.getResourceAsStream(GOLDENS)) {
      assertThat(in).as(GOLDENS).isNotNull();
      cases = JsonMapper.builder().build().readTree(in).get("cases");
    }
    List<Golden> goldens = new ArrayList<>();
    for (JsonNode node : cases) {
      goldens.add(
          new Golden(
              node.get("name").asString(),
              bytes(node.get("ledger")),
              bytes(node.get("torn_before")),
              node.get("repaired").asBoolean(),
              bytes(node.get("expected_ledger")),
              bytes(node.get("expected_torn"))));
    }
    return goldens.stream();
  }

  private static byte[] bytes(JsonNode segments) {
    if (segments == null || segments.isNull()) {
      return null;
    }
    ByteArrayOutputStream out = new ByteArrayOutputStream();
    for (JsonNode segment : segments) {
      byte[] chunk = HexFormat.of().parseHex(segment.get("hex").asString());
      for (int i = 0; i < segment.get("repeat").asInt(); i++) {
        out.writeBytes(chunk);
      }
    }
    return out.toByteArray();
  }

  @Test
  void theGoldensAreNotEmpty() throws IOException {
    assertThat(goldens().toList()).hasSizeGreaterThanOrEqualTo(10).anyMatch(Golden::repaired).anyMatch(golden -> !golden.repaired());
  }

  @ParameterizedTest(name = "{0}")
  @MethodSource("goldens")
  void javaRepairMatchesThePythonGolden(Golden golden) throws IOException {
    Path ledger = dir.resolve("glossary.events.jsonl");
    Files.write(ledger, golden.ledger());
    Path torn = dir.resolve("glossary.events.jsonl" + TornTailRepair.TORN_TAIL_SUFFIX);
    if (golden.tornBefore() != null) {
      Files.write(torn, golden.tornBefore());
    }

    Optional<TornTailRepair.Repair> repair = TornTailRepair.repair(ledger, LedgerLocks.forThisOs(), Duration.ofSeconds(10));

    assertThat(repair.isPresent()).as("repaired").isEqualTo(golden.repaired());
    assertThat(Files.readAllBytes(ledger)).as("ledger").isEqualTo(golden.expectedLedger());
    assertThat(Files.exists(torn) ? Files.readAllBytes(torn) : null).as("quarantine").isEqualTo(golden.expectedTorn());
    repair.ifPresent(r -> assertThat(r.quarantine()).isEqualTo(torn));
    repair.ifPresent(r -> assertThat(r.movedBytes()).isEqualTo(golden.ledger().length - golden.expectedLedger().length));
    assertThat(TornTailRepair.repair(ledger, LedgerLocks.forThisOs(), Duration.ofSeconds(10))).as("a second repair finds the tail whole").isEmpty();
  }
}
