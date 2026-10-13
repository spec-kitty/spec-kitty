package org.speckitty.missionstatus.application.query.port.in.dto;

/** A page of the Mission list: the requested size (null for the default; clamped, never refused) and the cursor of the last page. */
public record PageRequest(Integer pageSize, String pageCursor) {}
