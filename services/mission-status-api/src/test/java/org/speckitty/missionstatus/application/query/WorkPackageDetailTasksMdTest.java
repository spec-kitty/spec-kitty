package org.speckitty.missionstatus.application.query;

import static org.assertj.core.api.Assertions.assertThat;
import static org.assertj.core.api.Assertions.assertThatThrownBy;
import static org.speckitty.missionstatus.application.query.detail.DetailRoute.MID8;
import static org.speckitty.missionstatus.application.query.detail.DetailRoute.detail;
import static org.speckitty.missionstatus.application.query.detail.DetailRoute.fixture;
import static org.speckitty.missionstatus.application.query.detail.DetailRoute.write;
import static org.speckitty.missionstatus.application.query.detail.DetailRoute.wpFile;

import java.io.IOException;
import java.io.UncheckedIOException;
import java.nio.charset.StandardCharsets;
import java.nio.file.Files;
import java.nio.file.Path;
import org.junit.jupiter.api.Test;
import org.speckitty.missionstatus.application.query.port.in.exceptions.MissionStatusUnavailable;
import org.speckitty.missionstatus.domain.model.Diagnostic;
import org.speckitty.missionstatus.domain.model.DiagnosticCode;
import org.speckitty.missionstatus.domain.readmodel.detail.SubtaskEntry;
import org.speckitty.missionstatus.testsupport.DetailFixture;

/**
 * {@code tasks.md} at the port (AC-3.4, row M4b): the cap of 4 MiB is applied by the bytes the port reads, so a file of 4194304 bytes is read and
 * 4194305 are refused, both made here; a file that is not UTF-8 is refused; a leading byte order mark stays, so the first heading does not open
 * the section of its Work Package. The golden class {@code tasks-md} pins the Unicode rules of the titles themselves.
 */
class WorkPackageDetailTasksMdTest {

  private static final String ROWS = "## WP01\n- [ ] T001 Title\n";

  private static DetailFixture withTasks(byte[] content) {
    return fixture(
        root -> {
          write(root, "tasks/WP01-one.md", wpFile("WP01", "One", "subtasks: [T001]"));
          try {
            Files.write(root.resolve("kitty-specs/alpha/tasks.md"), content);
          } catch (IOException failure) {
            throw new UncheckedIOException(failure);
          }
        });
  }

  private static byte[] padded(String rows, int size) {
    byte[] head = rows.getBytes(StandardCharsets.UTF_8);
    byte[] out = new byte[size];
    java.util.Arrays.fill(out, (byte) ' ');
    System.arraycopy(head, 0, out, 0, head.length);
    return out;
  }

  @Test
  void aTasksMdOfExactlyTheCapIsReadAndOneByteMoreIsRefused() {
    DetailFixture at = withTasks(padded(ROWS, 4_194_304));
    DetailFixture over = withTasks(padded(ROWS, 4_194_305));

    assertThat(detail(at, "WP01").subtasks()).extracting(SubtaskEntry::title).containsExactly("Title");
    assertThatThrownBy(() -> detail(over, "WP01")).isInstanceOfSatisfying(MissionStatusUnavailable.class, refusal -> assertThat(refusal.code()).isEqualTo(DiagnosticCode.SOURCE_UNREADABLE));
    assertThat(over.diagnostics()).containsExactly(new Diagnostic(DiagnosticCode.SOURCE_UNREADABLE, MID8, null));
  }

  @Test
  void aTasksMdThatIsNotUtf8IsRefusedAndOneThatIsIsServed() {
    byte[] invalid = {'#', '#', ' ', 'W', 'P', '0', '1', '\n', (byte) 0xC3, (byte) 0x28, '\n'};
    DetailFixture bad = withTasks(invalid);
    DetailFixture good = withTasks(ROWS.getBytes(StandardCharsets.UTF_8));

    assertThatThrownBy(() -> detail(bad, "WP01")).isInstanceOfSatisfying(MissionStatusUnavailable.class, refusal -> assertThat(refusal.code()).isEqualTo(DiagnosticCode.SOURCE_UNREADABLE));
    assertThat(detail(good, "WP01").subtasks()).hasSize(1);
  }

  @Test
  void aLeadingByteOrderMarkStaysSoTheFirstHeadingDoesNotMatch() {
    DetailFixture marked = withTasks(("\ufeff" + ROWS).getBytes(StandardCharsets.UTF_8));
    DetailFixture plain = withTasks(ROWS.getBytes(StandardCharsets.UTF_8));

    assertThat(detail(marked, "WP01").subtasks()).extracting(SubtaskEntry::title).containsExactly((String) null);
    assertThat(detail(plain, "WP01").subtasks()).extracting(SubtaskEntry::title).containsExactly("Title");
  }

  @Test
  void crlfLinesKeepTheirCarriageReturnOnlyWherePythonStripKeepsIt() {
    DetailFixture fixture = withTasks("## WP01\r\n- [ ] T001 One\rtwo\r\n".getBytes(StandardCharsets.UTF_8));

    assertThat(detail(fixture, "WP01").subtasks()).extracting(SubtaskEntry::title).containsExactly("One\rtwo");
  }

  @Test
  void theTextOfTheFixtureIsOnlyReadFromThePrimaryDirectory() {
    DetailFixture fixture = withTasks(ROWS.getBytes(StandardCharsets.UTF_8));
    Path tasks = fixture.root().resolve("kitty-specs/alpha/tasks.md");

    assertThat(Files.isRegularFile(tasks)).isTrue();
    assertThat(detail(fixture, "WP01").subtasks()).hasSize(1);
  }
}
