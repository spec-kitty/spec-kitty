package org.speckitty.missionstatus.application.query.port.out;

import java.util.List;
import java.util.Optional;
import org.speckitty.missionstatus.application.query.port.out.dto.ArtifactBytes;
import org.speckitty.missionstatus.application.query.port.out.dto.ArtifactFile;
import org.speckitty.missionstatus.application.query.port.out.dto.MissionRef;
import org.speckitty.missionstatus.application.query.port.out.exceptions.SourceFault;

/**
 * The outbound seam of the artifact reads: a Mission's primary directory, read without following a link. Every path is relative to the
 * Mission directory and has already passed the artifact-path rule. A fault the reads cannot answer is a {@link SourceFault} of kind
 * {@code DIR_UNREADABLE}, never an {@code IOException}, a path or an operating-system message.
 */
public interface MissionArtifactSource {

  /**
   * The Mission directory whose {@code meta.json} holds {@code missionId}: the first one in code-point order of the directory name.
   * Empty when none does, including when {@code kitty-specs/} cannot be listed; a {@code meta.json} that cannot be read or parsed is
   * skipped.
   */
  Optional<MissionRef> findMission(String missionId);

  /**
   * Whether the Mission directory is a real directory inside the project root: true when it is, false when it is gone, is a link or
   * leaves the root. A directory that cannot be stat-ed is a fault.
   */
  boolean missionDirPresent(MissionRef ref);

  /** Every regular, non-link file below the Mission directory, as relative paths, in no particular order. A listing failure is a fault. */
  List<String> walk(MissionRef ref);

  /**
   * Whether no component of {@code path} is a link, every component but the last is a directory and the last is a regular file. A
   * missing component, or a file used as a directory, is false; any other failure is a fault.
   */
  boolean isRegularFileWithoutLinks(MissionRef ref, String path);

  /** The size and modification time of the file at {@code path}, not following a link; empty when it is gone. Any other failure is a fault. */
  Optional<ArtifactFile> stat(MissionRef ref, String path);

  /**
   * Opens the file at {@code path} without following a final link, takes its size from the open handle and, when that is at most
   * {@code cap}, reads at most {@code cap} + 1 bytes. Every failure is {@link ArtifactBytes.Unreadable}; this method throws nothing.
   */
  ArtifactBytes read(MissionRef ref, String path, int cap);
}
