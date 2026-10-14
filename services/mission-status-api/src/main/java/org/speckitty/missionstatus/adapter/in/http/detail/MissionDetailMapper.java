package org.speckitty.missionstatus.adapter.in.http.detail;

import java.util.List;
import org.speckitty.missionstatus.adapter.in.http.ContractMapper;
import org.speckitty.missionstatus.adapter.in.http.model.MissionPhase;
import org.speckitty.missionstatus.adapter.in.http.model.Readiness;
import org.speckitty.missionstatus.adapter.in.http.model.SubtaskProgress;
import org.speckitty.missionstatus.adapter.in.http.model.WorkPackageSummary;
import org.speckitty.missionstatus.domain.model.WpId;
import org.speckitty.missionstatus.domain.readmodel.detail.MissionDetail;

/**
 * Shapes the records of the Mission detail into the generated contract model. It holds no logic of the route: ordering, projection and
 * derivation are done by the application layer, so the mapper imports nothing of {@code domain.readmodel.derive}, {@code domain.redaction}
 * or {@code application} other than the inbound port (rule 15). The members of the head are written by {@code ContractMapper#overview}, the
 * conversion of the overview item itself, because the detail is that item plus {@code phases} and {@code workPackages}.
 */
public final class MissionDetailMapper {

  private MissionDetailMapper() {}

  public static org.speckitty.missionstatus.adapter.in.http.model.MissionDetail detail(MissionDetail detail) {
    org.speckitty.missionstatus.adapter.in.http.model.MissionOverview head = ContractMapper.overview(detail.overview());
    return new org.speckitty.missionstatus.adapter.in.http.model.MissionDetail(
        head.getMissionId(),
        head.getMid8(),
        head.getSlug(),
        head.getFriendlyName(),
        head.getDisplayNumber(),
        head.getMissionType(),
        head.getTargetBranch(),
        org.speckitty.missionstatus.adapter.in.http.model.MissionDetail.TopologyEnum.fromValue(head.getTopology().getValue()),
        head.getCreatedAt(),
        head.getStatusLaneCounts(),
        head.getWpTotal(),
        head.getBlockedCount(),
        head.getProgress(),
        org.speckitty.missionstatus.adapter.in.http.model.MissionDetail.LifecycleStatusEnum.fromValue(head.getLifecycleStatus().getValue()),
        head.getAcceptedAt(),
        head.getMergedAt(),
        head.getDiscardedAt(),
        head.getLastEventId(),
        head.getLastActivityAt(),
        head.getEventCount(),
        head.getStreamCursor(),
        head.getNextAction(),
        detail.phases().stream().map(MissionDetailMapper::phase).toList(),
        detail.workPackages().stream().map(MissionDetailMapper::summary).toList());
  }

  private static MissionPhase phase(org.speckitty.missionstatus.domain.readmodel.detail.MissionPhase phase) {
    return new MissionPhase(
        MissionPhase.NameEnum.fromValue(phase.name().wire()), MissionPhase.StatusEnum.fromValue(phase.status().wire()), MissionPhase.BasisEnum.fromValue(phase.basis().wire()));
  }

  private static WorkPackageSummary summary(org.speckitty.missionstatus.domain.readmodel.detail.WorkPackageSummary summary) {
    return new WorkPackageSummary(
        summary.wpId().value(),
        summary.title(),
        summary.phaseLabel(),
        summary.statusLane() == null ? null : WorkPackageSummary.StatusLaneEnum.fromValue(summary.statusLane().wire()),
        ids(summary.dependencies()),
        new Readiness(summary.readiness().satisfied(), ids(summary.readiness().unsatisfied())),
        summary.readyToStart(),
        new SubtaskProgress(summary.subtaskProgress().done(), summary.subtaskProgress().total()),
        summary.lastTransitionAt());
  }

  private static List<String> ids(List<WpId> ids) {
    return ids.stream().map(WpId::value).toList();
  }
}
