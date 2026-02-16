from __future__ import annotations

import time
from dataclasses import dataclass
from typing import Optional

import requests


class AuthError(RuntimeError):
    """Raised when OAuth token retrieval fails."""


@dataclass
class AccessToken:
    token: str
    expires_at_epoch: float  # epoch seconds when token is considered expired (with buffer)

    def is_valid(self) -> bool:
        return time.time() < self.expires_at_epoch


class OAuthClientCredentialsProvider:
    """OAuth2 client-credentials token provider with in-memory caching."""

    def __init__(self, auth_url: str, client_id: str, client_secret: str, timeout_seconds: float = 30.0) -> None:
        self._auth_url = auth_url
        self._client_id = client_id
        self._client_secret = client_secret
        self._timeout_seconds = timeout_seconds
        self._cached: Optional[AccessToken] = None

    def get_token(self) -> str:
        if self._cached and self._cached.is_valid():
            return self._cached.token

        token = self._request_new_token()
        self._cached = token
        return token.token

    def _request_new_token(self) -> AccessToken:
        headers = {"Content-Type": "application/x-www-form-urlencoded"}
        data = {
            "grant_type": "client_credentials",
            "client_id": self._client_id,
            "client_secret": self._client_secret,
        }

        try:
            resp = requests.post(self._auth_url, headers=headers, data=data, timeout=self._timeout_seconds)
        except requests.RequestException as exc:
            raise AuthError(f"Failed to reach auth server: {exc}") from exc

        if resp.status_code != 200:
            raise AuthError(f"Token request failed: HTTP {resp.status_code} - {resp.text}")

        payload = resp.json()
        access_token = str(payload.get("access_token", "")).strip()
        expires_in = int(payload.get("expires_in", 0))
        if not access_token or expires_in <= 0:
            raise AuthError(f"Invalid token response: {payload}")

        buffer_seconds = 30
        expires_at = time.time() + max(0, expires_in - buffer_seconds)
        return AccessToken(token=access_token, expires_at_epoch=expires_at)
