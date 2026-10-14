package org.speckitty.missionstatus.application.query;

import java.util.AbstractMap;
import java.util.ArrayList;
import java.util.List;
import java.util.Map;
import java.util.Objects;
import java.util.Optional;
import java.util.function.Consumer;
import java.util.regex.Pattern;
import org.speckitty.missionstatus.application.query.index.IndexedWorkPackage;
import org.speckitty.missionstatus.application.query.index.WorkPackageIndex;
import org.speckitty.missionstatus.application.query.index.WorkPackageIndexFault;
import org.speckitty.missionstatus.application.query.port.in.WorkPackageQuery;
import org.speckitty.missionstatus.application.query.port.in.exceptions.DetailRefusal;
import org.speckitty.missionstatus.application.query.port.in.exceptions.MissionStatusUnavailable;
import org.speckitty.missionstatus.application.query.port.out.dto.MissionRef;
import org.speckitty.missionstatus.application.query.port.out.exceptions.TextFault;
import org.speckitty.missionstatus.domain.model.Actor;
import org.speckitty.missionstatus.domain.model.CodePoints;
import org.speckitty.missionstatus.domain.model.Diagnostic;
import org.speckitty.missionstatus.domain.model.DiagnosticCode;
import org.speckitty.missionstatus.domain.model.HistoryRow;
import org.speckitty.missionstatus.domain.model.Lane;
import org.speckitty.missionstatus.domain.model.MissionId;
import org.speckitty.missionstatus.domain.model.ReviewOverrideRecord;
import org.speckitty.missionstatus.domain.model.ReviewResultRecord;
import org.speckitty.missionstatus.domain.model.StatusSnapshot;
import org.speckitty.missionstatus.domain.model.WpId;
import org.speckitty.missionstatus.domain.model.WpMetadata;
import org.speckitty.missionstatus.domain.model.WpResolved;
import org.speckitty.missionstatus.domain.model.WpState;
import org.speckitty.missionstatus.domain.readmodel.derive.HistoryOrder;
import org.speckitty.missionstatus.domain.readmodel.derive.ReadinessDeriver;
import org.speckitty.missionstatus.domain.readmodel.detail.Readiness;
import org.speckitty.missionstatus.domain.readmodel.detail.ReviewView;
import org.speckitty.missionstatus.domain.readmodel.detail.SubtaskProgress;
import org.speckitty.missionstatus.domain.readmodel.detail.WorkPackageView;
import org.speckitty.missionstatus.domain.readmodel.overview.Instants;
import org.speckitty.missionstatus.domain.redaction.LeakClasses;
import org.speckitty.missionstatus.domain.redaction.ProjectionError;
import org.speckitty.missionstatus.domain.redaction.Projector;

/**
 * The application service behind {@link WorkPackageQuery}: one Work Package of a Mission, its authored plan from the file and its resolved
 * state from the ledger, optionally with the prompt.
 *
 * <p>The sequence of a request is fixed (D-104): the probe-free lookup of the Mission by its id, the duplicate continuation, the one head from
 * {@link MissionReadModel} (the snapshot the resolved state is read from; no extra ledger call), then the shared Work Package index. For
 * {@code includePrompt=true} the index is asked to keep the body of the file that holds the requested identifier, from the very read that
 * indexed it: there is no second read of any file (FRESH3-007, D-76). Authored plan and resolved state never mix: the planning file's own
 * {@code agent}, {@code assignee}, {@code lane} or review keys are not read.
 *
 * <p>Strict members are projected with {@link Projector#strict} (a value that cannot be shown refuses the route when the member is required
 * and is null when it is nullable), human text with {@link Projector#human}. {@code subtasks} is ordered here by code point (this service is
 * its ordering owner: the adapter must not sort). The prompt is the one text member that is not projected (FR-009, operator Q3): it is
 * served as authored, and the guard is the loopback bind together with the Host and Origin check.
 *
 * <p>The admission gate is held for {@code includePrompt=true} only (S-13, operator ruling D-148): that response holds the read buffer, the
 * decoded text, the captured body and the serialised JSON together, about 11 MiB. The prompt-less call is not gated.
 */
public final class WorkPackageQueryService implements WorkPackageQuery {

  /** A Work Package identifier as a dependency may be written: checked for leaks first, then typed as a {@link WpId}. */
  private static final Pattern WP_ID = Pattern.compile("WP[0-9]{2,}$");

