package org.speckitty.missionstatus.testsupport;

import java.util.List;
import org.speckitty.missionstatus.application.query.port.in.MissionStatusQuery;
import org.speckitty.missionstatus.domain.model.Diagnostic;

/** What a port-level class sees of a realised fixture: the inbound port and the diagnostics the service wrote. */
public interface Fixture {

  MissionStatusQuery query();

  List<Diagnostic> diagnostics();
}
