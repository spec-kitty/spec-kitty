package org.speckitty.missionstatus.application.query;

import java.util.ArrayList;
import java.util.HashMap;
import java.util.List;
import java.util.Map;
import java.util.Objects;
import java.util.Optional;
import java.util.function.Consumer;
import java.util.regex.Pattern;
import org.speckitty.missionstatus.application.query.detail.ArtifactReferenceBuilder;
import org.speckitty.missionstatus.application.query.detail.ReadRefused;
import org.speckitty.missionstatus.application.query.detail.ReviewCycleReader;
import org.speckitty.missionstatus.application.query.detail.TasksMdReader;
import org.speckitty.missionstatus.application.query.detail.WorkspaceReader;
import org.speckitty.missionstatus.application.query.index.IndexedWorkPackage;
import org.speckitty.missionstatus.application.query.index.WorkPackageIndex;
import org.speckitty.missionstatus.application.query.index.WorkPackageIndexFault;
import org.speckitty.missionstatus.application.query.port.in.WorkPackageDetailQuery;
import org.speckitty.missionstatus.application.query.port.in.exceptions.DetailRefusal;
import org.speckitty.missionstatus.application.query.port.in.exceptions.MissionStatusUnavailable;
import org.speckitty.missionstatus.application.query.port.out.FrontmatterDecoder;
import org.speckitty.missionstatus.application.query.port.out.LanesDecoder;
import org.speckitty.missionstatus.application.query.port.out.TextSource;
import org.speckitty.missionstatus.application.query.port.out.dto.MissionRef;
import org.speckitty.missionstatus.application.query.port.out.exceptions.TextFault;
import org.speckitty.missionstatus.domain.model.Diagnostic;
import org.speckitty.missionstatus.domain.model.DiagnosticCode;
import org.speckitty.missionstatus.domain.model.Lane;
import org.speckitty.missionstatus.domain.model.MissionId;
import org.speckitty.missionstatus.domain.model.PyText;
import org.speckitty.missionstatus.domain.model.StatusSnapshot;
import org.speckitty.missionstatus.domain.model.WpId;
import org.speckitty.missionstatus.domain.model.WpMetadata;
import org.speckitty.missionstatus.domain.model.WpResolved;
import org.speckitty.missionstatus.domain.model.WpState;
import org.speckitty.missionstatus.domain.readmodel.derive.OwnedFilePatterns;
import org.speckitty.missionstatus.domain.readmodel.derive.TitleRows;
import org.speckitty.missionstatus.domain.readmodel.detail.DependencyEntry;
import org.speckitty.missionstatus.domain.readmodel.detail.OwnedFileEntry;
import org.speckitty.missionstatus.domain.readmodel.detail.SubtaskEntry;
import org.speckitty.missionstatus.domain.readmodel.detail.WorkPackageDetail;
import org.speckitty.missionstatus.domain.readmodel.detail.WorkspaceView;
import org.speckitty.missionstatus.domain.redaction.LeakClasses;
import org.speckitty.missionstatus.domain.redaction.ProjectionError;
import org.speckitty.missionstatus.domain.redaction.Projector;

/**
 * The application service behind {@link WorkPackageDetailQuery}: the subtasks, dependencies, review cycles, workspace, owned files and artifact
 * references of one Work Package (FR-003, FR-010).
 *
 * <p>The whole call runs inside the {@link AdmissionGate} (FR-022): the route is one of the heavy operations. Its sequence is fixed: the
 * probe-free lookup of the Mission by its id, the duplicate continuation, the one head from {@link MissionReadModel} (the snapshot it carries is
 * the only source of status, so the matched {@code meta.json} is read three times on a warm cache and four on a cold one, as on
 * {@code getMission}), the Work Package index, and then the sources the head does not carry: {@code tasks.md}, the review-cycle directory,
 * {@code lanes.json}, two {@code lstat}s of the lane worktree, and one listing of {@code tasks/}. A Work Package the ledger names and no file
 * holds is not found.
 *
 * <p>Every fault of the failure table that belongs to this route is decided here and reported once through the diagnostics consumer: a
 * {@link DetailRefusal} for an unknown Mission or Work Package, a {@link MissionStatusUnavailable} carrying the diagnostic code for the rest.
 * The adapter answers every one of the latter with the route's one 500 Problem, {@code source_unreadable}. A title that cannot be shown is
 * the exception: the Work Package is served with that member withheld and one {@code projection_refused} diagnostic (row M12).
 */
public final class WorkPackageDetailQueryService implements WorkPackageDetailQuery {

  /** The contract's {@code RelativeReference}: 1 to 256 characters on one line, not a drive letter and not starting with a slash, a backslash or a tilde. */
  private static final Pattern RELATIVE_REFERENCE = Pattern.compile("(?=[^\\n]{1,256}\\z)(?![A-Za-z]:)[^/\\\\~][^\\n]*");

  /** A Work Package identifier as a dependency may be written: checked for leaks first, then typed as a {@link WpId}. */
  private static final Pattern WP_ID = Pattern.compile("WP[0-9]{2,}");

