from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import pandas as pd


@dataclass
class ExcelWriteResult:
    rows_incoming: int
    rows_written: int
    file_path: str


class ExcelWriter:
    """
    Writes a single flat Excel file with one sheet: 'invoices'.

    - File: invoices.xlsx (path provided by Settings)
    - Sheet name: invoices
    - Columns:
        invoice_id, invoice_date, business_unit, job_type, total_amount, updated_at

    If file exists:
      - Load existing sheet
      - Append new rows
      - Deduplicate by invoice_id
      - Keep the most recent updated_at
      - Rewrite entire sheet

    If file does not exist:
      - Create file
      - Write sheet

    No formatting. No multiple sheets.
    """

    def __init__(self, output_path: str, sheet_name: str = "invoices") -> None:
        self._output_path = output_path
        self._sheet_name = sheet_name

    def write_invoices(self, df: pd.DataFrame) -> ExcelWriteResult:
        output_file = Path(self._output_path)
        output_file.parent.mkdir(parents=True, exist_ok=True)

        incoming = int(df.shape[0])

        if output_file.exists():
            existing = pd.read_excel(output_file, sheet_name=self._sheet_name, engine="openpyxl")
            combined = pd.concat([existing, df], ignore_index=True)
        else:
            combined = df.copy()

        # Deduplicate by invoice_id keeping most recent updated_at
        if not combined.empty:
            # ensure strings for sorting; ISO timestamps sort lexicographically correctly
            combined["updated_at"] = combined["updated_at"].astype("string")
            combined.sort_values(by=["invoice_id", "updated_at"], ascending=[True, False], inplace=True)
            combined = combined.drop_duplicates(subset=["invoice_id"], keep="first")

            # Keep column order
            combined = combined[
                ["invoice_id", "invoice_date", "business_unit", "job_type", "total_amount", "updated_at"]
            ]

        with pd.ExcelWriter(output_file, engine="openpyxl") as writer:
            combined.to_excel(writer, index=False, sheet_name=self._sheet_name)

        return ExcelWriteResult(rows_incoming=incoming, rows_written=int(combined.shape[0]), file_path=str(output_file))
