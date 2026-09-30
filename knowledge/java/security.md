# Java / Spring security checklist

## Input and injection
- Always use parameterized queries (JPA parameters, `JdbcClient` / `JdbcTemplate` placeholders); never build SQL with string concatenation.
- Validate all external input with Jakarta Bean Validation at the boundary.
- Never deserialize untrusted data with Java native serialization (`ObjectInputStream`). For Jackson, never enable default typing on untrusted input.
- Guard XML parsers against XXE: disable DTDs and external entities.
- Sanitize file paths from user input (`Path.normalize()` + check prefix) to prevent path traversal.

## Spring Security
- Configure with a `SecurityFilterChain` bean (the `WebSecurityConfigurerAdapter` class was removed).
- Deny by default: `anyRequest().authenticated()` last; open only what must be public.
- Keep CSRF protection for browser session-based apps; it can be disabled only for stateless token APIs.
- Hash passwords with `PasswordEncoderFactories.createDelegatingPasswordEncoder()` (bcrypt/argon2), never plain SHA/MD5.
- Use method security (`@PreAuthorize`) for fine-grained authorization, with `@EnableMethodSecurity`.

## Secrets and dependencies
- No secrets in code, `application.yml` in git, or logs.
- Scan dependencies (OWASP Dependency-Check, GitHub Dependabot, `mvn versions:display-dependency-updates`) and search CVE databases for libraries before recommending versions.
- Keep the JDK on the latest patch release of its LTS line.

## Crypto
- Use `SecureRandom` for tokens; never `Random` / `Math.random()` for security values.
- Use AES-GCM for symmetric encryption; never ECB mode. Prefer well-reviewed libraries over custom crypto.
