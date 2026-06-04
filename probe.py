"""Probe GSheet tab names + header columns + Lark base/wiki resolve. Chạy 1 lần trước khi sync thật."""
from __future__ import annotations

import os
import sys

import yaml
from google.oauth2.service_account import Credentials
from googleapiclient.discovery import build

from lark_client import LarkClient

SCOPES = ["https://www.googleapis.com/auth/spreadsheets.readonly"]


def main() -> int:
    os.environ.setdefault("GOOGLE_SERVICE_ACCOUNT_FILE", "service_account.json")
    creds = Credentials.from_service_account_file(
        os.environ["GOOGLE_SERVICE_ACCOUNT_FILE"], scopes=SCOPES
    )
    svc = build("sheets", "v4", credentials=creds, cache_discovery=False)

    with open("config.yaml") as f:
        cfg = yaml.safe_load(f)

    print("\n[1] Probe Google Sheets ===========================")
    for t in cfg["tables"]:
        sid = t["spreadsheet_id"]
        print(f"\n>>> {t['name']} ({sid})")
        try:
            meta = svc.spreadsheets().get(spreadsheetId=sid, fields="sheets.properties").execute()
            tabs = [s["properties"]["title"] for s in meta.get("sheets", [])]
            print(f"  tab names: {tabs}")
            first_tab = tabs[0]
            r = svc.spreadsheets().values().get(
                spreadsheetId=sid, range=f"{first_tab}!1:1"
            ).execute()
            header = r.get("values", [[]])[0]
            print(f"  header row tab '{first_tab}': {header}")
            r2 = svc.spreadsheets().values().get(
                spreadsheetId=sid, range=f"{first_tab}!A:A"
            ).execute()
            n = len(r2.get("values", [])) - 1
            print(f"  data row count (excluding header): {n}")
        except Exception as e:
            print(f"  ERROR: {e}")

    print("\n[2] Probe Lark Wiki -> Base ========================")
    lc = cfg["lark"]
    lark = LarkClient(lc["base_url"], lc["app_id"], lc["app_secret"])
    for t in cfg["tables"]:
        wt = t.get("wiki_token")
        if not wt:
            continue
        print(f"\n>>> {t['name']} wiki_token={wt}")
        try:
            app_token = lark.resolve_wiki_node(wt)
            print(f"  resolved app_token: {app_token}")
            recs = lark.list_all_records(app_token, t["lark_table_id"])
            print(f"  current records in table {t['lark_table_id']}: {len(recs)}")
            if recs:
                print(f"  sample fields: {list((recs[0].get('fields') or {}).keys())}")
        except Exception as e:
            print(f"  ERROR: {e}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
