package org.speckitty.missionstatus.adapter.out.ledger;

import static org.assertj.core.api.Assertions.assertThat;
import static org.assertj.core.api.Assertions.assertThatThrownBy;

import java.io.IOException;
import java.nio.charset.StandardCharsets;
import java.nio.file.Files;
import java.nio.file.NoSuchFileException;
import java.nio.file.Path;
import java.time.Duration;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.io.TempDir;

/** The repair's behaviour around its lock and a missing ledger; the byte-level outcomes are {@link TornTailRepairGoldenTest}'s. */
class TornTailRepairTest {

  @TempDir Path dir;

  @Test
  void theRepairTakesTheLeafLockBesideTheLedger() throws IOException {
    Path ledger = write("m.events.jsonl", "{\"a\": 1}\n{\"b\"");
    RecordingLock lock = new RecordingLock();

    TornTailRepair.repair(ledger, lock, Duration.ofSeconds(1));

    assertThat(lock.lockFile).isEqualTo(dir.resolve("m.events.jsonl" + TornTailRepair.REPAIR_LOCK_SUFFIX));
    assertThat(lock.timeout).isEqualTo(Duration.ofSeconds(1));
    assertThat(lock.released).isTrue();
  }

  @Test
  void theDefaultRepairUsesThePythonTimeoutAndThisOsLock() throws IOException {
    assertThat(TornTailRepair.REPAIR_LOCK_TIMEOUT).isEqualTo(Duration.ofSeconds(10));
    Path ledger = write("m.events.jsonl", "{\"a\": 1}\n{");
    assertThat(TornTailRepair.repair(ledger)).isPresent();
    assertThat(Files.readString(ledger)).isEqualTo("{\"a\": 1}\n");
  }

  @Test
  void aHeldLockMakesTheRepairTimeOutWithoutTouchingTheLedger() throws IOException {
    Path ledger = write("m.events.jsonl", "{\"a\": 1}\n{\"b\"");
    LedgerLock lock = LedgerLocks.forThisOs();
    try (LedgerLock.Held held = lock.acquire(dir.resolve("m.events.jsonl" + TornTailRepair.REPAIR_LOCK_SUFFIX), Duration.ofSeconds(1))) {
      assertThatThrownBy(() -> TornTailRepair.repair(ledger, lock, Duration.ofMillis(250))).isInstanceOf(LedgerLockTimeoutException.class);
    }
    assertThat(Files.readString(ledger)).isEqualTo("{\"a\": 1}\n{\"b\"");
    assertThat(dir.resolve("m.events.jsonl" + TornTailRepair.TORN_TAIL_SUFFIX)).doesNotExist();
  }

  @Test
  void aMissingLedgerIsRefusedAndNothingIsCreated() {
    Path ledger = dir.resolve("absent.events.jsonl");
    assertThatThrownBy(() -> TornTailRepair.repair(ledger, LedgerLocks.forThisOs(), Duration.ofSeconds(1))).isInstanceOf(NoSuchFileException.class);
    assertThat(ledger).doesNotExist();
    assertThat(dir.resolve("absent.events.jsonl" + TornTailRepair.TORN_TAIL_SUFFIX)).doesNotExist();
    // Like the Python repair, the lock is taken before the ledger is opened, so its lock file is left behind.
    assertThat(dir.resolve("absent.events.jsonl" + TornTailRepair.REPAIR_LOCK_SUFFIX)).exists();
  }

  /** The quarantine is written before the ledger is cut, so a failed quarantine write loses nothing (the Python test pins the same). */
  @Test
  void aFailedQuarantineWriteLeavesTheLedgerUntouched() throws IOException {
    Path ledger = write("m.events.jsonl", "{\"a\": 1}\n{\"b\"");
    Files.createDirectory(dir.resolve("m.events.jsonl" + TornTailRepair.TORN_TAIL_SUFFIX));
    assertThatThrownBy(() -> TornTailRepair.repair(ledger, LedgerLocks.forThisOs(), Duration.ofSeconds(1))).isInstanceOf(IOException.class);
    assertThat(Files.readString(ledger)).isEqualTo("{\"a\": 1}\n{\"b\"");
  }

  @Test
  void theCompleteLengthScansBackAcrossBlocks() throws IOException {
    Path ledger = dir.resolve("big.events.jsonl");
    byte[] bytes = new byte[3 * TornTailRepair.TAIL_SCAN_BLOCK + 5];
    java.util.Arrays.fill(bytes, (byte) 'x');
    bytes[3] = '\n';
    Files.write(ledger, bytes);
    try (var channel = java.nio.channels.FileChannel.open(ledger)) {
      assertThat(TornTailRepair.completeLength(channel, bytes.length)).isEqualTo(4);
      assertThat(TornTailRepair.completeLength(channel, 0)).isZero();
    }
  }

  private Path write(String name, String content) throws IOException {
    return Files.writeString(dir.resolve(name), content, StandardCharsets.UTF_8);
  }

  /** A lock that records what it was asked for and always grants it. */
  private static final class RecordingLock implements LedgerLock {
    Path lockFile;
    Duration timeout;
    boolean released;

    @Override
    public Held tryAcquire(Path lockFile) {
      throw new AssertionError("the repair waits for its lock");
    }

    @Override
    public Held acquire(Path lockFile, Duration timeout) {
      this.lockFile = lockFile;
      this.timeout = timeout;
      return () -> released = true;
    }
  }
}
