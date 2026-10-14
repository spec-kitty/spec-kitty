package org.speckitty.missionstatus.domain.readmodel.detail;

/**
 * Where a Work Package is worked on (the contract's {@code Workspace}).
 *
 * @param laneId the lane id, or null
 * @param laneBranch the lane branch, or null
 * @param planningBranch the planning branch, or null
 * @param worktreePresent whether the lane worktree exists
 */
public record WorkspaceView(String laneId, String laneBranch, String planningBranch, boolean worktreePresent) {}
