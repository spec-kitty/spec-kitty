package org.speckitty.missionstatus.adapter.out.filesystem.codec;

import java.util.List;

/**
 * One row per shape of the {@code actor} member, with the answer of the real oracle: the served projection
 * {@code Projector.actor} of {@code tests/contract/_mission_status_payloads.py}, run on the parsed value (a record is copied field by
 * field and the model is dropped, a string becomes {@code tool}, anything else is no actor; a handle is null unless it matches
 * {@code ^[A-Za-z0-9._:-]{1,128}$} and is none of the four resolver sentinels). {@code specify_cli.status.models.decode_actor} runs
 * first as the row-validity gate: where it raises {@code ValueError} the answer is {@code raise}.
 * {@code expected} is {@code tool|role|profile} with an empty part for null. Generated once from the oracle run.
 */
final class ActorOracleCases {

  /** The JSON text of the actor member, and the oracle answer for it. */
  record Case(String name, String actorJson, String expected) {}

  private ActorOracleCases() {}

  static List<Case> all() {
    return List.of(
        new Case("string-plain", "\"claude\"", "claude||"),
        new Case("string-colon-joined", "\"claude:opus-4.1_x\"", "claude:opus-4.1_x||"),
        new Case("string-migration", "\"migration:backfill_runtime_state\"", "migration:backfill_runtime_state||"),
        new Case("string-empty", "\"\"", "||"),
        new Case("string-space", "\" \"", "||"),
        new Case("string-inner-space", "\"a b\"", "||"),
        new Case("string-email", "\"user@example.com\"", "||"),
        new Case("string-path", "\"a/b\"", "||"),
        new Case("string-128", "\"xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx\"", "xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx||"),
        new Case("string-129", "\"xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx\"", "||"),
        new Case("string-non-ascii", "\"caf\u00e9\"", "||"),
        new Case("string-trailing-newline", "\"claude\\n\"", "claude\n||"),
        new Case("string-punctuation-only", "\"-.:_\"", "-.:_||"),
        new Case("string-None-text", "\"None\"", "None||"),
        new Case("null", "null", "||"),
        new Case("true", "true", "||"),
        new Case("false", "false", "||"),
        new Case("int", "5", "||"),
        new Case("int-negative", "-3", "||"),
        new Case("int-big", "123456789012345678901234567890", "||"),
        new Case("float", "1.5", "||"),
        new Case("float-small", "1e-07", "||"),
        new Case("float-1e-4", "0.0001", "||"),
        new Case("float-1e-5", "0.00001", "||"),
        new Case("float-1e15", "1e15", "||"),
        new Case("float-1e16", "1e16", "||"),
        new Case("float-1e22", "1e22", "||"),
        new Case("float-integral", "100.0", "||"),
        new Case("float-zero", "0.0", "||"),
        new Case("float-negative-zero", "-0.0", "||"),
        new Case("float-long", "123456789.123456789", "||"),
        new Case("float-NaN", "NaN", "||"),
        new Case("float-Infinity", "Infinity", "||"),
        new Case("float-minus-Infinity", "-Infinity", "||"),
        new Case("float-1e999", "1e999", "||"),
        new Case("sentinel-string-model", "\"__resolved_model_absent__\"", "||"),
        new Case("sentinel-string-profile", "\"__resolved_profile_absent__\"", "||"),
        new Case("sentinel-string-profile-version", "\"__resolved_profile_version_absent__\"", "||"),
        new Case("sentinel-string-provider", "\"__resolved_provider_absent__\"", "||"),
        new Case("sentinel-record-profile", "{\"role\": \"implementer\", \"profile\": \"__resolved_profile_absent__\", \"tool\": \"claude\", \"model\": \"__resolved_model_absent__\"}", "claude|implementer|"),
        new Case("sentinel-record-tool", "{\"role\": \"implementer\", \"profile\": \"java-jenny\", \"tool\": \"__resolved_provider_absent__\", \"model\": null}", "|implementer|java-jenny"),
        new Case("sentinel-record-role", "{\"role\": \"__resolved_profile_version_absent__\", \"profile\": \"java-jenny\", \"tool\": \"claude\", \"model\": null}", "claude||java-jenny"),
        new Case("sentinel-record-all", "{\"role\": \"__resolved_profile_absent__\", \"profile\": \"__resolved_provider_absent__\", \"tool\": \"__resolved_model_absent__\", \"model\": null}", "||"),
        new Case("sentinel-lookalike-string", "\"__resolved_model_absent\"", "__resolved_model_absent||"),
        new Case("list-empty", "[]", "||"),
        new Case("list-one", "[1]", "||"),
        new Case("structured-all", "{\"role\": \"implementer\", \"profile\": \"java-jenny\", \"tool\": \"claude\", \"model\": \"opus\"}", "claude|implementer|java-jenny"),
        new Case("structured-no-model", "{\"role\": \"r\", \"profile\": \"p\", \"tool\": \"t\", \"model\": null}", "t|r|p"),
        new Case("structured-all-null", "{\"role\": null, \"profile\": null, \"tool\": null, \"model\": null}", "||"),
        new Case("structured-tool-only", "{\"role\": null, \"profile\": null, \"tool\": \"claude\", \"model\": null}", "claude||"),
        new Case("structured-email-tool", "{\"role\": \"r\", \"profile\": \"p\", \"tool\": \"a@b.c\", \"model\": null}", "|r|p"),
        new Case("structured-space-role", "{\"role\": \"a b\", \"profile\": \"p\", \"tool\": \"t\", \"model\": null}", "t||p"),
        new Case("structured-empty-profile", "{\"role\": \"r\", \"profile\": \"\", \"tool\": \"t\", \"model\": null}", "t|r|"),
        new Case("structured-128-tool", "{\"role\": null, \"profile\": null, \"tool\": \"xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx\", \"model\": null}", "xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx||"),
        new Case("structured-129-tool", "{\"role\": null, \"profile\": null, \"tool\": \"xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx\", \"model\": null}", "||"),
        new Case("structured-colon-joined-tool", "{\"role\": null, \"profile\": null, \"tool\": \"claude:opus:implementer\", \"model\": null}", "claude:opus:implementer||"),
        new Case("structured-model-invalid-ignored", "{\"role\": null, \"profile\": null, \"tool\": \"t\", \"model\": \"not a handle@@\"}", "t||"),
        new Case("structured-missing-model", "{\"role\": \"r\", \"profile\": \"p\", \"tool\": \"t\"}", "raise"),
        new Case("structured-extra-key", "{\"role\": \"r\", \"profile\": \"p\", \"tool\": \"t\", \"model\": \"m\", \"x\": 1}", "raise"),
        new Case("structured-empty-object", "{}", "raise"),
        new Case("structured-int-tool", "{\"role\": \"r\", \"profile\": \"p\", \"tool\": 5, \"model\": null}", "raise"),
        new Case("structured-list-role", "{\"role\": [\"r\"], \"profile\": \"p\", \"tool\": \"t\", \"model\": null}", "raise"),
        new Case("structured-bool-model", "{\"role\": \"r\", \"profile\": \"p\", \"tool\": \"t\", \"model\": true}", "raise"));
  }
}
