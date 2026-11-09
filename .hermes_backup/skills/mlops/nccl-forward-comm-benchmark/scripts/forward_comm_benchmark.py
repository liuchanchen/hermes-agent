#!/usr/bin/env python3
"""Benchmark forward-pass-sized PCIe and NCCL communication buffers.

Run ``pcie`` as a normal Python process. Run ``p2p`` and ``alltoall`` through
``torchrun``. The benchmark validates received data before measuring it.
"""

from __future__ import annotations

import argparse
import json
import math
import os
import socket
import statistics
import time
from pathlib import Path
from typing import Callable

import torch
import torch.distributed as dist


DEFAULT_TOKENS = "1,8,64,128,512,8192"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--mode", choices=("pcie", "p2p", "alltoall"), required=True)
    parser.add_argument("--tokens", default=DEFAULT_TOKENS)
    parser.add_argument("--hidden-size", type=int, default=7168)
    parser.add_argument("--element-bytes", type=int, default=2)
    parser.add_argument(
        "--copies",
        type=int,
        default=None,
        help="Payload copies per token. Defaults to 1 for PCIe/P2P and 6 for alltoall.",
    )
    parser.add_argument("--iters", type=int, default=0, help="Override adaptive iteration count")
    parser.add_argument("--latency-iters", type=int, default=30)
    parser.add_argument("--output-json")
    return parser.parse_args()


def percentile(values: list[float], fraction: float) -> float:
    ordered = sorted(values)
    index = max(0, math.ceil(fraction * len(ordered)) - 1)
    return ordered[index]


def adaptive_iters(size_bytes: int) -> int:
    if size_bytes <= 128 * 1024:
        return 1000
    if size_bytes <= 2 * 1024 * 1024:
        return 400
    if size_bytes <= 16 * 1024 * 1024:
        return 150
    if size_bytes <= 128 * 1024 * 1024:
        return 40
    return 12


def summarize_samples(samples_s: list[float]) -> dict[str, float]:
    return {
        "sync_latency_p50_us": statistics.median(samples_s) * 1e6,
        "sync_latency_p95_us": percentile(samples_s, 0.95) * 1e6,
        "sync_latency_p99_us": percentile(samples_s, 0.99) * 1e6,
    }


