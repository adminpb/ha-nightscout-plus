"""DataUpdateCoordinator for Nightscout Plus."""

from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone
from typing import Any, Optional

from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .api import NightscoutClient, NightscoutAPIError
from .const import (
    DOMAIN,
    DEFAULT_SCAN_INTERVAL,
    NOTE_EVENT_TYPES,
    MEAL_EVENT_TYPES,
    BOLUS_EVENT_TYPES,
    EXERCISE_EVENT_TYPES,
)

_LOGGER = logging.getLogger(__name__)

# Local timezone for display
try:
    from zoneinfo import ZoneInfo
    LOCAL_TZ = ZoneInfo("Europe/Kyiv")
except Exception:
    LOCAL_TZ = timezone(timedelta(hours=2))  # fallback EET


def _parse_iso_to_ms(value: Optional[str]) -> Optional[int]:
    """Parse ISO datetime string to epoch milliseconds."""
    if not value or not isinstance(value, str):
        return None
    try:
        v = value.replace("Z", "+00:00")
        dt = datetime.fromisoformat(v)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return int(dt.timestamp() * 1000)
    except Exception:
        return None


def _ms_to_local_iso(ms: int) -> str:
    """Convert epoch ms to local ISO string."""
    dt_utc = datetime.fromtimestamp(ms / 1000, tz=timezone.utc)
    dt_local = dt_utc.astimezone(LOCAL_TZ)
    return dt_local.isoformat()


class NightscoutData:
    """Структура для зберігання всіх даних з Nightscout."""

    def __init__(self) -> None:
        self.sgvs: list[dict[str, Any]] = []
        self.treatments: list[dict[str, Any]] = []
        self.notes: list[dict[str, Any]] = []
        self.device_status: list[dict[str, Any]] = []
        self.server_status: dict[str, Any] = {}

    @property
    def latest_sgv(self) -> Optional[dict[str, Any]]:
        return self.sgvs[0] if self.sgvs else None

    @property
    def latest_treatment(self) -> Optional[dict[str, Any]]:
        return self.treatments[0] if self.treatments else None

    def find_latest_by_event_types(
        self, event_types: set[str]
    ) -> Optional[dict[str, Any]]:
        for t in self.treatments:
            if t.get("eventType") in event_types:
                return t
        return None

    def find_latest_with_notes(self) -> Optional[dict[str, Any]]:
        for t in self.treatments:
            notes = t.get("notes")
            if notes and str(notes).strip():
                return t
        return None

    def find_latest_with_carbs(self) -> Optional[dict[str, Any]]:
        for t in self.treatments:
            carbs = t.get("carbs")
            if carbs and float(carbs) > 0:
                return t
        return None

    def find_latest_with_insulin(self) -> Optional[dict[str, Any]]:
        for t in self.treatments:
            insulin = t.get("insulin")
            if insulin and float(insulin) > 0:
                return t
        return None

    def find_latest_note(self) -> Optional[dict[str, Any]]:
        result = self.find_latest_by_event_types(NOTE_EVENT_TYPES)
        if not result:
            result = self.find_latest_with_notes()
        return result

    def find_latest_meal(self) -> Optional[dict[str, Any]]:
        result = self.find_latest_with_carbs()
        if not result:
            result = self.find_latest_by_event_types(MEAL_EVENT_TYPES)
        return result

    def find_latest_bolus(self) -> Optional[dict[str, Any]]:
        result = self.find_latest_with_insulin()
        if not result:
            result = self.find_latest_by_event_types(BOLUS_EVENT_TYPES)
        return result

    def find_latest_exercise(self) -> Optional[dict[str, Any]]:
        return self.find_latest_by_event_types(EXERCISE_EVENT_TYPES)

    def get_iob(self) -> Optional[float]:
        return None

    def get_cob(self) -> Optional[float]:
        return None


