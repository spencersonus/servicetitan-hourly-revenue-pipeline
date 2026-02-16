from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, Iterable, Optional, Callable

import requests
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type


@dataclass
class ApiErrorDetail:
    status_code: int
    message: str
    url: str
    response_text: str


class ApiError(RuntimeError):
    def __init__(self, detail: ApiErrorDetail) -> None:
        super().__init__(f"API error {detail.status_code} for {detail.url}: {detail.message}")
        self.detail = detail


class ApiTimeoutError(RuntimeError):
    pass


class ApiClient:
    def __init__(
        self,
        base_url: str,
        app_key: str,
        get_access_token: Callable[[], str],
        timeout_seconds: float = 30.0,
    ) -> None:
        self._base_url = base_url.rstrip("/")
        self._app_key = app_key
        self._get_access_token = get_access_token
        self._timeout_seconds = timeout_seconds
        self._session = requests.Session()

    def _headers(self) -> Dict[str, str]:
        return {
            "Authorization": f"Bearer {self._get_access_token()}",
            "ST-App-Key": self._app_key,
            "Accept": "application/json",
        }

    @retry(
        reraise=True,
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=1, max=10),
        retry=retry_if_exception_type((requests.RequestException, ApiTimeoutError, ApiError)),
    )
    def request(
        self,
        method: str,
        path: str,
        params: Optional[Dict[str, Any]] = None,
        json_body: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        url = f"{self._base_url}/{path.lstrip('/')}"
        try:
            resp = self._session.request(
                method=method.upper(),
                url=url,
                headers=self._headers(),
                params=params,
                json=json_body,
                timeout=self._timeout_seconds,
            )
        except requests.Timeout as exc:
            raise ApiTimeoutError(f"Request timed out after {self._timeout_seconds}s: {url}") from exc
        except requests.RequestException as exc:
            raise exc

        if not (200 <= resp.status_code < 300):
            raise ApiError(
                ApiErrorDetail(
                    status_code=resp.status_code,
                    message="Non-success status code",
                    url=url,
                    response_text=resp.text,
                )
            )

        try:
            return resp.json()
        except ValueError as exc:
            raise ApiError(
                ApiErrorDetail(
                    status_code=resp.status_code,
                    message="Failed to parse JSON response",
                    url=url,
                    response_text=resp.text,
                )
            ) from exc

    def get_paginated(
        self,
        path: str,
        base_params: Optional[Dict[str, Any]] = None,
        page_size: int = 500,
    ) -> Iterable[Dict[str, Any]]:
        params: Dict[str, Any] = dict(base_params or {})
        page = 1

        while True:
            params["Page"] = page
            params["PageSize"] = page_size

            payload = self.request("GET", path, params=params)

            data = payload.get("data", [])
            if not isinstance(data, list):
                raise ApiError(
                    ApiErrorDetail(
                        status_code=200,
                        message="Unexpected payload shape: 'data' is not a list",
                        url=f"{self._base_url}/{path.lstrip('/')}",
                        response_text=str(payload),
                    )
                )

            for item in data:
                if isinstance(item, dict):
                    yield item

            has_more = bool(payload.get("hasMore", False))
            if not has_more:
                break

            page += 1
