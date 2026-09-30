# Research: getting more than Qwen3.6-35B-A3B out of 8 GB VRAM + 32 GB RAM

Date: 2026-09-30. Question: can compression (or anything else) let us run a *smarter* model than
Qwen3.6-35B-A3B at >= 30 tok/s on RTX 5060 Ti 8 GB + 32 GB DDR5?

## 1. The two constraints

1. **Capacity** - weights must fit in ~34 GB (VRAM + RAM minus Windows/IDE). Otherwise they stream from the
   SSD and speed collapses.
2. **Bandwidth** - every generated token reads the *active* weights. With most experts in RAM (DDR5, ~60-70 GB/s
   usable) the ceiling is roughly `bandwidth / active_bytes_per_token`. Measured: 3B active at ~4.5 bits -> 48 tok/s.

Any "smarter" candidate has to pass both. Compression attacks (1); only fewer active bits or speculative
decoding attack (2).

## 2. What the literature says about compressing MoE models

- **Experts tolerate low bits well.** Expert FFN layers keep quality at 2-bit much better than attention or
  dense FFN layers (MoQE, Microsoft; MoPEQ assigns 2/3/4 bits per expert by sensitivity with <5% loss).
  This is why "dynamic" GGUF quants (attention high precision, experts low) work.
- **Expert pruning is the main source of damage when stacking techniques.** MoE-XBench (arXiv 2608.21693,
  10 MoE models 30B-235B, 20-50% pruning, 1-16 bit, KV precision) finds: combined compression cannot be
  predicted from each technique alone, compression rate does not predict quality loss, **expert pruning is the
  dominant degradation source**, and averages hide task-specific failures.
  -> For a fixed size budget, prefer *less pruning + more bits* over *more pruning + fewer bits*, and always
  measure on our own tasks.
- **REAP** (ICLR 2026) is the best pruning criterion for generative/code tasks (near-lossless at 25-50% on code
  in the paper, but that is on their benchmarks; see the point above).
- **KV-cache compression** (TurboQuant, ICLR 2026; a llama.cpp fork adds turbo3/turbo4 KV types) frees memory
  for long context. Qwen3.6's hybrid attention already has a small KV cache (~0.7 GB for 128K at q8_0), so the
  gain for us is small.

## 3. Candidates checked

| Model | Total / active | SWE-bench V. | Size needed | Verdict |
|---|---|---|---|---|
| **Qwen3.6-35B-A3B** | 35B / 3B | 73.4 | 22 GB (Q4) | current; best that fits at speed |
| Qwen3.6-27B dense | 27B / 27B | 77.2 | 17 GB (Q4) | smarter, but every token reads ~17 GB -> ~4-6 tok/s here; ~10-15 with MTP (estimate) |
| Qwen3-Coder-Next | 80B / 3B | 70.6-74.2 | 46 GB (Q4); ~24 GB after 50% REAP | fits only heavily pruned, not smarter on benchmarks |
| Qwen3.5-122B-A10B (REAP 88B/99B exist) | 122B / 10B | lower than 3.6-35B | ~27 GB at ~2.5 bit after REAP | 10B active -> ~12-15 tok/s, not smarter than 3.6 |
| MiniMax M2.5 | 229B / 10B | 80.2 | 74 GB even at IQ2_XXS | does not fit |
| Qwen3.8-Flash-Next | 125B + 51B n-gram emb. / 6B | - | 75 GB at 1-bit | does not fit |

**Conclusion:** no compression path gives a clearly smarter model at >= 30 tok/s on this machine today. The models
that are smarter either don't fit (even at 2 bits after pruning) or have too many active parameters.

## 4. What *can* improve on today's setup (ranked)

### E1. Speculative decoding with the built-in MTP head - speed, zero quality loss
Qwen3.6 ships multi-token-prediction (MTP) heads. llama.cpp supports them (`--spec-type draft-mtp`, head in a
separate "*mtp*.gguf" sidecar or an MTP GGUF). The main model verifies several drafted tokens in one pass, so
output is identical to normal decoding. Reported speedups: 1.4-2.2x; ~100 tok/s for 35B-A3B on GPUs that hold
the whole model.
- **Caveat for us:** with experts in RAM, each drafted token can route to different experts, so verification
  reads more expert weights; the speedup will likely be at the low end. Must measure.
- **Zero-download alternative:** `--spec-type ngram-mod` drafts tokens by matching n-grams already in the
  context. Great for code editing and for reasoning models that repeat their thinking in the answer.
- **Why it matters for quality:** speed headroom can be *spent*: more thinking, more test-and-fix iterations
  per minute, or a higher-precision quant (E2).

### E2. Spend headroom on precision instead of size
If E1 gives ~1.5x, a UD-Q5_K_XL quant (~26 GB, fits) keeps experts at higher precision for a small quality gain,
at roughly the speed we have now. MoE-XBench suggests higher precision beats pruning for the same bytes.
Needs the eval suite to confirm the gain is real on Java tasks.

### E3. "Slow but smart" mode: Qwen3.6-27B for planning and reviews
OpenCode can use a different model per agent (e.g. Plan). Planning and reviews produce short outputs, so
~10-15 tok/s (27B + MTP, estimate) may be acceptable there, while the fast MoE does the building.
Both don't fit in RAM at once, so the server has to swap models (~10-20 s). Worth a trial once E1 is measured.

### E4. KV-cache compression (TurboQuant fork)
Low priority: our KV cache is already small. Revisit if we go beyond 128K context.

### Rejected
Heavier pruning of a bigger MoE (Coder-Next REAP-50, 122B REAP + 2-bit): largest quality risk (pruning is the
main damage source) for no benchmark gain over what we have.

## 5. Plan
1. E1 now: `serve.ps1 -Spec ngram` (no download) and `-Spec mtp` (needs the MTP head file); compare tok/s
   on the same prompt.
2. Build the Java eval suite (Phase 3), then E2 and E3 are decided by measurements.

## Sources
- MoE-XBench: https://arxiv.org/abs/2608.21693
- MoQE (experts robust to 2-bit): https://arxiv.org/abs/2310.02410
- REAP: https://arxiv.org/abs/2510.13999
- Qwen3.6 MTP in llama.cpp: https://mer.vin/2026/05/run-qwen-3-6-mtp-in-llama-cpp-faster-local-inference-with-built-in-speculative-decoding/
- Qwen3.6 MTP vs standard benchmarks: https://glukhov.org/it/llm-performance/benchmarks/comparing-qwen-3-6-mtp-vs-standard/
- MTP GGUF: https://huggingface.co/ggml-org/Qwen3.6-35B-A3B-MTP-GGUF
- TurboQuant KV cache: https://rits.shanghai.nyu.edu/ai/googles-turboquant-cuts-llm-memory-6x-with-zero-accuracy-loss/
- Qwen3.6-27B: https://rits.shanghai.nyu.edu/ai/qwen3-6-27b-a-dense-27b-model-that-beats-a-397b-moe-on-coding
- MiniMax M2.5 local requirements: https://www.unsloth.ai/docs/zh/mo-xing/tutorials/minimax-m25.md
- Qwen3.8-Flash-Next: https://atomic.chat/blog/guides/how-to-run-qwen-3-8-flash-next-locally
- llama.cpp speculative decoding docs: docs/speculative.md in the llama.cpp repo
