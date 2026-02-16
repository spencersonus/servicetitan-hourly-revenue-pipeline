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

    # Deduplicate
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

    # 🔥 HARD SANITIZE EVERYTHING
    combined = combined.replace([float("inf"), float("-inf")], None)
    combined = combined.where(pd.notnull(combined), None)

    # Convert entire dataframe to pure Python strings safely
    safe_values = [combined.columns.tolist()]

    for row in combined.itertuples(index=False):
        safe_row = []
        for value in row:
            if value is None:
                safe_row.append("")
            else:
                safe_row.append(str(value))
        safe_values.append(safe_row)

    worksheet.clear()
    worksheet.update(safe_values)

    return GoogleSheetsWriteResult(
        rows_incoming=incoming,
        rows_written=int(len(combined)),
        sheet_id=self.sheet_id,
        sheet_name=self.sheet_name,
    )
