"""Nightscout API client — пряме з'єднання через aiohttp.

Працює напряму з Nightscout REST API v1, без бібліотеки py-nightscout,
що дозволяє отримувати ВСІ поля (включно з notes, foodType тощо).
"""

import hashlib
import logging
from typing import Any, Optional

from aiohttp import ClientSession, ClientTimeout

from .const import API_ENTRIES, API_TREATMENTS, API_STATUS, API_DEVICE_STATUS

_LOGGER = logging.getLogger(__name__)

DEFAULT_TIMEOUT = ClientTimeout(total=30)


class NightscoutAPIError(Exception):
    """Nightscout API error."""


class NightscoutAuthError(NightscoutAPIError):
    """Authentication error."""


class NightscoutClient:
    """Async HTTP client for Nightscout API v1."""

    def __init__(
        self,
        url: str,
        api_secret: Optional[str] = None,
        session: Optional[ClientSession] = None,
    ) -> None:
        self._url = url.rstrip("/")
        self._session = session
        self._own_session = session is None

        self._headers: dict[str, str] = {
            "Content-Type": "application/json",
            "Accept": "application/json",
        }
        if api_secret:
            # Nightscout очікує SHA1 хеш api_secret
            self._headers["api-secret"] = hashlib.sha1(
                api_secret.encode("utf-8")
            ).hexdigest()

    async def _get_session(self) -> ClientSession:
        if self._session is None or self._session.closed:
            self._session = ClientSession(timeout=DEFAULT_TIMEOUT)
            self._own_session = True
        return self._session

    async def close(self) -> None:
        if self._own_session and self._session and not self._session.closed:
            await self._session.close()

    async def _request(self, path: str, params: Optional[dict] = None) -> Any:
        session = await self._get_session()
        url = f"{self._url}{path}"
        try:
            async with session.get(url, headers=self._headers, params=params) as resp:
                if resp.status == 401:
                    raise NightscoutAuthError(
                        f"Authentication failed (401) for {url}"
                    )
                resp.raise_for_status()
                return await resp.json()
        except NightscoutAuthError:
            raise
        except Exception as exc:
            raise NightscoutAPIError(f"Request to {url} failed: {exc}") from exc

    async def get_server_status(self) -> dict:
        """GET /api/v1/status.json"""
        return await self._request(API_STATUS)

    async def get_sgvs(self, count: int = 1) -> list[dict]:
        """GET /api/v1/entries/sgv.json — останні SGV записи."""
        return await self._request(API_ENTRIES, {"count": str(count)})

    async def get_treatments(self, count: int = 15) -> list[dict]:
        """GET /api/v1/treatments.json — treatments з УСІМА полями."""
        return await self._request(API_TREATMENTS, {"count": str(count)})

    async def get_device_status(self, count: int = 5) -> list[dict]:
        """GET /api/v1/devicestatus.json — статус пристроїв (IOB/COB)."""
        return await self._request(API_DEVICE_STATUS, {"count": str(count)})

    async def test_connection(self) -> dict:
        """Перевірка підключення — повертає server status або кидає виняток."""
        return await self.get_server_status()
