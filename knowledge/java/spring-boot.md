# Spring Boot best practices (Spring Boot 3.x / 4.x, Spring Framework 6.x / 7.x)

Spring Boot 4 / Spring Framework 7 (Nov 2025) require Java 17+ and Jakarta EE 11. Verify the project's version
with web_search before recommending version-specific APIs: they change between minor releases.

## Dependency injection
- Use **constructor injection** with `final` fields; with a single constructor no `@Autowired` is needed.
- Avoid field injection: it hides dependencies and makes tests harder.
- Keep beans stateless; do not keep request data in singleton fields.

## Configuration
- Bind settings with `@ConfigurationProperties` on a record, validated with `@Validated` + Jakarta constraints, instead of scattering `@Value`.
- Never commit secrets; use environment variables, a vault, or a cloud secret manager.
- Use profiles for environment differences, not `if` statements in code.

## Web layer
- Controllers stay thin: validate input (`@Valid`), call a service, map to a response DTO. Never expose JPA entities directly.
- Centralize error handling with `@RestControllerAdvice` returning RFC 9457 `ProblemDetail` (`spring.mvc.problemdetails.enabled=true`).
- Use `RestClient` (sync) or `WebClient` (reactive) for outbound HTTP; `RestTemplate` is in maintenance mode.
- Declarative HTTP interfaces (`@HttpExchange`) remove client boilerplate.

## Persistence (Spring Data JPA / Hibernate)
- Put `@Transactional` on service methods, not controllers or repositories; use `readOnly = true` for queries.
- Default associations to `LAZY`; fix N+1 queries with `JOIN FETCH`, `@EntityGraph`, or DTO projections.
- Keep `spring.jpa.open-in-view=false`.
- Manage schema with Flyway or Liquibase; never `ddl-auto=update` in production.
- Paginate unbounded queries (`Pageable`), and prefer projections for read-only views.

## Observability
- Use Actuator with only needed endpoints exposed; secure them.
- Use Micrometer for metrics and Micrometer Tracing / OpenTelemetry for traces.
- Log with SLF4J placeholders (`log.info("x={}", x)`), never string concatenation; never log secrets or personal data.

## Testing
- Unit test services with plain JUnit 5 + Mockito, no Spring context.
- Use slice tests (`@WebMvcTest`, `@DataJpaTest`) for layers and `@SpringBootTest` sparingly.
- Use Testcontainers (with `@ServiceConnection`) for real databases and brokers instead of H2 fakes.
