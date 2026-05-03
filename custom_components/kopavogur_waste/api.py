from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any
from urllib.parse import quote

BASE_URL = "https://www.kopavogur.is"
PICKUP_URL = f"{BASE_URL}/_/moya/garbage-collection/api/pickup"

@dataclass(frozen=True)
class LocationCandidate:
    id: str
    title: str

class KopavogurWasteApiError(Exception):
    pass

class KopavogurWasteApi:
    def __init__(self, session):
        self._session = session

    async def _json(self, url: str, *, params: dict[str, Any] | None = None) -> Any:
        async with self._session.get(url, params=params, timeout=20) as resp:
            text = await resp.text()
            if resp.status >= 400:
                raise KopavogurWasteApiError(f"HTTP {resp.status}: {text[:200]}")
            try:
                return await resp.json(content_type=None)
            except Exception as err:
                raise KopavogurWasteApiError(f"Invalid JSON from {url}: {text[:200]}") from err

    async def async_get_pickups(self, location_id: str | int) -> list[dict[str, Any]]:
        data = await self._json(PICKUP_URL, params={"location": location_id, "limit": 0})
        if not isinstance(data, list):
            raise KopavogurWasteApiError("Pickup response was not a list")
        return data

    async def async_resolve_address(self, address: str) -> LocationCandidate:
        candidates = await self.async_search_locations(address)
        if not candidates:
            raise KopavogurWasteApiError("No location found for address")
        return candidates[0]

    async def async_search_locations(self, address: str) -> list[LocationCandidate]:
        # The public page is backed by Moya garbage-collection endpoints. Kópavogur may rename
        # the lookup endpoint; try common variants and parse flexibly. Pickup itself is stable.
        endpoints = [
            (f"{BASE_URL}/_/moya/garbage-collection/api/locations", {"q": address}),
            (f"{BASE_URL}/_/moya/garbage-collection/api/locations", {"term": address}),
            (f"{BASE_URL}/_/moya/garbage-collection/api/location", {"q": address}),
            (f"{BASE_URL}/_/moya/garbage-collection/api/address", {"q": address}),
            (f"{BASE_URL}/_/moya/garbage-collection/api/address", {"term": address}),
            (f"{BASE_URL}/_/moya/garbage-collection/api/search", {"q": address}),
        ]
        last_error: Exception | None = None
        for url, params in endpoints:
            try:
                data = await self._json(url, params=params)
                parsed = self._parse_candidates(data)
                if parsed:
                    return parsed
            except Exception as err:
                last_error = err
        raise KopavogurWasteApiError(f"Could not resolve address. Last error: {last_error}")

    def _parse_candidates(self, data: Any) -> list[LocationCandidate]:
        items: list[Any]
        if isinstance(data, list):
            items = data
        elif isinstance(data, dict):
            for key in ("items", "results", "locations", "data"):
                if isinstance(data.get(key), list):
                    items = data[key]
                    break
            else:
                items = [data]
        else:
            return []

        out: list[LocationCandidate] = []
        for item in items:
            if not isinstance(item, dict):
                continue
            loc_id = item.get("id") or item.get("location") or item.get("value") or item.get("area") or item.get("areaId")
            title = item.get("title") or item.get("name") or item.get("label") or item.get("address") or str(loc_id)
            if loc_id is not None:
                out.append(LocationCandidate(str(loc_id), str(title)))
        return out


def ts_to_date(value: int | float | str | None) -> str | None:
    if value in (None, ""):
        return None
    return datetime.fromtimestamp(int(value), tz=timezone.utc).date().isoformat()
