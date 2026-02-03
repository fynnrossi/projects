"""HTTP client for the Squash Vision API.

Used by the CLI to register users, upload sessions, and fetch
leaderboard data.
"""

from __future__ import annotations

from typing import Any

import httpx

from squash_vision.social.history import get_api_url


class APIClient:
    """Synchronous client for the Squash Vision API."""

    def __init__(self, base_url: str | None = None, timeout: float = 15.0):
        self.base_url = (base_url or get_api_url()).rstrip("/")
        self.timeout = timeout

    def _url(self, path: str) -> str:
        return f"{self.base_url}{path}"

    def health(self) -> bool:
        try:
            r = httpx.get(self._url("/health"), timeout=self.timeout)
            return r.status_code == 200
        except httpx.HTTPError:
            return False

    def register(
        self, username: str, display_name: str, country_code: str = ""
    ) -> dict[str, Any]:
        r = httpx.post(
            self._url("/register"),
            json={
                "username": username,
                "display_name": display_name,
                "country_code": country_code,
            },
            timeout=self.timeout,
        )
        r.raise_for_status()
        return r.json()

    def upload_session(self, payload: dict[str, Any]) -> dict[str, Any]:
        r = httpx.post(
            self._url("/sessions"),
            json=payload,
            timeout=self.timeout,
        )
        r.raise_for_status()
        return r.json()

    def get_leaderboard(
        self,
        limit: int = 20,
        offset: int = 0,
        country: str | None = None,
        sort_by: str = "best",
    ) -> list[dict[str, Any]]:
        params: dict[str, Any] = {
            "limit": limit,
            "offset": offset,
            "sort_by": sort_by,
        }
        if country:
            params["country"] = country
        r = httpx.get(
            self._url("/leaderboard"),
            params=params,
            timeout=self.timeout,
        )
        r.raise_for_status()
        return r.json()

    def get_user(self, user_id: str) -> dict[str, Any]:
        r = httpx.get(self._url(f"/users/{user_id}"), timeout=self.timeout)
        r.raise_for_status()
        return r.json()

    def get_stats(self, user_id: str, period: str = "month") -> dict[str, Any]:
        r = httpx.get(
            self._url(f"/users/{user_id}/stats"),
            params={"period": period},
            timeout=self.timeout,
        )
        r.raise_for_status()
        return r.json()
