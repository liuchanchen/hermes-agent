#!/usr/bin/env python3
"""Fix missing http:// scheme on proxy export lines in ~/.bashrc.

Run on the remote host where the proxy is misconfigured, e.g.:
    ssh <host> 'python3 /tmp/fix_proxy.py --bashrc /home/<user>/.bashrc \
        --proxy-host 10.10.60.140 --proxy-port 7890'

Backs up the file to .bashrc.bak.<ts> before writing. Only rewrites lines
that have a bare host:port (no scheme).
"""
import argparse
import shutil
import time

VARS = ("http_proxy", "https_proxy", "ftp_proxy")


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--bashrc", default="~/.bashrc", help="path to bashrc")
    ap.add_argument("--proxy-host", required=True, help="proxy host, e.g. 10.10.60.140")
    ap.add_argument("--proxy-port", required=True, help="proxy port, e.g. 7890")
    args = ap.parse_args()

    path = args.bashrc.replace("~", __import__("os").path.expanduser("~"))
    with open(path) as f:
        s = f.read()

    bare = f"{args.proxy_host}:{args.proxy_port}"
    fixed = f"http://{bare}"
    changed = False

    for var in VARS:
        old = f"export {var}='{bare}'"
        new = f"export {var}='{fixed}'"
        if old in s:
            s = s.replace(old, new)
            print(f"fixed: {new}")
            changed = True

    if not changed:
        print("no bare host:port lines found (already OK or different format)")
        return 0

    shutil.copy2(path, f"{path}.bak.{int(time.time())}")
    with open(path, "w") as f:
        f.write(s)
    print("backup written, bashrc updated")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
