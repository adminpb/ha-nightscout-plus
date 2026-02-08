"""Sensor entities for Nightscout Plus.

v1.0.7:
  1) Blood Glucose (SGV) — з атрибутом history[] для Plotly графіка
  2) Notes — контейнер зі списком notes для plotly overlay
  
  Часові мітки конвертуються в Europe/Kyiv.
"""

import logging
from datetime import datetime, timezone, timedelta
from typing import Any, Optional

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorStateClass,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceEntryType
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import (
    DOMAIN,
    DIRECTION_ICONS,
    ICON_GLUCOSE,
    ICON_NOTE,
)
from .coordinator import NightscoutPlusCoordinator, NightscoutData

_LOGGER = logging.getLogger(__name__)

# mg/dL to mmol/L conversion factor
MGDL_TO_MMOL = 1.0 / 18.0182

# Local timezone
try:
    from zoneinfo import ZoneInfo
    LOCAL_TZ = ZoneInfo("Europe/Kyiv")
except Exception:
    LOCAL_TZ = timezone(timedelta(hours=2))


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up sensor entities from config entry."""
    coordinator: NightscoutPlusCoordinator = hass.data[DOMAIN][entry.entry_id][
        "coordinator"
    ]

    entities = [
        NightscoutGlucoseSensor(coordinator, entry),
        NightscoutNotesSensor(coordinator, entry),
    ]

    async_add_entities(entities)


# ---------------------------------------------------------------------------
# Base class
# ---------------------------------------------------------------------------
class NightscoutPlusBaseSensor(
    CoordinatorEntity[NightscoutPlusCoordinator], SensorEntity
):
    """Base sensor for Nightscout Plus."""

    _attr_has_entity_name = True

    def __init__(
        self,
        coordinator: NightscoutPlusCoordinator,
        entry: ConfigEntry,
        key: str,
        name: str,
        icon: str,
    ) -> None:
        super().__init__(coordinator)
        self._attr_unique_id = f"{entry.entry_id}_{key}"
        self._attr_name = name
        self._attr_icon = icon
        self._entry = entry

    @property
    def device_info(self):
        return {
            "identifiers": {(DOMAIN, self._entry.entry_id)},
            "name": "Nightscout",
            "manufacturer": "Nightscout Foundation",
            "model": "CGM Remote Monitor",
            "entry_type": DeviceEntryType.SERVICE,
        }

    @property
    def _data(self) -> NightscoutData:
        return self.coordinator.data


# ---------------------------------------------------------------------------
# 1. Blood Glucose (SGV)
# ---------------------------------------------------------------------------
class NightscoutGlucoseSensor(NightscoutPlusBaseSensor):
    """Current blood glucose value with trend direction icon.
    
    Атрибут history[] містить масив SGV точок для Plotly:
      [{"date": "ISO local", "sgv": mmol/L}, ...]
    """

    _attr_state_class = SensorStateClass.MEASUREMENT
    _attr_device_class = SensorDeviceClass.BLOOD_GLUCOSE_CONCENTRATION
    _attr_native_unit_of_measurement = "mg/dL"
    _attr_suggested_unit_of_measurement = "mmol/L"

    def __init__(self, coordinator, entry):
        super().__init__(
            coordinator, entry, "blood_glucose", "Blood Glucose", ICON_GLUCOSE
        )

    @property
    def native_value(self) -> Optional[float]:
        sgv = self._data.latest_sgv
        if sgv:
            raw = sgv.get("sgv")
            if raw is None:
                return None
            return float(raw)
        return None

    @property
    def icon(self) -> str:
        sgv = self._data.latest_sgv
        if sgv:
            direction = sgv.get("direction", "")
            return DIRECTION_ICONS.get(direction, ICON_GLUCOSE)
        return ICON_GLUCOSE

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        sgv = self._data.latest_sgv
        if not sgv:
            return {"history": [], "history_count": 0}
        attrs: dict[str, Any] = {}

        raw = sgv.get("sgv")
        if raw is not None:
            attrs["value_mmol"] = round(float(raw) * MGDL_TO_MMOL, 1)

        attrs["direction"] = sgv.get("direction")
        attrs["date"] = sgv.get("dateString")
        delta = sgv.get("delta")
        if delta is not None:
            attrs["delta"] = delta
            attrs["delta_mmol"] = round(float(delta) * MGDL_TO_MMOL, 1)
        attrs["device"] = sgv.get("device")
        attrs["noise"] = sgv.get("noise")

        # SGV history array for Plotly chart
        # Each entry: {"date": "local ISO string", "sgv": mmol/L float}
        history = []
        for s in self._data.sgvs:
            val = s.get("sgv")
            if val is None:
                continue
            try:
                sgv_mmol = round(float(val) * MGDL_TO_MMOL, 2)
            except (TypeError, ValueError):
                continue

            # Parse timestamp → local ISO string
            date_str = None
            date_ms = s.get("date")
            if isinstance(date_ms, (int, float)):
                dt_utc = datetime.fromtimestamp(date_ms / 1000, tz=timezone.utc)
                dt_local = dt_utc.astimezone(LOCAL_TZ)
                date_str = dt_local.isoformat()
            else:
                raw_ds = s.get("dateString")
                if raw_ds and isinstance(raw_ds, str):
                    try:
                        v = raw_ds.replace("Z", "+00:00")
                        dt_utc = datetime.fromisoformat(v)
                        if dt_utc.tzinfo is None:
                            dt_utc = dt_utc.replace(tzinfo=timezone.utc)
                        dt_local = dt_utc.astimezone(LOCAL_TZ)
                        date_str = dt_local.isoformat()
                    except Exception:
                        date_str = raw_ds

            if not date_str:
                continue

            history.append({"date": date_str, "sgv": sgv_mmol})

        # API returns newest first, reverse for chronological order
        history.reverse()
        attrs["history"] = history
        attrs["history_count"] = len(history)

        return {k: v for k, v in attrs.items() if v is not None}


# ---------------------------------------------------------------------------
# 2. Notes (timeline container for plotly)
# ---------------------------------------------------------------------------
class NightscoutNotesSensor(NightscoutPlusBaseSensor):
    """Notes container sensor.

    Використання:
    - точки для plotly беремо з attributes["notes"]
    - кожен note має created_at/timestamp_ms/text/sgv
    """

    def __init__(self, coordinator, entry):
        super().__init__(coordinator, entry, "notes", "Notes", ICON_NOTE)

    @property
    def native_value(self) -> Optional[str]:
        notes = self._data.notes
        if not notes:
            return None
        last = notes[-1]
        text = last.get("text")
        if isinstance(text, str) and text.strip():
            return text.strip()[:255]
        return "Notes"

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        return {
            "count": len(self._data.notes),
            "notes": self._data.notes,
        }
