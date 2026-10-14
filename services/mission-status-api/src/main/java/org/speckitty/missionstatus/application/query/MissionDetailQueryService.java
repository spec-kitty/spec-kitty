package org.speckitty.missionstatus.application.query;

import java.util.ArrayList;
import java.util.EnumMap;
import java.util.EnumSet;
import java.util.List;
import java.util.Map;
import java.util.Objects;
import java.util.Optional;
import java.util.Set;
import java.util.function.Consumer;
import java.util.regex.Pattern;
import org.speckitty.missionstatus.application.query.index.IndexedWorkPackage;
import org.speckitty.missionstatus.application.query.index.WorkPackageIndex;
import org.speckitty.missionstatus.application.query.index.WorkPackageIndexFault;
import org.speckitty.missionstatus.application.query.port.in.MissionDetailQuery;
import org.speckitty.missionstatus.application.query.port.in.exceptions.DetailRefusal;
import org.speckitty.missionstatus.application.query.port.in.exceptions.MissionStatusUnavailable;
import org.speckitty.missionstatus.application.query.port.out.TextSource;
import org.speckitty.missionstatus.application.query.port.out.dto.EntryStat;
import org.speckitty.missionstatus.application.query.port.out.dto.FileRef;
import org.speckitty.missionstatus.application.query.port.out.dto.MissionRef;
import org.speckitty.missionstatus.application.query.port.out.dto.ReadScope;
import org.speckitty.missionstatus.application.query.port.out.dto.RelativePath;
import org.speckitty.missionstatus.application.query.port.out.exceptions.SourceFault;
import org.speckitty.missionstatus.application.query.port.out.exceptions.TextFault;
import org.speckitty.missionstatus.domain.model.Diagnostic;
import org.speckitty.missionstatus.domain.model.DiagnosticCode;
import org.speckitty.missionstatus.domain.model.Lane;
import org.speckitty.missionstatus.domain.model.MissionId;
import org.speckitty.missionstatus.domain.model.StatusSnapshot;
import org.speckitty.missionstatus.domain.model.WpId;
import org.speckitty.missionstatus.domain.model.WpMetadata;
import org.speckitty.missionstatus.domain.model.WpResolved;
import org.speckitty.missionstatus.domain.model.WpState;
import org.speckitty.missionstatus.domain.readmodel.derive.PhaseDeriver;
import org.speckitty.missionstatus.domain.readmodel.derive.ReadinessDeriver;
import org.speckitty.missionstatus.domain.readmodel.detail.MissionDetail;
import org.speckitty.missionstatus.domain.readmodel.detail.MissionPhase;
import org.speckitty.missionstatus.domain.readmodel.detail.PhaseName;
import org.speckitty.missionstatus.domain.readmodel.detail.Readiness;
import org.speckitty.missionstatus.domain.readmodel.detail.SubtaskProgress;
import org.speckitty.missionstatus.domain.readmodel.detail.WorkPackageSummary;
import org.speckitty.missionstatus.domain.redaction.LeakClasses;
import org.speckitty.missionstatus.domain.redaction.ProjectionError;
import org.speckitty.missionstatus.domain.redaction.Projector;

/**
 * The application service behind {@link MissionDetailQuery}: the Mission head, its five phases and one summary per Work Package file.
 *
 * <p>The sequence of a request is fixed (D-104): the probe-free lookup of the Mission by its id, the duplicate continuation (one
 * {@code mission_id_duplicate} diagnostic when a second readable directory holds the id), then the one head from {@link MissionReadModel}.
 * Nothing else reads the Mission's {@code meta.json} or its ledger: the head is the same derivation, the same projection and the same cache as
 * the overview item of the list, so the detail without its phases and Work Packages <em>is</em> that item. The per-Work-Package state is
 * read from the cache entry of the head. The phases rest on the lane counts of the head, the set of lifecycle event types of the snapshot and
 * an {@code lstat} of the three planning files of the Mission's primary directory.
 *
 * <p>Every fault of the failure table that belongs to this route is decided here and reported once through the diagnostics consumer: a
 * {@link DetailRefusal} for an unknown Mission, a {@link MissionStatusUnavailable} carrying the diagnostic code for the rest. Strict and
 * human text is projected here, in the application layer; the mapper of the adapter only shapes the records. This service does not hold the
 * {@code AdmissionGate}: {@code getMission} is not one of the heavy operations.
 */
public final class MissionDetailQueryService implements MissionDetailQuery {

  /** A Work Package identifier as a dependency may be written: checked for leaks first, then typed as a {@link WpId}. */
  private static final Pattern WP_ID = Pattern.compile("WP[0-9]{2,}");

  /** The planning file of each planning phase, in workflow order. */
  private static final Map<PhaseName, String> PLANNING_FILES = new EnumMap<>(PhaseName.class);

