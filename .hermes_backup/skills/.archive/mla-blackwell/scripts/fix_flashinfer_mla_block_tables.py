#!/usr/bin/env python3
"""
Patch flashinfer_mla_sparse.py: replace unsqueeze(1) on block_tables with safe squeeze.

Root cause: topk_indices_physical is 2D [num_tokens, NUM_TOPK_TOKENS] after
triton_convert_req_index_to_global_index. The .unsqueeze(1) makes it 3D
[num_tokens, 1, NUM_TOPK_TOKENS], but FlashInfer 0.6.8.post1's
trtllm_batch_decode_with_kv_cache_mla expects exactly 2D for shared paged KV layout.

Symptom:
  ValueError: block_tables must be 2D for shared paged KV layout, got ndim=3

Safe for both pre-fix (ndim=3) and post-fix (ndim=2) states.
"""
import sys
import re

FILE = "/data/vllm-ds4-sm120/vllm/v1/attention/backends/mla/flashinfer_mla_sparse.py"
OLD = "            block_tables=topk_indices_physical.unsqueeze(1),"
NEW = "            block_tables=topk_indices_physical.squeeze(1) if topk_indices_physical.ndim == 3 else topk_indices_physical,"

def main():
    with open(FILE, "r") as f:
        content = f.read()

    if OLD in content:
        content = content.replace(OLD, NEW)
        with open(FILE, "w") as f:
            f.write(content)
        print(f"PATCHED: {FILE}")
        print(f"  Old: {OLD}")
        print(f"  New: {NEW}")
        return 0
    elif NEW in content:
        print(f"Already patched: {FILE}")
        return 0
    else:
        print(f"ERROR: Pattern not found in {FILE}")
        print(f"Looking for: {OLD}")
        # Show relevant lines for debugging
        with open(FILE, "r") as f:
            for i, line in enumerate(f, 1):
                if "block_tables" in line and ("unsqueeze" in line or "squeeze" in line):
                    print(f"  Line {i}: {line.rstrip()}")
        return 1

if __name__ == "__main__":
    sys.exit(main())