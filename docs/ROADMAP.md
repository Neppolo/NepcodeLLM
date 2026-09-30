# Roadmap

We build in phases. Each phase ends with something usable, and each later change must beat the previous
version on the eval suite (`eval/`).

## Phase 1 - Working baseline (now)
- [x] Repository, decision log, architecture
- [x] Tools layer: `web_search` (SearXNG), `fetch_url` (clean Markdown), `kb_search` / `kb_save_note` (SQLite FTS5), MCP server
- [x] Seed knowledge base: modern Java, Spring Boot, testing, security, build tools
- [x] Windows scripts: setup (llama.cpp CUDA + model + SearXNG), tune (`--n-cpu-moe` sweep), serve
- [x] Java-specialist system prompt
- [ ] **You:** run setup + tune on your PC, report tok/s and VRAM use
- [ ] Connect a client (Cline / Continue / OpenCode), use it for real work, export conversations (they become calibration traces)

## Phase 2 - Knowledge that stays current
- [ ] Knowledge base ingestion: crawl + chunk official docs (Spring Boot reference, JDK release notes, OWASP cheat sheets)
- [ ] Scheduled "freshness" job: check new Spring Boot / JDK / Hibernate releases and CVEs, write notes to the KB
- [ ] Review queue: promote `learned` notes to curated `knowledge/` after review
- [ ] Hybrid search (BM25 + small embedding model on CPU) if keyword search misses in evals
- [ ] Optional: a Java tools MCP (run `mvn test`, parse Surefire reports, dependency-update check)

## Phase 3 - Evaluation suite
- [ ] Runner: Docker sandbox with JDK + Maven, OpenAI-compatible client, JSON results
- [ ] Task sets: MultiPL-E Java, Spring tasks, planted-issue reviews, freshness questions, agentic repo tasks
- [ ] Baseline scores for the base model (the number every later change must beat)

## Phase 4 - Smaller: prune + quantize
- [ ] Calibration set from Java repos + your agentic traces (`pruning/build_calibration.py`)
- [ ] REAP at 25 / 30 / 35% on a rented GPU, imatrix Q4 quants
- [ ] Eval all variants, keep the smallest one within noise of the base
- [ ] Try speculative decoding with the model's MTP head if llama.cpp support is solid on this architecture

## Phase 5 - Specialize (only if evals show gaps)
- [ ] Curated, test-verified Java/Spring instruction data (generated, compiled, tests run - only passing samples kept)
- [ ] QLoRA fine-tune (cloud GPU), merge, re-quantize, re-eval
- [ ] Repeat pruning calibration on the fine-tuned model
