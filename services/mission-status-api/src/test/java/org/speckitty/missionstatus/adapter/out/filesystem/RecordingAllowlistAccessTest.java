package org.speckitty.missionstatus.adapter.out.filesystem;

import static org.assertj.core.api.Assertions.assertThat;
import static org.assertj.core.api.Assertions.assertThatThrownBy;

import java.io.IOException;
import java.nio.channels.SeekableByteChannel;
import java.nio.charset.StandardCharsets;
import java.nio.file.AccessDeniedException;
import java.nio.file.Files;
import java.nio.file.Path;
import java.util.List;
import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.io.TempDir;
import org.speckitty.missionstatus.adapter.out.filesystem.Allowlist.Access;
import org.speckitty.missionstatus.adapter.out.filesystem.Allowlist.OpenMode;
import org.speckitty.missionstatus.adapter.out.filesystem.Allowlist.PathClass;

/** The recording seam (AC-10a, AC-10e, AC-16a at primitive level) and its positive controls. */
class RecordingAllowlistAccessTest {

  @TempDir Path root;
  RecordingAllowlistAccess recorder;

  @BeforeEach
  void setUp() throws IOException {
    recorder = new RecordingAllowlistAccess(root);
    write("kitty-specs/m-01ABCDEF/status.events.jsonl", "{}\n");
    write("kitty-specs/m-01ABCDEF/meta.json", "{}");
    write("kitty-specs/m-01ABCDEF/research/notes.md", "secret frontmatter");
    write(".worktrees/m-01ABCDEF-coord/kitty-specs/m-01ABCDEF/meta.json", "{}");
    write("config.toml", "token = 1");
  }

  private void write(String relative, String text) throws IOException {
    Path file = root.resolve(relative);
    Files.createDirectories(file.getParent());
    Files.writeString(file, text);
  }

  private String readAll(Path file) throws IOException {
    try (SeekableByteChannel channel = recorder.openRead(file)) {
      java.nio.ByteBuffer buffer = java.nio.ByteBuffer.allocate(64);
      channel.read(buffer);
      return new String(buffer.array(), 0, buffer.position(), StandardCharsets.UTF_8);
    }
  }

  @Test
  void aReadOfTheLedgerIsRecordedAsAClassifiedReadAndThroughTheSeamReallyReads() throws IOException {
    assertThat(readAll(root.resolve("kitty-specs/m-01ABCDEF/status.events.jsonl"))).isEqualTo("{}\n");
    assertThat(recorder.accesses())
        .containsExactly(new Access(PathClass.LEDGER, "kitty-specs/m-01ABCDEF/status.events.jsonl", OpenMode.READ));
    assertThat(recorder.violations()).isEmpty();
  }

  @Test
  void theAccessIsRecordedBeforeTheOperatingSystemAnswersSoASwallowedFailureIsStillOnTheRecord() {
    recorder.failWhen(access -> access.pathClass() == PathClass.LEDGER, () -> new AccessDeniedException("injected"));
    Path ledger = root.resolve("kitty-specs/m-01ABCDEF/status.events.jsonl");
    try {
      recorder.openRead(ledger);
    } catch (IOException swallowed) {
      // the caller swallows the failure; the record must still show the attempt
    }
    assertThat(recorder.accesses()).hasSize(1);
    assertThat(recorder.accesses().get(0).mode()).isEqualTo(OpenMode.READ);
  }

  @Test
  void aFaultThatNamesNoPathNeverCarriesOneIntoTheRecord() {
    recorder.failWhen(access -> true, () -> new IOException("injected"));
    assertThatThrownBy(() -> recorder.stat(root.resolve("kitty-specs"), true)).isInstanceOf(IOException.class).hasMessage("injected");
    assertThat(recorder.accesses().toString()).doesNotContain(root.toString());
  }

  @Test
  void positiveControlAReadOfAFileOnNoClassIsRecordedAsAViolation() throws IOException {
    readAll(root.resolve("kitty-specs/m-01ABCDEF/research/notes.md"));
    assertThat(recorder.violations()).hasSize(1);
    assertThat(recorder.violations().get(0).access().path()).isEqualTo("kitty-specs/m-01ABCDEF/research/notes.md");
  }

  @Test
  void aListingAndAStatAreRecordedWithTheirOwnModes() throws IOException {
    recorder.listNames(root.resolve("kitty-specs"));
    recorder.stat(root.resolve("kitty-specs/m-01ABCDEF"), false);
    recorder.realPath(root);
    assertThat(recorder.accesses())
        .containsExactly(
            new Access(PathClass.SPECS_DIR, "kitty-specs", OpenMode.LIST),
            new Access(PathClass.MISSION_DIR, "kitty-specs/m-01ABCDEF", OpenMode.STAT),
            new Access(PathClass.PROJECT_ROOT, "", OpenMode.REALPATH));
    assertThat(recorder.violations()).isEmpty();
    recorder.clear();
    assertThat(recorder.accesses()).isEqualTo(List.of());
  }
}
