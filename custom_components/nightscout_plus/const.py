"""Constants for Nightscout Plus integration."""

DOMAIN = "nightscout_plus"

CONF_URL = "url"
CONF_API_SECRET = "api_secret"
CONF_TREATMENTS_COUNT = "treatments_count"

# Ти казав: до ~50 нотаток на добу -> 50 достатньо.
DEFAULT_TREATMENTS_COUNT = 50

# Частота опитування (сек). Залишаю як було.
DEFAULT_SCAN_INTERVAL = 300  # секунд

# Nightscout API endpoints
API_ENTRIES = "/api/v1/entries/sgv.json"
API_TREATMENTS = "/api/v1/treatments.json"
API_STATUS = "/api/v1/status.json"
API_DEVICE_STATUS = "/api/v1/devicestatus.json"

# Treatment event types grouped by category
NOTE_EVENT_TYPES = {
    "Note",
    "Announcement",
    "Question",
    "OpenAPS Offline",
    "Temporary Target",
}
MEAL_EVENT_TYPES = {
    "Meal Bolus",
    "Carb Correction",
    "Snack Bolus",
}
BOLUS_EVENT_TYPES = {
    "Correction Bolus",
    "Meal Bolus",
    "Snack Bolus",
    "Bolus",
    "Combo Bolus",
}
EXERCISE_EVENT_TYPES = {"Exercise"}

# Icons
ICON_GLUCOSE = "mdi:diabetes"
ICON_TREATMENT = "mdi:needle"
ICON_NOTE = "mdi:note-text"
ICON_MEAL = "mdi:food-apple"
ICON_BOLUS = "mdi:needle"
ICON_EXERCISE = "mdi:run"
ICON_LIST = "mdi:format-list-bulleted"
ICON_IOB = "mdi:water"
ICON_COB = "mdi:bread-slice"

# Glucose direction → icon mapping (як в оригінальній інтеграції)
DIRECTION_ICONS = {
    "DoubleUp": "mdi:chevron-double-up",
    "SingleUp": "mdi:chevron-up",
    "FortyFiveUp": "mdi:arrow-top-right",
    "Flat": "mdi:arrow-right",
    "FortyFiveDown": "mdi:arrow-bottom-right",
    "SingleDown": "mdi:chevron-down",
    "DoubleDown": "mdi:chevron-double-down",
}

# Platforms to set up
PLATFORMS = ["sensor"]
