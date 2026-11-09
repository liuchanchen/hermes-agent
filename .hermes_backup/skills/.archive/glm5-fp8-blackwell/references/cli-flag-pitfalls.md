# Reference: CLI Flag Interaction Pitfalls for GLM

## --reasoning-parser glm45 + --tool-call-parser glm47

These flags are designed for DeepSeek models (deepseek_v4). When used with GLM:

- `--reasoning-parser glm45` applies DeepSeek-V4-style thinking/response splitting to output
- The parser heuristically searches for "thinking" / "response" markers in generated text
- GLM output does NOT contain these markers, so the parser treats ALL generated content as "reasoning"
- Result: output goes to `reasoning`/`reasoning_content` fields, `content` stays null

**Fix**: Remove both `--reasoning-parser glm45` and `--tool-call-parser glm47` when serving GLM models.

## --chat-template-content-format string

This flag changes how the chat template handles content parts. Setting it to `string` forces single-string content instead of structured content parts. This is compatible with GLM's Jinja template but does NOT affect the garbled detokenization issue (which happens at the BPE decode level, not the template level).

## --enable-auto-tool-choice

Enables automatic tool-call detection in the output. For models without native tool-call formatting (like GLM), this is safe to enable but has no effect since no tool definitions are provided.

## Verdict for Production

The minimal working flag set for GLM-5.1-FP8 on Blackwell:

```
--attention-backend TRITON_MLA
--kv-cache-dtype fp8
--block-size 64
--max-model-len 65536
--gpu-memory-utilization 0.88
--enforce-eager
--tokenizer-mode hf
--hf-overrides '{"index_topk": 0}'
```

Do NOT add: `--reasoning-parser`, `--tool-call-parser`, `--chat-template-content-format` (unless testing).
