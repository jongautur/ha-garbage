from __future__ import annotations

import json
import re
from dataclasses import dataclass
from datetime import date, datetime, timedelta, timezone
from typing import Any

from .const import RVK_BIN_LABELS

# ---------------------------------------------------------------------------
# Shared
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class LocationCandidate:
    id: str
    title: str

class WasteApiError(Exception):
    pass


def ts_to_date(value: int | float | str | None) -> str | None:
    if value in (None, ""):
        return None
    return datetime.fromtimestamp(int(value), tz=timezone.utc).date().isoformat()


# ---------------------------------------------------------------------------
# Kópavogur
# ---------------------------------------------------------------------------

_KOP_BASE = "https://www.kopavogur.is"
_KOP_PICKUP = f"{_KOP_BASE}/_/moya/garbage-collection/api/pickup"

class KopavogurApi:
    def __init__(self, session) -> None:
        self._session = session

    async def _json(self, url: str, *, params: dict | None = None) -> Any:
        async with self._session.get(url, params=params, timeout=20) as resp:
            text = await resp.text()
            if resp.status >= 400:
                raise WasteApiError(f"HTTP {resp.status}: {text[:200]}")
            try:
                return await resp.json(content_type=None)
            except Exception as err:
                raise WasteApiError(f"Invalid JSON from {url}: {text[:200]}") from err

    async def async_get_pickups(self, location_id: str) -> list[dict]:
        data = await self._json(_KOP_PICKUP, params={"location": location_id, "limit": 0})
        if not isinstance(data, list):
            raise WasteApiError("Pickup response was not a list")
        result = []
        for item in data:
            dates = item.get("dates") or []
            next_dates = sorted(filter(None, (ts_to_date(d.get("dateFrom")) for d in dates)))
            result.append({
                "id": str(item.get("id", "")),
                "title": str(item.get("title", item.get("id", ""))),
                "next_dates": next_dates,
            })
        return result

    async def async_search_locations(self, address: str) -> list[LocationCandidate]:
        endpoints = [
            (f"{_KOP_BASE}/_/moya/garbage-collection/api/locations", {"q": address}),
            (f"{_KOP_BASE}/_/moya/garbage-collection/api/locations", {"term": address}),
            (f"{_KOP_BASE}/_/moya/garbage-collection/api/search", {"q": address}),
            (f"{_KOP_BASE}/_/moya/garbage-collection/api/address", {"q": address}),
        ]
        last_err: Exception | None = None
        for url, params in endpoints:
            try:
                data = await self._json(url, params=params)
                candidates = self._parse_candidates(data)
                if candidates:
                    return candidates
            except Exception as err:
                last_err = err
        raise WasteApiError(f"Could not resolve address. Last error: {last_err}")

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
        out = []
        for item in items:
            if not isinstance(item, dict):
                continue
            loc_id = (
                item.get("id") or item.get("location") or
                item.get("value") or item.get("area") or item.get("areaId")
            )
            title = (
                item.get("title") or item.get("name") or
                item.get("label") or item.get("address") or str(loc_id)
            )
            if loc_id is not None:
                out.append(LocationCandidate(str(loc_id), str(title)))
        return out


# ---------------------------------------------------------------------------
# Reykjavík
# ---------------------------------------------------------------------------

_RVK_DATA_URL = "https://reykjavik.is/sorphirdudagatal.data"
_RVK_AUTOCOMPLETE_URL = "https://reykjavik.is/location/addresses.data"
_RVK_AUTOCOMPLETE_ROUTE = "features/Location/routes/api/getAddressSearchRoute-0"

