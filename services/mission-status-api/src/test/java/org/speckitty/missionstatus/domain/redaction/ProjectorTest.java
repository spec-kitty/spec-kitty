package org.speckitty.missionstatus.domain.redaction;

import static org.assertj.core.api.Assertions.assertThat;
import static org.assertj.core.api.Assertions.assertThatThrownBy;

import java.util.List;
import java.util.regex.Pattern;
import org.junit.jupiter.api.Test;

/**
 * Plain unit tests of the projector; no Spring context. Every expected value below is what live Python gave for the same input
 * through {@code Projector.strict} / {@code Projector.human} in {@code tests/contract/_mission_status_payloads.py}.
 */
class ProjectorTest {

  private static final Pattern MISSION_ID = Pattern.compile("^[0-9A-HJKMNP-TV-Z]{26}$");

  private final Projector projector = new Projector(InlineLeakClasses.python());

  // ---- human fields ----------------------------------------------------------------------------------------------------

  @Test
  void aFriendlyNameWithAHostPathAndAnEmailIsServedWithBothTokens() {
    assertThat(projector.human("Fix /home/alice/dev/x now, mail bob@example.com", "friendlyName")).isEqualTo("Fix [path] now, mail [email]");
    assertThat(projector.redactions())
        .containsExactly(new Projector.Redaction("friendlyName", Projector.Kind.PATH), new Projector.Redaction("friendlyName", Projector.Kind.EMAIL));
  }

  @Test
  void aBareTildeAndCleanTextPassThroughAndATemporaryDirectoryIsAPath() {
    assertThat(projector.human("see ~/notes and /tmp/build/out.txt", "title")).isEqualTo("see ~/notes and [path]");
    assertThat(projector.human("clean text", "title")).isEqualTo("clean text");
    assertThat(projector.human("", "title")).isEmpty();
    assertThat(projector.human("/tmpx", "title")).isEqualTo("/tmpx");
    assertThat(projector.human("/home/", "title")).isEqualTo("/home/");
  }

  @Test
  void aNullHumanValueStaysNull() {
    assertThat(projector.human(null, "title")).isNull();
    assertThat(projector.redactions()).isEmpty();
  }

  @Test
  void everyHumanHostPathPatternRedactsItsOwnShape() {
    assertThat(projector.human("C:\\Users\\alice\\x.txt here", "t")).isEqualTo("[path] here");
    assertThat(projector.human("root: /root/secret/file ok", "t")).isEqualTo("root: [path] ok");
    assertThat(projector.human("/var/tmp/z y", "t")).isEqualTo("[path] y");
    assertThat(projector.human("a /home/bob", "t")).isEqualTo("a [path]");
  }

  @Test
  void aPathNeedsAnAnchorBeforeItsFirstSlash() {
    assertThat(projector.human("x/home/x", "t")).isEqualTo("x/home/x");
  }

  @Test
  void theWordClassIsUnicodeAwareLikePythonsStrPatterns() {
    // Python: the lookbehind (?<![\w.~-]) sees an e-acute as a word character, so no path starts here. java.util.regex needs
    // UNICODE_CHARACTER_CLASS to agree.
    assertThat(projector.human("\u00e9/home/x", "t")).isEqualTo("\u00e9/home/x");
    assertThat(projector.human("\u00e9@x.org", "t")).isEqualTo("\u00e9@x.org");
  }

  @Test
  void aCombiningMarkAJoinerOrAConnectorBeforeAPathOrAnAddressDoesNotHideIt() {
    // Python's \w is str.isalnum() or an underscore: a combining mark, a zero-width joiner and a tie are not word characters, so the
    // lookbehind lets the path or the address start right after them. java.util.regex with UNICODE_CHARACTER_CLASS reads them as word
    // characters and served the text unredacted.
    for (String joiner : List.of("\u0301", "\u200d", "\u203f")) {
      assertThat(projector.human("a" + joiner + "/home/x", "t")).as("path after U+" + Integer.toHexString(joiner.charAt(0))).isEqualTo("a" + joiner + "[path]");
      assertThat(projector.human("x" + joiner + "user@localhost", "t")).as("address after U+" + Integer.toHexString(joiner.charAt(0))).isEqualTo("x" + joiner + "[email]");
    }
    // U+001C to U+001F are whitespace in Python, so the rest of the token stops there.
    assertThat(projector.human("/home/alice\u001ftail", "t")).isEqualTo("[path]\u001ftail");
  }

  @Test
  void everyEmailInATextIsReplacedIncludingADotlessHostAndTwoInARow() {
    assertThat(projector.human("two a@b.org,c@d.net", "t")).isEqualTo("two [email],[email]");
    assertThat(projector.human("a@b.c", "t")).isEqualTo("[email]");
    assertThat(projector.human("user@localhost and a@b.comc@d.org", "t")).isEqualTo("[email] and [email]@d.org");
  }

