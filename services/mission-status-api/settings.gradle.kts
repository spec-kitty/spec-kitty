// Standalone build: deliberately NOT included in contracts/settings.gradle (separate dependency set, separate verification
// metadata). No toolchain resolver plugin (no implicit JDK download; see gradle.properties). Dependencies come from Maven Central
// and the Gradle plugin portal only.
pluginManagement {
    repositories {
        gradlePluginPortal()
        mavenCentral()
    }
}

dependencyResolutionManagement {
    repositoriesMode.set(RepositoriesMode.FAIL_ON_PROJECT_REPOS)
    repositories {
        mavenCentral()
    }
}

rootProject.name = "mission-status-api"

// The four modules of #6117 decision 12. The root project is the query-service deployable (the read API); the two libraries below
// were extracted from it by #6192 and hold no framework. command-cli, the write-service deployable, is a later child of #6117.
//   domain-model: the shared Mission status types (framework-free, no IO);
//   event-log:    the status.events.jsonl line decoder, its byte rules, and the event ordering and fold (depends on domain-model).
include("domain-model", "event-log")
