from __future__ import annotations

from typing import Any, Dict, List, Optional

import pandas as pd


class RevenueTransformer:
    """
    Normalize ServiceTitan invoice payloads to a strict flat schema:

    Input fields extracted (best-effort across common shapes):
      - invoice_id
      - invoice_date
      - business_unit_name
      - job_type_name
      - total
      - updated_at

    Output columns:
      - invoice_id
      - invoice_date (YYYY-MM-DD)
      - business_unit
      - job_type
      - total_amount
      - updated_at (full ISO datetime)
    """

    REQUIRED_COLUMNS = [
        "invoice_id",
        "invoice_date",
        "business_unit",
        "job_type",
        "total_amount",
        "updated_at",
    ]

    @staticmethod
    def _safe_get(d: Dict[str, Any], *keys: str) -> Optional[Any]:
        cur: Any = d
        for k in keys:
            if not isinstance(cur, dict):
                return None
            cur = cur.get(k)
        return cur

    def transform(self, invoices: List[Dict[str, Any]]) -> pd.DataFrame:
        rows: List[Dict[str, Any]] = []

        for inv in invoices:
            invoice_id = inv.get("id") or inv.get("invoiceId") or inv.get("invoice_id")

            # Invoice date: convert to YYYY-MM-DD
            invoice_date_raw = inv.get("invoiceDate") or inv.get("date") or inv.get("createdOn")

            # Updated timestamp: keep full ISO
            updated_at_raw = inv.get("modifiedOn") or inv.get("updatedOn") or inv.get("updatedAt") or inv.get("updated_at")

            business_unit_name = (
                self._safe_get(inv, "businessUnit", "name")
                or inv.get("businessUnitName")
                or inv.get("businessUnit")
            )

            job_type_name = (
                self._safe_get(inv, "jobType", "name")
                or inv.get("jobTypeName")
                or inv.get("jobType")
            )

            total = inv.get("total") or inv.get("totalAmount") or self._safe_get(inv, "summary", "total")

            rows.append(
                {
                    "invoice_id": invoice_id,
                    "invoice_date": invoice_date_raw,
                    "business_unit": business_unit_name,
                    "job_type": job_type_name,
                    "total_amount": total,
                    "updated_at": updated_at_raw,
                }
            )

        df = pd.DataFrame(rows)

        for col in self.REQUIRED_COLUMNS:
            if col not in df.columns:
                df[col] = None

        df = df[self.REQUIRED_COLUMNS]

        if df.empty:
            return df

        # Types and formatting
        df["invoice_id"] = df["invoice_id"].astype("string")
        df["business_unit"] = df["business_unit"].astype("string")
        df["job_type"] = df["job_type"].astype("string")
        df["total_amount"] = pd.to_numeric(df["total_amount"], errors="coerce")

        # invoice_date -> YYYY-MM-DD
        invoice_dt = pd.to_datetime(df["invoice_date"], errors="coerce", utc=True)
        df["invoice_date"] = invoice_dt.dt.strftime("%Y-%m-%d")

        # updated_at -> full ISO datetime (UTC, Z)
        updated_dt = pd.to_datetime(df["updated_at"], errors="coerce", utc=True)
        df["updated_at"] = updated_dt.dt.strftime("%Y-%m-%dT%H:%M:%SZ")

        return df
