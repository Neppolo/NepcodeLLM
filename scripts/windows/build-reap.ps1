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

if (-not (Get-Command cmake -ErrorAction SilentlyContinue)) { throw "CMake not found: install it (or the VS Build Tools 'C++ CMake tools' component)" }

# RTX 50xx (Blackwell, sm_120) needs CUDA >= 12.8. Older toolkits fall back to a CPU build.
$cuda = "OFF"
if (Get-Command nvcc -ErrorAction SilentlyContinue) {
    if ((nvcc --version | Out-String) -match 'release (\d+\.\d+)') {
        $cudaVer = [version]$Matches[1]
        if ($cudaVer -ge [version]"12.8") { $cuda = "ON" }
        else { Write-Warning "CUDA $cudaVer is too old for RTX 50xx (need 12.8+): building CPU-only" }
    }
}
Write-Host "llama.cpp $tag, CUDA=$cuda $cudaVer"

$build = Join-Path $Root "bin\reap-build"
cmake -S pruning\reap-score -B $build -DLLAMA_CPP_DIR="$src" -DGGML_CUDA=$cuda -DCMAKE_CUDA_ARCHITECTURES=120
if ($LASTEXITCODE -ne 0) {
    Write-Host @"
CMake configure failed. Common causes with CUDA on Windows:
  - 'No CUDA toolset found': Visual Studio was installed after the CUDA Toolkit. Re-run the CUDA installer
    (Custom > Visual Studio Integration), or run this script from the 'x64 Native Tools Command Prompt for VS 2022'.
  - 'unsupported Microsoft Visual Studio version': install VS 2022 Build Tools (C++ workload); CUDA supports
    only specific MSVC versions.
Delete bin\reap-build before retrying.
"@ -ForegroundColor Yellow
    throw "configure failed"
}
cmake --build $build --config Release -j
if ($LASTEXITCODE -ne 0) { throw "build failed" }
$exe = Get-ChildItem $build -Recurse -Filter llama-reap-score.exe | Select-Object -First 1
Copy-Item $exe.FullName $LlamaBin   # static llama.cpp; the CUDA runtime DLL comes from the toolkit on PATH
Write-Host "Built $LlamaBin\llama-reap-score.exe" -ForegroundColor Green
