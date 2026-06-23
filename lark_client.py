"""Lark Bitable API wrapper. Docs: https://open.larksuite.com/document/server-docs/docs/bitable-v1/"""
from __future__ import annotations

import time
from typing import Any

import requests

BATCH_SIZE = 500


class LarkClient:
    def __init__(self, base_url: str, app_id: str, app_secret: str) -> None:
        self.base_url = base_url.rstrip("/")
        self.app_id = app_id
        self.app_secret = app_secret
        self._token: str | None = None
        self._token_exp: float = 0.0

    def _tenant_token(self) -> str:
        if self._token and time.time() < self._token_exp - 60:
            return self._token
        r = requests.post(
            f"{self.base_url}/open-apis/auth/v3/tenant_access_token/internal",
            json={"app_id": self.app_id, "app_secret": self.app_secret},
            timeout=30,
        )
        r.raise_for_status()
        data = r.json()
        if data.get("code") != 0:
            raise RuntimeError(f"Lark token error: {data}")
        self._token = data["tenant_access_token"]
        self._token_exp = time.time() + data.get("expire", 7200)
        return self._token

    def _headers(self) -> dict[str, str]:
        return {
            "Authorization": f"Bearer {self._tenant_token()}",
            "Content-Type": "application/json; charset=utf-8",
        }

    def _request(self, method: str, path: str, *, json_body: Any = None, params: dict | None = None) -> dict:
        url = f"{self.base_url}{path}"
        for attempt in range(5):
            r = requests.request(method, url, headers=self._headers(), json=json_body, params=params, timeout=60)
            if r.status_code == 429 or r.status_code >= 500:
                time.sleep(2 ** attempt)
                continue
            try:
                data = r.json()
            except Exception:
                r.raise_for_status()
                raise
            if data.get("code") == 99991663:
                self._token = None
                continue
            if data.get("code") != 0:
                raise RuntimeError(f"Lark API error {method} {path}: {data}")
            return data
        raise RuntimeError(f"Lark API exhausted retries: {method} {path}")

    def resolve_wiki_node(self, wiki_token: str) -> str:
        """Wiki node token -> obj_token (= bitable app_token). Cần scope wiki:wiki:readonly."""
        path = "/open-apis/wiki/v2/spaces/get_node"
        data = self._request("GET", path, params={"token": wiki_token, "obj_type": "wiki"})
        node = data.get("data", {}).get("node", {})
        obj_type = node.get("obj_type")
        obj_token = node.get("obj_token")
        if obj_type != "bitable" or not obj_token:
            raise RuntimeError(f"Wiki node không phải bitable. obj_type={obj_type}, obj_token={obj_token}")
        return obj_token

    def list_fields(self, app_token: str, table_id: str) -> list[dict]:
        path = f"/open-apis/bitable/v1/apps/{app_token}/tables/{table_id}/fields"
        out: list[dict] = []
        page_token: str | None = None
        while True:
            params: dict[str, Any] = {"page_size": 100}
            if page_token:
                params["page_token"] = page_token
            data = self._request("GET", path, params=params)
            items = data.get("data", {}).get("items", []) or []
            out.extend(items)
            page_token = data.get("data", {}).get("page_token")
            if not data.get("data", {}).get("has_more") or not page_token:
                break
        return out

    def create_field(self, app_token: str, table_id: str, field_name: str, field_type: int = 1) -> dict:
        """field_type: 1=Text, 2=Number, 3=SingleSelect, 4=MultiSelect, 5=DateTime, 7=Checkbox, 11=Person."""
        path = f"/open-apis/bitable/v1/apps/{app_token}/tables/{table_id}/fields"
        body = {"field_name": field_name, "type": field_type}
        return self._request("POST", path, json_body=body)

    def update_field(self, app_token: str, table_id: str, field_id: str, field_name: str, field_type: int = 1) -> dict:
        path = f"/open-apis/bitable/v1/apps/{app_token}/tables/{table_id}/fields/{field_id}"
        body = {"field_name": field_name, "type": field_type}
        return self._request("PUT", path, json_body=body)

    def delete_field(self, app_token: str, table_id: str, field_id: str) -> dict:
        path = f"/open-apis/bitable/v1/apps/{app_token}/tables/{table_id}/fields/{field_id}"
        return self._request("DELETE", path)

    def ensure_primary_named(self, app_token: str, table_id: str, primary_name: str) -> None:
        """Đảm bảo primary field tên = primary_name. Nếu field tên này đang tồn tại non-primary -> xoá rồi rename primary."""
        fields = self.list_fields(app_token, table_id)
        primary = next((f for f in fields if f.get("is_primary")), None)
        if primary is None:
            return
        if primary.get("field_name") == primary_name:
            return
        conflict = next((f for f in fields if f.get("field_name") == primary_name and not f.get("is_primary")), None)
        if conflict:
            self.delete_field(app_token, table_id, conflict["field_id"])
        self.update_field(app_token, table_id, primary["field_id"], primary_name, field_type=primary.get("type", 1))

    def ensure_fields(self, app_token: str, table_id: str, names: list[str]) -> list[str]:
        """Đảm bảo các field tên trong `names` tồn tại. Thiếu thì tạo (type Text). Trả danh sách field đã tạo."""
        existing = {f["field_name"] for f in self.list_fields(app_token, table_id)}
        created: list[str] = []
        for n in names:
            if n not in existing:
                self.create_field(app_token, table_id, n, field_type=1)
                created.append(n)
        return created

    def list_all_records(self, app_token: str, table_id: str, fields: list[str] | None = None) -> list[dict]:
        """List toàn bộ record của 1 table. Trả về list dict có `record_id` + `fields`."""
        path = f"/open-apis/bitable/v1/apps/{app_token}/tables/{table_id}/records"
        out: list[dict] = []
        page_token: str | None = None
        while True:
            params: dict[str, Any] = {"page_size": 500}
            if page_token:
                params["page_token"] = page_token
            if fields:
                params["field_names"] = str(fields).replace("'", '"')
            data = self._request("GET", path, params=params)
            items = data.get("data", {}).get("items", []) or []
            out.extend(items)
            page_token = data.get("data", {}).get("page_token")
            if not data.get("data", {}).get("has_more") or not page_token:
                break
        return out

    def batch_create(self, app_token: str, table_id: str, records: list[dict[str, Any]]) -> int:
        if not records:
            return 0
        path = f"/open-apis/bitable/v1/apps/{app_token}/tables/{table_id}/records/batch_create"
        n = 0
        for chunk in _chunks(records, BATCH_SIZE):
            body = {"records": [{"fields": f} for f in chunk]}
            self._request("POST", path, json_body=body)
            n += len(chunk)
        return n

    def batch_delete(self, app_token: str, table_id: str, record_ids: list[str]) -> int:
        if not record_ids:
            return 0
        path = f"/open-apis/bitable/v1/apps/{app_token}/tables/{table_id}/records/batch_delete"
        n = 0
        for chunk in _chunks(record_ids, BATCH_SIZE):
            self._request("POST", path, json_body={"records": chunk})
            n += len(chunk)
        return n


def _chunks(seq: list, size: int):
    for i in range(0, len(seq), size):
        yield seq[i : i + size]
