# NepcodeLLM

A local, private coding assistant specialized in **Java + Spring**, built to get the **maximum quality in the
smallest footprint** on consumer hardware, and to **stay up to date** by researching the web.

Target machine: RTX 5060 Ti 8 GB, 32 GB DDR5-6600, i5-14400F, Windows. Target speed: **>= 30 tok/s**.

## The approach in one paragraph

Training a model from scratch that beats the best open models is not possible on consumer hardware, so we start
from the strongest open coding model that runs fast on this PC and make it better *for our use* instead:
remove what we do not use (vision encoder, MoE experts that barely contribute on Java work, found with REAP
and cut locally from the quantized file, with no cloud GPU), and give it tools to look things up (web search, official docs, a local
knowledge base of best practices that grows over time). Every change is measured on our own Java eval suite.
Decisions and their reasons are in [docs/DECISIONS.md](docs/DECISIONS.md); the plan is in [docs/ROADMAP.md](docs/ROADMAP.md).

## Architecture

```
 OpenCode (terminal, or VS Code's terminal)
   |  OpenAI-compatible API                       |  MCP (stdio)
   v                                              v
 llama-server (llama.cpp, CUDA)              nepcode MCP server (Python)
   Qwen3.6-35B-A3B MoE, ~3B active/token       web_search  -> SearXNG (Docker, localhost)
   GPU (8 GB): attention, shared weights,      fetch_url   -> page -> clean Markdown (cached)
     KV cache, some expert layers              kb_search   -> SQLite FTS5 over knowledge/ + saved notes
   RAM: remaining routed experts (--n-cpu-moe) kb_save_note-> verified findings persist for next time
```

**Why this model:** MoE with 35B total but ~3B active parameters per token. Quality comes from the 35B, speed
from the 3B: the active experts are small enough to read from DDR5 fast, so the model does not need to fit in
VRAM. Reported 73.4% on SWE-bench Verified, native tool calling, 256K context.

**Memory budget (Q4, before pruning):** ~20 GB weights -> ~6.5 GB on GPU + ~14 GB in RAM, leaving RAM for the
IDE. After 30% expert pruning: ~15 GB total, more layers on the GPU.

## Quick start (Windows)

Prerequisites: NVIDIA driver (recent, for RTX 50xx), Python 3.11+, Git, Docker Desktop (for web search).

```powershell
git clone <this repo>; cd NepcodeLLM
powershell -ExecutionPolicy Bypass -File scripts\windows\setup.ps1   # llama.cpp + model (~20 GB) + tools + SearXNG
powershell -ExecutionPolicy Bypass -File scripts\windows\tune.ps1    # finds the fastest --n-cpu-moe value
powershell -ExecutionPolicy Bypass -File scripts\windows\serve.ps1 -NCpuMoe <best value>
```

Then install OpenCode and copy [clients/opencode.json](clients/opencode.json) into place: see
[clients/README.md](clients/README.md). Optional, later: prune the model locally with `scripts\windows\prune.ps1`
(see [pruning/README.md](pruning/README.md)).

## Repository layout

| Path | What |
|------|------|
| `src/nepcode/` | Tools layer: search, fetch, knowledge base, MCP server, CLI (`nepcode serve / index / search / web / fetch`) |
| `knowledge/` | Curated best-practice notes (Markdown), indexed by `nepcode index` |
| `prompts/` | System prompt for the model |
| `scripts/windows/` | Setup, tune, serve, build-reap and prune scripts |
| `infra/searxng/` | Self-hosted search engine config |
| `pruning/` | Calibration set builder, local REAP scorer (C++, llama.cpp) and GGUF expert cutter |
| `eval/` | Java evaluation suite (Phase 3) |
| `clients/` | Client connection examples |
| `docs/` | Decisions and roadmap |

## Development

```bash
python -m venv .venv && .venv/bin/pip install -e ".[dev]"   # Windows: .venv\Scripts\pip
.venv/bin/pytest
```