  /**
   * The contract's relative-reference shape (the oracle's {@code _RELATIVE_REFERENCE}): one to 256 characters, no drive letter, not starting
   * with a slash, a backslash or a tilde. {@code (?d)} makes only {@code \n} a line ending, as Python's {@code .} and {@code $} do.
   */
  private static final Pattern RELATIVE_REFERENCE = Pattern.compile("(?d)(?![A-Za-z]:)[^/\\\\~].{0,255}$");

  private static final String APPROVED = "approved";
  private static final String CHANGES_REQUESTED = "changes_requested";

  private final MissionReadModel model;
  private final WorkPackageIndex index;
  private final Consumer<Diagnostic> diagnostics;
  private final MissionLocator locator;
  private final LeakClasses leaks;
  private final AdmissionGate gate;

  /**
   * @param model the read path shared with the other services of the query side: the lookup, the one head derivation and the one cache
   * @param index the shared Work Package index (the one bean of the whole mission)
   * @param diagnostics called once per occurrence of a fault
   * @param leaks the host-path, e-mail and secret patterns the projection applies
   * @param gate the shared admission gate, held for the prompt variant only
   */
  public WorkPackageQueryService(MissionReadModel model, WorkPackageIndex index, Consumer<Diagnostic> diagnostics, LeakClasses leaks, AdmissionGate gate) {
    this.model = Objects.requireNonNull(model, "model");
    this.index = Objects.requireNonNull(index, "index");
    this.diagnostics = Objects.requireNonNull(diagnostics, "diagnostics");
    this.locator = new MissionLocator(model, diagnostics);
    this.leaks = Objects.requireNonNull(leaks, "leaks");
    this.gate = Objects.requireNonNull(gate, "gate");
  }

  @Override
  public WorkPackageView workPackage(MissionId missionId, WpId wpId, boolean includePrompt) {
    if (includePrompt) {
      return gate.run(() -> serve(missionId, wpId, true));
    }
    return serve(missionId, wpId, false);
  }

  private WorkPackageView serve(MissionId missionId, WpId wpId, boolean includePrompt) {
    MissionLookup.Found found = locator.locate(missionId);
    MissionHead head = model.head(found.ref()).orElseThrow(DetailRefusal::notFound);
    String mid8 = found.mid8();

    WorkPackageIndex.Result indexed = indexOf(found.ref(), mid8, includePrompt ? Optional.of(wpId) : Optional.empty());
    IndexedWorkPackage file = indexed.workPackages().stream().filter(candidate -> candidate.id().equals(wpId)).findFirst().orElseThrow(DetailRefusal::notFound);
    try {
      return view(file, head.entry().snapshot(), includePrompt ? indexed.capturedBody().orElse(null) : null, new Projector(leaks));
    } catch (ProjectionError refused) {
      throw refuse(DiagnosticCode.PROJECTION_REFUSED, mid8);
    }
  }

  // ---- the lookup ------------------------------------------------------------------------------------------------------------------

  /** The Work Package files of the Mission (rows M4a, M5, M6, M10, M13): the index writes its own skip and duplicate diagnostics. */
  private WorkPackageIndex.Result indexOf(MissionRef ref, String mid8, Optional<WpId> captureBodyOf) {
    try {
      return index.build(ref, mid8, captureBodyOf, diagnostics);
    } catch (WorkPackageIndexFault fault) {
      throw refuse(DiagnosticCode.SOURCE_UNREADABLE, mid8);
    } catch (TextFault fault) {
      throw fault.kind() == TextFault.Kind.VANISHED ? DetailRefusal.notFound() : refuse(DiagnosticCode.SOURCE_UNREADABLE, mid8);
    }
  }

  // ---- the view ----------------------------------------------------------------------------------------------------------------------

