package org.speckitty.missionstatus.application.query.port.out.dto;

/**
 * The closed set of seven refusal kinds of plan section 7.2 that mission #5533 imports. {@link TextRefusals#of} maps every outcome that
 * can refuse to exactly one of them. Over-cap and an I/O failure are distinct kinds (D-68).
 */
public enum TextRefusal {
  /** Nothing at the path (absent, or the file or the Mission directory vanished). */
  NOT_FOUND,
  /** A directory or another non-file. */
  NOT_REGULAR,
  /** A link in any component, a reparse point or a path outside the root. */
  PATH_REFUSED,
  /** More than the cap was read, or the open handle was already larger. */
  OVER_CAP,
  /** Invalid strict UTF-8 or a NUL byte. */
  NOT_TEXT,
  /** A credential pattern in the decoded text. */
  SECRET_REFUSED,
  /** The operating system refused or failed. */
  IO_FAILURE
}
