# Pruning pipeline: make the model smaller for *our* use

Goal: remove weights that do nothing for Java/Spring agentic coding, keeping quality within noise of the base
model on our eval suite (see `eval/`). "Quality first" setting: **~25-35% of experts removed**.

## What gets removed

| Step | What | Size effect | Quality risk |
|------|------|-------------|--------------|
| 1 | Vision encoder (mmproj) | ~0.9 GB, free | none (we never send images) |
| 2 | REAP expert pruning, 30% | ~32B expert params -> ~22B, total ~35B -> ~25B | low if calibration is representative |
| 3 | Imatrix quantization (Q4_K_M / IQ4_XS) calibrated on Java | BF16 50 GB -> ~14-15 GB | low; imatrix protects the weights our data uses |

Step 1 is already done by `setup.ps1` / `serve.ps1` (mmproj is never downloaded).

Why it helps on your PC: fewer experts means less RAM and more MoE layers fit on the 8 GB GPU (lower
`--n-cpu-moe`), so it is somewhat faster too, and leaves RAM for IntelliJ + Docker. The active parameters per
token (~3B) do not change, so speed gains are modest; the main win is size.

**REAP** (Router-weighted Expert Activation Pruning, Cerebras, ICLR 2026) scores each expert by how often the
router selects it *and* how much its output contributes, measured on a calibration set, then drops the lowest
scored experts. It beats expert merging on generative tasks like code. Repo: https://github.com/CerebrasResearch/reap

## Hardware: this step runs in the cloud, once

REAP needs the BF16 checkpoint (~70 GB) plus activations, which will not fit in 32 GB RAM + 8 GB VRAM.
Rent one 80-141 GB GPU (H100 / H200 / A100-80GB) for a few hours on RunPod, Vast.ai or Lambda. Expected cost:
roughly $10-30 per pruning run. Everything after (serving, evals) runs locally.

## Steps

### 1. Build the calibration set (local)
Calibration decides which experts survive. It must look like your real usage: Java code, build files,
reviews, test writing and **agentic tool-call traces** (otherwise the experts that produce tool calls may be pruned).

```bash
# clone the repos listed in calibration_repos.txt (+ your own projects) into data/repos, then:
python pruning/build_calibration.py --src data/repos --traces data/traces.jsonl --out data/calibration
```

Good sources of traces: export conversations from your coding client while using the base model (Phase 1).

### 2. Prune with REAP (cloud GPU)
```bash
git clone https://github.com/CerebrasResearch/reap && cd reap
# Follow the repo README for the exact CLI and install steps (they change between versions).
# Inputs:  model = Qwen/Qwen3.6-35B-A3B (BF16), dataset = calibration.jsonl, pruning method = reap,
#          compression ratio = 0.25 / 0.30 / 0.35 (build all three, pick with evals).
# Output:  a HF-format checkpoint with fewer experts per layer.
```
Requires a `transformers` version that supports the `qwen3_5_moe` architecture.

### 3. Convert and quantize with an imatrix (same cloud machine)
```bash
git clone https://github.com/ggml-org/llama.cpp && cmake -S llama.cpp -B llama.cpp/build -DGGML_CUDA=ON && cmake --build llama.cpp/build -j
python llama.cpp/convert_hf_to_gguf.py pruned-30/ --outtype bf16 --outfile nepcode-30-bf16.gguf
llama.cpp/build/bin/llama-imatrix -m nepcode-30-bf16.gguf -f data/calibration/calibration.txt -o imatrix-30.dat -ngl 999
llama.cpp/build/bin/llama-quantize --imatrix imatrix-30.dat nepcode-30-bf16.gguf nepcode-30-Q4_K_M.gguf Q4_K_M
```
Download `nepcode-30-Q4_K_M.gguf` into `models\nepcode\` on your PC; `serve.ps1` picks it up automatically.

### 4. Accept or reject (local)
Run the eval suite on base vs each pruned variant. Accept the smallest variant whose scores stay within noise
of the base model. Record the result in `docs/DECISIONS.md`.
