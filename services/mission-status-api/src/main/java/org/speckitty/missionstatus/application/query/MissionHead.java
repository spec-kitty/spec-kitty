package org.speckitty.missionstatus.application.query;

import org.speckitty.missionstatus.domain.readmodel.overview.MissionOverview;

/**
 * The head of a Mission: the projected overview and the cache entry (the whole status snapshot with its per-Work-Package state, and the
 * stream cursor) it was derived from. Obtained only through {@link OverviewReader#head}.
 */
record MissionHead(MissionOverview overview, ProjectionCache.Entry entry) {}
