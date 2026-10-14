package org.speckitty.missionstatus.domain.model;

import java.util.List;
import java.util.Objects;

/**
 * The members of a Work Package file's validated frontmatter that the Work Package routes need (the oracle's {@code WPMetadata},
 * {@code src/specify_cli/status/wp_metadata.py}). The decoder validates every field of the model, including those that are not kept
 * here, and rejects the file when the oracle's model would; the members below are the ones a response is built from. The text members
 * are as stored (null when absent); the lists are never null.
 *
 * <p>{@code subtasks} holds the Python {@code str} of each entry. An entry that is a mapping, a sequence or a timestamp has a
 * {@code str} that this service does not reproduce (decision D-97, ledger entry SK-353); then {@code subtasksRefused} is true and the
 * list holds only the entries that could be stringified, and a route must answer {@code projection_refused} instead of serving it.
 */
public record WpMetadata(
    String workPackageId,
    String title,
    String phase,
    String taskType,
    String priority,
    String executionMode,
    String mergeTargetBranch,
    String planningBaseBranch,
    String role,
    String agentProfile,
    String model,
    List<String> dependencies,
    List<String> requirementRefs,
    List<String> trackerRefs,
    List<String> ownedFiles,
    List<String> subtasks,
    boolean subtasksRefused) {

  public WpMetadata {
    Objects.requireNonNull(workPackageId, "workPackageId");
    dependencies = List.copyOf(dependencies);
    requirementRefs = List.copyOf(requirementRefs);
    trackerRefs = List.copyOf(trackerRefs);
    ownedFiles = List.copyOf(ownedFiles);
    subtasks = List.copyOf(subtasks);
  }
}
