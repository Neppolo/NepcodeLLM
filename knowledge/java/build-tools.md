# Maven and Gradle

## Maven
- Pin plugin versions; set `maven.compiler.release` (not `source`/`target`).
- Manage versions with `<dependencyManagement>` and BOMs (`spring-boot-dependencies`, `junit-bom`, `testcontainers-bom`).
- Use the Maven Wrapper (`mvnw`) so builds are reproducible.
- Enforce rules with `maven-enforcer-plugin` (dependency convergence, banned dependencies, Java version).

## Gradle
- Use the Kotlin DSL (`build.gradle.kts`) and version catalogs (`gradle/libs.versions.toml`).
- Configure Java toolchains (`java { toolchain { languageVersion = JavaLanguageVersion.of(21) } }`).
- Enable the configuration cache and build cache; commit the Gradle Wrapper.
- Use `implementation` over `api` unless the dependency is part of the module's public API.

## Both
- Keep the dependency tree small; remove unused dependencies (`mvn dependency:analyze`).
- Run formatting (Spotless with google-java-format or palantir-java-format) and static analysis (Error Prone, SpotBugs, Checkstyle/PMD) in CI.
