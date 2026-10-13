package org.speckitty.missionstatus.adapter.out.filesystem;

import static org.assertj.core.api.Assertions.assertThat;

import java.io.IOException;
import java.nio.file.Files;
import java.nio.file.Path;
import java.util.Arrays;
import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.io.TempDir;
import org.speckitty.missionstatus.adapter.out.filesystem.ReadDirResolver.ReadClass;
import org.speckitty.missionstatus.application.query.port.out.dto.MissionRef;
import org.speckitty.missionstatus.application.query.port.out.exceptions.SourceFault;
import org.speckitty.missionstatus.application.query.port.out.exceptions.SourceFault.Kind;
import org.speckitty.missionstatus.domain.model.Topology;
import org.speckitty.missionstatus.testsupport.Rows;

/**
 * Every read of the adapter is capped (pre-merge fold J2). A file the project owner does not control must not be able to exhaust the heap:
 * an oversize {@code meta.json} is row L7, an oversize {@code lanes.json} is "no lanes", an oversize ledger is row L2.
 */
class ReadCapsTest {

  private static final String NAME = AdapterServiceHarness.ALPHA;
  private static final String ID = Rows.ALPHA_ID;
  private static final int ONE_MIB = 1024 * 1024;

  @TempDir Path sandbox;
  Path root;

  @BeforeEach
  void setUp() throws IOException {
    root = Files.createDirectory(sandbox.resolve("project"));
    AdapterServiceHarness.healthyProject(root);
  }

  private Path dir() {
    return root.resolve("kitty-specs").resolve(NAME);
  }

  private static byte[] padded(String json, int size) {
    byte[] bytes = Arrays.copyOf(json.getBytes(java.nio.charset.StandardCharsets.UTF_8), size);
    Arrays.fill(bytes, json.length(), size, (byte) ' ');
    return bytes;
  }

  @Test
  void anOversizeMetaJsonIsRowL7ForTheReadAndForTheResolver() throws IOException {
    AdapterServiceHarness.mission(root, NAME, ID, "2026-09-01T09:00:00+00:00", "");
    String json = Files.readString(dir().resolve("meta.json"));
    Files.write(dir().resolve("meta.json"), padded(json, ONE_MIB + 1));
    FilesystemMissionEventSource source = new FilesystemMissionEventSource(root);

    assertThat(faultOf(() -> source.readMeta(new MissionRef(NAME)))).isEqualTo(Kind.META_UNPARSEABLE);
    assertThat(faultOf(() -> source.stampLedger(new MissionRef(NAME)))).as("the resolver re-reads meta.json before every ledger operation").isEqualTo(Kind.META_UNPARSEABLE);
  }

  @Test
  void aMetaJsonAtTheCapStillReads() throws IOException {
    AdapterServiceHarness.mission(root, NAME, ID, "2026-09-01T09:00:00+00:00", "");
    String json = Files.readString(dir().resolve("meta.json"));
    Files.write(dir().resolve("meta.json"), padded(json, ONE_MIB));
    assertThat(new FilesystemMissionEventSource(root).readMeta(new MissionRef(NAME)).missionId().value()).isEqualTo(ID);
  }

  @Test
  void anOversizeLanesJsonReadsAsNoLanes() throws IOException {
    String meta = "{\"mission_id\":\"" + ID + "\",\"mission_slug\":\"" + NAME + "\",\"coordination_branch\":\"b\"}";
    String lanes =
        "{\"version\":1,\"mission_slug\":\"m\",\"mission_branch\":\"b\",\"target_branch\":\"main\","
            + "\"lanes\":[{\"lane_id\":\"lane-a\",\"wp_ids\":[\"WP01\"]}],\"computed_at\":\"t\",\"computed_from\":\"f\"}";
    AdapterServiceHarness.write(dir().resolve("meta.json"), meta);
    ReadDirResolver resolver = new ReadDirResolver(new SafeFiles(root, AllowlistAccess.passThrough()));

    AdapterServiceHarness.writeBytes(dir().resolve("lanes.json"), padded(lanes, 4096));
    assertThat(resolver.resolve(NAME).topology()).as("a small lanes.json with a code lane").isEqualTo(Topology.LANES_WITH_COORD);

    AdapterServiceHarness.writeBytes(dir().resolve("lanes.json"), padded(lanes, ONE_MIB + 1));
    ReadDirResolver.Resolution oversize = resolver.resolve(NAME);
    assertThat(oversize.topology()).as("the same document above 1 MiB is not read: no lanes").isEqualTo(Topology.COORD);
    assertThat(oversize.readClass()).isEqualTo(ReadClass.OWN);
  }

  @Test
  void anOversizeLedgerIsRowL2ForTheStampTheReadAndTheWindow() throws IOException {
    AdapterServiceHarness.mission(root, NAME, ID, "2026-09-01T09:00:00+00:00", AdapterServiceHarness.laneRow(1, "WP01", "planned", "claimed"));
    long size = Files.size(dir().resolve("status.events.jsonl"));
    MissionRef ref = new MissionRef(NAME);

    FilesystemMissionEventSource atCap = new FilesystemMissionEventSource(root, AllowlistAccess.passThrough(), size);
    assertThat(atCap.readLedger(ref, atCap.stampLedger(ref)).lines()).hasSize(1);
    assertThat(atCap.readLedgerFrom(ref, 0).lines()).hasSize(1);

    FilesystemMissionEventSource below = new FilesystemMissionEventSource(root, AllowlistAccess.passThrough(), size - 1);
    assertThat(faultOf(() -> below.stampLedger(ref))).isEqualTo(Kind.LEDGER_UNREADABLE);
    assertThat(faultOf(() -> below.readLedger(ref, null))).isEqualTo(Kind.LEDGER_UNREADABLE);
    assertThat(faultOf(() -> below.readLedgerFrom(ref, 0))).isEqualTo(Kind.LEDGER_UNREADABLE);
  }

  @Test
  void theShippedLedgerCapIs64MiB() {
    assertThat(FilesystemMissionEventSourceLedger.MAX_BYTES).isEqualTo(64L * 1024 * 1024);
  }

  private static Kind faultOf(Runnable call) {
    try {
      call.run();
    } catch (SourceFault fault) {
      return fault.kind();
    }
    return null;
  }
}
