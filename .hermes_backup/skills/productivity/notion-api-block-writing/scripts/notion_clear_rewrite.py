#!/usr/bin/env python3
"""Clear and/or rewrite a Notion page's content via the block API.

Modes (argv):
  clear  <page_id>                  delete all blocks recursively
  write  <page_id> <md_file>        append markdown file as blocks (does NOT clear)
  rewrite <page_id> <md_file>       clear then write

Reads NOTION_API_KEY from ~/.hermes/.env. Page must be shared with the
integration. Verified 2026-08-26 against Notion-Version 2025-09-03.

Run this as a BACKGROUND process for pages with 100+ blocks (execute_code's
300s cap will kill a big clear; this script prints progress with flush=True).
"""
import json, os, re, sys, time, urllib.request, urllib.error

PAGE_ID = None

def load_key():
    p = os.path.expanduser("~/.hermes/.env")
    if not os.path.exists(p):
        sys.exit("~/.hermes/.env not found")
    with open(p) as f:
        for line in f:
            if line.startswith("NOTION_API_KEY="):
                return line.split("=", 1)[1].strip().strip('"').strip("'")
    sys.exit("NOTION_API_KEY not found in ~/.hermes/.env")

KEY = load_key()
BASE = "https://api.notion.com/v1"
HDRS = {"Authorization": f"Bearer {KEY}", "Notion-Version": "2025-09-03",
        "Content-Type": "application/json"}

def api(method, path, body=None, retries=4):
    data = json.dumps(body).encode() if body else None
    req = urllib.request.Request(BASE + path, data=data, headers=HDRS, method=method)
    for a in range(retries):
        try:
            with urllib.request.urlopen(req) as r:
                return json.loads(r.read())
        except urllib.error.HTTPError as e:
            if e.code == 429:
                time.sleep(1.5); continue
            return {"_error": e.code, "_msg": e.read().decode()[:300]}
        except Exception:
            time.sleep(0.5)
    return {"_error": "retries-exhausted"}

def get_all_children(block_id):
    out, cursor = [], None
    while True:
        path = f"/blocks/{block_id}/children?page_size=100"
        if cursor:
            path += f"&start_cursor={cursor}"
        d = api("GET", path)
        if "_error" in d:
            break
        out.extend(d.get("results", []))
        if d.get("has_more"):
            cursor = d.get("next_cursor")
        else:
            break
    return out

def delete_recursive(block_id, stats):
    for k in get_all_children(block_id):
        delete_recursive(k["id"], stats)
    r = api("DELETE", f"/blocks/{block_id}")
    if "_error" not in r:
        stats["del"] += 1
    else:
        stats["fail"] += 1
        print(f"FAIL {block_id[:12]} {r.get('_msg','')[:80]}", flush=True)

def clear(page_id):
    stats = {"del": 0, "fail": 0}
    kids = get_all_children(page_id)
    total = len(kids)
    print(f"Deleting {total} top-level blocks recursively...", flush=True)
    for i, b in enumerate(kids):
        delete_recursive(b["id"], stats)
        if (i + 1) % 25 == 0 or i + 1 == total:
            print(f"  progress {i+1}/{total} deleted={stats['del']} fail={stats['fail']}", flush=True)
    print(f"DONE deleted={stats['del']} fail={stats['fail']}", flush=True)
    print("Remaining children:", len(get_all_children(page_id)), flush=True)

def rt(s):
    return [{"type": "text", "text": {"content": s}}]

def make_blocks(lines):
    """Small md subset -> blocks: h1-3, paragraph, quote, bullet, divider, code, table."""
    blocks, i, in_code, code_buf = [], 0, False, []
    table_buf, table_width = [], 0
    def flush_table():
        nonlocal table_buf, table_width
        if table_buf:
            rows = [{"object": "block", "type": "table_row",
                     "table_row": {"cells": [[{"type": "text", "text": {"content": c}}] for c in row]}}
                    for row in table_buf]
            blocks.append({"object": "block", "type": "table",
                           "table": {"table_width": table_width, "has_column_header": True,
                                     "has_row_header": False, "children": rows}})
            table_buf, table_width = [], 0
    while i < len(lines):
        line = lines[i].rstrip()
        if line.startswith("```"):
            if not in_code:
                in_code, code_buf = True, []
            else:
                in_code = False
                content = "\n".join(code_buf)
                for s in range(0, len(content), 1800):  # code cap ~2000
                    blocks.append({"object": "block", "type": "code",
                                   "code": {"rich_text": rt(content[s:s+1800]), "language": "plain text"}})
            i += 1; continue
        if in_code:
            code_buf.append(line); i += 1; continue
        if line.startswith("|"):
            cells = [c.strip() for c in line.strip("|").split("|")]
            if all(re.fullmatch(r":?-{2,}:?", c or "-") for c in cells):
                i += 1; continue
            table_buf.append(cells); table_width = len(cells); i += 1; continue
        flush_table()
        m = re.match(r"^(#{1,3})\s+(.*)$", line)
        if m:
            lvl, text = len(m.group(1)), m.group(2)
            btype = {1: "heading_1", 2: "heading_2", 3: "heading_3"}[lvl]
            blocks.append({"object": "block", "type": btype, btype: {"rich_text": rt(text)}})
            i += 1; continue
        if line.startswith(">"):
            blocks.append({"object": "block", "type": "quote",
                           "quote": {"rich_text": rt(line.lstrip("> ").strip())}})
            i += 1; continue
        if line.startswith("- "):
            blocks.append({"object": "block", "type": "bulleted_list_item",
                           "bulleted_list_item": {"rich_text": rt(line[2:].strip())}})
            i += 1; continue
        if re.fullmatch(r"-{3,}", line):
            blocks.append({"object": "block", "type": "divider", "divider": {}})
            i += 1; continue
        if not line.strip():
            i += 1; continue
        text = re.sub(r"\*\*(.*?)\*\*", r"\1", line)
        text = re.sub(r"`(.*?)`", r"\1", text)
        blocks.append({"object": "block", "type": "paragraph", "paragraph": {"rich_text": rt(text)}})
        i += 1
    flush_table()
    return blocks

def write(page_id, md_file):
    with open(md_file, encoding="utf-8") as f:
        lines = f.readlines()
    blocks = make_blocks(lines)
    print(f"Read {len(lines)} lines -> {len(blocks)} blocks", flush=True)
    for ci in range(0, len(blocks), 60):
        chunk = blocks[ci:ci+60]
        r = api("PATCH", f"/blocks/{page_id}/children", {"children": chunk})
        if "_error" in r:
            print(f"CHUNK {ci//60} FAILED: {r}", flush=True)
            sys.exit(1)
        print(f"appended chunk {ci//60+1}/{(len(blocks)-1)//60+1} ({len(chunk)} blocks)", flush=True)
        time.sleep(0.8)
    print("ALL-APPENDED", flush=True)

if __name__ == "__main__":
    mode = sys.argv[1] if len(sys.argv) > 1 else "help"
    if mode in ("clear", "rewrite") and len(sys.argv) > 2:
        clear(sys.argv[2])
    if mode in ("write", "rewrite") and len(sys.argv) > 3:
        write(sys.argv[2], sys.argv[3])
    elif mode == "help":
        print(__doc__)
