<#
.SYNOPSIS
  One-time setup of NepcodeLLM on Windows: llama.cpp (CUDA), the model, the tools venv and SearXNG.

.EXAMPLE
  powershell -ExecutionPolicy Bypass -File scripts\windows\setup.ps1
  powershell -ExecutionPolicy Bypass -File scripts\windows\setup.ps1 -Quant UD-IQ4_XS -SkipSearch
#>
param(
    [string]$ModelRepo = "unsloth/Qwen3.6-35B-A3B-GGUF",
    [string]$Quant = "UD-Q4_K_XL",
    [switch]$SkipModel,
    [switch]$SkipSearch
)
$ErrorActionPreference = "Stop"
$Root = Resolve-Path "$PSScriptRoot\..\.."
Set-Location $Root

function Step($msg) { Write-Host "`n==> $msg" -ForegroundColor Cyan }

Step "Checking prerequisites"
foreach ($cmd in "nvidia-smi", "python", "git") {
    if (-not (Get-Command $cmd -ErrorAction SilentlyContinue)) { throw "$cmd not found in PATH" }
}
nvidia-smi --query-gpu=name,driver_version,memory.total --format=csv,noheader

Step "Downloading latest llama.cpp CUDA build"
# RTX 50xx (Blackwell, sm_120) needs a build made with CUDA >= 12.8.
$release = Invoke-RestMethod "https://api.github.com/repos/ggml-org/llama.cpp/releases/latest"
$builds = $release.assets | Where-Object { $_.name -match '^llama-.*-bin-win-cuda-(\d+)\.(\d+)-x64\.zip$' } |
    ForEach-Object { [pscustomobject]@{ Asset = $_; Ver = [version]"$($Matches[1]).$($Matches[2])" } } |
    Where-Object { $_.Ver -ge [version]"12.8" } | Sort-Object Ver -Descending
if (-not $builds) { throw "No Windows CUDA >= 12.8 build found in llama.cpp $($release.tag_name)" }
$build = $builds[0]
$cudart = $release.assets | Where-Object { $_.name -match "^cudart-.*win-cuda-$([regex]::Escape($build.Ver.ToString()))-x64\.zip$" } | Select-Object -First 1

$binDir = Join-Path $Root "bin\llama.cpp"
New-Item -ItemType Directory -Force $binDir | Out-Null
foreach ($asset in @($build.Asset, $cudart) | Where-Object { $_ }) {
    $zip = Join-Path $env:TEMP $asset.name
    Write-Host "  $($asset.name)"
    Invoke-WebRequest $asset.browser_download_url -OutFile $zip
    Expand-Archive $zip -DestinationPath $binDir -Force
}
Set-Content (Join-Path $binDir "VERSION.txt") "$($release.tag_name) cuda-$($build.Ver)"
Write-Host "  llama.cpp $($release.tag_name) (CUDA $($build.Ver)) -> $binDir"

Step "Creating Python venv for the tools layer"
if (-not (Test-Path ".venv")) { python -m venv .venv }
& .\.venv\Scripts\python -m pip install --upgrade pip --quiet
& .\.venv\Scripts\pip install -e ".[dev]" "huggingface_hub[cli]" --quiet
& .\.venv\Scripts\nepcode index

if (-not $SkipModel) {
    Step "Downloading $ModelRepo ($Quant) - about 20 GB"
    # Only the language model: the vision projector (mmproj) is not downloaded, which is the first 'useless weight' we drop.
    & .\.venv\Scripts\hf download $ModelRepo --include "*$Quant*.gguf" --exclude "*mmproj*" --local-dir "models\base"
}

if (-not $SkipSearch) {
    Step "Starting SearXNG (Docker)"
    if (-not (Get-Command docker -ErrorAction SilentlyContinue)) {
        Write-Warning "Docker not found: install Docker Desktop, then run: docker compose -f infra\searxng\docker-compose.yml up -d"
    } else {
        $envFile = "infra\searxng\.env"
        if (-not (Test-Path $envFile)) {
            $bytes = New-Object byte[] 32
            [System.Security.Cryptography.RandomNumberGenerator]::Create().GetBytes($bytes)
            Set-Content $envFile "SEARXNG_SECRET=$(($bytes | ForEach-Object { $_.ToString('x2') }) -join '')"
        }
        docker compose -f infra\searxng\docker-compose.yml up -d
    }
}

Step "Done. Next: scripts\windows\tune.ps1 (find the fastest -NCpuMoe), then scripts\windows\serve.ps1"
