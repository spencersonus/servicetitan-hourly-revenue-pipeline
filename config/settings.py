from __future__ import annotations

import os
from dataclasses import dataclass


class SettingsError(RuntimeError):
    """Raised when required settings are missing or invalid."""


@dataclass(frozen=True)
class Settings:
    client_id: str
    client_secret: str
    tenant_id: str
    app_key: str
    base_url: str
    auth_url: str

    request_timeout_seconds: float = 30.0
    page_size: int = 500

    state_path: str = "state/sync_state.json"
    log_path: str = "logs/app.log"
    output_path: str = "output/invoices.xlsx"

    @staticmethod
    def _require_env(name: str) -> str:
        value = os.environ.get(name, "").strip()
        if not value:
            raise SettingsError(f"Missing required environment variable: {name}")
        return value

    @staticmethod
    def _derive_auth_url(base_url: str) -> str:
        # Production:  https://auth.servicetitan.io/connect/token
        # Integration: https://auth-integration.servicetitan.io/connect/token
        if "api-integration" in base_url:
            return "https://auth-integration.servicetitan.io/connect/token"
        return "https://auth.servicetitan.io/connect/token"

    @classmethod
    def from_env(cls) -> "Settings":
        base_url = cls._require_env("BASE_URL").rstrip("/")
        if not base_url.startswith("https://"):
            raise SettingsError("BASE_URL must start with https://")

        output_path = os.environ.get("EXCEL_PATH", "").strip() or "output/invoices.xlsx"

        settings = cls(
            client_id=cls._require_env("CLIENT_ID"),
            client_secret=cls._require_env("CLIENT_SECRET"),
            tenant_id=cls._require_env("TENANT_ID"),
            app_key=cls._require_env("APP_KEY"),
            base_url=base_url,
            auth_url=cls._derive_auth_url(base_url),
            output_path=output_path,
        )

        if not (1 <= settings.page_size <= 5000):
            raise SettingsError("page_size must be between 1 and 5000")

        return settings
