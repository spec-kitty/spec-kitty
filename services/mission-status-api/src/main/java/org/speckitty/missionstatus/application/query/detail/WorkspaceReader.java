package org.speckitty.missionstatus.application.query.detail;

import java.util.List;
import java.util.Objects;
import java.util.Optional;
import org.speckitty.missionstatus.application.query.port.out.LanesDecoder;
import org.speckitty.missionstatus.application.query.port.out.TextSource;
import org.speckitty.missionstatus.application.query.port.out.dto.BytesRead;
import org.speckitty.missionstatus.application.query.port.out.dto.EntryStat;
import org.speckitty.missionstatus.application.query.port.out.dto.FileRef;
import org.speckitty.missionstatus.application.query.port.out.dto.MissionRef;
import org.speckitty.missionstatus.application.query.port.out.dto.ReadScope;
import org.speckitty.missionstatus.application.query.port.out.dto.RelativePath;
import org.speckitty.missionstatus.application.query.port.out.exceptions.TextFault;
import org.speckitty.missionstatus.domain.model.LanesManifest;
import org.speckitty.missionstatus.domain.model.LanesResult;
import org.speckitty.missionstatus.domain.readmodel.derive.LaneNames;
import org.speckitty.missionstatus.domain.readmodel.detail.WorkspaceView;

/**
 * Where a Work Package runs (the oracle's {@code workspace_of}): its code lane and lane branch from the Mission's {@code lanes.json}, the
 * planning branch it was given, and whether its lane worktree is there (FR-010). No process is started and nothing under the worktree is
 * listed or read: {@code worktreePresent} is two {@code lstat}s.
 *
 * <p>{@code lanes.json} is read whenever the route runs, with a cap of 1 MiB applied by the bytes read. A file that is corrupt, of the legacy
 * shape, over the cap or not a file is {@link ReadRefused}, for every Work Package of the Mission (row W3). A missing file, or a Work Package
 * that is in no lane, gives null lane members.
 */
public final class WorkspaceReader {

  /** The most bytes of {@code lanes.json} the route reads (1 MiB). */
  public static final int LANES_CAP_BYTES = 1_048_576;

  private static final RelativePath LANES_JSON = RelativePath.of("lanes.json");
  private static final String WORKTREES = ".worktrees";
  private static final String GIT_ENTRY = ".git";

  private final TextSource text;
  private final LanesDecoder decoder;

  public WorkspaceReader(TextSource text, LanesDecoder decoder) {
    this.text = Objects.requireNonNull(text, "text");
    this.decoder = Objects.requireNonNull(decoder, "decoder");
  }

  /**
   * @param missionSlug the Mission's recorded slug, verbatim: it names the lane branch and the worktree directory
   * @param planningBranch the planning branch the projection already accepted, or null
   * @throws ReadRefused when {@code lanes.json} cannot be used
   * @throws TextFault when the port cannot read {@code lanes.json}, or a worktree stat fails other than "absent"
   */
  public WorkspaceView read(MissionRef mission, String missionSlug, String wpId, String planningBranch) {
    String planning = LaneNames.fittingPlanningBranch(planningBranch);
    Optional<LanesManifest> manifest = manifest(mission);
    Optional<LanesManifest.Lane> lane = manifest.flatMap(found -> found.laneFor(wpId));
    if (lane.isEmpty()) {
      return new WorkspaceView(null, null, planning, false);
    }
    String laneId = LaneNames.fittingLaneId(lane.get().laneId());
    if (laneId == null) {
      return new WorkspaceView(null, null, planning, false);
    }
    if (laneId.equals(LaneNames.PLANNING_LANE_ID)) {
      return new WorkspaceView(laneId, null, planning, false);
    }
    String branch = LaneNames.fittingBranch(LaneNames.codeLaneBranch(missionSlug, laneId));
    return new WorkspaceView(laneId, branch, planning, worktreePresent(LaneNames.worktreeDirName(missionSlug, laneId)));
  }

  private Optional<LanesManifest> manifest(MissionRef mission) {
    FileRef file = new FileRef.MissionFile(mission, LANES_JSON);
    return switch (text.readBytes(file, LANES_CAP_BYTES, ReadScope.AUTHORED)) {
      case BytesRead.Absent absent -> Optional.empty();
      case BytesRead.NotRegular notRegular -> throw new ReadRefused();
      case BytesRead.OverCap overCap -> throw new ReadRefused();
      case BytesRead.Bytes bytes -> usable(decoder.decode(bytes.content()));
    };
  }

  private static Optional<LanesManifest> usable(LanesResult result) {
    return switch (result) {
      case LanesResult.Manifest manifest -> Optional.of(manifest.manifest());
      case LanesResult.Corrupt corrupt -> throw new ReadRefused();
      case LanesResult.Legacy legacy -> throw new ReadRefused();
    };
  }

  /**
   * True when {@code .worktrees/<directory>} is a real directory (not a link) whose {@code .git} entry is a regular file or a directory
   * (not a link). Neither entry is followed. A link anywhere on the way is a refusal of the port, which reads as "not there"; any other
   * failure of a stat is a fault.
   */
  private boolean worktreePresent(String directory) {
    RelativePath lane;
    try {
      lane = new RelativePath(List.of(WORKTREES, directory));
    } catch (IllegalArgumentException notASegment) {
      return false;
    }
    try {
      if (!isKind(text.stat(new FileRef.ProjectFile(lane), ReadScope.AUTHORED), EntryStat.EntryKind.DIRECTORY)) {
        return false;
      }
      EntryStat git = text.stat(new FileRef.ProjectFile(lane.child(GIT_ENTRY)), ReadScope.AUTHORED);
      return isKind(git, EntryStat.EntryKind.FILE) || isKind(git, EntryStat.EntryKind.DIRECTORY);
    } catch (TextFault fault) {
      if (fault.kind() == TextFault.Kind.PATH_REFUSED) {
        return false;
      }
      throw fault;
    }
  }

  private static boolean isKind(EntryStat stat, EntryStat.EntryKind kind) {
    return stat instanceof EntryStat.Present present && present.kind() == kind;
  }
}
