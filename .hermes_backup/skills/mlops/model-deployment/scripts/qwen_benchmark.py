#!/usr/bin/env python3
"""Qwen-Image-2512 benchmark client.

Usage:
    python3 qwen_benchmark.py                    # defaults: 512x512, 20 steps, 3 runs
    python3 qwen_benchmark.py --url http://10.10.70.88:8000 --steps 10 --runs 5
    python3 qwen_benchmark.py --size 1024         # 1024x1024
    python3 qwen_benchmark.py --save /tmp/result.png   # save last image
"""

import urllib.request, json, time, base64, argparse, sys

def generate(base_url, payload):
    data = json.dumps(payload).encode()
    t0 = time.time()
    resp = urllib.request.urlopen(
        urllib.request.Request(f"{base_url}/generate", data=data,
            headers={"Content-Type": "application/json"}),
        timeout=600
    )
    result = json.loads(resp.read())
    elapsed = time.time() - t0
    img_bytes = len(base64.b64decode(result["image_base64"]))
    return elapsed, img_bytes

def main():
    parser = argparse.ArgumentParser(description="Qwen-Image-2512 benchmark client")
    parser.add_argument("--url",      default="http://10.10.70.88:8000")
    parser.add_argument("--prompt",   default="a majestic dragon flying over a fantasy kingdom, cinematic lighting")
    parser.add_argument("--neg",      default="blurry, low quality")
    parser.add_argument("--steps",    type=int, default=20)
    parser.add_argument("--runs",     type=int, default=3)
    parser.add_argument("--height",  type=int, default=512)
    parser.add_argument("--width",   type=int, default=512)
    parser.add_argument("--seed",    type=int, default=123)
    parser.add_argument("--cfg",     type=float, default=4.0)
    parser.add_argument("--save",    default=None, help="save last image to path")
    args = parser.parse_args()

    payload = {
        "prompt": args.prompt,
        "negative_prompt": args.neg,
        "num_inference_steps": args.steps,
        "true_cfg_scale": args.cfg,
        "height": args.height,
        "width": args.width,
        "seed": args.seed,
    }

    # verify server
    try:
        urllib.request.urlopen(f"{args.url}/health", timeout=5)
    except Exception as e:
        print(f"ERROR: cannot reach server at {args.url}/health — {e}")
        sys.exit(1)

    print(f"[{args.url}] {args.height}x{args.width}, {args.steps} steps")

    print("Warmup...")
    t, s = generate(args.url, payload)
    print(f"Warmup: {t:.1f}s ({s//1024}KB)")

    times = []
    for i in range(args.runs):
        t, s = generate(args.url, payload)
        times.append(t)
        print(f"Run {i+1}: {t:.1f}s ({s//1024}KB)")

    avg = sum(times) / len(times)
    print(f"\nAvg: {avg:.1f}s  Min: {min(times):.1f}s  Max: {max(times):.1f}s")
    print(f"Throughput: {60/avg:.2f} img/min")

if __name__ == "__main__":
    main()