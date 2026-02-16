# servicetitan-hourly-revenue-pipeline

Hourly incremental invoice sync from the ServiceTitan **Production** API (v2) that writes **raw invoice-level rows** to a single flat Excel file.

This is intentionally simple:
- ✅ OAuth2 Client Credentials authentication
- ✅ Incremental sync using `updatedSince` + `state/sync_state.json`
- ✅ Retries + pagination
- ✅ Writes **one** Excel file: `output/invoices.xlsx`
- ✅ No KPI aggregation
- ✅ No Databox Push API
- ✅ No SQL

## What it does
On each run:
1. Reads `last_sync_utc` from `state/sync_state.json`
2. Calls the invoices endpoint with `updatedSince=<last_sync_utc>` (defaults to 7 days ago if missing)
3. Flattens invoices into a strict column set
4. Writes to `output/invoices.xlsx` (sheet `invoices`)
   - Appends new rows
   - Deduplicates by `invoice_id`
   - Keeps the row with the most recent `updated_at`
5. Updates `state/sync_state.json` to the current UTC time if the run succeeds

## Excel output
- File: `output/invoices.xlsx`
- Sheet: `invoices`
- Columns:
  - `invoice_id`
  - `invoice_date` (YYYY-MM-DD)
  - `business_unit`
  - `job_type`
  - `total_amount`
  - `updated_at` (ISO datetime)

### SharePoint usage (Databox reads this file)
Databox will read a **local** Excel file. To have SharePoint keep it synced:
- Option A: Place this repository inside a SharePoint-synced folder, so `output/invoices.xlsx` is synced.
- Option B: Change the Excel output path via the `EXCEL_PATH` environment variable (or adjust the default in `config/settings.py`) to a local SharePoint sync directory, e.g.:
  - macOS: `~/Library/CloudStorage/OneDrive-.../Shared Documents/.../invoices.xlsx`
  - Windows: `C:\Users\<you>\OneDrive - <Org>\Shared Documents\...\invoices.xlsx`

## Setup (local)
### 1) Create a virtual environment
```bash
python3.11 -m venv .venv
source .venv/bin/activate
```

### 2) Install dependencies
```bash
pip install -r requirements.txt
```

### 3) Configure environment variables
Copy `.env.example` → `.env` and fill in values:
```bash
cp .env.example .env
```

Required:
- `CLIENT_ID`
- `CLIENT_SECRET`
- `TENANT_ID`
- `APP_KEY`
- `BASE_URL` (e.g., `https://api.servicetitan.io`)

Optional:
- `EXCEL_PATH` (override output path; defaults to `output/invoices.xlsx`)

### 4) Run
```bash
python main.py
```

Outputs:
- Excel: `output/invoices.xlsx`
- Logs: `logs/app.log`
- State: `state/sync_state.json`

## GitHub Actions (hourly)
Workflow: `.github/workflows/hourly.yml`

- Runs hourly via cron: `0 * * * *`
- Uses Python 3.11
- Installs requirements
- Runs `python main.py`
- Reads credentials from GitHub Secrets:
  - `CLIENT_ID`
  - `CLIENT_SECRET`
  - `TENANT_ID`
  - `APP_KEY`
  - `BASE_URL`

### Cron explanation
`0 * * * *` means “at minute 0 of every hour” (e.g., 1:00, 2:00, 3:00, ...).

## Folder structure
```
servicetitan-hourly-revenue-pipeline/
├── README.md
├── requirements.txt
├── .gitignore
├── .env.example
├── main.py
├── config/
│   └── settings.py
├── services/
│   ├── auth.py
│   ├── api_client.py
│   └── revenue_service.py
├── transform/
│   └── revenue_transformer.py
├── export/
│   └── excel_writer.py
├── state/
│   └── sync_state.json
├── logs/
└── .github/
    └── workflows/
        └── hourly.yml
```
