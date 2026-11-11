# HomeAssistant component: `clientraw`
[![Validate](https://github.com/pilotak/homeassistant-clientraw/workflows/Validate/badge.svg)](https://github.com/pilotak/homeassistant-clientraw/actions)
[![hacs_badge](https://img.shields.io/badge/HACS-Default-orange.svg)](https://github.com/custom-components/hacs)

The `clientraw` platform is WD Clientraw parser which can read data from your online weather station such a Davis Vantage PRO 2 (tested) and other generating clientraw.txt files

## Set up through the UI

1. Install the integration and restart Home Assistant.
2. Open **Settings > Devices & services > Add integration > Clientraw**.
3. Enter the full HTTP(S) URL of `clientraw.txt`, a station name (default: `clientraw`), a polling interval (1-59 minutes; default: 15), the station date format (DD/MM/YYYY, MM/DD/YYYY or YYYY-MM-DD), and its IANA timezone (for example, `Europe/Oslo`).
4. Review the **Monitored conditions** checklist and submit.

The integration fetches the URL and preselects conditions with usable readings. This is only a setup helper: you can uncheck suggestions or check any other supported condition. Zero values and negative temperatures are valid readings. A station may report zero for unsupported hardware, so detection cannot establish which physical sensors are installed.

Your confirmed selection stays unchanged between polls. Manually selected conditions with missing or malformed readings are unavailable until usable data appears; other readings continue updating. You can intentionally leave the selection empty.

Each station's sensors are grouped under one device named after the configured station. Existing entities join that device on reload without changing their entity IDs. Renaming the station or changing its URL keeps the same device.

### Change settings

- Use **Configure** on the integration entry to change the polling interval and monitored conditions. The checklist starts with your saved selection.
- Optionally select **Prefill a new conditions checklist from the URL** to review fresh suggestions before saving. This replaces your previous selection only after confirmation.
- Use the entry's three-dot menu > **Reconfigure** to change the URL, station name, date format or station timezone. You can keep your current selection or review fresh detection suggestions.
- Changing the URL or name preserves existing entity IDs. Multiple station entries are supported; each must use a different URL.
- Deselected conditions are removed from the entity registry on successful reload, including previously stale entries. Selected conditions with missing readings and selected user-disabled entities are retained. Re-enabling a removed condition creates a new registry entity: custom names, icons, unit overrides and the original entity ID are not guaranteed to survive, so check dashboards and automations. Recorder history is not deleted.
- Temperature, wind speed and gust, atmospheric pressure, precipitation, rain rate, and cloud height sensors use Home Assistant device classes and support per-entity unit selection. For example, choose m/s, km/h, mph or knots in a wind sensor's settings. Initial display units follow HA's unit system, with km/h or mph suggested for wind and in/h suggested for imperial rain rate. Explicit unit overrides are preserved.

### Native units and statistics

Native values do not depend on Home Assistant's unit system: temperatures are Celsius, wind is knots, rain is millimeters, pressure is hPa, cloud height is feet, humidity is percent and solar irradiance is W/m². The source rain rate is mm/min and is multiplied by 60 to expose a fixed mm/h native value, which HA can convert to in/h. HA handles display conversion; display precision is suggested as two decimals without rounding the source reading.

Solar irradiance stays in W/m²: the minimum supported HA 2024.12 does not provide sensor conversion to BTU/(h×ft²). This replaces the previous imperial-only custom conversion.

Live measurements (current temperature/feels-like, humidity, pressure, current and rolling-average wind, rain rate, cloud height, solar and UV) use `measurement` for long-term statistics. Daily, monthly and yearly rainfall use `total_increasing`, with HA treating decreases as counter resets. Station corrections to accumulated rainfall can therefore affect the statistical sum.

Yesterday's rainfall, min/max temperatures and humidity, hourly/daily gust maxima, forecasts, symbols, station/date/timestamps and wind direction have no state class. They are not live measurements or accumulating counters; angle-aware statistics are not available at the supported HA minimum.

Adding a state class does not retroactively backfill long-term statistics. Older incorrect rain-rate/cloud-height readings are not rewritten. If HA reports incompatible historical units or statistics metadata, review **Developer tools > Statistics** rather than deleting history automatically.

### Migrate an existing YAML installation

Existing `sensor: - platform: clientraw` configurations are automatically imported into UI entries on restart, including their name, URL, interval, and exact monitored conditions. Import can complete while the station is offline; Home Assistant retries connecting automatically.

Existing entity IDs, registry customizations, and automation references are preserved. After checking that the imported entry works under **Settings > Devices & services**, remove only the old Clientraw sensor block from `configuration.yaml` and restart. **Do not delete the whole file or unrelated settings.** A Repairs warning reminds you to remove the block. The YAML path is retained only for migration, not for managing new installations.

Leaving the old block temporarily in place will not create duplicate entries or overwrite later UI edits. If multiple legacy definitions conflict over an endpoint or entity, Repairs reports the conflict instead of overwriting or taking ownership of another entry's entities. Resolve the duplicate configuration before removing the affected YAML.

**Rollback is not automatically reversible.** Migration preserves entity IDs forward but rewrites unique IDs and registry ownership to the UI entry. Downgrading and restoring legacy YAML without restoring the registry may create duplicate entities with `_2` suffixes. Take a complete Home Assistant backup before upgrading, including configuration, registries and recorder database. For rollback, restore the matching pre-upgrade backup and integration version; do not manually edit `.storage`.

Existing UI entries and YAML imports default to DD/MM/YYYY and HA's current timezone. The timezone is saved once, so later changes to HA's timezone do not silently change station timestamp interpretation. Use **Reconfigure** if the station differs.

## Supported monitored conditions

All existing conditions remain available in the checklist:
  - **dewpoint**: Dewpoint (°C or °F)
  - **heat_index**: Heat index (°C or °F)
  - **temp**: Temperature (°C or °F)
  - **temp_indoor**: Temperature (°C or °F)
  - **temp_day_max**: Today MAX temperature (°C or °F)
  - **temp_day_min**: Today MIN temperature (°C or °F)
  - **humidex**: Humidex (°C or °F)
  - **wind_degrees**: Where the wind is coming from in degrees, with true north at 0° and progressing clockwise.
  - **wind_dir**: Wind Direction as string ie.: N, NW, etc.
  - **wind_gust_hour**: Wind Gust in last hour (km/h or mph)
  - **wind_gust_day**: Wind Gust in last day (km/h or mph)
  - **wind_speed**: Current Wind Speed (km/h or mph)
  - **wind_speed_average**: Last 60 Sec Avg Wind Speed (km/h or mph)
  - **wind_speed_avg_10min**: 10 Min Avg Wind Speed (km/h or mph)
  - **symbol**: Symbol
  - **daily_rain**: Daily Rain (mm or in)
  - **yesterday_rain**: Yesterday Rain (mm or in)
  - **monthly_rain**: Monthly Rain (mm or in)
  - **yearly_rain**: Yearly Rain (mm or in)
  - **rain_rate**: Rain rate (mm/h or in/h)
  - **pressure**: Pressure (hPa or inHg)
  - **humidity**: Relative humidity (%)
  - **humidity_indoor**: Relative indoor humidity (%)
  - **humidity_max**: Max relative humidity (%)
  - **humidity_min**: Min relative humidity (%)
  - **cloud_height**: Cloud Height (m or ft; source field is feet)
  - **forecast**: string based output ie.: night showers
  - **station**: station name without the trailing update time (for example, `TILSKI`)
  - **date**: current date
  - **last_updated**: station update timestamp combining date field 74 in the configured format with hour/minute/second fields 29-31, interpreted in the configured station timezone and exposed as UTC. This is the feed's timestamp, not the integration's last poll time.
  - **wind_chill**: Wind Chill (°C or °F)
  - **wind_chill_max**: Today MAX Wind Chill (°C or °F)
  - **wind_chill_min**: Today MIN Wind Chill (°C or °F)
  - **vp_solar**: Solar Irradiation (W/m²)
  - **uv_index**: UV Index
  - **apparent_temp**: Apparent temperature (°C or °F)
  - **apparent_temp_min**: Min apparent temperature (°C or °F)
  - **apparent_temp_max**: Max apparent temperature (°C or °F)

For existing entries, enable **Last updated (last_updated)** under **Configure > Monitored conditions**. The Date sensor is retained as raw text for compatibility. Station omits a valid trailing `-HH:MM:SS`; names containing other hyphens are preserved. Timestamp parsing does not depend on that suffix.

Missing/invalid dates or clock fields, and ambiguous/nonexistent local times during daylight-saving transitions, make Last updated unavailable rather than guessing an offset or using poll time. An actionable Repairs warning appears when selected and clears on recovery or deselection; other sensors continue updating. Explicit date format prevents guessing between ambiguous dates such as `9/11/2026`.

### Corrected source interpretations

The supplied [Clientraw description](clientrawdescription.txt) documents rain rate (field 10) in mm/min, cloud height (73) in feet, and Humidex at field 45. The original integration instead treated rain rate as a length, cloud height as meters and Humidex as field 44 (windchill).

- A rain rate of `0.1` now displays 6 mm/h, not 0.1 mm/h.
- A cloud height of `1000` now displays 304.8 m or 1000 ft, not 1000 m or 3280.84 ft.
- Humidex now reads its own field instead of duplicating windchill.
- Apparent temperature values correctly convert to °F rather than retaining Celsius numbers under a Fahrenheit label.

These corrections preserve selected entity IDs but intentionally change affected readings; old recorded values are not corrected.

## Install via [HACS](https://github.com/custom-components/hacs)
You can find this integration in a store.

## Install manually
You need to copy `clientraw` folder from this repo to the `custom_components` folder in the root of your configuration, file tree should look like this:
```
└── ...
└── configuration.yaml
└── custom_components
    └── clientraw
        └── ... (all integration files, including translations/)
```

>__Note__: if the `custom_components` directory does not exist, you need to create it.

## Development

The test suite uses Home Assistant 2024.12.4 on Python 3.12 to check compatibility with the declared 2024.12 minimum:

```sh
python -m pip install -r requirements-test.txt
python -m pytest
python -m pycodestyle custom_components/clientraw tests
```

Tests use deterministic clientraw fixtures; no live weather-station URL is required.

## Symbol codes
```
0 =  sunny
1 =  clear night
2 =  cloudy
3 =  cloudy2
4 =  night cloudy
5 =  dry
6 =  fog
7 =  haze
8 =  heavyrain
9 =  mainly fine
10 = mist
11 = night fog
12 = night heavy rain
13 = night overcast
14 = night rain
15 = night showers
16 = night snow
17 = night thunder
18 = overcast
19 = partly cloudy
20 = rain
21 = rain2
22 = showers
23 = sleet
24 = sleet showers
25 = snow
26 = snow melt
27 = snow showers2
28 = sunny
29 = thunder showers
30 = thunder showers2
31 = thunder storms
32 = tornado
33 = windy
34 = stopped raining
35 = windy rain
36 = sunrise
37 = sunset
```
