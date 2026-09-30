<#
.SYNOPSIS
  Start the model as an OpenAI-compatible server on http://localhost:8080/v1.

.DESCRIPTION
  Attention, shared experts and KV cache stay on the GPU; the routed experts of the first -NCpuMoe layers are
  kept in system RAM (--n-cpu-moe). Only ~3B parameters are active per token, so DDR5 bandwidth keeps
  generation fast. Tune -NCpuMoe with tune.ps1: lower = more on the GPU = faster, until VRAM runs out.
#>
param(
    [string]$Model,
    [int]$NCpuMoe = 30,
    [int]$Ctx = 65536,
    [int]$Threads = 6,          # i5-14400F: 6 performance cores
    [int]$Port = 8080,
    [switch]$NoThink            # disable the thinking phase for faster, shorter answers
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
    "--cache-type-k", "q8_0", "--cache-type-v", "q8_0",
    "--threads", $Threads,
    "--jinja",                  # use the model's chat template: required for tool calling
    "--temp", "0.6", "--top-p", "0.95", "--top-k", "20", "--min-p", "0",
    "--host", "127.0.0.1", "--port", $Port
)
if ($NoThink) { $llamaArgs += @("--chat-template-kwargs", '{"enable_thinking":false}') }

Write-Host "Model: $Model"
Write-Host "Endpoint: http://127.0.0.1:$Port/v1  (model name: nepcode)"
& (Join-Path $LlamaBin "llama-server.exe") @llamaArgs
