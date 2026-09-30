<#
.SYNOPSIS
  Start the model as an OpenAI-compatible server on http://localhost:8080/v1.

.DESCRIPTION
  Attention, shared experts and KV cache stay on the GPU; the routed experts of the first -NCpuMoe layers are
  kept in system RAM (--n-cpu-moe). Only ~3B parameters are active per token, so DDR5 bandwidth keeps
  generation fast. Tune -NCpuMoe with tune.ps1: lower = more on the GPU = faster, until VRAM runs out.
  If VRAM overflows, Windows silently spills into shared memory and speed drops 3-5x: raise -NCpuMoe.
#>
param(
    [string]$Model,
    [int]$NCpuMoe = 35,         # RTX 5060 Ti 8 GB: 30 is the fastest that fits in a short benchmark, +5 for the 128K KV cache
    [int]$UBatch = 1024,        # larger = faster prompt processing, more VRAM; pick with tune.ps1 phase 2 (1024 won on the 5060 Ti)
    [int]$Ctx = 131072,         # Qwen advises >= 128K: with less, long agentic sessions lose track and loop
    [double]$PresencePenalty = 0.5,  # 0 = Qwen's coding default; raise toward 1.5 if the model repeats itself
    [int]$Threads = 6,          # i5-14400F: 6 performance cores
    [int]$Port = 8080,
    [switch]$NoThink,           # disable the thinking phase for faster, shorter answers
    # Speculative decoding (output is identical, only speed changes):
    #   ngram - drafts from n-grams already in the context; no download, good for code edits
    #   mtp   - uses the model's multi-token-prediction head; needs an MTP GGUF (see docs/research/compression-and-speed.md)
    [ValidateSet("none", "ngram", "mtp")][string]$Spec = "none"
)
$ErrorActionPreference = "Stop"
. "$PSScriptRoot\common.ps1"
if (-not $Model) { $Model = Find-Model }

$llamaArgs = @(
    "--model", $Model,
    "--alias", "nepcode",
    "--n-gpu-layers", "999",
    "--n-cpu-moe", $NCpuMoe,
    "--flash-attn", "on",
    "--ctx-size", $Ctx,
    # 2 slots sharing one KV pool: OpenCode's side requests (titles, summaries) don't evict the main session's cache
    "--parallel", "2", "--kv-unified",
    "--ubatch-size", $UBatch, "--batch-size", [math]::Max($UBatch, 2048),
    "--cache-type-k", "q8_0", "--cache-type-v", "q8_0",
    "--threads", $Threads,
    "--jinja",                  # use the model's chat template: required for tool calling
    "--temp", "0.6", "--top-p", "0.95", "--top-k", "20", "--min-p", "0", "--presence-penalty", $PresencePenalty,
    "--host", "127.0.0.1", "--port", $Port
)
switch ($Spec) {
    "ngram" {
        # values from llama.cpp docs/speculative.md: MoE models need long drafts
        $llamaArgs += @("--spec-type", "ngram-mod", "--spec-ngram-mod-n-match", "24",
                        "--spec-ngram-mod-n-min", "48", "--spec-ngram-mod-n-max", "64")
    }
    "mtp" {
        $llamaArgs += @("--spec-type", "draft-mtp")
        # MTP head either inside the main GGUF, or as a separate "*mtp*.gguf" next to it
        $sidecar = Get-ChildItem (Split-Path $Model) -Filter *.gguf |
            Where-Object { $_.Name -match "mtp" -and $_.FullName -ne $Model } | Select-Object -First 1
        if ($sidecar) { $llamaArgs += @("--spec-draft-model", $sidecar.FullName, "--spec-draft-ngl", "999") }
    }
}
if ($NoThink) { $llamaArgs += @("--chat-template-kwargs", '{"enable_thinking":false}') }

Write-Host "Model: $Model  (ctx $Ctx, n-cpu-moe $NCpuMoe, ubatch $UBatch, spec $Spec)"
Write-Host "Check the log for VRAM overflow: if generation is far below ~40 tok/s, restart with -NCpuMoe 37 (or -Ctx 98304)."
Write-Host "Endpoint: http://127.0.0.1:$Port/v1  (model name: nepcode)"
& (Join-Path $LlamaBin "llama-server.exe") @llamaArgs