class NightscoutPlusCoordinator(DataUpdateCoordinator[NightscoutData]):
    """Coordinator that fetches data from Nightscout."""

    def __init__(
        self,
        hass: HomeAssistant,
        client: NightscoutClient,
        treatments_count: int = 50,
        update_interval: int = DEFAULT_SCAN_INTERVAL,
    ) -> None:
        super().__init__(
            hass,
            _LOGGER,
            name=DOMAIN,
            update_interval=timedelta(seconds=update_interval),
        )
        self.client = client
        self.treatments_count = treatments_count

    @staticmethod
    def _sgv_time_ms(sgv: dict[str, Any]) -> Optional[int]:
        """Nightscout SGV usually has 'date' (ms)."""
        v = sgv.get("date")
        if isinstance(v, int):
            return v
        return None

    @staticmethod
    def _note_time_ms(t: dict[str, Any]) -> Optional[int]:
        """Nightscout treatment: prefer 'timestamp' (ms), fallback created_at."""
        v = t.get("timestamp")
        if isinstance(v, int):
            return v
        return _parse_iso_to_ms(t.get("created_at"))

    @staticmethod
    def _is_note(t: dict[str, Any]) -> bool:
        """Note if notes text present OR eventType indicates note-ish."""
        notes = t.get("notes")
        if isinstance(notes, str) and notes.strip():
            return True
        if t.get("eventType") in NOTE_EVENT_TYPES:
            return True
        return False

    @staticmethod
    def _note_text(t: dict[str, Any]) -> str:
        notes = t.get("notes")
        if isinstance(notes, str) and notes.strip():
            return notes.strip()
        ev = t.get("eventType")
        if isinstance(ev, str) and ev.strip():
            return ev.strip()
        return "Note"

    def _nearest_sgv_value(
        self, note_ts_ms: int, sgvs: list[dict[str, Any]]
    ) -> Optional[float]:
        """Find nearest SGV by absolute timestamp diff."""
        best_sgv: Optional[dict[str, Any]] = None
        best_diff: Optional[int] = None

        for sgv in sgvs:
            ts = self._sgv_time_ms(sgv)
            if ts is None:
                continue
            diff = abs(ts - note_ts_ms)
            if best_diff is None or diff < best_diff:
                best_diff = diff
                best_sgv = sgv

        if not best_sgv:
            return None

        raw = best_sgv.get("sgv")
        if raw is None:
            return None
        try:
            return float(raw)
        except (TypeError, ValueError):
            return None

    async def _async_update_data(self) -> NightscoutData:
        """Fetch data from Nightscout API."""
        data = NightscoutData()

        try:
            import asyncio

            sgvs_task = self.client.get_sgvs(count=288)
            treatments_task = self.client.get_treatments(count=self.treatments_count)

            results = await asyncio.gather(
                sgvs_task,
                treatments_task,
                return_exceptions=True,
            )

            # SGVs
            if isinstance(results[0], list):
                data.sgvs = results[0]
            elif isinstance(results[0], Exception):
                _LOGGER.warning("Failed to fetch SGVs: %s", results[0])

            # Treatments
            if isinstance(results[1], list):
                data.treatments = results[1]
            elif isinstance(results[1], Exception):
                _LOGGER.warning("Failed to fetch treatments: %s", results[1])

            # Build notes timeline (sorted old→new, local timezone)
            notes: list[dict[str, Any]] = []
            for t in data.treatments:
                if not self._is_note(t):
                    continue

                ts_ms = self._note_time_ms(t)
                if ts_ms is None:
                    continue

                note = {
                    "created_at": _ms_to_local_iso(ts_ms),
                    "timestamp_ms": ts_ms,
                    "text": self._note_text(t),
                    "enteredBy": t.get("enteredBy"),
                    "uuid": t.get("uuid"),
                    "eventType": t.get("eventType"),
                }

                # y-value for marker (put on glucose line)
                sgv = self._nearest_sgv_value(ts_ms, data.sgvs)
                if sgv is None:
                    note["sgv"] = None
                else:
                    note["sgv"] = round(float(sgv) / 18.0182, 1)

                notes.append(note)

            notes.sort(key=lambda x: int(x.get("timestamp_ms", 0)))
            data.notes = notes

        except NightscoutAPIError as err:
            raise UpdateFailed(f"Nightscout API error: {err}") from err
        except Exception as err:
            raise UpdateFailed(f"Unexpected error: {err}") from err

        return data
