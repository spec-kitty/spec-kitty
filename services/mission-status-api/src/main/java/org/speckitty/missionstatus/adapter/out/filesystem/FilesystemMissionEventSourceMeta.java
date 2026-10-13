package org.speckitty.missionstatus.adapter.out.filesystem;

import java.math.BigInteger;
import java.util.Set;
import org.speckitty.missionstatus.application.query.port.out.exceptions.SourceFault;
import org.speckitty.missionstatus.application.query.port.out.exceptions.SourceFault.Kind;
import org.speckitty.missionstatus.domain.model.MissionId;
import org.speckitty.missionstatus.domain.model.MissionMeta;
import org.speckitty.missionstatus.domain.model.PyText;
import org.speckitty.missionstatus.domain.model.Topology;
import org.speckitty.missionstatus.domain.readmodel.overview.Instants;
import tools.jackson.databind.JsonNode;

/**
 * {@code meta.json} into a {@link MissionMeta}, the way the oracle reads it: {@code load_meta} for the document (strict UTF-8,
 * {@code json.loads}, an object at the top), {@code resolve_mission_identity} for slug, number and type, and
 * {@code build_overview} for the rest. Every way the document cannot be used is the single outcome {@code META_UNPARSEABLE} (row L7),
 * including a member the domain cannot hold (a missing or malformed {@code mission_id}, a missing {@code target_branch} or
 * {@code created_at} or one without a UTC offset, a {@code mission_number} the oracle refuses). Python's differences kept on purpose: an integer
 * {@code mission_number} beyond 31 bits is refused here (the service carries the field as a 32-bit integer by decision, FR-004 of
 * 2026-10-12; the contract's field is a plain integer), and the {@code str()} of a list or
 * an object used as a slug or a friendly name reads as absent.
 */
final class FilesystemMissionEventSourceMeta {

  private static final Set<String> SENTINELS = Set.of("pending", "unassigned", "TBD");

  private FilesystemMissionEventSourceMeta() {}

  /**
   * Reads {@code meta.json}, capped at {@link SafeFiles#SMALL_FILE_MAX} (a real one is a few hundred bytes). An absent file is
   * {@code VANISHED}, a link or non-regular entry {@code PATH_REFUSED}, and an unreadable or oversize file {@code META_UNPARSEABLE} (L7).
   */
  static byte[] read(SafeFiles files, java.nio.file.Path file) {
    return files.readRegular(file, SafeFiles.SMALL_FILE_MAX, Kind.PATH_REFUSED, Kind.META_UNPARSEABLE).orElseThrow(() -> new SourceFault(Kind.VANISHED));
  }

  /** Decodes the bytes of the Mission directory {@code directoryName}'s {@code meta.json}. */
  static MissionMeta decode(byte[] bytes, String directoryName) {
    JsonNode meta = ReadDirResolverJson.object(bytes).orElseThrow(FilesystemMissionEventSourceMeta::unusable);
    try {
      String slug = slug(meta, directoryName);
      return new MissionMeta(
          missionId(meta),
          slug,
          friendlyName(meta),
          displayNumber(meta.get("mission_number")),
          missionType(meta.get("mission_type")),
          requiredText(meta.get("target_branch")),
          topology(meta.get("topology")),
          createdAt(meta.get("created_at")),
          optionalText(meta.get("accepted_at")),
          optionalText(meta.get("merged_at")),
          optionalText(meta.get("discarded_at")),
          ReadDirResolverJson.truthy(meta.get("baseline_merge_commit")));
    } catch (IllegalArgumentException | NullPointerException unusable) {
      throw unusable();
    }
  }

  private static SourceFault unusable() {
    return new SourceFault(Kind.META_UNPARSEABLE);
  }

  private static MissionId missionId(JsonNode meta) {
    JsonNode id = meta.get("mission_id");
    if (id == null || !id.isString()) {
      throw unusable();
    }
    return new MissionId(id.stringValue());
  }

