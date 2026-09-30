# Pruning pipeline: make the model smaller for *our* use, locally and for free

Goal: remove weights that do nothing for Java/Spring agentic coding while keeping quality within noise of the
base model on our eval suite (`eval/`). Setting: "quality first", **~25-35% of experts removed**.

**Pruning is optional.** The unpruned Q4 model already fits (about 6.5 GB VRAM + 14 GB RAM) and meets the speed
goal. Pruning buys free RAM, a smaller file and a few more tok/s. It never makes the model smarter.

## How it works

| Step | What | Size effect | Where | Cost |
|------|------|-------------|-------|------|
| 1 | Drop the vision encoder (mmproj) | ~0.9 GB | never downloaded | free |
| 2 | Score every expert with REAP on Java calibration data | - | your GPU, `llama-reap-score` | free, minutes to hours |
| 3 | Cut the lowest-scored experts straight out of the Q4 GGUF | ~20 GB -> ~14-15 GB at 30% | your PC, `prune_experts.py` | free, minutes |

**REAP** (Router-weighted Expert Activation Pruning, Cerebras, ICLR 2026) scores expert *j* as the mean of
`router_weight_j(x) * ||expert_output_j(x)||` over the calibration tokens routed to it. It beats expert merging
and frequency-based pruning on code generation. Paper: https://arxiv.org/abs/2510.13999

### Why this needs no cloud GPU
The official REAP code loads the full BF16 checkpoint (~70 GB), which needs an 80 GB+ GPU. We skip that:
- `llama-reap-score` (in `reap-score/`) runs the **quantized GGUF you already have** through llama.cpp, with
  experts offloaded to RAM as usual, and hooks three tensors of each MoE layer: the chosen expert ids, their
  router weights and each expert's output. From those it computes the REAP score. No extra download.
- `prune_experts.py` removes experts by **byte surgery on the GGUF**: every expert is a contiguous slice of the
  `ffn_*_exps` tensors plus one row of the router. The kept experts stay bit-identical, nothing is
  re-quantized, so there's no second quality loss.

Trade-off: scores are measured on the Q4 model rather than BF16. 4-bit noise should barely change which experts
rank lowest, but we'll confirm with evals (base vs pruned) before adopting a pruned model.

Tested here on a synthetic qwen3moe model: experts planted as useless score exactly 0 and are the ones removed,
kept experts are bit-identical, and llama.cpp loads and runs the pruned file (`tests/test_prune.py` + manual run).
Not yet run on the real Qwen3.6 model: that's our first joint step.

## Steps (Windows)

### 0. One-time: build the scorer
Needs Visual Studio 2022 Build Tools (C++), CMake, and ideally the CUDA Toolkit 12.8+ (without it, the build is CPU-only
and scoring is slower but still works).
```powershell
scripts\windows\build-reap.ps1
```

### 1. Build the calibration set
Calibration decides which experts survive, so it must look like your real usage: Java code, build files,
reviews, test writing, and **agentic tool-call traces** (otherwise the experts that write tool calls could be pruned).
Aim for ~0.5-1M tokens.
```powershell
# clone the repos in calibration_repos.txt (+ your own projects) into data\repos, then:
.venv\Scripts\python pruning\build_calibration.py --src data\repos --traces data\traces.jsonl --out data\calibration
```
Traces: export OpenCode sessions made with the base model during Phase 1.

### 2. Score + prune
```powershell
scripts\windows\prune.ps1 -Calibration data\calibration\calibration.txt -Ratio 0.3
```
Scoring runs once (saved to `data\reap-scores.json`); re-running with another `-Ratio` only redoes the fast cut.
Build 0.25 / 0.30 / 0.35 variants and let the evals pick. `serve.ps1` automatically prefers the model in `models\nepcode\`.

### 3. Accept or reject
Run the eval suite on base vs each variant; keep the smallest one within noise of the base, and record it in
`docs/DECISIONS.md`.

## Limits
- Same number of experts removed in every layer (llama.cpp needs a single `expert_count`).
- A GGUF that contains multi-token-prediction (MTP) layers is rejected: use a standard (non-MTP) GGUF.
- Split (multi-file) GGUFs must be merged first with `llama-gguf-split --merge`.

## Optional: the official REAP on a rented GPU
To score on BF16 weights with the reference implementation (https://github.com/CerebrasResearch/reap), rent an
80 GB+ GPU for a few hours (~$10-30), prune, then convert + quantize with llama.cpp (`convert_hf_to_gguf.py`,
`llama-imatrix` on `calibration.txt`, `llama-quantize --imatrix`). Only worth it if evals show the local
method loses quality.
