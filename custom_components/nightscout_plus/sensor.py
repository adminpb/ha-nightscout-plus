"""Sensor entities for Nightscout Plus.

Зараз створюємо ТІЛЬКИ:
  1) Blood Glucose (SGV)
  2) Notes (контейнер зі списком notes для plotly overlay)

Старі сенсори (meal/bolus/iob/cob/...) залишені в файлі, але НЕ додаються в async_setup_entry,
щоб не генерувати попередження/Unavailable, коли даних в Nightscout немає.
"""

import logging
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
    ICON_TREATMENT,
    ICON_MEAL,
    ICON_BOLUS,
    ICON_EXERCISE,
    ICON_IOB,
    ICON_COB,
    ICON_LIST,
)
from .coordinator import NightscoutPlusCoordinator, NightscoutData

_LOGGER = logging.getLogger(__name__)

# mg/dL to mmol/L conversion factor
MGDL_TO_MMOL = 1.0 / 18.0182


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up sensor entities from config entry."""
    coordinator: NightscoutPlusCoordinator = hass.data[DOMAIN][entry.entry_id][
        "coordinator"
    ]

    # ✅ Тільки 2 сенсори: glucose + notes
    entities = [
        NightscoutGlucoseSensor(coordinator, entry),
        NightscoutNotesSensor(coordinator, entry),
    ]

    async_add_entities(entities)


def _clean_attrs(treatment: Optional[dict]) -> dict[str, Any]:
    """Extract useful attributes from a treatment dict, skip internal fields."""
    if not treatment:
        return {}
    return {
        k: v
        for k, v in treatment.items()
        if not k.startswith("_") and v is not None and v != ""
    }


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
    """Current blood glucose value with trend direction icon."""

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
            return {"history": []}
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
        # Each entry: {"date": "ISO string", "sgv": mmol/L float}
        history = []
        for s in self._data.sgvs:
            val = s.get("sgv")
            if val is None:
                continue
            try:
                sgv_mmol = round(float(val) * MGDL_TO_MMOL, 2)
            except (TypeError, ValueError):
                continue

            # Determine ISO date string
            date_str = s.get("dateString")
            if not date_str:
                date_ms = s.get("date")
                if isinstance(date_ms, (int, float)):
                    from datetime import datetime as _dt, timezone as _tz
                    date_str = _dt.fromtimestamp(
                        date_ms / 1000, tz=_tz.utc
                    ).isoformat()
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
        # state неважливий для графіка — але хай буде щось читабельне
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


# ---------------------------------------------------------------------------
# Нижче — старі сенсори (залишені, але не створюються)
# ---------------------------------------------------------------------------

class NightscoutLastTreatmentSensor(NightscoutPlusBaseSensor):
    """Latest treatment of any kind."""

    def __init__(self, coordinator, entry):
        super().__init__(
            coordinator, entry, "last_treatment", "Last Treatment", ICON_TREATMENT
        )

    @property
    def native_value(self) -> Optional[str]:
        t = self._data.latest_treatment
        if t:
            return t.get("eventType", "Unknown")
        return None

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        return _clean_attrs(self._data.latest_treatment)


class NightscoutLastNoteSensor(NightscoutPlusBaseSensor):
    """Latest user note / annotation."""

    def __init__(self, coordinator, entry):
        super().__init__(coordinator, entry, "last_note", "Last Note", ICON_NOTE)

    @property
    def native_value(self) -> Optional[str]:
        t = self._data.find_latest_note()
        if t:
            notes = t.get("notes", "")
            if notes:
                return str(notes)[:255]
            return t.get("eventType", "Note")
        return None

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        return _clean_attrs(self._data.find_latest_note())


class NightscoutLastMealSensor(NightscoutPlusBaseSensor):
    """Latest meal / carb entry."""

    _attr_native_unit_of_measurement = "g"

    def __init__(self, coordinator, entry):
        super().__init__(coordinator, entry, "last_meal", "Last Meal", ICON_MEAL)

    @property
    def native_value(self) -> Optional[float]:
        t = self._data.find_latest_meal()
        if t:
            carbs = t.get("carbs")
            if carbs:
                return float(carbs)
        return None

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        attrs = _clean_attrs(self._data.find_latest_meal())
        t = self._data.find_latest_meal()
        if t:
            food = t.get("foodType")
            if food:
                attrs["food_type"] = food
        return attrs


class NightscoutLastBolusSensor(NightscoutPlusBaseSensor):
    """Latest insulin bolus."""

    _attr_native_unit_of_measurement = "U"

    def __init__(self, coordinator, entry):
        super().__init__(coordinator, entry, "last_bolus", "Last Bolus", ICON_BOLUS)

    @property
    def native_value(self) -> Optional[float]:
        t = self._data.find_latest_bolus()
        if t:
            insulin = t.get("insulin")
            if insulin:
                return float(insulin)
        return None

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        return _clean_attrs(self._data.find_latest_bolus())


class NightscoutLastExerciseSensor(NightscoutPlusBaseSensor):
    """Latest exercise entry."""

    _attr_native_unit_of_measurement = "min"

    def __init__(self, coordinator, entry):
        super().__init__(
            coordinator, entry, "last_exercise", "Last Exercise", ICON_EXERCISE
        )

    @property
    def native_value(self) -> Optional[float]:
        t = self._data.find_latest_exercise()
        if t:
            duration = t.get("duration")
            if duration:
                return float(duration)
        return None

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        return _clean_attrs(self._data.find_latest_exercise())


class NightscoutIOBSensor(NightscoutPlusBaseSensor):
    """Insulin On Board from devicestatus."""

    _attr_native_unit_of_measurement = "U"
    _attr_state_class = SensorStateClass.MEASUREMENT

    def __init__(self, coordinator, entry):
        super().__init__(coordinator, entry, "iob", "Insulin On Board", ICON_IOB)

    @property
    def native_value(self) -> Optional[float]:
        iob = self._data.get_iob()
        if iob is not None:
            return round(float(iob), 2)
        return None

    @property
    def available(self) -> bool:
        return super().available and self._data.get_iob() is not None


class NightscoutCOBSensor(NightscoutPlusBaseSensor):
    """Carbs On Board from devicestatus."""

    _attr_native_unit_of_measurement = "g"
    _attr_state_class = SensorStateClass.MEASUREMENT

    def __init__(self, coordinator, entry):
        super().__init__(coordinator, entry, "cob", "Carbs On Board", ICON_COB)

    @property
    def native_value(self) -> Optional[float]:
        cob = self._data.get_cob()
        if cob is not None:
            return round(float(cob), 1)
        return None

    @property
    def available(self) -> bool:
        return super().available and self._data.get_cob() is not None