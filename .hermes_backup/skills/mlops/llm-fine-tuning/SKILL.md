---
name: llm-fine-tuning
description: LLM fine-tuning and post-training — YAML configs (Axolotl), fast LoRA (Unsloth), TRL RLHF/DPO/GRPO, structured generation (Outlines), and refusal ablation (Obliteratus)
version: 1.0.0
author: curator
license: MIT
platforms: [linux]
metadata:
  hermes:
    tags: [MLOps, Fine-tuning, LoRA, QLoRA, RLHF, DPO, GRPO, Structured-output, Refusal-ablation]
    homepage: ""
---

# LLM Fine-Tuning & Post-Training

Umbrella skill for fine-tuning and post-training workflows on LLMs. Covers the full pipeline from YAML-based fine-tuning configuration (Axolotl), through accelerated LoRA/QLoRA training (Unsloth) and RLHF alignment (TRL), to post-training modifications like structured output grammar-guiding (Outlines) and refusal behaviour removal (Obliteratus).

## When to use

- You need to fine-tune an LLM for a domain or task.
- You want LoRA/QLoRA for memory-efficient training.
- You need RLHF / DPO / GRPO preference alignment.
- You need constrained/structure text generation via grammar-based token filtering.
- You want to ablate refusal behaviors from an open-weight model.

## Quick reference

| Tool | Use case | Key command |
|------|----------|-------------|
| **Axolotl** | YAML-driven full or LoRA fine-tuning, 100+ model support, multimodal | `accelerate launch -m axolotl.cli.train config.yml` |
| **Unsloth** | 2-5× faster LoRA/QLoRA training, reduced VRAM | Install via pip, use `FastLanguageModel` |
| **TRL** | Python-driven RLHF (SFT→DPO/PPO/GRPO) | `SFTTrainer`, `DPOTrainer`, `GRPOTrainer` from `trl` |
| **Outlines** | Structured JSON/regex/Pydantic generation via FSM token filtering | `outlines.generate.json(model, schema)` |
| **Obliteratus** | Ablate refusals from open-weight models via diff-in-means | `obliteratus obliterate <model> --method advanced` |

---

## 1. Axolotl — YAML-based LLM Fine-tuning

Common patterns for Axolotl:

```yaml
base_model: mistralai/Mistral-7B-v0.1
model_type: MistralForCausalLM
tokenizer_type: LlamaTokenizer
load_in_8bit: false
load_in_4bit: true
strict: false
chat_template: mistral
datasets:
  - path: dataset.jsonl
    type: sharegpt
    conversation: mistral
val_set_size: 0.05
output_dir: ./lora-out
sequence_len: 4096
sample_packing: true
lora_r: 32
lora_alpha: 64
lora_modules_to_save:
  - embed_tokens
  - lm_head
lora_target_modules:
  - q_proj
  - k_proj
  - v_proj
  - o_proj
  - gate_proj
  - up_proj
  - down_proj
micro_batch_size: 2
gradient_accumulation_steps: 4
num_epochs: 3
optimizer: paged_adamw_8bit
lr_scheduler: cosine
learning_rate: 2e-4
train_on_inputs: false
group_by_length: false
bf16: true
tf32: true
gradient_checkpointing: true
logging_steps: 1
flash_attention: true
deeppeed: deepspeed_configs/zero2.json
save_safetensors: true  # critical for multi-GPU
```

Key paths: FSDP config, context_parallel_size, save_compressed for Azure Blob upload.

## 2. Unsloth — Accelerated LoRA/QLoRA

```python
from unsloth import FastLanguageModel
model, tokenizer = FastLanguageModel.from_pretrained(
    model_name="unsloth/mistral-7b-bnb-4bit",
    max_seq_length=4096,
    dtype=None,
    load_in_4bit=True,
)
model = FastLanguageModel.get_peft_model(
    model,
    r=16,
    target_modules=["q_proj", "k_proj", "v_proj", "o_proj",
                    "gate_proj", "up_proj", "down_proj"],
    lora_alpha=16,
    lora_dropout=0,
    bias="none",
    use_gradient_checkpointing="unsloth",
    random_state=3407,
)
```