  private final MissionReadModel model;
  private final WorkPackageIndex index;
  private final AdmissionGate gate;
  private final Consumer<Diagnostic> diagnostics;
  private final MissionLocator locator;
  private final LeakClasses leaks;
  private final TasksMdReader tasksMd;
  private final ReviewCycleReader cycles;
  private final WorkspaceReader workspace;
  private final ArtifactReferenceBuilder references;

  /**
   * @param model the read path shared with the other services of the query side: the lookup, the one head derivation and the one cache
   * @param index the shared Work Package index (the one bean of the whole mission)
   * @param text the text-read port
   * @param frontmatter the decoder of a review-cycle file
   * @param lanes the decoder of {@code lanes.json}
   * @param gate the admission gate of the heavy operations (the one bean)
   * @param diagnostics called once per occurrence of a fault
   * @param leaks the host-path, e-mail and secret patterns the projection applies
   */
  public WorkPackageDetailQueryService(
      MissionReadModel model,
      WorkPackageIndex index,
      TextSource text,
      FrontmatterDecoder frontmatter,
      LanesDecoder lanes,
      AdmissionGate gate,
      Consumer<Diagnostic> diagnostics,
      LeakClasses leaks) {
    this.model = Objects.requireNonNull(model, "model");
    this.index = Objects.requireNonNull(index, "index");
    this.gate = Objects.requireNonNull(gate, "gate");
    this.diagnostics = Objects.requireNonNull(diagnostics, "diagnostics");
    this.locator = new MissionLocator(model, diagnostics);
    this.leaks = Objects.requireNonNull(leaks, "leaks");
    Objects.requireNonNull(text, "text");
    this.tasksMd = new TasksMdReader(text);
    this.cycles = new ReviewCycleReader(text, Objects.requireNonNull(frontmatter, "frontmatter"));
    this.workspace = new WorkspaceReader(text, Objects.requireNonNull(lanes, "lanes"));
    this.references = new ArtifactReferenceBuilder(text);
  }

  @Override
  public WorkPackageDetail workPackageDetail(MissionId missionId, WpId wpId) {
    return gate.run(() -> detail(missionId, wpId));
  }

  private WorkPackageDetail detail(MissionId missionId, WpId wpId) {
    MissionLookup.Found found = locator.locate(missionId);
    MissionHead head = model.head(found.ref()).orElseThrow(DetailRefusal::notFound);
    String mid8 = found.mid8();
    WorkPackageIndex.Result indexed = indexOf(found.ref(), mid8);
    IndexedWorkPackage file = indexed.workPackages().stream().filter(candidate -> candidate.id().equals(wpId)).findFirst().orElseThrow(DetailRefusal::notFound);
    if (file.metadata().subtasksRefused()) {
      // SK-353 (D-97): subtasks written as mappings have a Python str() this service does not reproduce
      throw refuse(DiagnosticCode.PROJECTION_REFUSED, mid8);
    }
    try {
      return assemble(found, head.entry().snapshot(), indexed, file);
    } catch (ProjectionError refused) {
      throw refuse(DiagnosticCode.PROJECTION_REFUSED, mid8);
    } catch (ReadRefused unusable) {
      throw refuse(DiagnosticCode.SOURCE_UNREADABLE, mid8);
    } catch (TextFault fault) {
      throw textFault(fault, mid8);
    }
  }

  // ---- the lookup ------------------------------------------------------------------------------------------------------------------

  /** The Work Package files of the Mission (rows M4a, M5, M6, M10, M13): the index writes its own skip and duplicate diagnostics. The route holds no body. */
  private WorkPackageIndex.Result indexOf(MissionRef ref, String mid8) {
    try {
      return index.build(ref, mid8, Optional.empty(), diagnostics);
    } catch (WorkPackageIndexFault fault) {
      throw refuse(DiagnosticCode.SOURCE_UNREADABLE, mid8);
    } catch (TextFault fault) {
      throw textFault(fault, mid8);
    }
  }

  // ---- the detail ------------------------------------------------------------------------------------------------------------------

  private WorkPackageDetail assemble(MissionLookup.Found found, StatusSnapshot snapshot, WorkPackageIndex.Result indexed, IndexedWorkPackage file) {
    MissionRef ref = found.ref();
    String mid8 = found.mid8();
    WpMetadata metadata = file.metadata();
    String wp = file.id().value();
    Projector projector = new Projector(leaks);
    WpResolved resolved = snapshot.resolved().getOrDefault(wp, WpResolved.empty());
    Map<String, String> titles = tasksMd.read(ref).map(text -> TitleRows.titles(text, wp)).orElse(Map.of());

    List<OwnedFileEntry> owned = new ArrayList<>();
    for (String pattern : metadata.ownedFiles()) {
      String clean = projector.strict(pattern, "ownedFiles", false, RELATIVE_REFERENCE);
      owned.add(new OwnedFileEntry(clean, OwnedFilePatterns.isGlob(clean), OwnedFileEntry.ChangeState.UNKNOWN));
    }
    String planning = projector.strict(metadata.planningBaseBranch(), "workspace.planningBranch", true);
    WorkspaceView where = workspace.read(ref, found.meta().slug(), wp, planning);
    List<SubtaskEntry> subtasks = subtasks(metadata.subtasks(), titles, resolved, projector, mid8);
    List<DependencyEntry> dependencies = dependencies(metadata.dependencies(), indexed, snapshot, projector, mid8);
    ArtifactReferenceBuilder.Built pointers = references.build(ref, file.id());
    return new WorkPackageDetail(
        found.meta().missionId(),
        file.id(),
        subtasks,
        dependencies,
        cycles.read(ref, ref.name(), pointers.promptFileName(), resolved.history(), projector),
        where,
        owned,
        pointers.references());
  }

