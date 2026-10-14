package org.speckitty.missionstatus.application.query;

import java.util.Objects;
import java.util.function.Consumer;
import org.speckitty.missionstatus.application.query.port.in.exceptions.DetailRefusal;
import org.speckitty.missionstatus.application.query.port.in.exceptions.MissionStatusUnavailable;
import org.speckitty.missionstatus.application.query.port.out.exceptions.SourceFault;
import org.speckitty.missionstatus.domain.model.Diagnostic;
import org.speckitty.missionstatus.domain.model.DiagnosticCode;
import org.speckitty.missionstatus.domain.model.MissionId;

/** The Mission lookup the Mission-scoped detail routes share: the id to its {@link MissionLookup.Found}, or the route's refusal. */
final class MissionLocator {

  private final MissionReadModel model;
  private final Consumer<Diagnostic> diagnostics;

  MissionLocator(MissionReadModel model, Consumer<Diagnostic> diagnostics) {
    this.model = Objects.requireNonNull(model, "model");
    this.diagnostics = Objects.requireNonNull(diagnostics, "diagnostics");
  }

  /**
   * The Mission that holds the id, with the duplicate continuation. A readable Mission that holds the id wins over any faulted sibling (D-39);
   * with no match the first fault in byte order decides: a refused directory is a 404 with {@code path_refused}, an unusable
   * {@code meta.json} and an unreadable directory are 500s.
   */
  MissionLookup.Found locate(MissionId id) {
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

  private void note(DiagnosticCode code, String mid8) {
    diagnostics.accept(new Diagnostic(code, mid8, null));
  }

  private MissionStatusUnavailable refuse(DiagnosticCode code, String mid8) {
    Diagnostic diagnostic = new Diagnostic(code, mid8, null);
    diagnostics.accept(diagnostic);
    return new MissionStatusUnavailable(diagnostic);
  }
}
