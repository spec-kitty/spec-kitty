package org.speckitty.missionstatus.domain.readmodel.reducer;

import java.util.Comparator;
import org.speckitty.missionstatus.domain.model.StatusEvent;

/** The order in which the fold applies events. It is a constructor argument of the reducer so a test can inject a wrong one. */
public interface EventOrdering extends Comparator<StatusEvent> {}
