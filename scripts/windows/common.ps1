# Shared helpers for the Windows scripts.
$Root = Resolve-Path "$PSScriptRoot\..\.."
$LlamaBin = Join-Path $Root "bin\llama.cpp"

function Find-Model([string]$Dir = "models") {
    # Prefer a pruned/custom build in models\nepcode, fall back to the base download. Skip vision projectors.
    foreach ($sub in "nepcode", "base") {
        $path = Join-Path $Root "$Dir\$sub"
        if (Test-Path $path) {
            $gguf = Get-ChildItem $path -Recurse -Filter *.gguf | Where-Object { $_.Name -notmatch "mmproj" } |
                Sort-Object Name | Select-Object -First 1   # first shard if split
            if ($gguf) { return $gguf.FullName }
        }
    }
    throw "No .gguf model found under $Dir\nepcode or $Dir\base. Run setup.ps1 first."
}
