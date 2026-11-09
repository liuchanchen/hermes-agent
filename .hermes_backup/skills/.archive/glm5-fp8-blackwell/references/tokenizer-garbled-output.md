# Tokenizer Detokenization Issue — Debugging Notes

## Symptom

The vLLM server responds to requests with garbled text output:

```
content: " belleparticipants(Point方的UIButton被_emb libertsthrough GetMessage..."
```

This is **deterministic** — same input always produces the same garbled output. The pattern
starts consistently suggesting the model is generating valid token IDs but vLLM's detokenizer
decodes them incorrectly.

**Verified**: Token IDs are generated correctly (the model works). The issue is only in the
decode/detokenize step.

## Confirmed: Standalone Tokenizer Works

```python
from transformers import AutoTokenizer
t = AutoTokenizer.from_pretrained("/data/models/glm_5_1_fp8", trust_remote_code=True)
t.encode("Hello, how are you?", add_special_tokens=False)   # [9703, 11, 1246, 525, 498, 30]
t.decode([9703, 11, 1246, 525, 498, 30])                     # "Hello, how are you?" ✅
```

The HuggingFace `AutoTokenizer` round-trips correctly. The issue is in vLLM's internal tokenizer path.

## vLLM Tokenizer Backend

vLLM wraps tokenizers in `CachedTokenizersBackend` (`vllm.tokenizers`). Even with `--tokenizer-mode hf`,
the V1 engine may use a different codepath internally for decode:

```python
from vllm.tokenizers import get_tokenizer
tok = get_tokenizer("/data/models/glm_5_1_fp8", trust_remote_code=True, tokenizer_mode="hf")
tok.decode([9703, 11, 1246, 525, 498, 30])  # "Hello, how are you?" ✅ (works standalone)
```

The standalone vLLM tokenizer also works. The problem is in the **server's HTTP response path**.

## Suspect: GLM Tokenizer Backend Type

The GLM tokenizer is a `TokenizersBackend` (HuggingFace `tokenizers` Rust-backed):

```python
AutoTokenizer.from_pretrained(...)  # returns <class 'transformers.TokenizersBackend'>
```

This backend uses `tokenizer.json` with BPE configuration. The garbled output is consistent
with the byte-level BPE decoder not being properly initialized in vLLM's server context.

`--tokenizer-mode hf` sets `tokenizer_mode` to HuggingFace but the V1 engine's `EngineCore`
process may re-initialize the tokenizer separately with a different backend.

## Attempted Fixes (none worked)

| Fix | Result |
|-----|--------|
| `--tokenizer-mode auto` | Garbled |
| `--tokenizer-mode hf` | Garbled |
| Both with `--trust-remote-code` | Garbled |
| `--tokenizer-mode slow` | Might work (untested on this model) |

## Untested Approaches

1. **`--tokenizer-mode slow`**: Forces pure-Python HuggingFace tokenizer. May bypass the
   `tokenizers` Rust backend that's causing the issue. Available in vLLM V1.

2. **`--skip-tokenizer-init`**: Skips vLLM's internal tokenizer entirely. Client must handle
   tokenization. Set `tokenizer_mode` param on each request instead.

3. **Inspect `CachedTokenizersBackend.decode()`**: The vLLM server uses `decode()` from
   `vllm.tokenizers` which may apply post-processing differently than HuggingFace.

4. **Custom tokenizer script**: Write a custom wrapper that delegates to
   `AutoTokenizer.from_pretrained()` for decode calls.
