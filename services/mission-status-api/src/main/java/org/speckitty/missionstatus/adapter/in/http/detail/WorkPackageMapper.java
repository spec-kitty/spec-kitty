package org.speckitty.missionstatus.adapter.in.http.detail;

import java.math.BigDecimal;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;
import org.speckitty.missionstatus.adapter.in.http.dto.WorkPackage;
import org.speckitty.missionstatus.adapter.in.http.model.Actor;
import org.speckitty.missionstatus.adapter.in.http.model.Actor1;
import org.speckitty.missionstatus.adapter.in.http.model.Assignment;
import org.speckitty.missionstatus.adapter.in.http.model.Authored;
import org.speckitty.missionstatus.adapter.in.http.model.Cancellation;
import org.speckitty.missionstatus.adapter.in.http.model.HistoryEntry;
import org.speckitty.missionstatus.adapter.in.http.model.Readiness;
import org.speckitty.missionstatus.adapter.in.http.model.Review;
import org.speckitty.missionstatus.adapter.in.http.model.ReviewOverride;
import org.speckitty.missionstatus.adapter.in.http.model.ReviewResult;
import org.speckitty.missionstatus.adapter.in.http.model.Staleness;
import org.speckitty.missionstatus.adapter.in.http.model.SubtaskProgress;
import org.speckitty.missionstatus.domain.model.HistoryRow;
import org.speckitty.missionstatus.domain.model.Lane;
import org.speckitty.missionstatus.domain.model.WpId;
import org.speckitty.missionstatus.domain.readmodel.detail.ReviewView;
import org.speckitty.missionstatus.domain.readmodel.detail.WorkPackageView;

/**
 * Shapes a {@link WorkPackageView} into the hand record of the contract's {@code WorkPackage} (the generated twin of that schema writes
 * {@code "promptMarkdown":null} and is never used for a response, D-79 check c). It holds no logic of the route: ordering, projection and
 * derivation are done by the application layer, so the mapper imports nothing of {@code domain.readmodel.derive}, {@code domain.redaction} or
 * {@code application} other than the inbound port (rule 15), and no non-record class of {@code domain.model}. The {@code subtasks} map is
 * built in the order of the entry list the service ordered by code point; it is not sorted here, and the record's serializer writes it in
 * code point order, not in the UTF-16 order of the canonical writer. {@code promptMarkdown} is absent from the body unless the view has one.
 */
public final class WorkPackageMapper {

  private WorkPackageMapper() {}

  public static WorkPackage workPackage(WorkPackageView view) {
    return new WorkPackage(
        view.wpId().value(),
        view.title(),
        view.phaseLabel(),
        new Authored(view.authored().role(), view.authored().agentProfile(), view.authored().model(), view.authored().subtasks()),
        view.ownedFiles(),
        ids(view.dependencies()),
        view.requirementRefs(),
        view.executionMode(),
        view.taskType(),
        view.priority(),
        view.mergeTargetBranch(),
        view.trackerRefs(),
        view.statusLane() == null ? null : view.statusLane().wire(),
        new Assignment(
            view.assignment().agent(),
            view.assignment().assignee(),
            view.assignment().role(),
            view.assignment().agentProfile(),
            view.assignment().agentProfileVersion(),
            view.assignment().model(),
            view.assignment().provider()),
        subtasks(view.subtasks()),
        new SubtaskProgress(view.subtaskProgress().done(), view.subtaskProgress().total()),
        view.implementerOfRecord(),
        view.lastTransitionAt(),
        view.forceCount(),
        view.lastEventId(),
        new Actor(view.actor().tool(), view.actor().role(), view.actor().profile()),
        cancellation(view.cancellation()),
        new Readiness(view.readiness().satisfied(), ids(view.readiness().unsatisfied())),
        view.readyToStart(),
        review(view.review()),
        view.history().stream().map(WorkPackageMapper::entry).toList(),
        staleness(view.staleness()),
        view.promptMarkdown());
  }

  private static List<String> ids(List<WpId> ids) {
    return ids.stream().map(WpId::value).toList();
  }

  private static Map<String, String> subtasks(List<Map.Entry<String, Lane>> ordered) {
    Map<String, String> subtasks = new LinkedHashMap<>();
    for (Map.Entry<String, Lane> entry : ordered) {
      subtasks.put(entry.getKey(), entry.getValue().wire());
    }
    return subtasks;
  }

  private static Cancellation cancellation(WorkPackageView.Cancellation cancellation) {
    return cancellation == null ? null : new Cancellation(Cancellation.ReasonSourceEnum.fromValue(cancellation.reasonSource().wire()), cancellation.reason());
  }

  private static Review review(ReviewView review) {
    ReviewResult result = null;
    if (review.latestResult() != null) {
      result = new ReviewResult(review.latestResult().reviewer(), ReviewResult.VerdictEnum.fromValue(review.latestResult().verdict().wire()), review.latestResult().reference());
    }
    ReviewOverride override = null;
    if (review.override() != null) {
      override = new ReviewOverride(review.override().complete(), review.override().at(), review.override().actor(), review.override().reason());
    }
    return new Review(result, override);
  }

  private static HistoryEntry entry(HistoryRow row) {
    return new HistoryEntry(
        row.eventId(),
        row.at(),
        HistoryEntry.KindEnum.TRANSITION,
        row.fromLane() == null ? null : HistoryEntry.FromStatusLaneEnum.fromValue(row.fromLane()),
        row.toLane() == null ? null : HistoryEntry.ToStatusLaneEnum.fromValue(row.toLane()),
        new Actor1(row.actor().tool(), row.actor().role(), row.actor().profile()),
        row.force(),
        row.reason(),
        row.reviewVerdict() == null ? null : HistoryEntry.ReviewVerdictEnum.fromValue(row.reviewVerdict()));
  }

  private static Staleness staleness(WorkPackageView.Staleness staleness) {
    if (staleness == null) {
      return null;
    }
    return new Staleness(
        Staleness.StatusEnum.fromValue(staleness.status().wire()),
        staleness.reason() == null ? null : Staleness.ReasonEnum.fromValue(staleness.reason().wire()),
        staleness.minutesSinceCommit() == null ? null : BigDecimal.valueOf(staleness.minutesSinceCommit()));
  }
}
