package org.speckitty.missionstatus.application.query.detail;

import java.util.Objects;
import java.util.Optional;
import org.speckitty.missionstatus.application.query.port.out.TextSource;
import org.speckitty.missionstatus.application.query.port.out.dto.EntryStat;
import org.speckitty.missionstatus.application.query.port.out.dto.FileRef;
import org.speckitty.missionstatus.application.query.port.out.dto.MissionRef;
import org.speckitty.missionstatus.application.query.port.out.dto.ReadScope;
import org.speckitty.missionstatus.application.query.port.out.dto.RelativePath;
import org.speckitty.missionstatus.application.query.port.out.dto.TextRead;

/**
 * The text of a Mission's {@code tasks.md}, for the subtask titles (the oracle's {@code read_tasks_md}). The cap of 4 MiB is applied by the
 * port by the bytes it reads, never by a size read earlier, so a file that grows while it is read is still refused.
 */
public final class TasksMdReader {

  /** The most bytes of {@code tasks.md} the route reads (4 MiB). */
  public static final int CAP_BYTES = 4_194_304;

  private static final RelativePath TASKS_MD = RelativePath.of("tasks.md");

  private final TextSource text;

  public TasksMdReader(TextSource text) {
    this.text = Objects.requireNonNull(text, "text");
  }

  /**
   * The strictly decoded text (a leading byte order mark stays), or empty when there is no regular file called {@code tasks.md} (it is absent,
   * a directory or a link: no titles, no error).
   *
   * @throws ReadRefused when the file is over the cap or is not UTF-8
   * @throws org.speckitty.missionstatus.application.query.port.out.exceptions.TextFault when the port cannot read it
   */
  public Optional<String> read(MissionRef mission) {
    FileRef file = new FileRef.MissionFile(mission, TASKS_MD);
    if (!(text.stat(file, ReadScope.AUTHORED) instanceof EntryStat.Present present) || present.kind() != EntryStat.EntryKind.FILE) {
      return Optional.empty();
    }
    return switch (text.readText(file, CAP_BYTES, ReadScope.AUTHORED)) {
      case TextRead.Text read -> Optional.of(read.text());
      case TextRead.Absent absent -> Optional.empty();
      case TextRead.NotRegular notRegular -> Optional.empty();
      case TextRead.OverCap overCap -> throw new ReadRefused();
      case TextRead.NotText notText -> throw new ReadRefused();
    };
  }
}
