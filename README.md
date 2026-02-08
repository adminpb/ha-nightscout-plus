# Nightscout Plus

[![HACS Custom](https://img.shields.io/badge/HACS-Custom-41BDF5.svg)](https://github.com/hacs/integration)
[![Version](https://img.shields.io/badge/version-1.0.7-blue.svg)](https://github.com/adminpb/ha-nightscout-plus)

Enhanced [Nightscout](https://nightscout.github.io/) integration for Home Assistant with full Plotly chart support.

Unlike the built-in Nightscout integration, **Nightscout Plus** exposes raw SGV history and treatment notes as sensor attributes — making it possible to build rich, interactive glucose charts directly in your HA dashboard.

## Features

- **Blood Glucose sensor** — current value in mmol/L with trend direction icon
  - `history` attribute: array of up to 288 SGV data points (24h) for Plotly charts
  - Each point: `{"date": "ISO local time", "sgv": mmol/L}`
  - `history_count` attribute for diagnostics
  - Delta, direction, noise, device info
- **Notes sensor** — container for Nightscout treatment notes
  - `notes` attribute: array of notes with coordinates for chart overlay
  - Each note: `{"created_at", "text", "sgv", "timestamp_ms", "eventType", ...}`
  - SGV value matched to nearest glucose reading for accurate marker placement
- **Timezone-aware** — all timestamps converted from UTC to local time (configurable, default `Europe/Kyiv`)
- **Direct API access** — uses Nightscout REST API v1 via aiohttp (no py-nightscout dependency)

## Installation

### HACS (recommended)

1. Open HACS → Integrations → ⋮ → Custom repositories
2. Add `https://github.com/adminpb/ha-nightscout-plus` as **Integration**
3. Install **Nightscout Plus**
4. Restart Home Assistant

### Manual

1. Copy the `nightscout_plus/` folder to `/config/custom_components/`
2. Restart Home Assistant

### Setup

1. Go to **Settings → Devices & Integrations → Add Integration**
2. Search for **Nightscout Plus**
3. Enter your Nightscout URL and API Secret (optional if publicly readable)
4. Set number of treatments to fetch (default: 50)

## Dashboard

The integration is designed to work with [Plotly Graph Card](https://github.com/dbuezas/lovelace-plotly-graph-card).

See `dashboard.yaml` for a complete example configuration with:
- Color-coded glucose zones
- Per-point coloring based on glucose level
- Treatment note markers as diamond overlays
- Target line at 4.9 mmol/L

### Glucose Zones

| Zone | Range (mmol/L) | Color |
|------|----------------|-------|
| LOW | < 3.9 | 🔴 Red |
| SAFE | 3.9 – 6.0 | 🟢 Green |
| OK | 6.0 – 7.8 | 🟡 Yellow-green |
| HIGH | 7.8 – 10.0 | 🩷 Pink |
| VERY HIGH | > 10.0 | 🔴 Red |
| Target | 4.9 | Dark green solid line |

### Plotly Configuration

The chart reads data from sensor attributes, not from HA's history database:

```yaml
# SGV line + dots from attributes
x: |-
  $fn ({ hass }) => {
    const hist = hass.states['sensor.nightscout_plus_blood_glucose']?.attributes?.history;
    if (!hist || !Array.isArray(hist) || hist.length === 0) return [];
    return hist.map(h => h.date);
  }

# Notes overlay
x: |-
  $fn ({ hass }) => {
    const notes = hass.states['sensor.nightscout_plus_notes']?.attributes?.notes || [];
    return notes
      .filter(n => n && n.created_at && n.sgv !== null)
      .map(n => n.created_at);
  }
```

## File Structure

```
custom_components/nightscout_plus/
├── __init__.py        # Platform setup & teardown
├── api.py             # Async HTTP client for Nightscout REST API v1
├── config_flow.py     # UI configuration flow with reconfigure support
├── const.py           # Constants, icons, event type mappings
├── coordinator.py     # DataUpdateCoordinator (SGV + treatments → notes)
├── manifest.json      # Integration metadata
├── sensor.py          # Blood Glucose + Notes sensor entities
└── strings.json       # UI strings for config flow
```

## Requirements

- Home Assistant 2024.1+
- [Plotly Graph Card](https://github.com/dbuezas/lovelace-plotly-graph-card) (HACS) — for dashboard charts
- Nightscout instance with API v1 enabled

## Changelog

### v1.0.7 (2026-02-08)
- **FIX**: UTC → local timezone conversion for all timestamps (sensor + coordinator)
- **NEW**: `history[]` attribute on Blood Glucose sensor for Plotly charts
- **NEW**: `history_count` diagnostic attribute
- **NEW**: Hover tooltips with time display (`%H:%M`)
- **IMPROVE**: Color-coded glucose zones (LOW/SAFE/OK/HIGH/VERY HIGH) + target 4.9

### v1.0.4
- Initial release with SGV + Notes sensors

## License

MIT
