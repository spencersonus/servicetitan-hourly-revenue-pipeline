from __future__ import annotations

from dataclasses import dataclass
from typing import Optional
import os
import pandas as pd
import gspread
from google.oauth2.service_account import Credentials


@dataclass
class GoogleSheetsWriteResult:
    rows_incoming: int
    rows_written: int
    sheet_id: str
    sheet_name: str


class GoogleSheetsWriter:
    """
    Handles writing invoice rows to a Google Sheets document. It appends new rows,
    deduplicates by invoice_id (keeping the latest updated_at), and rewrites
    the sheet. Requires a service account email and private key provided via
    environment variables. The target sheet is identified by its spreadsheet
    ID and a worksheet name.
    """

    def __init__(self, sheet_id: str, sheet_name: str = "invoices") -> None:
        self.sheet_id = sheet_id
        self.sheet_name = sheet_name
        self._client = self._authorize()

    def _authorize(self) -> gspread.Client:
        client_email = os.environ.get("GOOGLE_SERVICE_ACCOUNT_EMAIL")
        private_key = os.environ.get("GOOGLE_PRIVATE_KEY")
        if not client_email or not private_key:
            raise RuntimeError(
                "Google Sheets credentials are not set in environment variables"
            )
        private_key = private_key.replace("\\n", "\n")
        scopes = ["https://www.googleapis.com/auth/spreadsheets"]
        credentials_dict = {
            "type": "service_account",
            "client_email": client_email,
            "private_key": private_key,
            "token_uri": "https://oauth2.googleapis.com/token",
        }
        creds = Credentials.from_service_account_info(credentials_dict, scopes=scopes)
        return gspread.authorize(creds)

    def write_invoices(
        self,
        df: pd.DataFrame,
        dedupe_key: str = "invoice_id",
        updated_col: str = "updated_at",
    ) -> GoogleSheetsWriteResult:
        incoming = int(df.shape[0])
        sh = self._client.open_by_key(self.sheet_id)
        try:
            worksheet = sh.worksheet(self.sheet_name)
        except gspread.exceptions.WorksheetNotFound:
            worksheet = sh.add_worksheet(title=self.sheet_name, rows=1, cols=len(df.columns))
            worksheet.append_row(list(df.columns))
        data = worksheet.get_all_values()
        if data:
            header = data[0]
            existing_rows = data[1:]
            existing_df = pd.DataFrame(existing_rows, columns=header)
        else:
            existing_df = pd.DataFrame(columns=df.columns)
        combined = pd.concat([existing_df, df], ignore_index=True, sort=False)
        if dedupe_key in combined.columns and updated_col in combined.columns:
            combined[updated_col] = pd.to_datetime(combined[updated_col], errors="coerce")
            combined.sort_values(
                by=[dedupe_key, updated_col], ascending=[True, False], inplace=True
            )
            combined = combined.drop_duplicates(subset=[dedupe_key], keep="first")
        combined_values = [combined.columns.tolist()] + combined.astype(str).values.tolist()
        worksheet.clear()
        worksheet.update(combined_values)
        return GoogleSheetsWriteResult(
            rows_incoming=incoming,
            rows_written=int(len(combined)),
            sheet_id=self.sheet_id,
            sheet_name=self.sheet_name,
        )
