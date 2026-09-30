# Java testing best practices

## JUnit 5 (Jupiter)
- One behavior per test; name tests after the behavior (`returnsEmptyWhenUserUnknown`), or use `@DisplayName`.
- Arrange / Act / Assert structure; no logic (loops, ifs) in tests.
- Use `@ParameterizedTest` with `@CsvSource` / `@MethodSource` for input variations.
- Use AssertJ for fluent, readable assertions (`assertThat(list).extracting(User::name).containsExactly(...)`).
- `assertThrows` returns the exception: assert on its message or fields.

## Mocking (Mockito)
- Mock only what you do not own at boundaries (HTTP clients, clocks, repositories in unit tests); do not mock value objects.
- Prefer `@ExtendWith(MockitoExtension.class)` with strict stubs to catch unused stubbing.
- Inject a `java.time.Clock` instead of calling `Instant.now()` directly, so time is testable.

## Integration tests
- Use Testcontainers for databases, Kafka, Redis; reuse containers across a test class.
- Keep tests independent: each test sets up its own data and does not rely on execution order.

## Coverage and quality
- Coverage (JaCoCo) is a signal, not a goal; focus on branches with business logic.
- Mutation testing (PIT) reveals tests that execute code without checking it.
