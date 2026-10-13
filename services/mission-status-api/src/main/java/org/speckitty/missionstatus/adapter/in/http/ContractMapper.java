package org.speckitty.missionstatus.adapter.in.http;

import java.math.BigDecimal;
import java.util.List;
import org.speckitty.missionstatus.adapter.in.http.model.MissionOverviewPage;
import org.speckitty.missionstatus.adapter.in.http.model.MissionProgress;
import org.speckitty.missionstatus.adapter.in.http.model.PageInfo;
import org.speckitty.missionstatus.adapter.in.http.model.Project;
import org.speckitty.missionstatus.adapter.in.http.model.StatusLaneCounts;
import org.speckitty.missionstatus.adapter.in.http.model.StreamCursor;
import org.speckitty.missionstatus.domain.model.Lane;
import org.speckitty.missionstatus.domain.readmodel.overview.MissionOverview;
import org.speckitty.missionstatus.domain.readmodel.overview.MissionPage;
import org.speckitty.missionstatus.domain.readmodel.overview.Progress;
import org.speckitty.missionstatus.domain.readmodel.overview.ProjectHeader;

/** Domain values to the generated contract models. The timestamps stay the text the domain holds (the models type them as text). */
final class ContractMapper {

  private ContractMapper() {}

  static Project project(ProjectHeader header) {
    return new Project(
        header.name(),
        header.missionCount(),
        header.specKittyVersion(),
        header.schemaVersion(),
        Project.HealthEnum.fromValue(header.health().wire()),
        header.currentBranch(),
        header.lastActivityAt());
  }

  static MissionOverviewPage page(MissionPage page) {
    List<org.speckitty.missionstatus.adapter.in.http.model.MissionOverview> items = page.items().stream().map(ContractMapper::overview).toList();
    return new MissionOverviewPage(items, new PageInfo(page.nextPageCursor() != null, page.nextPageCursor(), page.pageSize()));
  }

  static org.speckitty.missionstatus.adapter.in.http.model.MissionOverview overview(MissionOverview item) {
    return new org.speckitty.missionstatus.adapter.in.http.model.MissionOverview(
        item.missionId().value(),
        item.mid8(),
        item.slug(),
        item.friendlyName(),
        item.displayNumber(),
        item.missionType(),
        item.targetBranch(),
        org.speckitty.missionstatus.adapter.in.http.model.MissionOverview.TopologyEnum.fromValue(item.topology().wire()),
        item.createdAt(),
        counts(item),
        item.wpTotal(),
        item.blockedCount(),
        progress(item.progress()),
        org.speckitty.missionstatus.adapter.in.http.model.MissionOverview.LifecycleStatusEnum.fromValue(item.lifecycleStatus().wire()),
        item.acceptedAt(),
        item.mergedAt(),
        item.discardedAt(),
        item.lastEventId(),
        item.lastActivityAt(),
        item.eventCount(),
        new StreamCursor(item.streamCursor().offset(), item.streamCursor().invariant()),
        item.nextAction());
  }

  private static StatusLaneCounts counts(MissionOverview item) {
    return new StatusLaneCounts(
        count(item, Lane.PLANNED), count(item, Lane.CLAIMED), count(item, Lane.IN_PROGRESS), count(item, Lane.FOR_REVIEW), count(item, Lane.IN_REVIEW),
        count(item, Lane.APPROVED), count(item, Lane.DONE), count(item, Lane.BLOCKED), count(item, Lane.CANCELED));
  }

  private static int count(MissionOverview item, Lane lane) {
    return item.statusLaneCounts().getOrDefault(lane, 0);
  }

  private static MissionProgress progress(Progress progress) {
    return new MissionProgress(
        BigDecimal.valueOf(progress.weightedPercentage()), BigDecimal.valueOf(progress.donePercentage()), progress.doneCount(), MissionProgress.SemanticsEnum.fromValue(Progress.SEMANTICS));
  }
}
