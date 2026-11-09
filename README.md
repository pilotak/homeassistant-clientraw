# HomeAssistant component: `clientraw`
[![Validate](https://github.com/pilotak/homeassistant-clientraw/workflows/Validate/badge.svg)](https://github.com/pilotak/homeassistant-clientraw/actions)
[![hacs_badge](https://img.shields.io/badge/HACS-Default-orange.svg)](https://github.com/custom-components/hacs)

The `clientraw` platform is WD Clientraw parser which can read data from your online weather station such a Davis Vantage PRO 2 (tested) and other generating clientraw.txt files

## Set up through the UI

1. Install the integration and restart Home Assistant.
2. Open **Settings > Devices & services > Add integration > Clientraw**.
3. Enter the full HTTP(S) URL of `clientraw.txt`, a station name (default: `clientraw`), and a polling interval (1-59 minutes; default: 15).
4. Review the **Monitored conditions** checklist and submit.

The integration fetches the URL and preselects conditions with usable readings. This is only a setup helper: you can uncheck suggestions or check any other supported condition. Zero values and negative temperatures are valid readings. A station may report zero for unsupported hardware, so detection cannot establish which physical sensors are installed.

Your confirmed selection stays unchanged between polls. Manually selected conditions with missing or malformed readings are unavailable until usable data appears; other readings continue updating. You can intentionally leave the selection empty.

Each station's sensors are grouped under one device named after the configured station. Existing entities join that device on reload without changing their entity IDs. Renaming the station or changing its URL keeps the same device.

### Change settings

- Use **Configure** on the integration entry to change the polling interval and monitored conditions. The checklist starts with your saved selection.
- Optionally select **Prefill a new conditions checklist from the URL** to review fresh suggestions before saving. This replaces your previous selection only after confirmation.
- Use the entry's three-dot menu > **Reconfigure** to change the URL or station name. You can keep your current selection or review fresh detection suggestions.
- Changing the URL or name preserves existing entity IDs. Multiple station entries are supported; each must use a different URL.

### Migrate an existing YAML installation

Existing `sensor: - platform: clientraw` configurations are automatically imported into UI entries on restart, including their name, URL, interval, and exact monitored conditions. Import can complete while the station is offline; Home Assistant retries connecting automatically.

Existing entity IDs, registry customizations, and automation references are preserved. After checking that the imported entry works under **Settings > Devices & services**, remove only the old Clientraw sensor block from `configuration.yaml` and restart. **Do not delete the whole file or unrelated settings.** A Repairs warning reminds you to remove the block. The YAML path is retained only for migration, not for managing new installations.

Leaving the old block temporarily in place will not create duplicate entries or overwrite later UI edits. If multiple legacy definitions conflict over an endpoint or entity, Repairs reports the conflict instead of overwriting or taking ownership of another entry's entities. Resolve the duplicate configuration before removing the affected YAML.

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
  - **last_updated**: station update timestamp combining the date (`day/month/year`) and time in the station field, interpreted in Home Assistant's configured timezone. This is the feed's timestamp, not the integration's last poll time.
  - **wind_chill**: Wind Chill (°C or °F)
  - **wind_chill_max**: Today MAX Wind Chill (°C or °F)
  - **wind_chill_min**: Today MIN Wind Chill (°C or °F)
  - **vp_solar**: Solar Irradiation (W/m² or BTU/(h×ft²))
  - **uv_index**: UV Index
  - **apparent_temp**: Apparent temperature (°C or °F)
  - **apparent_temp_min**: Min apparent temperature (°C or °F)
  - **apparent_temp_max**: Max apparent temperature (°C or °F)

For existing entries, enable **Last updated (last_updated)** under **Configure > Monitored conditions**. The Date sensor is retained for compatibility. Station now omits a valid trailing `-HH:MM:SS`; names containing other hyphens are preserved. Missing or invalid date/time data makes Last updated unavailable.

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
