#!/usr/bin/env python3
"""Check the ChatGPT account Codex weekly rate limit on a remote host.

Run on the remote host that has ~/.codex/auth.json:
    ssh <host> 'python3 /tmp/check_codex_limits.py'

Reads the access token from ~/.codex/auth.json, routes through the proxy
(env vars or --proxy), and calls the Codex usage endpoint. Prints the
weekly window usage, reset time, and plan type.
"""
import argparse
import json
import os
import urllib.request

AUTH_PATH = "~/.codex/auth.json"
USAGE_URL = "https://chatgpt.com/backend-api/codex/usage"


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--auth", default=AUTH_PATH)
    ap.add_argument("--proxy", default="", help="e.g. http://10.10.60.140:7890")
    args = ap.parse_args()

    path = args.auth.replace("~", os.path.expanduser("~"))
    with open(path) as f:
        auth = json.load(f)
    token = auth["tokens"]["access_token"]

    handlers = []
    proxy = args.proxy or os.environ.get("https_proxy") or os.environ.get("HTTPS_PROXY") or ""
    if proxy:
        handlers.append(urllib.request.ProxyHandler({"http": proxy, "https": proxy}))
    opener = urllib.request.build_opener(*handlers)

    req = urllib.request.Request(USAGE_URL, headers={
        "Authorization": f"Bearer {token}",
        "User-Agent": "codex-cli/0.149.1",
        "Content-Type": "application/json",
        "Accept": "application/json",
        "Origin": "https://chatgpt.com",
    })
    with opener.open(req, timeout=20) as r:
        d = json.loads(r.read())

    print(f"email:     {d.get('email')}")
    print(f"plan_type: {d.get('plan_type')}")
    rl = d.get("rate_limit", {})
    print(f"allowed:       {rl.get('allowed')}")
    print(f"limit_reached: {rl.get('limit_reached')}")
    pw = rl.get("primary_window") or {}
    if pw:
        print(f"used_percent:       {pw.get('used_percent')}%")
        print(f"window_seconds:     {pw.get('limit_window_seconds')} (604800 = 7 days)")
        print(f"reset_after_sec:    {pw.get('reset_after_seconds')}")
        print(f"reset_at_epoch:     {pw.get('reset_at')}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
