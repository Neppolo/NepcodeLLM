<#
.SYNOPSIS
  Install the OpenCode config (local model + research tools + system prompt) with this repo's paths filled in.
  Works from any folder. Backs up an existing config.
#>
$ErrorActionPreference = "Stop"
. "$PSScriptRoot\common.ps1"

$dir = Join-Path $env:USERPROFILE ".config\opencode"
$dst = Join-Path $dir "opencode.json"
New-Item -ItemType Directory -Force $dir | Out-Null
if (Test-Path $dst) {
    $backup = "$dst.bak-$(Get-Date -Format yyyyMMdd-HHmmss)"
    Copy-Item $dst $backup
    Write-Host "Existing config backed up to $backup"
}

$repo = ($Root.ToString() -replace '\\', '/')
$json = (Get-Content (Join-Path $Root "clients\opencode.json") -Raw) -replace 'C:/path/to/NepcodeLLM', $repo
# UTF-8 without BOM: some JSON parsers reject the BOM that Windows PowerShell 5.1 writes by default
[IO.File]::WriteAllText($dst, $json, (New-Object Text.UTF8Encoding $false))
Write-Host "Wrote $dst (repo: $repo)" -ForegroundColor Green

if (-not (Test-Path (Join-Path $Root ".venv\Scripts\nepcode.exe"))) {
    Write-Warning "nepcode.exe not found in .venv: run scripts\windows\setup.ps1 first, or the research tools will not start."
}
