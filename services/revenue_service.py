from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

from services.api_client import ApiClient


class SyncStateError(RuntimeError):
    pass


@dataclass
class SyncState:
    last_sync_utc: Optional[str]

    @staticmethod
    def load(path: str) -> "SyncState":
        p = Path(path)
        if not p.exists():
            return SyncState(last_sync_utc=None)

        try:
            obj = json.loads(p.read_text(encoding="utf-8"))
        except Exception as exc:
            raise SyncStateError(f"Failed to read sync state file: {path}") from exc

        last_sync = obj.get("last_sync_utc")
        if last_sync is None:
            return SyncState(last_sync_utc=None)
        if not isinstance(last_sync, str) or not last_sync.strip():
            return SyncState(last_sync_utc=None)
        return SyncState(last_sync_utc=last_sync.strip())

    def save(self, path: str) -> None:
        p = Path(path)
        p.parent.mkdir(parents=True, exist_ok=True)
        payload = {"last_sync_utc": self.last_sync_utc}
        p.write_text(json.dumps(payload, indent=2), encoding="utf-8")


class RevenueService:
    """Fetch invoices updated since last sync timestamp using `updatedSince`."""

    def __init__(self, api_client: ApiClient, tenant_id: str, state_path: str, page_size: int = 500) -> None:
        self._api = api_client
        self._tenant_id = tenant_id
        self._state_path = state_path
        self._page_size = page_size

    def read_last_sync_utc(self) -> str:
        state = SyncState.load(self._state_path)
        if not state.last_sync_utc:
            dt = datetime.now(timezone.utc) - timedelta(days=7)
            return dt.isoformat().replace("+00:00", "Z")
        return state.last_sync_utc

    def fetch_updated_invoices(self) -> List[Dict[str, Any]]:
        updated_since = self.read_last_sync_utc()

        # ServiceTitan v2 invoices endpoint pattern (Accounting):
        path = f"accounting/v2/tenant/{self._tenant_id}/invoices"

        params = {"updatedSince": updated_since}

        invoices: List[Dict[str, Any]] = []
        for item in self._api.get_paginated(path=path, base_params=params, page_size=self._page_size):
            invoices.append(item)
        return invoices

    def update_sync_state_to_now(self) -> None:
        now_utc = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
        SyncState(last_sync_utc=now_utc).save(self._state_path)
