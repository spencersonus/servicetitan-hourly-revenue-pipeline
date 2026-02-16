# servicetitan-hourly-revenue-pipeline  

Hourly incremental invoice revenue sync from the ServiceTitan **Production** API (v2), designed for automated execution via GitHub Actions.  

## Project overview  
This pipeline:  
1. Authenticates via **OAuth2 Client Credentials** (machine-to-machine)  
2. Pulls invoices updated since the last successful run using `updatedSince` incremental sync logic  
3. Normalizes/flatten invoice data into a tabular structure  
4. Appends into `output/hourly_revenue.xlsx` and deduplicates by `invoice_id`  
5. Writes logs to console and `logs/app.log`  

### Why incremental sync?  
ServiceTitan invoice lists can be large. Instead of pulling everything repeatedly, this pipeline stores a `last_sync_utc` timestamp in `state/sync_state.json`. Each run requests only invoices updated after that timestamp via `updatedSince`. If the state file is missing or empty, it defaults to **7 days ago**.  

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

### 3) Create your `.env`  
Copy `.env.example` → `.env` and fill in values:  
```bash
cp .env.example .env
```

### 4) Run  
```bash
python main.py
```

Outputs:  
- Excel: `output/hourly_revenue.xlsx`  
- Logs: `logs/app.log`  
- State: `state/sync_state.json`  

## Environment variables (.env)  
Required:  
- `CLIENT_ID`  
- `CLIENT_SECRET`  
- `TENANT_ID`  
- `APP_KEY`  
- `BASE_URL`  

Notes:  
- `BASE_URL` should typically be `https://api.servicetitan.io` for Production.  
- The auth token endpoint is derived automatically:  
  - If `BASE_URL` contains `api-integration`, auth becomes `https://auth-integration.servicetitan.io/connect/token`  
  - Otherwise, auth defaults to `https://auth.servicetitan.io/connect/token`  

## GitHub Secrets setup  
In your GitHub repo:  
1. Go to **Settings → Secrets and variables → Actions**  
2. Add these **Repository secrets**:  
   - `CLIENT_ID`  
   - `CLIENT_SECRET`  
   - `TENANT_ID`  
   - `APP_KEY`  
   - `BASE_URL`  

GitHub Actions will inject them into `main.py` at runtime.  

## How the hourly GitHub Action works  
Workflow file: `.github/workflows/hourly.yml`  

- Runs every hour using cron: `0 * * * *`  
- Uses Python 3.11  
- Installs requirements  
- Runs `python main.py`  
- Uploads the generated Excel and logs as artifacts  

## Cron explanation  
`0 * * * *` means:  
- minute = 0  
- every hour  
- every day/month/week  

So it runs at: `HH:00` every hour.  

## How pagination works (ServiceTitan convention)  
ServiceTitan list endpoints support:  
- `Page` (starts at 1)  
- `PageSize` (1–5000, default 50)  

Typical response includes:  
- `hasMore` boolean  
- `data` list  

This repo automatically iterates pages until `hasMore` is false.  

## How to extend to a Databox API push  
A common extension is to push aggregated metrics to Databox after writing Excel.  

Suggested approach:  
1. Add `services/databox_client.py`  
2. After Excel export, compute summary metrics (e.g. total revenue last hour, invoice count)  
3. POST to Databox Push API in `main.py` (guarded by optional env vars, e.g. `DATABOX_PUSH_TOKEN`)  

Keep the current pipeline intact, and treat Databox as an optional downstream.
