"""Đọc Google Sheet qua Service Account."""
from __future__ import annotations

import json
import os
from typing import Any

from google.oauth2.service_account import Credentials
from googleapiclient.discovery import build

SCOPES = ["https://www.googleapis.com/auth/spreadsheets.readonly"]


def _load_credentials() -> Credentials:
    raw = os.environ.get("GOOGLE_SERVICE_ACCOUNT_JSON")
    if raw:
        info = json.loads(raw)
        return Credentials.from_service_account_info(info, scopes=SCOPES)
    path = os.environ.get("GOOGLE_SERVICE_ACCOUNT_FILE", "service_account.json")
    return Credentials.from_service_account_file(path, scopes=SCOPES)


def _col_letter(idx: int) -> str:
    """0 -> A, 1 -> B, ..., 25 -> Z, 26 -> AA."""
    s = ""
    n = idx
    while True:
        s = chr(ord("A") + n % 26) + s
        n = n // 26 - 1
        if n < 0:
            return s


class GSheetClient:
    def __init__(self) -> None:
        creds = _load_credentials()
        self._svc = build("sheets", "v4", credentials=creds, cache_discovery=False)

    def list_tab_names(self, spreadsheet_id: str) -> list[str]:
        meta = self._svc.spreadsheets().get(
            spreadsheetId=spreadsheet_id, fields="sheets.properties"
        ).execute()
        return [s["properties"]["title"] for s in meta.get("sheets", [])]

    def read_all_tabs_positional(self, spreadsheet_id: str, num_cols: int) -> list[dict[str, Any]]:
        """Đọc TẤT CẢ tab. Mỗi tab lấy num_cols cột đầu (A, B, ..., kth).
        Trả về list dict: {A:..., B:..., ..., __tab: tab_name, __row_idx: i (toàn sheet)}.
        Lấy hết row có data, KHÔNG skip header (header tab khác nhau, không chuẩn hoá được).
        """
        tabs = self.list_tab_names(spreadsheet_id)
        end_letter = _col_letter(num_cols - 1)
        cols = [_col_letter(i) for i in range(num_cols)]

        ranges = [f"'{tab}'!A:{end_letter}" for tab in tabs]
        resp = (
            self._svc.spreadsheets()
            .values()
            .batchGet(
                spreadsheetId=spreadsheet_id,
                ranges=ranges,
                valueRenderOption="UNFORMATTED_VALUE",
            )
            .execute()
        )

        out: list[dict[str, Any]] = []
        global_idx = 0
        for tab, vr in zip(tabs, resp.get("valueRanges", [])):
            for raw in vr.get("values", []) or []:
                if not any(str(c).strip() for c in raw):
                    continue
                padded = list(raw) + [""] * (num_cols - len(raw))
                global_idx += 1
                row: dict[str, Any] = {cols[j]: _normalize(padded[j]) for j in range(num_cols)}
                row["__tab"] = tab
                row["__row_idx"] = global_idx
                out.append(row)
        return out

    def read_range(self, spreadsheet_id: str, a1_range: str) -> list[dict[str, Any]]:
        """Đọc range, hàng đầu là header. Trả về list dict + key `__row_idx` (1-based ở data, không tính header)."""
        resp = (
            self._svc.spreadsheets()
            .values()
            .get(
                spreadsheetId=spreadsheet_id,
                range=a1_range,
                valueRenderOption="UNFORMATTED_VALUE",
            )
            .execute()
        )
        values: list[list[Any]] = resp.get("values", [])
        if not values:
            return []
        header = [str(c).strip() for c in values[0]]
        rows: list[dict[str, Any]] = []
        for i, raw in enumerate(values[1:], start=1):
            padded = list(raw) + [""] * (len(header) - len(raw))
            row = {header[j]: _normalize(padded[j]) for j in range(len(header))}
            row["__row_idx"] = i
            rows.append(row)
        return rows


def _normalize(v: Any) -> Any:
    if v is None:
        return ""
    if isinstance(v, str):
        return v
    return v
