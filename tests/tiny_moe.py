"""Build a tiny random qwen3moe GGUF for testing the pruning tools (no downloads needed)."""

from __future__ import annotations

from pathlib import Path

import numpy as np
from gguf import GGMLQuantizationType, GGUFReader, GGUFValueType, GGUFWriter, quants

ARCH = "qwen3moe"
N_EMBD, N_HEAD, N_HEAD_KV, HEAD_DIM, N_FF_EXP, N_LAYER, N_EXPERT, N_USED = 64, 4, 2, 16, 32, 2, 8, 2


def build(path: Path, vocab_gguf: Path | None = None, dead_experts: tuple[int, ...] = (), seed: int = 0) -> Path:
    """Experts listed in `dead_experts` get all-zero down projections, so their REAP score is 0.

    Expert tensors are Q8_0 to exercise byte slicing of quantized data. With `vocab_gguf` (a llama.cpp
    ggml-vocab-*.gguf) the tokenizer is copied in so llama.cpp can run the model; otherwise a dummy is used.
    """
    rng = np.random.default_rng(seed)
    w = GGUFWriter(path, arch=ARCH)
    w.add_block_count(N_LAYER)
    w.add_context_length(4096)
    w.add_embedding_length(N_EMBD)
    w.add_feed_forward_length(N_FF_EXP)
    w.add_head_count(N_HEAD)
    w.add_head_count_kv(N_HEAD_KV)
    w.add_key_length(HEAD_DIM)
    w.add_value_length(HEAD_DIM)
    w.add_rope_freq_base(1e6)
    w.add_layer_norm_rms_eps(1e-6)
    w.add_expert_count(N_EXPERT)
    w.add_expert_used_count(N_USED)
    w.add_expert_feed_forward_length(N_FF_EXP)

    if vocab_gguf:
        vr = GGUFReader(vocab_gguf)
        for f in vr.fields.values():
            if f.name.startswith("tokenizer."):
                sub = f.types[-1] if f.types[0] == GGUFValueType.ARRAY else None
                w.add_key_value(f.name, f.contents(), f.types[0], sub_type=sub)
        n_vocab = len(vr.get_field("tokenizer.ggml.tokens").contents())
    else:
        n_vocab = 16
        w.add_tokenizer_model("gpt2")
        w.add_token_list([f"t{i}" for i in range(n_vocab)])

    def f32(*shape):
        return (rng.standard_normal(shape) * 0.05).astype(np.float32)

    def q8(arr):
        return quants.quantize(arr, GGMLQuantizationType.Q8_0), GGMLQuantizationType.Q8_0

    w.add_tensor("token_embd.weight", f32(n_vocab, N_EMBD))
    w.add_tensor("output_norm.weight", np.ones(N_EMBD, np.float32))
    w.add_tensor("output.weight", f32(n_vocab, N_EMBD))
    for i in range(N_LAYER):
        p = f"blk.{i}."
        w.add_tensor(p + "attn_norm.weight", np.ones(N_EMBD, np.float32))
        w.add_tensor(p + "attn_q.weight", f32(N_HEAD * HEAD_DIM, N_EMBD))
        w.add_tensor(p + "attn_k.weight", f32(N_HEAD_KV * HEAD_DIM, N_EMBD))
        w.add_tensor(p + "attn_v.weight", f32(N_HEAD_KV * HEAD_DIM, N_EMBD))
        w.add_tensor(p + "attn_output.weight", f32(N_EMBD, N_HEAD * HEAD_DIM))
        w.add_tensor(p + "attn_q_norm.weight", np.ones(HEAD_DIM, np.float32))
        w.add_tensor(p + "attn_k_norm.weight", np.ones(HEAD_DIM, np.float32))
        w.add_tensor(p + "ffn_norm.weight", np.ones(N_EMBD, np.float32))
        w.add_tensor(p + "ffn_gate_inp.weight", f32(N_EXPERT, N_EMBD))
        for name, shape in (("ffn_gate_exps", (N_EXPERT, N_FF_EXP, N_EMBD)), ("ffn_up_exps", (N_EXPERT, N_FF_EXP, N_EMBD))):
            data, qtype = q8(f32(*shape))
            w.add_tensor(p + name + ".weight", data, raw_dtype=qtype)
        down = f32(N_EXPERT, N_EMBD, N_FF_EXP)
        down[list(dead_experts)] = 0.0
        data, qtype = q8(down)
        w.add_tensor(p + "ffn_down_exps.weight", data, raw_dtype=qtype)

    w.write_header_to_file()
    w.write_kv_data_to_file()
    w.write_tensors_to_file()
    w.close()
    return path