  private WorkPackageView view(IndexedWorkPackage file, StatusSnapshot snapshot, String prompt, Projector projector) {
    WpMetadata metadata = file.metadata();
    if (metadata.subtasksRefused()) {
      // SK-353 (D-97): subtasks written as mappings have a Python str() this service does not reproduce
      throw new ProjectionError("subtasks", ProjectionError.Reason.NOT_REPRESENTABLE);
    }
    WpId id = file.id();
    WpState state = snapshot.workPackages().get(id.value());
    WpResolved resolved = snapshot.resolved().getOrDefault(id.value(), WpResolved.empty());
    Lane lane = state == null || !state.lane().isDisplay() ? null : state.lane();

    String title = projector.human(metadata.title(), "title");
    if (title == null) {
      throw new ProjectionError("title", ProjectionError.Reason.MISSING);
    }
    List<WpId> dependencies = dependencies(metadata.dependencies(), projector);
    Readiness readiness = ReadinessDeriver.derive(dependencies, snapshot.workPackages());
    List<Map.Entry<String, Lane>> subtasks = new ArrayList<>();
    SubtaskProgress progress = subtasks(resolved, projector, subtasks);

    return new WorkPackageView(
        id,
        title,
        projector.human(metadata.phase(), "phaseLabel"),
        new WorkPackageView.Authored(
            projector.human(metadata.role(), "authored.role"),
            projector.human(metadata.agentProfile(), "authored.agentProfile"),
            projector.human(metadata.model(), "authored.model"),
            strictList(metadata.subtasks(), "authored.subtasks", projector)),
        strictList(metadata.ownedFiles(), "ownedFiles", projector),
        dependencies,
        strictList(metadata.requirementRefs(), "requirementRefs", projector),
        projector.human(normaliseQuoted(metadata.executionMode()), "executionMode"),
        projector.human(metadata.taskType(), "taskType"),
        projector.human(metadata.priority(), "priority"),
        projector.strict(metadata.mergeTargetBranch(), "mergeTargetBranch", true),
        strictList(metadata.trackerRefs(), "trackerRefs", projector),
        lane,
        resolved.assignment(),
        subtasks,
        progress,
        state == null || state.implementerOfRecord() == null ? null : Actor.ofText(state.implementerOfRecord()).tool(),
        state == null ? null : state.lastTransitionAt(),
        state == null ? 0 : state.forceCount(),
        state == null ? null : state.lastEventId(),
        resolved.actor(),
        cancellation(lane, state, projector),
        readiness,
        ReadinessDeriver.readyToStart(lane, readiness),
        new ReviewView(reviewResult(resolved.reviewResult(), projector), reviewOverride(resolved.reviewOverride(), projector)),
        history(resolved.history(), projector),
        null,
        prompt);
  }

  private static List<WpId> dependencies(List<String> authored, Projector projector) {
    List<WpId> dependencies = new ArrayList<>();
    for (String dependency : authored) {
      String clean = projector.strict(dependency, "dependencies", false, WP_ID);
      dependencies.add(WpId.parse(clean).orElseThrow(() -> new ProjectionError("dependencies", ProjectionError.Reason.NOT_REPRESENTABLE)));
    }
    return dependencies;
  }

  private static List<String> strictList(List<String> values, String field, Projector projector) {
    List<String> clean = new ArrayList<>();
    for (String value : values) {
      clean.add(projector.strict(value, field, false, RELATIVE_REFERENCE));
    }
    return clean;
  }

  /**
   * The resolved subtasks in code point order of their ids (AC-2.7), and done over total. A subtask id that cannot be shown refuses (row T7);
   * a status that is not one of the nine display lanes ({@code genesis} and {@code uninitialized} are carried by the reduction, as Python
   * accepts them) is a projection refusal, never a null (WP05 review N3, D-159 d).
   */
  private static SubtaskProgress subtasks(WpResolved resolved, Projector projector, List<Map.Entry<String, Lane>> into) {
    int done = 0;
    for (Map.Entry<String, Lane> subtask : resolved.subtasks().entrySet()) {
      String key = projector.strict(subtask.getKey(), "subtasks", false, RELATIVE_REFERENCE);
      Lane status = subtask.getValue();
      if (!status.isDisplay()) {
        throw new ProjectionError("subtasks", ProjectionError.Reason.NOT_REPRESENTABLE);
      }
      if (status == Lane.DONE) {
        done++;
      }
      into.add(new AbstractMap.SimpleImmutableEntry<>(key, status));
    }
    into.sort((left, right) -> CodePoints.compare(left.getKey(), right.getKey()));
    return new SubtaskProgress(done, into.size());
  }

  /** {@code normalise_quoted}: the text trimmed, one balanced pair of literal quotes removed, and nothing left is no value. */
  private static String normaliseQuoted(String value) {
    if (value == null) {
      return null;
    }
    String text = value.strip();
    if (text.length() >= 2 && text.charAt(0) == text.charAt(text.length() - 1) && (text.charAt(0) == '"' || text.charAt(0) == '\'')) {
      text = text.substring(1, text.length() - 1).strip();
    }
    return text.isEmpty() ? null : text;
  }

  private static WorkPackageView.Cancellation cancellation(Lane lane, WpState state, Projector projector) {
    if (lane != Lane.CANCELED) {
      return null;
    }
    WorkPackageView.ReasonSource source = "operator".equals(state.reasonSource()) ? WorkPackageView.ReasonSource.OPERATOR : WorkPackageView.ReasonSource.SYNTHETIC;
    return new WorkPackageView.Cancellation(source, projector.human(state.cancellationReason(), "cancellation.reason"));
  }

