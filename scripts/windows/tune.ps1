<#
.SYNOPSIS
  Find the fastest settings for serve.ps1 on this PC.

.DESCRIPTION
  Phase 1: generation speed for several --n-cpu-moe values (fewer experts in RAM = faster, until VRAM is full).
  Phase 2: prompt-processing speed for several micro-batch sizes, with a realistic 4K-token prompt.
           Agentic clients send long prompts (system prompt, tool definitions, files), so this matters.

  On Windows, the NVIDIA driver does not fail when VRAM is full: it silently spills into shared system memory
  and speed collapses. Such runs are flagged as "VRAM overflow". To make overflow fail loudly instead, set
  NVIDIA Control Panel > Manage 3D settings > CUDA - Sysmem Fallback Policy > Prefer No Sysmem Fallback.

.EXAMPLE
  scripts\windows\tune.ps1
  scripts\windows\tune.ps1 -Values "34,33,32,31" -SkipBatch
#>
param(
    [string]$Model,
    # Comma-separated strings: with "powershell -File", "-Values 33,30" arrives as one string, and a cast to int
    # would read it as 3330 (comma as thousands separator). Parse explicitly instead.
    [string]$Values = "36,33,30,27,24,21",
    [string]$UBatches = "512,1024,2048",
    [int]$Headroom = 3,        # serve.ps1 uses a long context (bigger KV cache), so keep this many layers' experts off the GPU
    [int]$Threads = 6,
    [switch]$SkipBatch
)
$ErrorActionPreference = "Stop"
. "$PSScriptRoot\common.ps1"
function ConvertTo-IntList([string]$s) { @($s -split '[,; ]+' | Where-Object { $_ } | ForEach-Object { [int]$_ }) }
$ValueList = ConvertTo-IntList $Values
$UBatchList = ConvertTo-IntList $UBatches
if (-not $Model) { $Model = Find-Model }
$bench = Join-Path $LlamaBin "llama-bench.exe"
$logDir = Join-Path $Root "data"
New-Item -ItemType Directory -Force $logDir | Out-Null
Write-Host "Model: $Model"

function Invoke-Bench([string]$Name, [string[]]$BenchArgs) {
    # llama.cpp logs to stderr; Windows PowerShell 5.1 turns redirected stderr into errors, so relax it here
    $log = Join-Path $logDir "tune-$Name.log"
    $ErrorActionPreference = "Continue"
    $out = & $bench -m $Model -ngl 999 -fa 1 -t $Threads -o json @BenchArgs 2> $log
    $code = $LASTEXITCODE
    $ErrorActionPreference = "Stop"
    if ($code -ne 0 -or -not $out) { Write-Host " failed - see $log"; return $null }
    $rows = ($out | Out-String) | ConvertFrom-Json
    [pscustomobject]@{
        PromptTps = [math]::Round((@($rows) | Where-Object { $_.n_prompt -gt 0 }).avg_ts)
        GenTps    = [math]::Round((@($rows) | Where-Object { $_.n_gen -gt 0 }).avg_ts, 1)
    }
}

Write-Host "`n== Phase 1: experts in RAM (--n-cpu-moe) vs generation speed" -ForegroundColor Cyan
$results = foreach ($n in $ValueList) {
    Write-Host "n-cpu-moe = $n ..." -NoNewline
    $r = Invoke-Bench "ncmoe-$n" @("-ncmoe", $n, "-p", "512", "-n", "128")
    if (-not $r) { continue }
    Write-Host (" prompt {0:N0} tok/s, generation {1:N1} tok/s" -f $r.PromptTps, $r.GenTps)
    [pscustomobject]@{ NCpuMoe = $n; PromptTps = $r.PromptTps; GenTps = $r.GenTps; Note = "" }
}
if (-not $results) { throw "every run failed; check the logs in $logDir" }

$peak = ($results | Measure-Object GenTps -Maximum).Maximum
foreach ($r in $results) { if ($r.GenTps -lt 0.6 * $peak) { $r.Note = "VRAM overflow" } }
$results | Format-Table

$fits = $results | Where-Object { -not $_.Note }
$fastest = ($fits | Sort-Object NCpuMoe | Select-Object -First 1).NCpuMoe
$serveNcmoe = $fastest + $Headroom
Write-Host "Fastest that fits: -NCpuMoe $fastest. For serve.ps1 use -NCpuMoe $serveNcmoe ($Headroom layers of headroom for the long-context KV cache)." -ForegroundColor Green

if ($SkipBatch) { return }

Write-Host "`n== Phase 2: micro-batch size vs prompt speed (4096-token prompt, -NCpuMoe $serveNcmoe)" -ForegroundColor Cyan
$batch = foreach ($ub in $UBatchList) {
    Write-Host "ubatch = $ub ..." -NoNewline
    $b = [math]::Max($ub, 2048)
    $r = Invoke-Bench "ubatch-$ub" @("-ncmoe", $serveNcmoe, "-ub", $ub, "-b", $b, "-p", "4096", "-n", "64")
    if (-not $r) { continue }
    Write-Host (" prompt {0:N0} tok/s, generation {1:N1} tok/s" -f $r.PromptTps, $r.GenTps)
    [pscustomobject]@{ UBatch = $ub; PromptTps = $r.PromptTps; GenTps = $r.GenTps; Note = "" }
}
if ($batch) {
    foreach ($r in $batch) { if ($r.GenTps -lt 0.6 * $peak) { $r.Note = "VRAM overflow" } }
    $batch | Format-Table
    $best = $batch | Where-Object { -not $_.Note } | Sort-Object PromptTps -Descending | Select-Object -First 1
    if ($best) {
        Write-Host "Recommended: scripts\windows\serve.ps1 -NCpuMoe $serveNcmoe -UBatch $($best.UBatch)" -ForegroundColor Green
    }
}
