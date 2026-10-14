package org.speckitty.missionstatus.domain.readmodel.detail;

import java.util.List;
import java.util.Map;
import java.util.Objects;
import org.speckitty.missionstatus.domain.model.Actor;
import org.speckitty.missionstatus.domain.model.Assignment;
import org.speckitty.missionstatus.domain.model.HistoryRow;
import org.speckitty.missionstatus.domain.model.Lane;
import org.speckitty.missionstatus.domain.model.WpId;

/**
 * One Work Package (the contract's {@code WorkPackage} schema). Text members are stored values; the mapper's caller redacts the human ones.
 *
 * <p>{@code subtasks} is an ORDERED list of entries, never a map: the order is significant on the wire (the code-point order of the
 * subtask id) and is fixed by whoever builds the view; the mapper must not re-sort. Entries are immutable.
 *
 * @param phaseLabel the authored phase label, or null
 * @param executionMode authored, or null
 * @param taskType authored, or null
 * @param priority authored, or null
 * @param mergeTargetBranch authored, or null
 * @param statusLane the lane, or null for a Work Package with a planning file and no events
 * @param implementerOfRecord a handle, or null
 * @param lastTransitionAt the time of the last transition as stored, or null
 * @param lastEventId the id of the last event, or null
 * @param cancellation set only for a canceled Work Package, or null
 * @param staleness the staleness verdict, or null
 * @param promptMarkdown the prompt text; null unless the prompt was asked for and could be shown
 */
public record WorkPackageView(
    WpId wpId,
    String title,
    String phaseLabel,
    Authored authored,
    List<String> ownedFiles,
    List<WpId> dependencies,
    List<String> requirementRefs,
    String executionMode,
    String taskType,
    String priority,
    String mergeTargetBranch,
    List<String> trackerRefs,
    Lane statusLane,
    Assignment assignment,
    List<Map.Entry<String, Lane>> subtasks,
    SubtaskProgress subtaskProgress,
    String implementerOfRecord,
    String lastTransitionAt,
    int forceCount,
    String lastEventId,
    Actor actor,
    Cancellation cancellation,
    Readiness readiness,
    boolean readyToStart,
    ReviewView review,
    List<HistoryRow> history,
    Staleness staleness,
    String promptMarkdown) {

  public WorkPackageView {
    Objects.requireNonNull(wpId, "wpId");
    Objects.requireNonNull(title, "title");
    Objects.requireNonNull(authored, "authored");
    Objects.requireNonNull(assignment, "assignment");
    Objects.requireNonNull(subtaskProgress, "subtaskProgress");
    Objects.requireNonNull(actor, "actor");
    Objects.requireNonNull(readiness, "readiness");
    Objects.requireNonNull(review, "review");
    ownedFiles = List.copyOf(ownedFiles);
    dependencies = List.copyOf(dependencies);
    requirementRefs = List.copyOf(requirementRefs);
    trackerRefs = List.copyOf(trackerRefs);
    subtasks = List.copyOf(subtasks);
    history = List.copyOf(history);
  }

  /**
   * What the Work Package file itself says about its subtasks and roles (the contract's {@code Authored}).
   *
   * @param role authored, or null
   * @param agentProfile authored, or null
   * @param model authored, or null
   * @param subtasks the authored subtask roster
   */
  public record Authored(String role, String agentProfile, String model, List<String> subtasks) {
    public Authored {
      subtasks = List.copyOf(subtasks);
    }
  }

  /** Why a Work Package was canceled (the contract's {@code Cancellation}). */
  public record Cancellation(ReasonSource reasonSource, String reason) {
    public Cancellation {
      Objects.requireNonNull(reasonSource, "reasonSource");
    }
  }

  /** Who stated the cancellation reason. */
  public enum ReasonSource {
    OPERATOR("operator"),
    SYNTHETIC("synthetic");

    private final String wire;

    ReasonSource(String wire) {
      this.wire = wire;
    }

    public String wire() {
      return wire;
    }
  }

  /**
   * Whether a Work Package looks abandoned (the contract's {@code Staleness}).
   *
   * @param reason the cause, or null
   * @param minutesSinceCommit minutes since the last commit, or null
   */
  public record Staleness(Status status, Reason reason, Double minutesSinceCommit) {
    public Staleness {
      Objects.requireNonNull(status, "status");
      if (minutesSinceCommit != null && minutesSinceCommit < 0) {
        throw new IllegalArgumentException("minutes are not negative");
      }
    }

    /** The staleness verdict. */
    public enum Status {
      FRESH("fresh"),
      STALE("stale"),
      NOT_APPLICABLE("not_applicable");

      private final String wire;

      Status(String wire) {
        this.wire = wire;
      }

      public String wire() {
        return wire;
      }
    }

    /** Why staleness does not apply. */
    public enum Reason {
      PLANNING_ARTIFACT_REPO_ROOT_SHARED_WORKSPACE("planning_artifact_repo_root_shared_workspace"),
      LIVE_CLAIM_PROCESS("live_claim_process");

      private final String wire;

      Reason(String wire) {
        this.wire = wire;
      }

      public String wire() {
        return wire;
      }
    }
  }
}
