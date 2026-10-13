package org.speckitty.missionstatus.domain.model;

import java.util.Set;

/**
 * Who made a lane transition, as three handles (the contract's {@code Actor}): {@code tool} is the agent or tool, {@code role} the role
 * and {@code profile} the agent profile. The model is not part of an actor.
 *
 * <p>The decode follows {@code specify_cli.status.models.decode_actor} and the contract's reading of it: a stored actor that is a
 * structured record is copied field by field ({@link #Actor(String, String, String)}, model dropped); a plain string becomes the
 * {@code tool} with the other two null and is never split on a colon ({@link #ofText}); any other value is {@link #NONE}. A handle is
 * 1 to 128 characters from {@code A-Z a-z 0-9 . _ : -} (the contract's {@code ActorHandle}, ASCII only, no line ending); a value that
 * does not fit is null, never forwarded and never repaired. The four resolver sentinels that a stored record carries for "nothing was
 * resolved" ({@code __resolved_model_absent__} and its profile, profile-version and provider siblings) fit the shape but are not
 * handles: they are null too, as in the oracle's projection.
 */
public record Actor(String tool, String role, String profile) {

  /** An actor of three null handles: nothing was recorded, or nothing that fits a handle. */
  public static final Actor NONE = new Actor(null, null, null);

  private static final int MAX_HANDLE_LENGTH = 128;

  private static final Set<String> RESOLVER_SENTINELS =
      Set.of("__resolved_model_absent__", "__resolved_profile_absent__", "__resolved_profile_version_absent__", "__resolved_provider_absent__");

  public Actor {
    tool = handle(tool);
    role = handle(role);
    profile = handle(profile);
  }

  /** A plain string actor: the {@code tool}, with {@code role} and {@code profile} null. */
  public static Actor ofText(String text) {
    return new Actor(text, null, null);
  }

  private static String handle(String value) {
    if (value == null || value.isEmpty() || value.length() > MAX_HANDLE_LENGTH || RESOLVER_SENTINELS.contains(value)) {
      return null;
    }
    for (int i = 0; i < value.length(); i++) {
      if (!isHandleCharacter(value.charAt(i))) {
        return null;
      }
    }
    return value;
  }

  private static boolean isHandleCharacter(char c) {
    return (c >= 'a' && c <= 'z') || (c >= 'A' && c <= 'Z') || (c >= '0' && c <= '9') || c == '.' || c == '_' || c == ':' || c == '-';
  }
}
