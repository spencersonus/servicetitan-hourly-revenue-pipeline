from __future__ import annotations

import logging
import time
from datetime import datetime, timezone
from pathlib import Path

from dotenv import load_dotenv

from config.settings import Settings
from export.excel_writer import ExcelWriter
from services.api_client import ApiClient
from services.auth import OAuthClientCredentialsProvider
from services.revenue_service import RevenueService
from transform.revenue_transformer import RevenueTransformer


def setup_logging(log_path: str) -> logging.Logger:
    Path(log_path).parent.mkdir(parents=True, exist_ok=True)

    logger = logging.getLogger("servicetitan-invoices")
    logger.setLevel(logging.INFO)
    logger.handlers.clear()
    logger.propagate = False

    formatter = logging.Formatter(
        fmt="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
        datefmt="%Y-%m-%dT%H:%M:%SZ",
    )

    ch = logging.StreamHandler()
    ch.setLevel(logging.INFO)
    ch.setFormatter(formatter)

    fh = logging.FileHandler(log_path)
    fh.setLevel(logging.INFO)
    fh.setFormatter(formatter)

    logger.addHandler(ch)
    logger.addHandler(fh)

    # Ensure UTC timestamps in logs
    logging.Formatter.converter = time.gmtime  # type: ignore[attr-defined]

    return logger


def main() -> None:
    # Load .env locally (GitHub Actions provides env vars via Secrets; dotenv is harmless there)
    load_dotenv()

    settings = Settings.from_env()
    logger = setup_logging(settings.log_path)

    start = time.time()
    run_started = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
    logger.info("start | run_started=%s", run_started)

    token_provider = OAuthClientCredentialsProvider(
        auth_url=settings.auth_url,
        client_id=settings.client_id,
        client_secret=settings.client_secret,
        timeout_seconds=settings.request_timeout_seconds,
    )

    api_client = ApiClient(
        base_url=settings.base_url,
        app_key=settings.app_key,
        get_access_token=token_provider.get_token,
        timeout_seconds=settings.request_timeout_seconds,
    )

    revenue_service = RevenueService(
        api_client=api_client,
        tenant_id=settings.tenant_id,
        state_path=settings.state_path,
        page_size=settings.page_size,
    )

    last_sync_utc = revenue_service.read_last_sync_utc()
    logger.info("state | last_sync_utc=%s", last_sync_utc)

    logger.info("token | retrieving access token")
    _ = token_provider.get_token()
    logger.info("token | ok")

    logger.info("fetch | pulling invoices updated since last sync")
    invoices = revenue_service.fetch_updated_invoices()
    logger.info("fetch | records_fetched=%d", len(invoices))

    transformer = RevenueTransformer()
    df = transformer.transform(invoices)
    logger.info("transform | rows=%d", int(df.shape[0]))

    writer = ExcelWriter(settings.output_path, sheet_name="invoices")
    result = writer.write_invoices(df)

    logger.info(
        "export | incoming_rows=%d total_rows_after_write=%d file=%s",
        result.rows_incoming,
        result.rows_written,
        result.file_path,
    )

    # Update sync_state.json ONLY after successful write
    revenue_service.update_sync_state_to_now()
    logger.info("state | sync_state updated")

    duration_s = time.time() - start
    logger.info("completion | duration_seconds=%.2f", duration_s)


if __name__ == "__main__":
    main()
