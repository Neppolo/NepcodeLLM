<#
.SYNOPSIS
  Build llama-reap-score (the local REAP expert scorer) against the same llama.cpp version setup.ps1 installed.

.DESCRIPTION
  Needs: Git, CMake, Visual Studio 2022 Build Tools ("Desktop development with C++").
  With the CUDA Toolkit (>= 12.8 for RTX 50xx) installed it builds with GPU support (scoring takes minutes);
  without it, a CPU build (scoring takes a few hours, still free).
#>
$ErrorActionPreference = "Stop"
. "$PSScriptRoot\common.ps1"
Set-Location $Root

$src = Join-Path $Root "bin\llama.cpp-src"
$tag = if (Test-Path "$LlamaBin\VERSION.txt") { (Get-Content "$LlamaBin\VERSION.txt").Split(" ")[0] } else { "master" }
if (-not (Test-Path $src)) {
    git clone --depth 1 --branch $tag https://github.com/ggml-org/llama.cpp $src
}

$cuda = if (Get-Command nvcc -ErrorAction SilentlyContinue) { "ON" } else { "OFF" }
Write-Host "llama.cpp $tag, CUDA=$cuda"
$build = Join-Path $Root "bin\reap-build"
cmake -S pruning\reap-score -B $build -DLLAMA_CPP_DIR="$src" -DGGML_CUDA=$cuda -DCMAKE_CUDA_ARCHITECTURES=120
cmake --build $build --config Release -j
$exe = Get-ChildItem $build -Recurse -Filter llama-reap-score.exe | Select-Object -First 1
Copy-Item $exe.FullName $LlamaBin   # static build; CUDA runtime DLLs are already in bin\llama.cpp
Write-Host "Built $LlamaBin\llama-reap-score.exe" -ForegroundColor Green