  static {
    PLANNING_FILES.put(PhaseName.SPECIFY, "spec.md");
    PLANNING_FILES.put(PhaseName.PLAN, "plan.md");
    PLANNING_FILES.put(PhaseName.TASKS, "tasks.md");
  }

  private final MissionReadModel model;
  private final WorkPackageIndex index;
  private final TextSource text;
  private final Consumer<Diagnostic> diagnostics;
  private final LeakClasses leaks;

  /**
   * @param model the read path shared with the other services of the query side: the lookup, the one head derivation and the one cache
   * @param index the shared Work Package index (the one bean of the whole mission)
   * @param text the text-read port, for the {@code lstat} of the planning files
   * @param diagnostics called once per occurrence of a fault
   * @param leaks the host-path, e-mail and secret patterns the projection applies
   */
  public MissionDetailQueryService(MissionReadModel model, WorkPackageIndex index, TextSource text, Consumer<Diagnostic> diagnostics, LeakClasses leaks) {
    this.model = Objects.requireNonNull(model, "model");
    this.index = Objects.requireNonNull(index, "index");
    this.text = Objects.requireNonNull(text, "text");
    this.diagnostics = Objects.requireNonNull(diagnostics, "diagnostics");
    this.leaks = Objects.requireNonNull(leaks, "leaks");
  }

  @Override
  public MissionDetail mission(MissionId missionId) {
    MissionLookup.Found found = locate(missionId);
    MissionHead head = model.head(found.ref()).orElseThrow(DetailRefusal::notFound);
    String mid8 = found.mid8();
    StatusSnapshot snapshot = head.entry().snapshot();

    WorkPackageIndex.Result indexed = indexOf(found.ref(), mid8);
    Set<PhaseName> artifacts = artifactsOf(found.ref(), mid8);
    List<MissionPhase> phases = PhaseDeriver.derive(head.overview().statusLaneCounts(), head.overview().wpTotal(), artifacts, snapshot.lifecycleTypes());
    return new MissionDetail(head.overview(), phases, summaries(indexed, snapshot, mid8));
  }

  // ---- the lookup ------------------------------------------------------------------------------------------------------------------

  /**
   * The Mission that holds the id, with the duplicate continuation. A readable Mission that holds the id wins over any faulted sibling (D-39);
   * with no match the first fault in byte order decides: a refused directory is a 404 with {@code path_refused}, an unusable
   * {@code meta.json} and an unreadable directory are 500s.
   */
  private MissionLookup.Found locate(MissionId id) {
    MissionLookup.Scan scan;
    try {
      scan = model.find(id);
    } catch (SourceFault fault) {
      throw refuse(DiagnosticCode.MISSION_DIR_UNREADABLE, Diagnostic.NONE);
    }
    MissionLookup.Found found = scan.found();
    if (found != null) {
      if (model.hasDuplicate(scan)) {
        note(DiagnosticCode.MISSION_ID_DUPLICATE, found.mid8());
      }
      return found;
    }
    SourceFault.Kind unreadable = scan.firstFault();
    if (unreadable == SourceFault.Kind.PATH_REFUSED) {
      note(DiagnosticCode.PATH_REFUSED, Diagnostic.NONE);
    } else if (unreadable == SourceFault.Kind.META_UNPARSEABLE) {
      throw refuse(DiagnosticCode.META_UNPARSEABLE, Diagnostic.NONE);
    } else if (unreadable != null) {
      throw refuse(DiagnosticCode.MISSION_DIR_UNREADABLE, Diagnostic.NONE);
    }
    throw DetailRefusal.notFound();
  }

  // ---- the sources the head does not carry -------------------------------------------------------------------------------------------

  /** The Work Package files of the Mission (rows M4a, M5, M6, M10, M13): the index writes its own skip and duplicate diagnostics. */
  private WorkPackageIndex.Result indexOf(MissionRef ref, String mid8) {
    try {
      return index.build(ref, mid8, Optional.empty(), diagnostics);
    } catch (WorkPackageIndexFault fault) {
      throw refuse(DiagnosticCode.SOURCE_UNREADABLE, mid8);
    } catch (TextFault fault) {
      throw textFault(fault, mid8);
    }
  }