  private static ReviewView.Result reviewResult(ReviewResultRecord record, Projector projector) {
    if (record == null) {
      return null;
    }
    ReviewView.Verdict verdict = verdictOf(record.verdict(), "review.latestResult.verdict");
    if (verdict == null) {
      throw new ProjectionError("review.latestResult.verdict", ProjectionError.Reason.MISSING);
    }
    String reference = projector.human(record.reference() == null ? "" : record.reference(), "review.latestResult.reference");
    return new ReviewView.Result(record.reviewer(), verdict, reference);
  }

  /**
   * The review override: null for no record or the release marker (every member empty); otherwise {@code complete} is "all four present" and
   * the time is shown only when it is an instant with an offset. A complete record whose time cannot be shown is refused (row T14); a partial
   * one shows {@code at: null}.
   */
  private static ReviewView.ReviewOverride reviewOverride(ReviewOverrideRecord record, Projector projector) {
    if (record == null) {
      return null;
    }
    boolean atPresent = !record.at().isEmpty();
    boolean actorPresent = !record.actor().isEmpty();
    boolean reasonPresent = !record.reason().isEmpty();
    if (!atPresent && !actorPresent && !reasonPresent && record.wpId().isEmpty()) {
      return null;
    }
    boolean dated = atPresent && Instants.hasOffset(record.at());
    if (record.complete() && !dated) {
      throw new ProjectionError("review.override.at", ProjectionError.Reason.NOT_REPRESENTABLE);
    }
    return new ReviewView.ReviewOverride(
        record.complete(),
        dated ? record.at() : null,
        actorPresent ? Actor.ofText(record.actor()).tool() : null,
        reasonPresent ? projector.human(record.reason(), "review.override.reason") : null);
  }

  /** The verdict of the contract, or null for none; any other text (or a value that was not text) cannot be shown. */
  private static ReviewView.Verdict verdictOf(String stored, String field) {
    if (stored == null) {
      return null;
    }
    return switch (stored) {
      case APPROVED -> ReviewView.Verdict.APPROVED;
      case CHANGES_REQUESTED -> ReviewView.Verdict.CHANGES_REQUESTED;
      default -> throw new ProjectionError(field, ProjectionError.Reason.NOT_REPRESENTABLE);
    };
  }

  // ---- history -----------------------------------------------------------------------------------------------------------------------

  /**
   * The transitions of the Work Package in history order (the parsed instant, then the event id) as the route shows them: the event id is a
   * strict member (T12), the stamp must be an instant with an offset (T13), a lane of {@code genesis} or {@code uninitialized} is null and
   * any other lane outside the nine is a refusal (N3, D-159 d), the reason is human text and a verdict outside the contract is a refusal.
   */
  static List<HistoryRow> history(List<HistoryRow> rows, Projector projector) {
    List<HistoryRow> shown = new ArrayList<>();
    for (HistoryRow row : HistoryOrder.order(rows)) {
      String eventId = projector.strict(row.eventId(), "history.eventId", false);
      if (row.at() == null || !Instants.hasOffset(row.at())) {
        throw new ProjectionError("history.at", ProjectionError.Reason.NOT_REPRESENTABLE);
      }
      String verdict = row.reviewVerdict();
      if (verdict != null) {
        verdictOf(verdict, "history.reviewVerdict");
      }
      shown.add(
          new HistoryRow(
              row.wpId(), eventId, row.at(), displayLane(row.fromLane()), displayLane(row.toLane()), row.actor(), row.force(), projector.human(row.reason(), "history.reason"), verdict));
    }
    return shown;
  }

  /** A stored lane text as the route shows it: null stays null, {@code genesis} and {@code uninitialized} become null, a display lane stays, any other text is a refusal. */
  static String displayLane(String stored) {
    if (stored == null) {
      return null;
    }
    for (Lane lane : Lane.values()) {
      if (lane.wire().equals(stored)) {
        return lane.isDisplay() ? stored : null;
      }
    }
    throw new ProjectionError("history.lane", ProjectionError.Reason.NOT_REPRESENTABLE);
  }

  // ---- diagnostics -------------------------------------------------------------------------------------------------------------------

  private void note(DiagnosticCode code, String mid8) {
    diagnostics.accept(new Diagnostic(code, mid8, null));
  }

  private MissionStatusUnavailable refuse(DiagnosticCode code, String mid8) {
    Diagnostic diagnostic = new Diagnostic(code, mid8, null);
    diagnostics.accept(diagnostic);
    return new MissionStatusUnavailable(diagnostic);
  }
}
