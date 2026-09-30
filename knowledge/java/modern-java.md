# Modern Java (21 / 25 LTS)

Target the latest LTS the project can use. Java 25 is the current LTS (Sep 2025); Java 21 is the previous one.
Always check the project's `maven.compiler.release` / Gradle toolchain before using newer language features.

## Language features to prefer
- **Records** for immutable data carriers (DTOs, value objects, query results). Validate in the compact constructor.
- **Sealed interfaces + records + pattern matching `switch`** to model closed hierarchies; the compiler checks exhaustiveness, so no `default` branch is needed.
- **Record patterns** (`if (obj instanceof Point(int x, int y))`) instead of manual casts and getters.
- **`var`** for local variables when the type is obvious from the right-hand side; not for fields or public APIs.
- **Text blocks** (`"""`) for SQL, JSON and multi-line strings.
- **Sequenced collections** (`getFirst()`, `getLast()`, `reversed()`) instead of `list.get(0)` / `list.get(list.size() - 1)`.

## Virtual threads (Project Loom)
- Use virtual threads for blocking I/O-bound work: `Executors.newVirtualThreadPerTaskExecutor()`; in Spring Boot 3.2+ set `spring.threads.virtual.enabled=true`.
- Do not pool virtual threads; create one per task.
- Avoid long `synchronized` blocks around blocking I/O on JDK 21-23 (pinning). JDK 24+ (JEP 491) removed most pinning with `synchronized`.
- Limit concurrency to scarce resources with a `Semaphore`, not a small thread pool.
- Virtual threads do not speed up CPU-bound work.

## Null handling and immutability
- Return `Optional<T>` from lookups that may find nothing; never pass `Optional` as a parameter or store it in fields.
- Prefer `List.of`, `Map.of`, `Set.of`, `Stream.toList()` for unmodifiable results.
- Make fields `final` by default; use constructor injection.

## Streams
- Use streams for transformation pipelines; use a plain loop when there are side effects, checked exceptions or early exits.
- Avoid `parallelStream()` unless measured: it uses the common ForkJoinPool and rarely helps in server code.

## Exceptions
- Never swallow exceptions; log with context or rethrow wrapped with a cause.
- Use unchecked domain exceptions for business errors; keep checked exceptions for recoverable, caller-actionable conditions.
- Use try-with-resources for every `AutoCloseable`.
