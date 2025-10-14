#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import os
import sqlite3
import sys
from typing import Any, Dict, List, Tuple


def ensure_app_path() -> None:
    root = "/opt/web"
    if root not in sys.path:
        sys.path.append(root)


ensure_app_path()

# Lazy imports after path set
from app.core.config import settings  # type: ignore  # noqa: E402
from app.services.mcp_client import get_netdisk_client  # type: ignore  # noqa: E402


def open_db() -> sqlite3.Connection:
    db_path = os.path.join(settings.data_dir, "baidu_netdisk.db")
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    return conn


def fetch_candidates(conn: sqlite3.Connection, start_id: int, limit: int) -> List[Tuple[int, int]]:
    # Return list of (id, fs_id) where md5 missing/blank
    cur = conn.cursor()
    cur.execute(
        """
        SELECT id, fs_id
        FROM exported_files
        WHERE (file_md5 IS NULL OR length(trim(file_md5)) < 16)
          AND fs_id IS NOT NULL
          AND id >= ?
        ORDER BY id ASC
        LIMIT ?
        """,
        (start_id, limit),
    )
    return [(int(r["id"]), int(r["fs_id"])) for r in cur.fetchall()]


def parse_metas_for_md5(meta_resp: Dict[str, Any]) -> Dict[int, str]:
    """Extract {fsid: md5} from various possible response shapes."""
    mapping: Dict[int, str] = {}
    candidates: List[Dict[str, Any]] = []
    if isinstance(meta_resp, dict):
        # common shapes
        if isinstance(meta_resp.get("list"), list):
            candidates = meta_resp.get("list", [])
        elif isinstance(meta_resp.get("data"), dict) and isinstance(meta_resp["data"].get("list"), list):
            candidates = meta_resp["data"].get("list", [])
        else:
            # maybe already list-like dicts
            pass

    for item in candidates:
        try:
            fsid = int(item.get("fs_id") or item.get("fsid") or item.get("fsId"))
        except Exception:
            continue
        md5 = item.get("md5") or item.get("block_md5") or item.get("md5sum")
        if isinstance(md5, str) and len(md5.strip()) >= 16:
            mapping[fsid] = md5.strip()
    return mapping


def update_md5(conn: sqlite3.Connection, updates: Dict[int, str]) -> int:
    if not updates:
        return 0
    cur = conn.cursor()
    rows = 0
    for fsid, md5 in updates.items():
        cur.execute(
            "UPDATE exported_files SET file_md5 = ? WHERE fs_id = ?",
            (md5, fsid),
        )
        rows += cur.rowcount
    conn.commit()
    return rows


def main() -> int:
    ap = argparse.ArgumentParser(description="Refresh file_md5 in exported_files using MCP file_metas")
    ap.add_argument("--mode", choices=["public", "user"], default="public", help="token mode for MCP client")
    ap.add_argument("--user-id", type=int, default=0, help="user id when mode=user")
    ap.add_argument("--start-id", type=int, default=1, help="exported_files.id lower bound (ignored when --resume and state exists)")
    ap.add_argument("--limit", type=int, default=200, help="max rows to scan this run")
    ap.add_argument("--batch-size", type=int, default=50, help="fsids per file_metas call")
    ap.add_argument("--state-file", type=str, default="/opt/web/.data/md5_refresh.state", help="path to resume state file")
    ap.add_argument("--resume", action="store_true", help="resume from state file if exists")
    args = ap.parse_args()

    conn = open_db()
    # Resolve start id with resume
    start_id = args.start_id
    if args.resume and os.path.exists(args.state_file):
        try:
            with open(args.state_file, "r", encoding="utf-8") as f:
                saved = int(f.read().strip() or "0")
                if saved > 0:
                    start_id = saved + 1
                    print(f"[resume] continue from id>{saved} -> start-id={start_id}")
        except Exception:
            pass

    rows = fetch_candidates(conn, start_id, args.limit)
    if not rows:
        print("No candidates found.")
        return 0

    # Build MCP client
    if args.mode == "public":
        client = get_netdisk_client(mode="public")
    else:
        if args.user_id <= 0:
            print("--user-id required when --mode=user", file=sys.stderr)
            return 2
        client = get_netdisk_client(user_id=args.user_id, mode="user")

    # Chunk fsids
    fsids: List[int] = [fsid for (_id, fsid) in rows]
    total_updates = 0
    last_processed_id = 0
    for i in range(0, len(fsids), args.batch_size):
        chunk = fsids[i : i + args.batch_size]
        try:
            payload = json.dumps(chunk)
            metas = client.file_metas(fsids=payload)
        except Exception as e:
            print(f"file_metas error: {e}")
            continue
        mapping = parse_metas_for_md5(metas or {})
        applied = update_md5(conn, mapping)
        total_updates += applied
        # update last processed id for resume (use corresponding exported_files id, not fsid)
        try:
            last_processed_id = rows[min(len(rows) - 1, (i + args.batch_size) - 1)][0]
        except Exception:
            pass
        if args.state_file:
            try:
                os.makedirs(os.path.dirname(args.state_file), exist_ok=True)
                with open(args.state_file, "w", encoding="utf-8") as f:
                    f.write(str(last_processed_id))
            except Exception as e:
                print(f"warn: cannot write state file: {e}")
        print(f"batch {i//args.batch_size+1}: asked={len(chunk)} parsed={len(mapping)} updated={applied} next_start>{last_processed_id}")

    print(f"Done. candidates={len(rows)} total_updates={total_updates}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())


