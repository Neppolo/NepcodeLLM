# Evaluation suite (Phase 3)

Every change (pruned variant, quant, prompt, knowledge base) is accepted only if it wins or ties here.
Public benchmarks are mostly Python; we need our own Java suite.

## Planned metrics
1. **Functional correctness** - Java tasks with hidden JUnit tests, run in Docker (`mvn -q test`). Score = pass@1.
   Sources: MultiPL-E Java (HumanEval/MBPP ports), plus our own Spring tasks (controller + service + JPA + tests).
2. **Agentic** - small repo-level tasks: the model gets a broken Spring project and must make the tests pass
   using tools (a mini SWE-bench for Java).
3. **Best practices** - review tasks with known planted issues (N+1 query, field injection, SQL injection,
   swallowed exception, missing `@Transactional`...). Score = issues found / planted, minus false positives.
4. **Freshness** - questions whose answer changed after the model's training cutoff (latest Spring Boot version,
   new property names, recent CVEs). Checks that the research tools are actually used.
5. **Speed** - prompt processing and generation tok/s from `scripts/windows/tune.ps1`. Floor: 30 tok/s generation.

## Task format
```
eval/tasks/<id>/
  task.md          # the prompt given to the model
  project/         # starting code (Maven project)
  hidden-tests/    # tests copied in after the model finishes
  meta.yaml        # category, difficulty, expected issues (for review tasks)
```
