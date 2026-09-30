<#
.SYNOPSIS
  Benchmark generation speed for several --n-cpu-moe values and report the fastest one that fits in VRAM.
#>
param(
    [string]$Model,
    [int[]]$Values = @(36, 33, 30, 27, 24, 21),
    [int]$Threads = 6
)
$ErrorActionPreference = "Stop"
. "$PSScriptRoot\common.ps1"
if (-not $Model) { $Model = Find-Model }
$bench = Join-Path $LlamaBin "llama-bench.exe"
$logDir = Join-Path $Root "data"
New-Item -ItemType Directory -Force $logDir | Out-Null
Write-Host "Model: $Model"

$results = foreach ($n in $Values) {
    Write-Host "n-cpu-moe = $n ..." -NoNewline
    # llama.cpp logs to stderr; Windows PowerShell 5.1 turns redirected stderr into errors, so relax it here
    $log = Join-Path $logDir "tune-ncmoe-$n.log"
    $ErrorActionPreference = "Continue"
    $out = & $bench -m $Model -ngl 999 -ncmoe $n -fa 1 -t $Threads -p 512 -n 128 -o json 2> $log
    $code = $LASTEXITCODE
    $ErrorActionPreference = "Stop"
    if ($code -ne 0 -or -not $out) { Write-Host " failed (out of VRAM?) - see $log"; continue }
    $rows = ($out | Out-String) | ConvertFrom-Json
    $pp = ($rows | Where-Object { $_.n_prompt -gt 0 }).avg_ts
    $tg = ($rows | Where-Object { $_.n_gen -gt 0 }).avg_ts
    Write-Host (" prompt {0:N0} tok/s, generation {1:N1} tok/s" -f $pp, $tg)
    [pscustomobject]@{ NCpuMoe = $n; PromptTps = [math]::Round($pp); GenTps = [math]::Round($tg, 1) }
}
$results | Format-Table
$best = $results | Sort-Object GenTps -Descending | Select-Object -First 1
if ($best) {
    Write-Host "Fastest: -NCpuMoe $($best.NCpuMoe) ($($best.GenTps) tok/s)." -ForegroundColor Green
    Write-Host "Leave ~1 GB of VRAM free for long contexts: if serve.ps1 runs out of memory at full context, use a value 2-3 higher."
}