class ReykjavikApi:
    def __init__(self, session) -> None:
        self._session = session

    async def _fetch_text(self, url: str, params: dict) -> str:
        async with self._session.get(
            url,
            params=params,
            timeout=20,
            headers={"Accept": "text/x-component, */*"},
        ) as resp:
            if resp.status >= 400:
                raise WasteApiError(f"HTTP {resp.status} from {url}")
            return await resp.text()

    async def async_get_pickups(self, address: str, postal_code: str) -> list[dict]:
        text = await self._fetch_text(_RVK_DATA_URL, {"a": address, "p": postal_code})
        return self._parse_pickups(text)

    async def async_search_locations(self, query: str) -> list[LocationCandidate]:
        text = await self._fetch_text(
            _RVK_AUTOCOMPLETE_URL,
            {"q": query, "_routes": _RVK_AUTOCOMPLETE_ROUTE},
        )
        return self._parse_autocomplete(text)

    # ------------------------------------------------------------------
    # Parsing
    # ------------------------------------------------------------------

    def _extract_p_chunk(self, text: str, chunk_id: str) -> list:
        """Extract and parse a P-chunk array from an RSC response."""
        match = re.search(rf'{re.escape(chunk_id)}:(\[.+)', text, re.DOTALL)
        if not match:
            return []
        decoder = json.JSONDecoder()
        try:
            arr, _ = decoder.raw_decode(match.group(1))
        except json.JSONDecodeError:
            return []
        return arr if isinstance(arr, list) else []

    def _resolve_rsc(self, arr: list) -> dict:
        """
        Resolve the RSC wire-format flat array into a plain Python dict.

        The array uses absolute indices. P-chunk arrays start at an offset
        encoded in their first element: arr[0] = [-7, next_abs] where
        next_abs - 1 is the absolute index of arr[0].
        """
        first = arr[0]
        if not (isinstance(first, list) and len(first) >= 2 and isinstance(first[1], int)):
            raise WasteApiError("Unexpected RSC array format")
        offset = first[1] - 1  # absolute index of arr[0]

        def get(abs_idx: int):
            local = abs_idx - offset
            return arr[local] if 0 <= local < len(arr) else None

        def resolve(abs_idx: int):
            if abs_idx < 0:
                return None
            val = get(abs_idx)
            if val is None:
                return None
            if isinstance(val, dict):
                return {
                    get(int(k[1:])): resolve(v) if isinstance(v, int) else v
                    for k, v in val.items()
                    if k.startswith("_")
                }
            if isinstance(val, list):
                return [resolve(i) if isinstance(i, int) and i >= 0 else None for i in val]
            return val

        return resolve, offset, get

    def _parse_pickups(self, text: str) -> list[dict]:
        # Find which P-chunk contains sorpInfo (the schedule data).
        # The outer array references sorpInfo as ["P", N]; find N.
        chunk_match = re.search(r'"sorpInfo",\["P",(\d+)\]', text)
        chunk_id = f"P{chunk_match.group(1)}" if chunk_match else "P18"

        arr = self._extract_p_chunk(text, chunk_id)
        if not arr:
            raise WasteApiError("No schedule data found in Reykjavík response")

        try:
            resolve, offset, get = self._resolve_rsc(arr)
        except WasteApiError:
            raise
        except Exception as err:
            raise WasteApiError(f"Failed to parse Reykjavík response: {err}") from err

        try:
            nb_local = arr.index("nextBinnings")
        except ValueError:
            raise WasteApiError("No pickup schedule found for this address")

        nb_abs = offset + nb_local + 1
        nb_resolved = resolve(nb_abs)

        if not isinstance(nb_resolved, dict):
            raise WasteApiError("Failed to resolve pickup schedule")

        result = []
        for bin_key, label in RVK_BIN_LABELS.items():
            bin_data = nb_resolved.get(bin_key)
            if not isinstance(bin_data, dict):
                continue
            next_dates = bin_data.get("next") or []
            next_dates = sorted({d for d in next_dates if isinstance(d, str) and d})
            result.append({"id": bin_key, "title": label, "next_dates": next_dates})

        return result

    def _parse_autocomplete(self, text: str) -> list[LocationCandidate]:
        """
        Extract address candidates from the Reykjavík autocomplete response.
        Looks for (address_string, postal_code) pairs encoded in the RSC array.
        Falls back to regex scanning for the pattern used in the stadfang data.
        """
        # Try each P-chunk
        for chunk_match in re.finditer(r'P(\d+):', text):
            arr = self._extract_p_chunk(text, f"P{chunk_match.group(1)}")
            candidates = self._candidates_from_array(arr)
            if candidates:
                return candidates

        # Fallback: scan for quoted address strings followed by postal codes
        # Pattern from stadfang data: "heiti_nefnifall","<street>","postnumer_id","<code>"
        results = []
        for m in re.finditer(r'"heiti_nefnifall","([^"]+)","[^"]*postnumer_id","(\d+)"', text):
            street, postal = m.group(1), m.group(2)
            results.append(LocationCandidate(id=f"{street}:{postal}", title=f"{street}, {postal}"))
        return results

    def _candidates_from_array(self, arr: list) -> list[LocationCandidate]:
        if not arr:
            return []
        try:
            street_idx = arr.index("heiti_nefnifall")
            postal_idx = arr.index("postnumer_id")
        except ValueError:
            return []

        candidates = []
        for i in range(len(arr) - 1):
            if arr[i] == "heiti_nefnifall" and isinstance(arr[i + 1], str):
                street = arr[i + 1]
                for j in range(i, min(i + 30, len(arr) - 1)):
                    if arr[j] == "postnumer_id" and isinstance(arr[j + 1], str):
                        postal = arr[j + 1]
                        candidates.append(
                            LocationCandidate(id=f"{street}:{postal}", title=f"{street}, {postal}")
                        )
                        break
        return candidates


