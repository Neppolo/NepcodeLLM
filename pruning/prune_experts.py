"""Remove low-saliency MoE experts from a GGUF model, directly on the quantized file.

Each expert is a contiguous slice of the `blk.N.ffn_*_exps` tensors (and a row of the router `ffn_gate_inp`),
so dropping experts is exact byte surgery: the kept experts are bit-identical to the input, nothing is
re-quantized, and it runs in minutes on a normal PC.

Scores come from `llama-reap-score` (pruning/reap-score). The same number of experts is removed from every
layer because llama.cpp requires one `expert_count` for the whole model.

Usage:
  python pruning/prune_experts.py models/base/model.gguf --scores reap-scores.json --ratio 0.3 \
      -o models/nepcode/nepcode-reap30.gguf
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

import numpy as np
from gguf import GGUFReader, GGUFValueType, GGUFWriter, Keys

_BLOCK = re.compile(r"^blk\.(\d+)\.(.+)$")


def is_expert_tensor(suffix: str) -> bool:
    """Tensors indexed by expert along their outermost dimension. Shared-expert tensors (`*_shexp`) are kept."""
    if "shexp" in suffix:
        return False
    return "_exps" in suffix or suffix.startswith("ffn_gate_inp.") or suffix.startswith("exp_probs_b")


def expert_scores(layer: dict, criterion: str) -> np.ndarray:
    total = np.asarray(layer["score_sum"], dtype=np.float64)
    count = np.asarray(layer["count"], dtype=np.float64)
    if criterion == "reap":  # mean router-weighted output norm over routed tokens (the REAP paper criterion)
        return np.divide(total, count, out=np.zeros_like(total), where=count > 0)
    if criterion == "ean":  # summed contribution: also rewards frequently used experts
        return total
    if criterion == "freq":
        return count
    raise ValueError(criterion)


def select_experts(scores: dict, n_expert: int, n_keep: int, criterion: str) -> dict[int, np.ndarray]:
    keep = {}
    for il, layer in scores["layers"].items():
        s = expert_scores(layer, criterion)
        if len(s) != n_expert:
            raise SystemExit(f"layer {il}: {len(s)} scores but the model has {n_expert} experts")
        # highest scores survive; keep original order so expert ids stay monotonic
        keep[int(il)] = np.sort(np.argsort(-s, kind="stable")[:n_keep])
    return keep


def prune(src: Path, dst: Path, scores: dict, n_keep: int, criterion: str) -> None:
    reader = GGUFReader(src)
    arch = reader.get_field(Keys.General.ARCHITECTURE).contents()
    if reader.get_field("split.count") is not None:
        raise SystemExit("split GGUF input is not supported: merge it first with llama-gguf-split --merge")

    count_key = Keys.LLM.EXPERT_COUNT.format(arch=arch)
    used_key = Keys.LLM.EXPERT_USED_COUNT.format(arch=arch)
    n_expert = int(reader.get_field(count_key).contents())
    n_used = int(reader.get_field(used_key).contents())
    if not n_used < n_keep < n_expert:
        raise SystemExit(f"must keep between {n_used + 1} and {n_expert - 1} experts, got {n_keep}")

    keep = select_experts(scores, n_expert, n_keep, criterion)
    expert_layers = {int(m.group(1)) for t in reader.tensors if (m := _BLOCK.match(t.name)) and is_expert_tensor(m.group(2))}
    missing = sorted(expert_layers - keep.keys())
    if missing:
        raise SystemExit(
            f"no scores for MoE layers {missing}. If these are multi-token-prediction layers, use a GGUF without MTP."
        )

    writer = GGUFWriter(dst, arch=arch)
    for field in reader.fields.values():
        if field.name == Keys.General.ARCHITECTURE or field.name.startswith("GGUF."):
            continue
        val_type = field.types[0]
        sub_type = field.types[-1] if val_type == GGUFValueType.ARRAY else None
        value = n_keep if field.name == count_key else field.contents()
        writer.add_key_value(field.name, value, val_type, sub_type=sub_type)
    writer.add_string("nepcode.pruning", f"{criterion}: kept {n_keep}/{n_expert} experts per layer")

    def out_data(tensor):
        m = _BLOCK.match(tensor.name)
        if m and is_expert_tensor(m.group(2)):
            if tensor.data.shape[0] != n_expert:
                raise SystemExit(f"{tensor.name}: expected {n_expert} experts on axis 0, shape {tensor.data.shape}")
            return np.ascontiguousarray(tensor.data[keep[int(m.group(1))]])
        return tensor.data

    for tensor in reader.tensors:
        shape = list(tensor.data.shape)
        m = _BLOCK.match(tensor.name)
        if m and is_expert_tensor(m.group(2)):
            shape[0] = n_keep
        itemsize = tensor.data.dtype.itemsize
        writer.add_tensor_info(tensor.name, shape, tensor.data.dtype, int(np.prod(shape)) * itemsize, tensor.tensor_type)

    writer.write_header_to_file()
    writer.write_kv_data_to_file()
    writer.write_ti_data_to_file()
    for i, tensor in enumerate(reader.tensors, 1):
        writer.write_tensor_data(out_data(tensor), tensor_endianess=reader.endianess)
        print(f"\r  {i}/{len(reader.tensors)} tensors", end="", file=sys.stderr)
    writer.close()
    print(file=sys.stderr)


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("model", type=Path)
    ap.add_argument("--scores", type=Path, required=True, help="JSON written by llama-reap-score")
    group = ap.add_mutually_exclusive_group(required=True)
    group.add_argument("--ratio", type=float, help="fraction of experts to remove per layer, e.g. 0.3")
    group.add_argument("--keep", type=int, help="number of experts to keep per layer")
    ap.add_argument("--criterion", choices=["reap", "ean", "freq"], default="reap")
    ap.add_argument("-o", "--output", type=Path, required=True)
    args = ap.parse_args()

    scores = json.loads(args.scores.read_text())
    n_expert = int(scores["n_expert"])
    n_keep = args.keep if args.keep is not None else n_expert - round(n_expert * args.ratio)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    prune(args.model, args.output, scores, n_keep, args.criterion)
    print(f"Wrote {args.output} ({n_keep}/{n_expert} experts per layer, {args.output.stat().st_size / 2**30:.2f} GiB)")


if __name__ == "__main__":
    main()
