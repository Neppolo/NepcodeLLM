import json
import sys
from pathlib import Path

import numpy as np
from gguf import GGUFReader

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "pruning"))
sys.path.insert(0, str(Path(__file__).resolve().parent))

import tiny_moe  # noqa: E402
from prune_experts import expert_scores, is_expert_tensor, prune  # noqa: E402


def fake_scores(n_layer: int, n_expert: int, weak: list[int]) -> dict:
    layers = {}
    for il in range(n_layer):
        score_sum = [0.0 if j in weak else 10.0 + j for j in range(n_expert)]
        layers[str(il)] = {"score_sum": score_sum, "count": [5] * n_expert}
    return {"n_expert": n_expert, "layers": layers}


def test_is_expert_tensor():
    assert is_expert_tensor("ffn_down_exps.weight")
    assert is_expert_tensor("ffn_gate_up_exps.weight")
    assert is_expert_tensor("ffn_gate_inp.weight")
    assert not is_expert_tensor("ffn_gate_inp_shexp.weight")
    assert not is_expert_tensor("ffn_down_shexp.weight")
    assert not is_expert_tensor("attn_q.weight")


def test_expert_scores_criteria():
    layer = {"score_sum": [6.0, 0.0, 3.0], "count": [3, 0, 1]}
    assert expert_scores(layer, "reap").tolist() == [2.0, 0.0, 3.0]
    assert expert_scores(layer, "ean").tolist() == [6.0, 0.0, 3.0]
    assert expert_scores(layer, "freq").tolist() == [3.0, 0.0, 1.0]


def test_prune_removes_weak_experts_bit_exactly(tmp_path: Path):
    src = tiny_moe.build(tmp_path / "tiny.gguf")
    dst = tmp_path / "pruned.gguf"
    weak = [1, 4, 6]
    prune(src, dst, fake_scores(tiny_moe.N_LAYER, tiny_moe.N_EXPERT, weak), n_keep=5, criterion="reap")

    a, b = GGUFReader(src), GGUFReader(dst)
    assert b.get_field("qwen3moe.expert_count").contents() == 5
    kept = [j for j in range(tiny_moe.N_EXPERT) if j not in weak]
    ta = {t.name: t for t in a.tensors}
    for t in b.tensors:
        src_t = ta[t.name]
        assert t.tensor_type == src_t.tensor_type
        if "_exps" in t.name or "ffn_gate_inp" in t.name:
            assert t.data.shape[0] == 5
            assert np.array_equal(t.data, src_t.data[kept])
        else:
            assert np.array_equal(t.data, src_t.data)
    # untouched metadata is carried over
    assert b.get_field("qwen3moe.block_count").contents() == tiny_moe.N_LAYER
    assert len(b.get_field("tokenizer.ggml.tokens").contents()) == 16


def test_prune_rejects_missing_layer_scores(tmp_path: Path):
    src = tiny_moe.build(tmp_path / "tiny.gguf")
    scores = fake_scores(tiny_moe.N_LAYER, tiny_moe.N_EXPERT, [0])
    del scores["layers"]["1"]
    try:
        prune(src, tmp_path / "out.gguf", scores, n_keep=6, criterion="reap")
    except SystemExit as e:
        assert "no scores for MoE layers [1]" in str(e)
    else:
        raise AssertionError("expected SystemExit")


def test_scores_file_roundtrip(tmp_path: Path):
    p = tmp_path / "s.json"
    p.write_text(json.dumps(fake_scores(1, 4, [2])))
    assert json.loads(p.read_text())["layers"]["0"]["score_sum"][2] == 0.0