# ---------------------------------------------------------------------------
# Hafnarfjörður
# ---------------------------------------------------------------------------

_HFJ_EVENTS_URL = "https://hafnarfjordur.is/wp-json/avista/get-calendar-events/"
_WEEKDAY_MAP = {"mo": 0, "tu": 1, "we": 2, "th": 3, "fr": 4, "sa": 5, "su": 6}


def _expand_rrule(rrule: dict, today: date, limit: int = 10) -> list[str]:
    """Expand a weekly rrule into upcoming ISO date strings."""
    try:
        dtstart = date.fromisoformat(rrule["dtstart"])
        until = date.fromisoformat(rrule["until"])
        interval_weeks = int(rrule.get("interval", 1))
        days = sorted(_WEEKDAY_MAP[d] for d in (rrule.get("byweekday") or []) if d in _WEEKDAY_MAP)
    except (KeyError, ValueError, TypeError):
        return []

    if not days or until < today:
        return []

    anchor_monday = dtstart - timedelta(days=dtstart.weekday())
    results: list[str] = []
    current_monday = anchor_monday

    while current_monday <= until + timedelta(weeks=1) and len(results) < limit:
        for wd in days:
            candidate = current_monday + timedelta(days=wd)
            if candidate < dtstart or candidate < today:
                continue
            if candidate > until:
                return results
            results.append(candidate.isoformat())
            if len(results) >= limit:
                return results
        current_monday += timedelta(weeks=interval_weeks)

    return results


class HafnarfjordurApi:
    def __init__(self, session) -> None:
        self._session = session

    async def async_get_pickups(self, street: str) -> list[dict]:
        async with self._session.get(
            _HFJ_EVENTS_URL,
            params={"search_street": street},
            timeout=20,
        ) as resp:
            if resp.status >= 400:
                raise WasteApiError(f"HTTP {resp.status} from Hafnarfjörður API")
            try:
                data = await resp.json(content_type=None)
            except Exception as err:
                raise WasteApiError(f"Invalid JSON from Hafnarfjörður API: {err}") from err

        return self._normalize(data)

    def _normalize(self, data: dict) -> list[dict]:
        events = data.get("events") or []
        if not events:
            raise WasteApiError("No events returned — street name not found")

        today = date.today()
        by_type: dict[str, dict] = {}

        for event in events:
            props = event.get("extendedProps") or {}
            trash = props.get("trash_types") or {}
            bin_id = trash.get("value", "")
            bin_label = trash.get("label", bin_id)
            rrule = event.get("rrule") or {}

            if not bin_id or not rrule:
                continue

            if bin_id not in by_type:
                by_type[bin_id] = {"label": bin_label, "rrules": []}
            by_type[bin_id]["rrules"].append(rrule)

        result = []
        for bin_id in sorted(by_type):
            info = by_type[bin_id]
            all_dates: list[str] = []
            for rrule in info["rrules"]:
                all_dates.extend(_expand_rrule(rrule, today, limit=10))
            next_dates = sorted(set(all_dates))[:8]
            result.append({"id": bin_id, "title": info["label"], "next_dates": next_dates})

        return result