  /**
   * Which of the three planning files is a regular file of the primary directory. An {@code lstat} that never follows a link: a link is no
   * artifact and writes one {@code path_refused} (a recorded, stricter divergence from the oracle, V1). A stat that fails for any reason other
   * than "absent" refuses (row M8, V2); the oracle would call that pending.
   */
  private Set<PhaseName> artifactsOf(MissionRef ref, String mid8) {
    Set<PhaseName> present = EnumSet.noneOf(PhaseName.class);
    for (Map.Entry<PhaseName, String> planning : PLANNING_FILES.entrySet()) {
      EntryStat stat;
      try {
        stat = text.stat(new FileRef.MissionFile(ref, RelativePath.of(planning.getValue())), ReadScope.AUTHORED);
      } catch (TextFault fault) {
        throw textFault(fault, mid8);
      }
      if (stat instanceof EntryStat.Present entry) {
        if (entry.kind() == EntryStat.EntryKind.FILE) {
          present.add(planning.getKey());
        } else if (entry.kind() == EntryStat.EntryKind.SYMLINK) {
          note(DiagnosticCode.PATH_REFUSED, mid8);
        }
      }
    }
    return present;
  }

  /** A Mission that has gone since the lookup is plainly unknown; every other fault of the text-read port is {@code source_unreadable}. */
  private RuntimeException textFault(TextFault fault, String mid8) {
    return fault.kind() == TextFault.Kind.VANISHED ? DetailRefusal.notFound() : refuse(DiagnosticCode.SOURCE_UNREADABLE, mid8);
  }

  // ---- the Work Package summaries ------------------------------------------------------------------------------------------------------

  /** One summary per Work Package file, in identifier order (plain string order); a Work Package with events and no file is not listed. */
  private List<WorkPackageSummary> summaries(WorkPackageIndex.Result indexed, StatusSnapshot snapshot, String mid8) {
    Projector projector = new Projector(leaks);
    List<WorkPackageSummary> summaries = new ArrayList<>();
    try {
      for (IndexedWorkPackage file : indexed.workPackages()) {
        summaries.add(summary(file, snapshot, projector, mid8));
      }
    } catch (ProjectionError refused) {
      throw refuse(DiagnosticCode.PROJECTION_REFUSED, mid8);
    }
    return summaries;
  }

  private WorkPackageSummary summary(IndexedWorkPackage file, StatusSnapshot snapshot, Projector projector, String mid8) {
    WpMetadata metadata = file.metadata();
    if (metadata.subtasksRefused()) {
      // SK-353 (D-97): subtasks written as mappings have a Python str() this service does not reproduce
      throw refuse(DiagnosticCode.PROJECTION_REFUSED, mid8);
    }
    WpId id = file.id();
    String title = projector.human(metadata.title(), "title");
    if (title == null) {
      throw new ProjectionError("title", ProjectionError.Reason.MISSING);
    }
    List<WpId> dependencies = dependencies(metadata.dependencies(), projector);
    WpState state = snapshot.workPackages().get(id.value());
    Lane lane = state == null || !state.lane().isDisplay() ? null : state.lane();
    Readiness readiness = ReadinessDeriver.derive(dependencies, snapshot.workPackages());
    return new WorkPackageSummary(
        id,
        title,
        projector.human(metadata.phase(), "phaseLabel"),
        lane,
        dependencies,
        readiness,
        ReadinessDeriver.readyToStart(lane, readiness),
        progressOf(snapshot.resolved().get(id.value())),
        state == null ? null : state.lastTransitionAt());
  }

  private static List<WpId> dependencies(List<String> authored, Projector projector) {
    List<WpId> dependencies = new ArrayList<>();
    for (String dependency : authored) {
      String clean = projector.strict(dependency, "dependencies", false, WP_ID);
      dependencies.add(WpId.parse(clean).orElseThrow(() -> new ProjectionError("dependencies", ProjectionError.Reason.NOT_REPRESENTABLE)));
    }
    return dependencies;
  }

  /**
   * Done over total, from the resolved subtask map. A subtask status that is not one of the nine display lanes ({@code genesis} and
   * {@code uninitialized} are carried by the reduction, as Python accepts them) is a projection refusal, never a null (WP05 review N3, D-159 d).
   */
  private static SubtaskProgress progressOf(WpResolved resolved) {
    if (resolved == null) {
      return new SubtaskProgress(0, 0);
    }
    int done = 0;
    for (Lane status : resolved.subtasks().values()) {
      if (!status.isDisplay()) {
        throw new ProjectionError("subtaskProgress", ProjectionError.Reason.NOT_REPRESENTABLE);
      }
      if (status == Lane.DONE) {
        done++;
      }
    }
    return new SubtaskProgress(done, resolved.subtasks().size());
  }

  // ---- diagnostics -----------------------------------------------------------------------------------------------------------------

  private void note(DiagnosticCode code, String mid8) {
    diagnostics.accept(new Diagnostic(code, mid8, null));
  }

  private MissionStatusUnavailable refuse(DiagnosticCode code, String mid8) {
    Diagnostic diagnostic = new Diagnostic(code, mid8, null);
    diagnostics.accept(diagnostic);
    return new MissionStatusUnavailable(diagnostic);
  }
}
