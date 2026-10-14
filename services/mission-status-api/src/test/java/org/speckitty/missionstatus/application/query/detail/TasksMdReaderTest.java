package org.speckitty.missionstatus.application.query.detail;

import static org.assertj.core.api.Assertions.assertThat;
import static org.assertj.core.api.Assertions.assertThatThrownBy;

import java.nio.charset.StandardCharsets;
import java.util.Arrays;
import org.junit.jupiter.api.Test;
import org.speckitty.missionstatus.application.query.port.out.TextSource;
import org.speckitty.missionstatus.application.query.port.out.dto.BytesRead;
import org.speckitty.missionstatus.application.query.port.out.dto.DirListing;
import org.speckitty.missionstatus.application.query.port.out.dto.EntryStat;
import org.speckitty.missionstatus.application.query.port.out.dto.FileRef;
import org.speckitty.missionstatus.application.query.port.out.dto.MissionRef;
import org.speckitty.missionstatus.application.query.port.out.dto.ReadScope;
import org.speckitty.missionstatus.application.query.port.out.dto.RelativePath;
import org.speckitty.missionstatus.application.query.port.out.dto.TextRead;
import org.speckitty.missionstatus.application.query.port.out.exceptions.TextFault;
import org.speckitty.missionstatus.testsupport.InMemoryTextSource;

/** {@link TasksMdReader} over the in-memory port: what each answer of the port becomes, the scope of the read, and the cap by length. */
class TasksMdReaderTest {

  private static final MissionRef MISSION = new MissionRef("alpha");
  private static final FileRef TASKS_MD = new FileRef.MissionFile(MISSION, RelativePath.of("tasks.md"));

  private static byte[] bytes(int size) {
    byte[] out = new byte[size];
    Arrays.fill(out, (byte) 'x');
    return out;
  }

  @Test
  void theTextOfARegularFileIsReadUnderTheAuthoredScopeAndNothingElseIsAsked() {
    InMemoryTextSource source = new InMemoryTextSource().file(TASKS_MD, "## WP01\n".getBytes(StandardCharsets.UTF_8));

    assertThat(new TasksMdReader(source).read(MISSION)).contains("## WP01\n");
    assertThat(source.readRefs()).containsOnly(TASKS_MD);
    assertThat(source.readScopes()).isNotEmpty().containsOnly(ReadScope.AUTHORED);
  }

  @Test
  void anAbsentFileADirectoryAndALinkGiveNoTextAndNoError() {
    assertThat(new TasksMdReader(new InMemoryTextSource()).read(MISSION)).isEmpty();
    assertThat(new TasksMdReader(new InMemoryTextSource().dir(TASKS_MD, "a")).read(MISSION)).isEmpty();
    assertThat(new TasksMdReader(new InMemoryTextSource().link(TASKS_MD)).read(MISSION)).isEmpty();
  }

  @Test
  void aFileOfExactlyTheCapIsReadAndOneByteMoreIsRefused() {
    assertThat(new TasksMdReader(new InMemoryTextSource().file(TASKS_MD, bytes(TasksMdReader.CAP_BYTES))).read(MISSION)).hasValueSatisfying(text -> assertThat(text).hasSize(4_194_304));
    assertThatThrownBy(() -> new TasksMdReader(new InMemoryTextSource().file(TASKS_MD, bytes(TasksMdReader.CAP_BYTES + 1))).read(MISSION)).isInstanceOf(ReadRefused.class);
    assertThat(TasksMdReader.CAP_BYTES).isEqualTo(4 * 1024 * 1024);
  }

  @Test
  void bytesThatAreNotUtf8AreRefused() {
    InMemoryTextSource source = new InMemoryTextSource().file(TASKS_MD, new byte[] {(byte) 0xC3, (byte) 0x28});

    assertThatThrownBy(() -> new TasksMdReader(source).read(MISSION)).isInstanceOf(ReadRefused.class);
  }

  @Test
  void aFaultOfThePortIsNotSwallowed() {
    for (TextFault.Kind kind : TextFault.Kind.values()) {
      InMemoryTextSource source = new InMemoryTextSource().fault(TASKS_MD, kind);

      assertThatThrownBy(() -> new TasksMdReader(source).read(MISSION)).isInstanceOfSatisfying(TextFault.class, fault -> assertThat(fault.kind()).isEqualTo(kind));
    }
  }

  /** A port that says "a regular file" to the stat and then gives another answer to the read: the file changed between the two calls. */
  private static TextSource racing(TextRead answer) {
    return new TextSource() {
      @Override
      public DirListing list(FileRef dir, int nameLimit, ReadScope scope) {
        throw new UnsupportedOperationException();
      }

      @Override
      public EntryStat stat(FileRef path, ReadScope scope) {
        return new EntryStat.Present(EntryStat.EntryKind.FILE, 1, 0);
      }

      @Override
      public BytesRead readBytes(FileRef file, int cap, ReadScope scope) {
        throw new UnsupportedOperationException();
      }

      @Override
      public TextRead readText(FileRef file, int cap, ReadScope scope) {
        return answer;
      }
    };
  }

  @Test
  void aFileThatVanishesOrStopsBeingRegularBetweenTheStatAndTheReadGivesNoTextAndNoError() {
    assertThat(new TasksMdReader(racing(new TextRead.Absent())).read(MISSION)).isEmpty();
    assertThat(new TasksMdReader(racing(new TextRead.NotRegular())).read(MISSION)).isEmpty();
    assertThatThrownBy(() -> new TasksMdReader(racing(new TextRead.OverCap())).read(MISSION)).isInstanceOf(ReadRefused.class);
    assertThatThrownBy(() -> new TasksMdReader(racing(new TextRead.NotText())).read(MISSION)).isInstanceOf(ReadRefused.class);
  }

  @Test
  void aReadRefusedCarriesNothingToLeak() {
    ReadRefused refused = new ReadRefused();

    assertThat(refused.getMessage()).isNull();
    assertThat(refused.getCause()).isNull();
    assertThat(refused.getStackTrace()).isEmpty();
  }
}
