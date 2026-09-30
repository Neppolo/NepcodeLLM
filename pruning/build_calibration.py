"""Build the calibration set that decides which MoE experts survive pruning (and drives the imatrix quant).

The set must look like real usage, not just raw code. Experts that never fire on it get pruned, so it mixes:
  - Java/Spring source files, framed as chat tasks (explain / review / write tests / refactor)
  - build + config files that appear in Java projects (pom.xml, Gradle, YAML, SQL, Dockerfile)
  - optional agentic traces (JSONL with OpenAI-style `messages`, incl. tool calls) so tool-use experts survive

Outputs:
  calibration.jsonl  - one {"messages": [...]} per line (for REAP)
  calibration.txt    - the same samples as plain text (for llama-imatrix)

Usage:
  python pruning/build_calibration.py --src path/to/repos --traces my_traces.jsonl --out data/calibration
"""

from __future__ import annotations

import argparse
import json
import random
from pathlib import Path

TASKS = {
    ".java": [
        "Review this Java class for bugs, security issues and best-practice violations. Rank findings by severity.",
        "Write JUnit 5 tests with AssertJ for this class.",
        "Explain what this code does and point out anything non-idiomatic for modern Java.",
        "Refactor this code to modern Java (records, pattern matching, sealed types) where it helps readability.",
    ],
    ".kt": ["Explain this Kotlin code and suggest improvements."],
    ".xml": ["Review this Maven POM: outdated plugins, missing version pins, dependency problems."],
    ".gradle": ["Review this Gradle build script and suggest improvements."],
    ".kts": ["Review this Gradle Kotlin DSL build script and suggest improvements."],
    ".yml": ["Review this Spring configuration for security and production-readiness issues."],
    ".yaml": ["Review this configuration for security and production-readiness issues."],
    ".properties": ["Review these Spring properties for security and production-readiness issues."],
    ".sql": ["Review this SQL / migration for correctness, indexing and performance."],
    "Dockerfile": ["Review this Dockerfile for size, security and caching best practices."],
}
# Relative weight of each extension group in the final mix (Java dominates, the rest keeps project context alive).
WEIGHTS = {".java": 0.70, ".xml": 0.05, ".gradle": 0.02, ".kts": 0.03, ".yml": 0.04, ".yaml": 0.02,
           ".properties": 0.02, ".sql": 0.05, ".kt": 0.03, "Dockerfile": 0.04}
SKIP_DIRS = {".git", "target", "build", "node_modules", ".gradle", ".idea", "out"}


def file_kind(path: Path) -> str | None:
    if path.name == "Dockerfile":
        return "Dockerfile"
    return path.suffix if path.suffix in TASKS else None


def collect(src_dirs: list[Path], min_chars: int, max_chars: int) -> dict[str, list[Path]]:
    by_kind: dict[str, list[Path]] = {k: [] for k in TASKS}
    for src in src_dirs:
        for path in src.rglob("*"):
            if not path.is_file() or SKIP_DIRS.intersection(path.relative_to(src).parts):
                continue
            kind = file_kind(path)
            if kind and min_chars <= path.stat().st_size <= max_chars:
                by_kind[kind].append(path)
    return by_kind


def make_sample(path: Path, kind: str, rng: random.Random) -> dict:
    code = path.read_text(encoding="utf-8", errors="replace")
    lang = {"Dockerfile": "dockerfile", ".kts": "kotlin", ".kt": "kotlin"}.get(kind, kind.lstrip("."))
    prompt = f"{rng.choice(TASKS[kind])}\n\n`{path.name}`:\n```{lang}\n{code}\n```"
    return {"messages": [{"role": "user", "content": prompt}]}


def to_text(sample: dict) -> str:
    parts = []
    for m in sample["messages"]:
        content = m.get("content") or ""
        if m.get("tool_calls"):
            content += "\n" + json.dumps(m["tool_calls"])
        parts.append(f"<|{m['role']}|>\n{content}")
    return "\n".join(parts)


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--src", type=Path, nargs="+", required=True, help="directories with source repositories")
    ap.add_argument("--traces", type=Path, help="optional JSONL of agentic chats ({'messages': [...]})")
    ap.add_argument("--out", type=Path, default=Path("data/calibration"))
    ap.add_argument("--samples", type=int, default=1024, help="number of code samples (traces are added on top)")
    ap.add_argument("--min-chars", type=int, default=400)
    ap.add_argument("--max-chars", type=int, default=24_000)
    ap.add_argument("--seed", type=int, default=0)
    args = ap.parse_args()

    rng = random.Random(args.seed)
    by_kind = collect(args.src, args.min_chars, args.max_chars)
    samples: list[dict] = []
    for kind, weight in WEIGHTS.items():
        files = by_kind[kind]
        n = min(len(files), round(args.samples * weight))
        samples += [make_sample(p, kind, rng) for p in rng.sample(files, n)]
        print(f"{kind:12} {n:5} samples  (from {len(files)} files)")

    if args.traces:
        traces = [json.loads(line) for line in args.traces.read_text(encoding="utf-8").splitlines() if line.strip()]
        samples += traces
        print(f"{'traces':12} {len(traces):5} samples")

    rng.shuffle(samples)
    args.out.mkdir(parents=True, exist_ok=True)
    with open(args.out / "calibration.jsonl", "w", encoding="utf-8") as f:
        f.writelines(json.dumps(s, ensure_ascii=False) + "\n" for s in samples)
    (args.out / "calibration.txt").write_text("\n\n".join(to_text(s) for s in samples), encoding="utf-8")
    print(f"Wrote {len(samples)} samples to {args.out}")


if __name__ == "__main__":
    main()
