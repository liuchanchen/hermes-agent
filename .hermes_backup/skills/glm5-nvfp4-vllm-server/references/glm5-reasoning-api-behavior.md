# GLM-5.1-NVFP4 Reasoning API Behavior

## Context

Server started with `--reasoning-parser glm45 --tool-call-parser glm47` flags on GLM-5.1-NVFP4 (NVFP4 quantization). This is a GLM-proprietary reasoning mode separate from OpenAI-compatible structured output.

## Endpoint Behavior

### `/v1/chat/completions`

Returns the reasoning chain in the `reasoning` field and `content` as `null` because all token budget is consumed by the thinking process:

```json
{
  "choices": [{
    "message": {
      "reasoning": "1. **分析请求:** ...\n2. **确定答案:** ...\n3. **构建输出:** ...",
      "content": null,
      "tool_calls": []
    }
  }]
}
```

**With `reasoning_effort`** (request-time parameter):
- `reasoning_effort: "high"` (default) — verbose step-by-step thinking
- `reasoning_effort: "low"` — shorter reasoning; same `content: null` behavior

**Effect on `finish_reason`:**
- `length` (hit max_tokens) — reasoning consumes the entire token budget; `content` stays null
- `stop` — model chose to stop before token limit

### `/v1/completions` (plain completion)

Gives the **final answer only**, no reasoning field:

```json
{
  "choices": [{
    "text": "量子计算利用量子叠加和纠缠，实现并行计算，指数级提升特定问题的求解速度。",
    "finish_reason": "stop"
  }]
}
```

This is the correct endpoint for:
- Clean output without thinking trace
- Health check probes (no `null` content to interpret)
- Any downstream consumer expecting plain text

## Diagnostic Pattern

```bash
# PROBE: use /v1/completions — gives clean text, no null content ambiguity
curl -s -X POST http://localhost:8000/v1/completions \
  -H "Content-Type: application/json" \
  -d '{"model":"glm5_1_fp8","prompt":"量子计算的核心原理是什么？","max_tokens":100,"temperature":0}'

# DEBUG: use /v1/chat/completions — reveals reasoning chain
curl -s -X POST http://localhost:8000/v1/chat/completions \
  -H "Content-Type: application/json" \
  -d '{"model":"glm5_1_fp8","messages":[{"role":"user","content":"量子计算的核心原理是什么？"}],"max_tokens":200}'
```

## GPU Utilization During Inference

During generation on TP=8 single-node:
- Cards 0,1,3,4,6,7: ~98% GPU util (active TP workers)
- Cards 2,5: ~80% (slightly less load)
- All cards: ~87,117 MiB (~89%) memory occupied

## Historical Log (2026-06-08)

Tested with short (50 tokens, ~2.3s TTFT), medium (150 tokens, ~1.6s), long (300 tokens). All responded correctly. Server is healthy.

## Related

- `--reasoning-parser glm45` — server-side flag, always active when server started via `start_glm5_nvfp4.sh`
- `--tool-call-parser glm47` — enables structured tool calls; tool_calls array empty unless client sends tool definitions
- GLM-5.1-FP8 (FP8 model) may have different reasoning behavior — verify separately if using a different model