# Decision log

Each entry: date, decision, why, and what would make us revisit it.

## 2026-09-30 - Base model: Qwen3.6-35B-A3B
- **Why:** best quality we can run at 30+ tok/s on RTX 5060 Ti 8 GB + 32 GB DDR5. MoE with ~3B active params,
  73.4% SWE-bench Verified (reported by Qwen), native tool calling,
  256K context. Dense 7-9B models fit fully in VRAM but score far lower on agentic coding.
- **How it fits:** attention + shared weights + KV cache on the GPU, part of the routed experts in RAM
  (`--n-cpu-moe`). Reported: 30-40 tok/s on 8 GB cards with DDR5.
- **Revisit when:** a newer open MoE coder with better Java/agentic scores and similar active size ships.
  The research tools exist partly to notice this.

## 2026-09-30 - No training from scratch; no fine-tune yet
- **Why:** pretraining a competitive coder needs trillions of tokens and thousands of GPU-hours. Fine-tuning
  a strong base with small data often hurts general reasoning. Knowledge that changes (versions, APIs) belongs
  in retrieval, not weights.
- **Revisit when:** evals show a systematic Java weakness that prompts + RAG cannot fix. Then: QLoRA on
  curated, verified Java data, measured against the eval suite.

## 2026-09-30 - Size reduction: drop vision + REAP ~30% experts, "quality first" (updated below)
- **Why:** user wants maximum quality in minimum space. Vision is unused (free win). REAP pruning with
  domain calibration removes experts that do not fire on Java work. Keep ~70% of experts to stay within noise.
- **Revisit when:** evals show the pruned model loses on any category; then prune less (20-25%).

## 2026-09-30 - Web research: self-hosted SearXNG + trafilatura, exposed over MCP
- **Why:** free, private, no API keys; MCP works with every major coding client. Official docs domains are
  ranked first. Verified findings are saved to the local knowledge base (SQLite FTS5), so knowledge accumulates.
- **Revisit when:** search quality is a bottleneck in freshness evals (then try a paid API like Brave/Tavily
  behind the same tool interface), or when the KB outgrows keyword search (then add embeddings/hybrid search).

## 2026-09-30 - Primary stack: Java + Spring
- Calibration data, knowledge base and evals focus on Java 21/25, Spring Boot 3/4, JPA, Maven/Gradle, JUnit.

## 2026-09-30 - Pruning runs locally, on the quantized GGUF (no cloud GPU)
- **Why:** user wants to avoid paying for cloud GPUs. The reference REAP needs BF16 weights (~70 GB) on one GPU.
  Our `llama-reap-score` computes the same REAP criterion through llama.cpp on the Q4 GGUF with RAM offload, and
  `prune_experts.py` slices experts out of the quantized tensors (bit-exact, no re-quantization).
- **Risk:** scores come from a 4-bit model. Mitigated by evals (base vs pruned).
- **Revisit when:** a pruned model loses on evals; then compare against the reference REAP on a rented GPU once.

## 2026-09-30 - Client: OpenCode in the terminal
- **Why:** user works in VS Code but wants a terminal-only option. OpenCode is an open-source terminal agent
  that supports OpenAI-compatible local servers and MCP, and runs fine inside VS Code's terminal.
- **Revisit when:** tool-calling reliability with the local model is poor in OpenCode (then try Qwen Code,
  which is tuned for Qwen models).

## 2026-09-30 - Search works without Docker (ddgs fallback)
- **Why:** Docker Desktop is a heavy install just for search. `web_search` now uses SearXNG when it is running
  and otherwise the `ddgs` metasearch library (free, no key). SearXNG stays the more private option.
- **Revisit when:** ddgs gets rate-limited or its results are poor in freshness evals.

## 2026-09-30 - First benchmark on the target PC (base model, UD-Q4_K_XL, llama.cpp b11146, CUDA 13.4 build)
| --n-cpu-moe | prompt tok/s | generation tok/s |
|---|---|---|
| 36 | 195 | 42.8 |
| 33 | 208 | 44.4 |
| 30 | 313 | 44.8 |
| 27 | 59 | 14.0 (VRAM overflow into shared memory) |
| 24 | 61 | 12.0 (overflow) |
| 21 | 61 | 8.1 (overflow) |
- **Result:** speed goal met: ~44 tok/s generation, 1.5x the 30 tok/s target, before any pruning.
- **Serve default:** `-NCpuMoe 33` (only 0.4 tok/s slower than 30, leaves ~1.3 GB for the 64K-context KV cache).
- **Finding:** on Windows, VRAM overflow does not fail, it spills into shared memory at 3-5x lower speed.
  Pruning's benefit here is real: fewer experts per layer means more layers fit before the overflow cliff.
- **Next bottleneck:** prompt processing (~200-300 tok/s) for long agentic prompts; tune.ps1 phase 2 tests larger micro-batches.
- **Accidental data point (all experts in RAM, `--n-cpu-moe` above the layer count):** 37.1 tok/s generation;
  prompt 249 / 380 / 587 tok/s with micro-batch 512 / 1024 / 2048 (4K-token prompt). So micro-batch 2048
  more than doubles prompt speed, and even with every expert in RAM generation stays above the 30 tok/s goal.

## 2026-09-30 - Tuned serving settings: -NCpuMoe 33 -UBatch 1024
Second run (warmer system, same build): phase 1 gave 46.8 tok/s at 33 and 51.1 tok/s at 30.
Phase 2 at `--n-cpu-moe 33`, 4K-token prompt:

| micro-batch | prompt tok/s | generation tok/s |
|---|---|---|
| 512 | 426 | 48.0 |
| 1024 | 723 | 48.8 |
| 2048 | 514 | 48.4 |

- **Decision:** serve with `-NCpuMoe 33 -UBatch 1024` (now the `serve.ps1` defaults): ~48 tok/s generation,
  ~720 tok/s prompt, so a 10K-token agentic prompt is read in ~14 s instead of ~40 s.
- 2048 is slower than 1024 at this setting: its bigger compute buffer likely pushes VRAM to the limit.