  @Test
  void textThatLooksLikeARefAndNotAnAddressIsLeftAlone() {
    assertThat(projector.human("name@build1 owner/repo@ref HEAD@{1} @scope/pkg", "t")).isEqualTo("name@build1 owner/repo@ref HEAD@{1} @scope/pkg");
  }

  @Test
  void aSecretInAHumanTextCannotBeRedactedAndIsRefusedWithoutItsValue() {
    String leaked = "token " + InlineLeakClasses.fakeGithubToken() + " leak";
    assertThatThrownBy(() -> projector.human(leaked, "title"))
        .isInstanceOfSatisfying(
            ProjectionError.class,
            error -> {
              assertThat(error.fieldName()).isEqualTo("title");
              assertThat(error.reason()).isEqualTo(ProjectionError.Reason.LEAK_REMAINS);
            })
        .hasMessage("title: redaction left a leak in a human text field")
        .message()
        .doesNotContain(InlineLeakClasses.fakeGithubToken());
    assertThatThrownBy(() -> projector.human("key " + InlineLeakClasses.fakeAwsKeyId() + " x", "title")).isInstanceOf(ProjectionError.class);
  }

  // ---- strict fields ---------------------------------------------------------------------------------------------------

  @Test
  void aCleanStrictValueIsServedAsItIs() {
    assertThat(projector.strict("feature/x", "targetBranch", false)).isEqualTo("feature/x");
    assertThat(projector.strict("fine-1.0", "slug", true)).isEqualTo("fine-1.0");
    assertThat(projector.strict("a b", "slug", true)).isEqualTo("a b");
    assertThat(projector.redactions()).isEmpty();
  }

  @Test
  void aNullableStrictFieldHoldingAPathShapedValueIsNulledAndRecorded() {
    for (String pathShaped : List.of("/abs", "~/x", "C:\\x", "C:/x", "a/home/bob/x", "home/bob/x", "/home/bob/", "C:\\Users\\bob\\", "\u00e9/home/b/c/")) {
      assertThat(projector.strict(pathShaped, "missionType", true)).as(pathShaped).isNull();
    }
    assertThat(projector.redactions()).hasSize(9).allSatisfy(redaction -> assertThat(redaction).isEqualTo(new Projector.Redaction("missionType", Projector.Kind.NULLED)));
  }

  @Test
  void aNullableStrictFieldHoldingAnEmailOrASecretOrNothingIsNulled() {
    assertThat(projector.strict("x@y.org", "f", true)).isNull();
    assertThat(projector.strict(InlineLeakClasses.fakeGithubToken(), "f", true)).isNull();
    assertThat(projector.strict("", "f", true)).isNull();
  }

  @Test
  void aNullStrictValueIsNullWhenNullableAndRecordedNowhere() {
    assertThat(projector.strict(null, "f", true)).isNull();
    assertThat(projector.redactions()).isEmpty();
  }

  @Test
  void aNonNullableStrictFieldWithATokenShapedValueIsRefusedAndTheMessageHasNoValue() {
    String token = InlineLeakClasses.fakeGithubToken();
    assertThatThrownBy(() -> projector.strict(token, "targetBranch", false))
        .isInstanceOfSatisfying(
            ProjectionError.class,
            error -> {
              assertThat(error.fieldName()).isEqualTo("targetBranch");
              assertThat(error.reason()).isEqualTo(ProjectionError.Reason.NOT_REPRESENTABLE);
            })
        .hasMessage("targetBranch: a strict field holds a value that is not representable")
        .message()
        .doesNotContain(token);
  }

  @Test
  void everyOtherNonRepresentableStrictValueIsRefusedWhenNotNullable() {
    for (String value : List.of("/abs", "~/x", "C:\\x", "a/home/bob/x", "x@y.org", "", "/home/bob/")) {
      assertThatThrownBy(() -> projector.strict(value, "slug", false)).as(value).isInstanceOf(ProjectionError.class);
    }
  }

  @Test
  void aMissingNonNullableStrictFieldIsRefusedAsMissing() {
    assertThatThrownBy(() -> projector.strict(null, "missionId", false))
        .isInstanceOfSatisfying(ProjectionError.class, error -> assertThat(error.reason()).isEqualTo(ProjectionError.Reason.MISSING))
        .hasMessage("missionId: a required strict field is missing");
  }

  @Test
  void aStrictValueMustMatchItsPatternFromTheStartLikePythonsMatch() {
    String ulid = "01HXYZ0000000000000000000A";
    assertThat(projector.strict(ulid, "missionId", false, MISSION_ID)).isEqualTo(ulid);
    assertThat(projector.strict("not-a-ulid", "missionId", true, MISSION_ID)).isNull();
    assertThatThrownBy(() -> projector.strict("not-a-ulid", "missionId", false, MISSION_ID)).isInstanceOf(ProjectionError.class);
    // Python's re.match anchors at the start only: an unanchored pattern accepts a prefix match.
    assertThat(projector.strict("abc-tail", "slug", false, Pattern.compile("abc"))).isEqualTo("abc-tail");
  }
}
