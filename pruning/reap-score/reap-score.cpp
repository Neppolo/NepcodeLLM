// llama-reap-score: collect REAP expert saliency scores for a MoE GGUF model, on your own GPU.
//
// REAP (Router-weighted Expert Activation Pruning, Cerebras, ICLR 2026) scores expert j of a layer as the mean,
// over the calibration tokens routed to j, of  g_j(x) * ||f_j(x)||_2  (router weight times expert output norm).
// Low-score experts contribute little and are pruned by pruning/prune_experts.py.
//
// Because this reads the already-quantized GGUF through llama.cpp (with --n-cpu-moe offload), it needs no BF16
// checkpoint and no big GPU. It hooks three tensors that llama.cpp's MoE graph names per layer:
//   ffn_moe_topk-N          selected expert ids        I32 [n_used, n_tokens]
//   ffn_moe_weights[_norm]-N  their final router weights F32 [1, n_used, n_tokens]
//   ffn_moe_down-N          per-expert outputs         F32 [n_embd, n_used, n_tokens] (before weighting)
//
// Usage: llama-reap-score -m model.gguf -f calibration.txt -o reap-scores.json -c 512 -ngl 999 --n-cpu-moe 30

#include "arg.h"
#include "common.h"
#include "log.h"
#include "llama.h"
#include "ggml.h"
#include "ggml-backend.h"

#include <cinttypes>
#include <cmath>
#include <cstdio>
#include <cstring>
#include <map>
#include <string>
#include <vector>

struct layer_stats {
    std::vector<double>  score_sum;  // sum of g * ||f|| over routed tokens
    std::vector<int64_t> count;      // number of routed tokens
    std::vector<int32_t> topk;       // pending ids for the current ubatch
    std::vector<float>   weights;    // pending weights for the current ubatch
    int64_t n_used = 0, n_tokens = 0;
};

struct collector {
    std::map<int, layer_stats> layers;
    int64_t n_expert = 0;
    std::vector<uint8_t> buf;
    bool warned_order = false;
};

static bool parse_name(const char * name, std::string & kind, int & il) {
    const char * dash = strrchr(name, '-');
    if (!dash || strncmp(name, "ffn_moe_", 8) != 0) return false;
    kind.assign(name, dash - name);
    il = atoi(dash + 1);
    return kind == "ffn_moe_topk" || kind == "ffn_moe_weights" || kind == "ffn_moe_weights_norm" ||
           kind == "ffn_moe_down";
}

// Copy a (possibly strided, possibly device-resident) tensor to host memory.
static const uint8_t * fetch(collector & c, const ggml_tensor * t) {
    const size_t nbytes = ggml_nbytes(t);
    if (ggml_backend_buffer_is_host(t->buffer)) return (const uint8_t *) t->data;
    c.buf.resize(nbytes);
    ggml_backend_tensor_get(t, c.buf.data(), 0, nbytes);
    return c.buf.data();
}

static bool cb_eval(struct ggml_tensor * t, bool ask, void * user_data) {
    std::string kind;
    int il;
    if (!parse_name(t->name, kind, il)) return ask ? false : true;
    if (ask) return true;

    auto & c = *(collector *) user_data;
    auto & L = c.layers[il];
    const uint8_t * d = fetch(c, t);

    if (kind == "ffn_moe_topk") {
        GGML_ASSERT(t->type == GGML_TYPE_I32);
        L.n_used = t->ne[0];
        L.n_tokens = t->ne[1];
        L.topk.resize(L.n_used * L.n_tokens);
        for (int64_t tok = 0; tok < L.n_tokens; ++tok)
            for (int64_t k = 0; k < L.n_used; ++k)
                L.topk[tok * L.n_used + k] = *(const int32_t *) (d + k * t->nb[0] + tok * t->nb[1]);
        L.weights.clear();
    } else if (kind == "ffn_moe_weights" || kind == "ffn_moe_weights_norm") {
        // _norm (if the model renormalizes top-k weights) arrives after the raw weights and overrides them.
        GGML_ASSERT(t->type == GGML_TYPE_F32);
        const bool is_3d = t->ne[0] == 1;  // raw: [1, n_used, n_tokens]; norm: [n_used, n_tokens]
        const int64_t n_used = is_3d ? t->ne[1] : t->ne[0];
        const int64_t n_tok  = is_3d ? t->ne[2] : t->ne[1];
        const size_t s_k   = is_3d ? t->nb[1] : t->nb[0];
        const size_t s_tok = is_3d ? t->nb[2] : t->nb[1];
        L.weights.resize(n_used * n_tok);
        for (int64_t tok = 0; tok < n_tok; ++tok)
            for (int64_t k = 0; k < n_used; ++k)
                L.weights[tok * n_used + k] = *(const float *) (d + k * s_k + tok * s_tok);
    } else {  // ffn_moe_down
        GGML_ASSERT(t->type == GGML_TYPE_F32);
        const int64_t n_embd = t->ne[0], n_used = t->ne[1], n_tok = t->ne[2];
        if (L.topk.size() != (size_t) (n_used * n_tok) || L.weights.size() != L.topk.size()) {
            if (!c.warned_order) {
                LOG_WRN("layer %d: expert ids/weights missing for this ubatch, skipping (graph fusion?)\n", il);
                c.warned_order = true;
            }
            return true;
        }
        for (int64_t tok = 0; tok < n_tok; ++tok) {
            for (int64_t k = 0; k < n_used; ++k) {
                const uint8_t * row = d + k * t->nb[1] + tok * t->nb[2];
                double ss = 0.0;
                for (int64_t e = 0; e < n_embd; ++e) {
                    const float v = *(const float *) (row + e * t->nb[0]);
                    ss += (double) v * v;
                }
                const int32_t j = L.topk[tok * n_used + k];
                if (j < 0 || j >= c.n_expert) continue;
                L.score_sum[j] += L.weights[tok * n_used + k] * std::sqrt(ss);
                L.count[j] += 1;
            }
        }
        L.topk.clear();
        L.weights.clear();
    }
    return true;
}

