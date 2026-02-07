"""DataUpdateCoordinator for Nightscout Plus."""

import logging
from datetime import timedelta
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


class NightscoutData:
    """Структура для зберігання всіх даних з Nightscout."""

    def __init__(self) -> None:
        self.sgvs: list[dict] = []
        self.treatments: list[dict] = []
        self.device_status: list[dict] = []
        self.server_status: dict = {}

    @property
    def latest_sgv(self) -> Optional[dict]:
        return self.sgvs[0] if self.sgvs else None

    @property
    def latest_treatment(self) -> Optional[dict]:
        return self.treatments[0] if self.treatments else None

    def find_latest_by_event_types(self, event_types: set[str]) -> Optional[dict]:
        for t in self.treatments:
            if t.get("eventType") in event_types:
                return t
        return None

    def find_latest_with_notes(self) -> Optional[dict]:
        """Знайти останній treatment з непорожнім notes."""
        for t in self.treatments:
            notes = t.get("notes")
            if notes and str(notes).strip():
                return t
        return None

    def find_latest_with_carbs(self) -> Optional[dict]:
        for t in self.treatments:
            carbs = t.get("carbs")
            if carbs and float(carbs) > 0:
                return t
        return None

    def find_latest_with_insulin(self) -> Optional[dict]:
        for t in self.treatments:
            insulin = t.get("insulin")
            if insulin and float(insulin) > 0:
                return t
        return None

    def find_latest_note(self) -> Optional[dict]:
        """Шукає замітку: спочатку по eventType, потім будь-який з notes."""
        result = self.find_latest_by_event_types(NOTE_EVENT_TYPES)
        if not result:
            result = self.find_latest_with_notes()
        return result

    def find_latest_meal(self) -> Optional[dict]:
        result = self.find_latest_with_carbs()
        if not result:
            result = self.find_latest_by_event_types(MEAL_EVENT_TYPES)
        return result

    def find_latest_bolus(self) -> Optional[dict]:
        result = self.find_latest_with_insulin()
        if not result:
            result = self.find_latest_by_event_types(BOLUS_EVENT_TYPES)
        return result

    def find_latest_exercise(self) -> Optional[dict]:
        return self.find_latest_by_event_types(EXERCISE_EVENT_TYPES)

    def get_iob(self) -> Optional[float]:
        """Витягнути IOB з devicestatus (OpenAPS/Loop)."""
        for ds in self.device_status:
            # OpenAPS format
            openaps = ds.get("openaps")
            if openaps:
                iob_data = openaps.get("iob") or openaps.get("suggested", {}).get("IOB")
                if iob_data is not None:
                    if isinstance(iob_data, dict):
                        return iob_data.get("iob")
                    return float(iob_data)
            # Loop format
            loop = ds.get("loop")
            if loop:
                iob_data = loop.get("iob")
                if iob_data and isinstance(iob_data, dict):
                    return iob_data.get("iob")
            # Pump format (деякі uploaders)
            pump = ds.get("pump")
            if pump:
                iob_data = pump.get("iob")
                if iob_data is not None:
                    if isinstance(iob_data, dict):
                        return iob_data.get("bolusiob")
                    return float(iob_data)
        return None

    def get_cob(self) -> Optional[float]:
        """Витягнути COB з devicestatus."""
        for ds in self.device_status:
            openaps = ds.get("openaps")
            if openaps:
                suggested = openaps.get("suggested", {})
                cob = suggested.get("COB")
                if cob is not None:
                    return float(cob)
            loop = ds.get("loop")
            if loop:
                cob_data = loop.get("cob")
                if cob_data and isinstance(cob_data, dict):
                    return cob_data.get("cob")
        return None


class NightscoutPlusCoordinator(DataUpdateCoordinator[NightscoutData]):
    """Coordinator that fetches data from Nightscout."""

    def __init__(
        self,
        hass: HomeAssistant,
        client: NightscoutClient,
        treatments_count: int = 15,
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

    async def _async_update_data(self) -> NightscoutData:
        """Fetch data from Nightscout API."""
        data = NightscoutData()

        try:
            # Паралельно запитуємо всі дані
            import asyncio

            sgvs_task = self.client.get_sgvs(count=1)
            treatments_task = self.client.get_treatments(count=self.treatments_count)
            device_status_task = self.client.get_device_status(count=5)

            results = await asyncio.gather(
                sgvs_task,
                treatments_task,
                device_status_task,
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

            # Device status
            if isinstance(results[2], list):
                data.device_status = results[2]
            elif isinstance(results[2], Exception):
                _LOGGER.debug("Failed to fetch device status: %s", results[2])

        except NightscoutAPIError as err:
            raise UpdateFailed(f"Nightscout API error: {err}") from err

        return data
