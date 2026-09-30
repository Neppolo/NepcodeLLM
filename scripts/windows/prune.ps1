<#
.SYNOPSIS
  Local, free expert pruning: score experts with REAP on your GPU, then cut the lowest-scored ones from the GGUF.

.EXAMPLE
  scripts\windows\prune.ps1 -Calibration data\calibration\calibration.txt -Ratio 0.3
#>
param(
    [Parameter(Mandatory)][string]$Calibration,
    [double]$Ratio = 0.3,
    [string]$Model,
    [int]$NCpuMoe = 30,
    [string]$Criterion = "reap"
)
$ErrorActionPreference = "Stop"
. "$PSScriptRoot\common.ps1"
Set-Location $Root
if (-not $Model) { $Model = Find-Model -BaseOnly }   # always prune from the original download
$scores = "data\reap-scores.json"
New-Item -ItemType Directory -Force data, models\nepcode | Out-Null

if (-not (Test-Path $scores)) {
    & "$LlamaBin\llama-reap-score.exe" -m $Model -f $Calibration -o $scores -c 512 -ngl 999 --n-cpu-moe $NCpuMoe -fa on
    if ($LASTEXITCODE -ne 0) { throw "scoring failed" }
} else {
    Write-Host "Reusing $scores (delete it to re-score with new calibration data)"
}

$pct = [int]($Ratio * 100)
$out = "models\nepcode\$([IO.Path]::GetFileNameWithoutExtension($Model))-reap$pct.gguf"
& .\.venv\Scripts\python pruning\prune_experts.py $Model --scores $scores --ratio $Ratio --criterion $Criterion -o $out
if ($LASTEXITCODE -ne 0) { throw "pruning failed" }
Write-Host "Done: $out. Run tune.ps1 again: more layers now fit on the GPU." -ForegroundColor Green