static bool write_json(const collector & c, const std::string & path, const char * model_path, int64_t n_tokens) {
    FILE * f = fopen(path.c_str(), "w");
    if (!f) return false;
    fprintf(f, "{\n  \"method\": \"reap\",\n  \"model\": \"%s\",\n  \"n_expert\": %" PRId64 ",\n  \"n_tokens\": %" PRId64
               ",\n  \"layers\": {", model_path, c.n_expert, n_tokens);
    bool first_layer = true;
    for (const auto & [il, L] : c.layers) {
        if (L.count.empty()) continue;
        fprintf(f, "%s\n    \"%d\": {\"score_sum\": [", first_layer ? "" : ",", il);
        for (int64_t j = 0; j < c.n_expert; ++j) fprintf(f, "%s%.6g", j ? ", " : "", L.score_sum[j]);
        fprintf(f, "], \"count\": [");
        for (int64_t j = 0; j < c.n_expert; ++j) fprintf(f, "%s%" PRId64, j ? ", " : "", L.count[j]);
        fprintf(f, "]}");
        first_layer = false;
    }
    fprintf(f, "\n  }\n}\n");
    fclose(f);
    return true;
}

int main(int argc, char ** argv) {
    common_params params;
    params.out_file = "reap-scores.json";
    params.n_ctx = 512;  // all tokens produce logits (see below), so keep chunks small: 512 x vocab floats
    params.escape = false;

    common_init();
    if (!common_params_parse(argc, argv, params, LLAMA_EXAMPLE_IMATRIX)) return 1;
    if (params.prompt.empty()) {
        LOG_ERR("provide the calibration text with -f calibration.txt\n");
        return 1;
    }
    const int n_ctx = params.n_ctx;
    params.n_batch = std::max(params.n_batch, n_ctx);
    params.n_parallel = 1;
    params.warmup = false;

    collector c;
    params.cb_eval = cb_eval;
    params.cb_eval_user_data = &c;

    llama_backend_init();
    llama_numa_init(params.numa);
    auto init = common_init_from_params(params);
    llama_model * model = init->model();
    llama_context * ctx = init->context();
    if (!model || !ctx) {
        LOG_ERR("failed to load model\n");
        return 1;
    }

    // Number of experts from GGUF metadata "<arch>.expert_count".
    char arch[64] = {0}, val[64] = {0};
    llama_model_meta_val_str(model, "general.architecture", arch, sizeof(arch));
    if (llama_model_meta_val_str(model, (std::string(arch) + ".expert_count").c_str(), val, sizeof(val)) < 0 ||
        atoll(val) <= 0) {
        LOG_ERR("model '%s' is not a mixture-of-experts model\n", arch);
        return 1;
    }
    c.n_expert = atoll(val);

    std::vector<llama_token> tokens = common_tokenize(ctx, params.prompt, true, params.parse_special);
    const int64_t n_chunk = (int64_t) tokens.size() / n_ctx;
    if (n_chunk == 0) {
        LOG_ERR("calibration text is shorter than one context (%d tokens)\n", n_ctx);
        return 1;
    }
    LOG_INF("arch=%s n_expert=%" PRId64 " tokens=%zu chunks=%" PRId64 " x %d\n", arch, c.n_expert, tokens.size(),
            n_chunk, n_ctx);

    // Size the stats before any callback writes to them.
    const int n_layer = llama_model_n_layer(model);
    for (int il = 0; il < n_layer; ++il) {
        c.layers[il].score_sum.assign(c.n_expert, 0.0);
        c.layers[il].count.assign(c.n_expert, 0);
    }

    llama_batch batch = llama_batch_init(n_ctx, 0, 1);
    const int64_t t_start = ggml_time_us();
    for (int64_t i = 0; i < n_chunk; ++i) {
        llama_memory_clear(llama_get_memory(ctx), true);
        common_batch_clear(batch);
        for (int p = 0; p < n_ctx; ++p) {
            // Request outputs for every token: otherwise llama.cpp computes the last layer only for output rows.
            common_batch_add(batch, tokens[i * n_ctx + p], p, {0}, true);
        }
        if (llama_decode(ctx, batch)) {
            LOG_ERR("llama_decode failed on chunk %" PRId64 "\n", i);
            return 1;
        }
        const double elapsed = (ggml_time_us() - t_start) / 1e6;
        LOG_INF("chunk %" PRId64 "/%" PRId64 "  %.0f tok/s  ETA %.0f s\n", i + 1, n_chunk,
                (i + 1) * n_ctx / elapsed, elapsed / (i + 1) * (n_chunk - i - 1));
        if ((i + 1) % 10 == 0) write_json(c, params.out_file, params.model.path.c_str(), (i + 1) * n_ctx);
    }
    llama_batch_free(batch);

    if (!write_json(c, params.out_file, params.model.path.c_str(), n_chunk * n_ctx)) {
        LOG_ERR("cannot write %s\n", params.out_file.c_str());
        return 1;
    }
    LOG_INF("wrote %s\n", params.out_file.c_str());
    llama_backend_free();
    return 0;
}
