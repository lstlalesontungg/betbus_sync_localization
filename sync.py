"""Sync 1 chiều Google Sheet -> Lark Base. Full replace mode.

Mỗi run: list all record Lark -> delete all -> create lại từ GSheet.
Mirror 100% theo thứ tự row của GSheet.
Dup key: vẫn ghi cả 2 row, thêm note vào cột warning.
"""
from __future__ import annotations

import os
import sys
from collections import defaultdict
from typing import Any

import yaml

from gsheet_client import GSheetClient
from lark_client import LarkClient


def load_config() -> dict:
    raw = os.environ.get("SYNC_CONFIG_YAML")
    if raw:
        return yaml.safe_load(raw)
    path = os.environ.get("SYNC_CONFIG_FILE", "config.yaml")
    with open(path, "r", encoding="utf-8") as f:
        return yaml.safe_load(f)


def detect_duplicates(rows: list[dict], key_col: str, with_tab: bool = False) -> dict[int, str]:
    """Trả về map row_idx -> warning text. Nếu with_tab=True, message gồm tab name."""
    by_key: dict[str, list[tuple[int, str]]] = defaultdict(list)
    for r in rows:
        k = str(r.get(key_col, "")).strip()
        if not k:
            continue
        by_key[k].append((r["__row_idx"], r.get("__tab", "")))
    warn: dict[int, str] = {}
    for k, entries in by_key.items():
        if len(entries) >= 2:
            if with_tab:
                detail = ", ".join(f"row {i} tab '{t}'" for i, t in entries)
            else:
                detail = f"rows {[i for i, _ in entries]}"
            msg = f"DUP key='{k}' tại {detail}"
            for i, _ in entries:
                warn[i] = msg
    return warn


def _to_text(v: Any) -> str:
    if v is None or v == "":
        return ""
    if isinstance(v, bool):
        return "TRUE" if v else "FALSE"
    if isinstance(v, float) and v.is_integer():
        return str(int(v))
    return str(v)


def build_payload(row: dict, warn: dict[int, str], dup_col: str, header_cols: list[str],
                  extra_cols: list[str] | None = None) -> dict[str, Any]:
    idx = row["__row_idx"]
    fields: dict[str, Any] = {c: _to_text(row.get(c, "")) for c in header_cols}
    if extra_cols:
        for c in extra_cols:
            fields[c] = _to_text(row.get(c, ""))
    fields[dup_col] = warn.get(idx, "")
    return fields


def resolve_app_token(lark: LarkClient, t: dict) -> str:
    if t.get("app_token"):
        return t["app_token"]
    if t.get("wiki_token"):
        return lark.resolve_wiki_node(t["wiki_token"])
    raise RuntimeError(f"Table {t.get('name')} thiếu app_token hoặc wiki_token")


def sync_table(gs: GSheetClient, lark: LarkClient, t: dict, dup_key_col: str, dup_col: str) -> dict:
    merge_all = bool(t.get("merge_all_tabs"))
    if merge_all:
        num_cols = int(t.get("num_columns", 9))
        rows = gs.read_all_tabs_positional(t["spreadsheet_id"], num_cols)
        header_cols = [chr(ord("A") + i) for i in range(num_cols)]
        extra_cols = ["__tab"]
        local_dup_col = dup_key_col if dup_key_col in header_cols else header_cols[0]
        warn = detect_duplicates(rows, local_dup_col, with_tab=True)
    else:
        rows = gs.read_range(t["spreadsheet_id"], t["gsheet_range"])
        if not rows:
            return {"gsheet_rows": 0, "deleted": 0, "created": 0, "dup_rows": 0, "skipped": "empty sheet"}
        header_cols = [k for k in rows[0].keys() if k != "__row_idx"]
        extra_cols = []
        warn = detect_duplicates(rows, dup_key_col)

    if not rows:
        return {"gsheet_rows": 0, "deleted": 0, "created": 0, "dup_rows": 0, "skipped": "empty sheet"}

    app_token = resolve_app_token(lark, t)
    table_id = t["lark_table_id"]

    lark.ensure_primary_named(app_token, table_id, header_cols[0])
    needed = header_cols + extra_cols + [dup_col]
    created = lark.ensure_fields(app_token, table_id, needed)
    if created:
        print(f"  auto-created fields: {created}", flush=True)

    existing = lark.list_all_records(app_token, table_id)
    existing_ids = [r["record_id"] for r in existing]

    n_del = lark.batch_delete(app_token, table_id, existing_ids)

    payloads = [build_payload(r, warn, dup_col, header_cols, extra_cols) for r in rows]
    n_new = lark.batch_create(app_token, table_id, payloads)

    return {
        "gsheet_rows": len(rows),
        "lark_existing": len(existing),
        "deleted": n_del,
        "created": n_new,
        "dup_rows": len(warn),
        "dup_groups": len({w for w in warn.values()}),
    }


def main() -> int:
    cfg = load_config()
    gs = GSheetClient()
    lark_cfg = cfg["lark"]
    lark = LarkClient(
        base_url=lark_cfg["base_url"],
        app_id=lark_cfg["app_id"],
        app_secret=lark_cfg["app_secret"],
    )
    dup_key_col = cfg.get("duplicate_key_column", "key")
    dup_col = cfg.get("dup_warning_column", "__dup_warning")

    exit_code = 0
    for t in cfg["tables"]:
        print(f"=== Sync '{t['name']}' ===", flush=True)
        try:
            stats = sync_table(gs, lark, t, dup_key_col, dup_col)
            print(f"  result: {stats}", flush=True)
        except Exception as e:
            print(f"  FAILED: {e}", flush=True)
            exit_code = 1
    return exit_code


if __name__ == "__main__":
    sys.exit(main())
