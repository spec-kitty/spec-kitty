package org.speckitty.missionstatus.domain.readmodel.overview;

import java.util.List;

/**
 * One page of overviews: the items in contract order, the cursor of the next page (null when none), the Mission count of the same
 * enumeration and the page size applied. It carries no diagnostics.
 */
public record MissionPage(List<MissionOverview> items, String nextPageCursor, int missionCount, int pageSize) {}