def time_cuda_operation(
    operation: Callable[[], None], size_bytes: int, iterations: int, latency_iters: int
) -> dict[str, float]:
    warmups = min(20, max(3, iterations // 10))
    for _ in range(warmups):
        operation()
    torch.cuda.synchronize()

    start = time.perf_counter()
    for _ in range(iterations):
        operation()
    torch.cuda.synchronize()
    elapsed = time.perf_counter() - start
    average_s = elapsed / iterations

    samples: list[float] = []
    for _ in range(latency_iters):
        torch.cuda.synchronize()
        start = time.perf_counter()
        operation()
        torch.cuda.synchronize()
        samples.append(time.perf_counter() - start)

    result = {
        "steady_time_us": average_s * 1e6,
        "steady_payload_GBps": size_bytes / average_s / 1e9,
    }
    result.update(summarize_samples(samples))
    return result


# ---- PCIe baseline -------------------------------------------------------


def bench_pcie(args: argparse.Namespace) -> dict:
    device = torch.device("cuda:0")
    copies = args.copies or 1
    hidden_bytes = args.hidden_size * args.element_bytes
    results: dict[str, dict] = {}

    for t_str in args.tokens.split(","):
        tokens = int(t_str)
        payload = hidden_bytes * copies * tokens
        if payload > 2 * 1024**3:
            print(f"  Skip {tokens} tokens ({payload / 1e9:.2f} GB > 2 GB)")
            continue
        print(f"tokens={tokens}  payload={payload} bytes ({payload / 1024**2:.1f} MiB)")

        host_buf = torch.empty(payload // args.element_bytes, dtype=torch.bfloat16, pin_memory=True)
        gpu_buf = torch.empty_like(host_buf, device=device)
        host_buf.fill_(0)
        gpu_buf.fill_(1)

        iters = args.iters or adaptive_iters(payload)

        def h2d():
            gpu_buf.copy_(host_buf, non_blocking=False)

        def d2h():
            host_buf.copy_(gpu_buf, non_blocking=False)

        h2d_res = time_cuda_operation(h2d, payload, iters, args.latency_iters)
        d2h_res = time_cuda_operation(d2h, payload, iters, args.latency_iters)

        entry = {
            "tokens": tokens,
            "payload_bytes": payload,
            "copies": copies,
            "h2d": h2d_res,
            "d2h": d2h_res,
        }
        results[str(tokens)] = entry
        print(
            f"  H2D p50={h2d_res['sync_latency_p50_us']:.2f} us  "
            f"steady={h2d_res['steady_payload_GBps']:.2f} GB/s"
        )
        print(
            f"  D2H p50={d2h_res['sync_latency_p50_us']:.2f} us  "
            f"steady={d2h_res['steady_payload_GBps']:.2f} GB/s"
        )

    return results


# ---- P2P -----------------------------------------------------------------


def init_dist(args: argparse.Namespace):
    rank = int(os.environ["RANK"])
    local_rank = int(os.environ["LOCAL_RANK"])
    world_size = int(os.environ["WORLD_SIZE"])
    torch.cuda.set_device(local_rank)

    backend = "nccl" if torch.cuda.device_count() >= world_size else "gloo"
    dist.init_process_group(backend=backend)
    return rank, local_rank, world_size


def bench_p2p(args: argparse.Namespace) -> dict:
    rank, local_rank, world_size = init_dist(args)
    assert world_size == 2, "P2P requires exactly 2 ranks"
    copies = args.copies or 1
    hidden_bytes = args.hidden_size * args.element_bytes
    results: dict[str, dict] = {}

    for t_str in args.tokens.split(","):
        tokens = int(t_str)
        payload = hidden_bytes * copies * tokens
        if payload > 2 * 1024**3:
            if rank == 0:
                print(f"  Skip {tokens} tokens ({payload / 1e9:.2f} GB > 2 GB)")
            continue

        buf = torch.empty(payload // args.element_bytes, dtype=torch.bfloat16, device=f"cuda:{local_rank}")
        buf.fill_(rank + 1)
        recv_buf = torch.empty_like(buf)

        iters = args.iters or adaptive_iters(payload)

        def p2p_op():
            if rank == 0:
                dist.send(buf, dst=1)
                dist.recv(recv_buf, src=1)
            else:
                dist.recv(recv_buf, src=0)
                dist.send(buf, dst=0)

        res = time_cuda_operation(p2p_op, payload * 2, iters, args.latency_iters)

        # validate
        expected = torch.full_like(recv_buf, 2 - rank)
        valid = torch.equal(recv_buf, expected)

        entry = {
            "tokens": tokens,
            "payload_bytes": payload,
            "copies": copies,
            "valid": valid,
            **res,
        }
        results[str(tokens)] = entry
        if rank == 0:
            print(
                f"  tokens={tokens}  p50={res['sync_latency_p50_us']:.2f} us  "
                f"steady={res['steady_payload_GBps']:.2f} GB/s  "
                f"valid={valid}"
            )

    dist.destroy_process_group()
    return results


# ---- All-to-all ----------------------------------------------------------


def bench_alltoall(args: argparse.Namespace) -> dict:
    rank, local_rank, world_size = init_dist(args)
    copies = args.copies or 6  # top-6 experts
    hidden_bytes = args.hidden_size * args.element_bytes
    results: dict[str, dict] = {}

    for t_str in args.tokens.split(","):
        tokens = int(t_str)
        payload = hidden_bytes * copies * tokens
        if payload > 2 * 1024**3:
            if rank == 0:
                print(f"  Skip {tokens} tokens ({payload / 1e9:.2f} GB > 2 GB)")
            continue

        send_buf = torch.empty(payload // args.element_bytes, dtype=torch.bfloat16, device=f"cuda:{local_rank}")
        recv_buf = torch.empty(payload // args.element_bytes, dtype=torch.bfloat16, device=f"cuda:{local_rank}")
        send_buf.fill_(rank + 1)

        # all-to-all splits evenly across peers
        send_chunk = send_buf.view(world_size, -1).contiguous()
        recv_chunk = recv_buf.view(world_size, -1).contiguous()

        iters = args.iters or adaptive_iters(payload)

        def a2a_op():
            dist.all_to_all([recv_chunk[i] for i in range(world_size)],
                           [send_chunk[i] for i in range(world_size)])

        res = time_cuda_operation(a2a_op, payload * (world_size - 1), iters, args.latency_iters)

        # validate
        valid = True
        for i in range(world_size):
            if i == rank:
                continue
            expected = torch.full_like(recv_chunk[i], i + 1)
            if not torch.equal(recv_chunk[i], expected):
                valid = False
                break

        entry = {
            "tokens": tokens,
            "payload_bytes": payload,
            "copies": copies,
            "world_size": world_size,
            "valid": valid,
            **res,
        }
        results[str(tokens)] = entry
        if rank == 0:
            print(
                f"  tokens={tokens}  p50={res['sync_latency_p50_us']:.2f} us  "
                f"steady={res['steady_payload_GBps']:.2f} GB/s  "
                f"valid={valid}"
            )

    dist.destroy_process_group()
    return results


# ---- Main ----------------------------------------------------------------


def main():
    args = parse_args()

    if args.mode == "pcie":
        results = bench_pcie(args)
    elif args.mode == "p2p":
        results = bench_p2p(args)
    elif args.mode == "alltoall":
        results = bench_alltoall(args)
    else:
        raise ValueError(f"Unknown mode: {args.mode}")

    if args.output_json:
        output = {
            "host": socket.gethostname(),
            "mode": args.mode,
            "tokens": args.tokens,
            "hidden_size": args.hidden_size,
            "element_bytes": args.element_bytes,
            "copies": args.copies or 6 if args.mode == "alltoall" else 1,
            "results": results,
        }
        out_path = Path(args.output_json)
        out_path.parent.mkdir(parents=True, exist_ok=True)
        out_path.write_text(json.dumps(output, indent=2))
        print(f"Results saved to {out_path}")


if __name__ == "__main__":
    main()
