from __future__ import annotations

from dataclasses import dataclass
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
    Writes invoice rows to a Google Sheet.

    - Appends new rows
    - Deduplicates by invoice_id (keeps latest updated_at)
    - Rewrites entire worksheet
    - Sanitizes NaN / inf values
    """

    def __init__(self, sheet_id: str, sheet_name: str = "invoices") -> None:
        self.sheet_id = sheet_id
        self.sheet_name = sheet_name
        self._client = self._authorize()

    def _authorize(self) -> gspread.Client:
        client_email = os.environ.get("GOOGLE_SERVICE_ACCOUNT_EMAIL")
        private_key = os.environ.get("GOOGLE_PRIVATE_KEY")

        if not client_email:
            raise RuntimeError("Missing GOOGLE_SERVICE_ACCOUNT_EMAIL")

        if not private_key:
            raise RuntimeError("Missing GOOGLE_PRIVATE_KEY")

        credentials_dict = {
            "type": "service_account",
            "client_email": client_email.strip(),
            "private_key": private_key,
            "token_uri": "https://oauth2.googleapis.com/token",
        }

        scopes = ["https://www.googleapis.com/auth/spreadsheets"]

        creds = Credentials.from_service_account_info(
            credentials_dict,
            scopes=scopes,
        )

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
            worksheet = sh.add_worksheet(
                title=self.sheet_name,
                rows=1,
                cols=len(df.columns),
            )
            worksheet.append_row(list(df.columns))

        existing_data = worksheet.get_all_values()

        if existing_data:
            header = existing_data[0]
            existing_rows = existing_data[1:]
            existing_df = pd.DataFrame(existing_rows, columns=header)
        else:
            existing_df = pd.DataFrame(columns=df.columns)

        combined = pd.concat([existing_df, df], ignore_index=True, sort=False)

        if dedupe_key in combined.columns and updated_col in combined.columns:
            combined[updated_col] = pd.to_datetime(
                combined[updated_col],
                errors="coerce",
            )
            combined.sort_values(
                by=[dedupe_key, updated_col],
                ascending=[True, False],
                inplace=True,
            )
            combined = combined.drop_duplicates(
                subset=[dedupe_key],
                keep="first",
            )

        # 🔥 CRITICAL FIX: Remove NaN / inf before JSON encoding
        combined = combined.replace([float("inf"), float("-inf")], None)
        combined = combined.where(pd.notnull(combined), None)

        # Convert everything to string safely
        safe_values = [
            combined.columns.tolist()
        ] + combined.astype(str).values.tolist()

        worksheet.clear()
        worksheet.update(safe_values)

        return GoogleSheetsWriteResult(
            rows_incoming=incoming,
            rows_written=int(len(combined)),
            sheet_id=self.sheet_id,
            sheet_name=self.sheet_name,
        )