  /**
   * One entry per authored roster id, in authored order. The title is the cleaned row of {@code tasks.md} (a title the projection cannot show is
   * withheld with one {@code projection_refused}); the lane is the resolved subtask lane, null when none is recorded and never {@code planned}.
   * A recorded lane that is not one of the nine display lanes is a projection refusal (WP05 review N3, D-159 d), not a null.
   */
  private List<SubtaskEntry> subtasks(List<String> roster, Map<String, String> titles, WpResolved resolved, Projector projector, String mid8) {
    List<SubtaskEntry> entries = new ArrayList<>();
    for (String authored : roster) {
      String id = projector.strict(authored, "subtasks", false, RELATIVE_REFERENCE);
      String raw = titles.get(authored);
      Lane lane = resolved.subtasks().get(authored);
      if (lane != null && !lane.isDisplay()) {
        throw new ProjectionError("subtasks.statusLane", ProjectionError.Reason.NOT_REPRESENTABLE);
      }
      entries.add(new SubtaskEntry(id, raw == null ? null : humanOrNull(raw, projector, mid8), lane));
    }
    return entries;
  }

  /**
   * One entry per authored dependency, in authored order. The title is the display title of the Work Package it names, else its id; a title the
   * projection cannot show is replaced by the id with one {@code projection_refused}. An id that names no Work Package keeps its id as title and
   * has no lane.
   */
  private List<DependencyEntry> dependencies(List<String> authored, WorkPackageIndex.Result indexed, StatusSnapshot snapshot, Projector projector, String mid8) {
    Map<String, IndexedWorkPackage> known = new HashMap<>();
    indexed.workPackages().forEach(candidate -> known.put(candidate.id().value(), candidate));
    List<DependencyEntry> entries = new ArrayList<>();
    for (String dependency : authored) {
      String clean = projector.strict(dependency, "dependencies", false, WP_ID);
      WpId id = WpId.parse(clean).orElseThrow(() -> new ProjectionError("dependencies", ProjectionError.Reason.NOT_REPRESENTABLE));
      WpState state = snapshot.workPackages().get(clean);
      Lane lane = state == null || !state.lane().isDisplay() ? null : state.lane();
      entries.add(new DependencyEntry(id, dependencyTitle(known.get(clean), clean, projector, mid8), lane));
    }
    return entries;
  }

  private String dependencyTitle(IndexedWorkPackage known, String id, Projector projector, String mid8) {
    if (known == null) {
      return id;
    }
    String title = known.metadata().title();
    String shown = PyText.strip(title != null ? title : known.metadata().workPackageId());
    if (shown.isEmpty()) {
      return id;
    }
    String clean = humanOrNull(shown, projector, mid8);
    return clean == null || clean.isEmpty() ? id : clean;
  }

  /**
   * A human text: withheld (null, with one {@code projection_refused}) when it holds a credential or a leak the substitution cannot remove,
   * otherwise with each host path and e-mail address replaced. The credential is looked for in the text as stored, before any replacement.
   */
  private String humanOrNull(String value, Projector projector, String mid8) {
    if (leaks.credential(value)) {
      note(DiagnosticCode.PROJECTION_REFUSED, mid8);
      return null;
    }
    try {
      return projector.human(value, "title");
    } catch (ProjectionError unremovable) {
      note(DiagnosticCode.PROJECTION_REFUSED, mid8);
      return null;
    }
  }

  // ---- faults ----------------------------------------------------------------------------------------------------------------------

  /** A Mission that has gone since the lookup is plainly unknown; every other fault of the text-read port is {@code source_unreadable}. */
  private RuntimeException textFault(TextFault fault, String mid8) {
    return fault.kind() == TextFault.Kind.VANISHED ? DetailRefusal.notFound() : refuse(DiagnosticCode.SOURCE_UNREADABLE, mid8);
  }

  private void note(DiagnosticCode code, String mid8) {
    diagnostics.accept(new Diagnostic(code, mid8, null));
  }

  private MissionStatusUnavailable refuse(DiagnosticCode code, String mid8) {
    Diagnostic diagnostic = new Diagnostic(code, mid8, null);
    diagnostics.accept(diagnostic);
    return new MissionStatusUnavailable(diagnostic);
  }
}