  /** {@code safe_mission_slug(str(mission_slug or slug), directory name)}: a slug that is not one safe segment reads as the directory name. */
  private static String slug(JsonNode meta, String directoryName) {
    JsonNode chosen = ReadDirResolverJson.truthy(meta.get("mission_slug")) ? meta.get("mission_slug") : meta.get("slug");
    String candidate = ReadDirResolverJson.truthy(chosen) ? pyStr(chosen) : null;
    return candidate != null && isSafeSlug(candidate) ? candidate : directoryName;
  }

  /** {@code assert_safe_path_segment}: ASCII alphanumeric first, then alphanumerics, dot, underscore or hyphen, and no {@code ..}. */
  static boolean isSafeSlug(String value) {
    if (value.isEmpty() || value.contains("..")) {
      return false;
    }
    for (int i = 0; i < value.length(); i++) {
      char c = value.charAt(i);
      boolean alphanumeric = (c >= 'a' && c <= 'z') || (c >= 'A' && c <= 'Z') || (c >= '0' && c <= '9');
      if (!(alphanumeric || (i > 0 && (c == '.' || c == '_' || c == '-')))) {
        return false;
      }
    }
    return true;
  }

  /** {@code str(meta.get("friendly_name") or "")}: the text as stored; the strip and the slug fallback are the deriver's. */
  private static String friendlyName(JsonNode meta) {
    JsonNode name = meta.get("friendly_name");
    return ReadDirResolverJson.truthy(name) ? pyStr(name) : null;
  }

  /** {@code _coerce_mission_number}: null or empty reads as absent; an integer or a digit string is the number; anything else is refused. */
  private static Integer displayNumber(JsonNode raw) {
    if (raw == null || raw.isNull()) {
      return null;
    }
    if (raw.isIntegralNumber()) {
      BigInteger value = raw.bigIntegerValue();
      if (value.bitLength() > 31) {
        throw unusable();
      }
      return value.intValue();
    }
    if (!raw.isString()) {
      throw unusable();
    }
    String stripped = PyText.strip(raw.stringValue());
    if (stripped.isEmpty()) {
      return null;
    }
    if (SENTINELS.contains(stripped)) {
      throw unusable();
    }
    String withoutZeros = stripLeadingZeros(stripped);
    if (withoutZeros.isEmpty()) {
      return 0;
    }
    Integer parsed = FilesystemMissionEventSourceProject.pyInt(withoutZeros);
    if (parsed == null) {
      throw unusable();
    }
    return parsed;
  }

  private static String stripLeadingZeros(String text) {
    int start = 0;
    while (start < text.length() && text.charAt(start) == '0') {
      start++;
    }
    return text.substring(start);
  }

  /** {@code read_mission_type}: a stripped, non-blank string, else typeless. */
  private static String missionType(JsonNode raw) {
    if (raw == null || !raw.isString()) {
      return null;
    }
    String stripped = PyText.strip(raw.stringValue());
    return stripped.isEmpty() ? null : stripped;
  }

  /** {@code topology_of}: a stored string that names one of the four shapes, else unknown. */
  private static Topology topology(JsonNode raw) {
    return raw != null && raw.isString() ? Topology.fromStored(raw.stringValue()) : Topology.UNKNOWN;
  }

  /** {@code _optional_text}: a non-empty string, else absent. */
  private static String optionalText(JsonNode raw) {
    return raw != null && raw.isString() && !raw.stringValue().isEmpty() ? raw.stringValue() : null;
  }

  /** {@code created_at} is served, so it needs an offset (RFC 3339): one without is refused like a missing one (FR-004 ruling, 2026-10-13). */
  private static String createdAt(JsonNode raw) {
    String text = requiredText(optionalText(raw));
    if (!Instants.hasOffset(text)) {
      throw unusable();
    }
    return text;
  }

  private static String requiredText(JsonNode raw) {
    if (raw == null || !raw.isString()) {
      throw unusable();
    }
    return raw.stringValue();
  }

  private static String requiredText(String text) {
    if (text == null) {
      throw unusable();
    }
    return text;
  }

  /** Python's {@code str()} of a scalar; null for a list or an object. */
  private static String pyStr(JsonNode value) {
    if (value.isString()) {
      return value.stringValue();
    }
    if (value.isBoolean()) {
      return value.booleanValue() ? "True" : "False";
    }
    return value.isNumber() ? value.asString() : null;
  }
}
