# PP=2 Tuning Results — DeepSeek V4 Pro

**Environment:** 70.96 (master) + 70.98 (worker), ConnectX-6 RoCE v2
**GPU:** RTX PRO 6000 Blackwell SE × 8 per node (96 GB/card)
**vLLM:** 0.6.0.dev0 (jasl/vllm, ds4-sm120 branch)
**KV:** fp8, block-size=256, gpu-memory-utilization=0.92, max-model-len=1,048,576

## Strategies Tested

| Strategy | TP | PP | DP | EP | Description |
|----------|----|----|----|----|-------------|
| DP | 8 | 1 | 2 | 16 | Data parallelism — full model on each node, data split |
| PP | 8 | 2 | 1 | 8 | Pipeline parallelism — model layers split across nodes |

## S1: Short Prompt (128 input, 128 output, 10 concurrent, inf rate)

| Config | Strategy | TTFT mean | TPOT mean | Output tok/s |
|--------|----------|-----------|-----------|-------------|
| 8192/512 | **PP** | **2.17s** | 99.7ms | 86.2 |
| 8192/512 | DP | 2.58s | 99.3ms | 83.9 |
| 8192/256 | **PP** | **3.32s** | 105.5ms | 76.5 |
| 8192/128 | **PP** | **5.92s** | 102.8ms | 67.4 |
| 8192/128 | DP | 12.69s | 108.6ms | 48.2 |
| 16384/256 | **PP** | 16.03s | 102.8ms | 44.0 |
| 16384/128 | **PP** | 16.31s | 102.4ms | 43.6 |
| 16384/512 | **PP** | **1.35s** | 99.5ms | **91.3** |

## S2: Long Prompt (60K input, 128 output, 5 concurrent, inf rate)

| Config | Strategy | TTFT mean | TTFT p99 | TPOT mean |
|--------|----------|-----------|----------|-----------|
| 8192/256 | **PP** | **182.3s** | **318.6s** | 1.18s |
| 8192/512 | **PP** | 186.7s | 327.6s | 1.22s |
| 8192/128 | **PP** | 188.8s | 330.4s | 1.23s |
| 8192/128 | DP | 260.5s | 416.1s | 1.36s |
| 16384/256 | **PP** | 197.5s | 338.8s | 1.23s |

## S3: Prefix Cache (60K prefix, 128 suffix, 5 concurrent, 1 prefix)

| Config | Strategy | TTFT mean | TPOT mean | Output tok/s |
|--------|----------|-----------|-----------|-------------|
| 8192/128 | **PP** | **43.2s** | 81.0ms | **7.73** |
| 8192/256 | **PP** | 43.9s | 98.1ms | 7.41 |
| 8192/512 | **PP** | 44.4s | **60.7ms** | 7.15 |
| 8192/128 | DP | 142.8s | 93.2ms | 4.14 |
| 16384/256 | **PP** | 48.5s | 56.4ms | 5.15 |

## Direct DP vs PP Comparison (8192/128)

| Metric | DP | PP | PP Advantage |
|--------|----|----|--------------|
| S1 TTFT | 12.69s | **5.92s** | **2.1× faster** |
| S1 TPOT | 108.6ms | **102.8ms** | 5.3% better |
| S1 tok/s | 48.2 | **67.4** | 40% more |
| S2 TTFT | 260.5s | **188.8s** | 28% faster |
| S3 TTFT | 142.8s | **43.2s** | **3.3× faster** |
| S3 TPOT | 93.2ms | 81.0ms | 13% better |
| S3 tok/s | 4.14 | **7.73** | 87% more |

## Recommended Config: PP=2, 8192/512

```bash
bash /data/venvs/vllm-ds4/start_dsv4_pro_2node.sh master  # on 70.96
bash /data/venvs/vllm-ds4/start_dsv4_pro_2node.sh worker  # on 70.98
```

## Configs That OOM

These configs failed with insufficient KV cache memory (needed 18+ GiB/GPU, had ~5.5 GiB):
- 32768/256, 32768/128, 32768/512
- 65536/64, 65536/128
- 16384/512 under PP (server crashed during long prompt benchmark)

## DP Handshake Failure Notes

DP mode startup fails consistently with `--api-server-count 1` on headless nodes:
```
ValueError: --api-server-count=1 cannot be used with --headless
```
Fix: remove `--api-server-count` from headless node config. The default (matching data_parallel_size) is correct.

When DP starts, the ZMQ ROUTER socket bound to `tcp://10.10.71.96:29550` must be unique — leftover processes holding this port cause `Address already in use`. Clean up with `fuser -k 29550/tcp`.