Unsloth is a drop-in replacement for HuggingFace trainer with optimized Triton kernels. Works with Qwen, Llama, Mistral, Gemma, Yi, DeepSeek.

## 3. TRL — RLHF / DPO / GRPO Alignment

### SFT (Supervised Fine-tuning)
```python
from trl import SFTTrainer
trainer = SFTTrainer(
    model=model,
    train_dataset=dataset,
    tokenizer=tokenizer,
    args=transformers.TrainingArguments(
        output_dir="./sft-out",
        per_device_train_batch_size=4,
        num_train_epochs=3,
        bf16=True,
    ),
)
trainer.train()
```

### DPO (Preference Alignment)
```python
from trl import DPOTrainer
trainer = DPOTrainer(
    model=model,
    ref_model=ref_model,
    train_dataset=pref_dataset,  # {prompt, chosen, rejected}
    tokenizer=tokenizer,
    args=TrainingArguments(output_dir="./dpo-out"),
)
trainer.train()
```

### GRPO (Group-relative Policy Optimization)
```python
from trl import GRPOTrainer
GRPOTrainer(
    model="Qwen/Qwen2.5-1.5B-Instruct",
    reward_funcs=[reward_func],
    train_dataset=dataset,
    args=GRPOConfig(
        output_dir="./grpo-out",
        num_iterations=1,
        beta=0.04,
        max_prompt_length=512,
    ),
)
```

Key advantages: GRPO online RL runs without a critic model (group-relative advantage estimation). Reward functions can combine correctness + formatting + style.

### Method selection guide:
- **Need supervised instruction tuning?** → SFTTrainer
- **Have preference pairs (chosen/rejected)?** → DPOTrainer
- **Need online RL with reward function (math, coding)?** → GRPOTrainer
- **Want PPO with critic?** → PPOTrainer (3 models, high VRAM)

## 4. Outlines — Structured Generation

```python
from outlines import models, generate

model = models.transformers("mistralai/Mistral-7B-v0.1")

# JSON schema
from pydantic import BaseModel
class Character(BaseModel):
    name: str
    age: int
    traits: list[str]

generator = generate.json(model, Character)
result = generator("Create a fantasy character")

# Regex-guided
generator = generate.regex(model, r"\d{3}-\d{3}-\d{4}")
result = generator("My phone number is")
```

Outlines converts schema → CFG → FSM at compilation time. Zero-overhead at inference (FSM compiled once, cached). Supports Transformers, llama.cpp, vLLM, and OpenAI backends.

## 5. Obliteratus — Refusal Ablation

```bash
# Basic ablation (default)
obliteratus obliterate meta-llama/Llama-3.1-8B-Instruct \
  --method advanced

# For MoE models
obliteratus obliterate <model> --method nuclear

# For reasoning models
obliteratus obliterate <model> --method surgical

# With 4-bit quantization to reduce VRAM
obliteratus obliterate <model> --method advanced \
  --quantization bitsandbytes-nf4
```

AGPL-3.0 licensed. Methods target different model architectures. Verification: `obliteratus test <model>` checks refusal rate (<5%) and perplexity change (<10%).

---

## Pitfalls

- **Axolotl with DeepSpeed** — set `save_safetensors: true` or multi-GPU saves may fail.
- **Unsloth** — requires specific CUDA toolkit versions; check compatibility matrix.
- **GRPO** — reward function design is critical; the reward signal guides the entire optimization.
- **Outlines with vLLM** — requires `vllm` >= 0.6.0 for FSM integration.
- **Obliteratus** — verify model output quality after ablation; some methods can degrade quality for non-refusal categories.
- **Axolotl + Unsloth + TRL** — do NOT mix. Each has its own trainer abstraction. Choose one framework per pipeline.
