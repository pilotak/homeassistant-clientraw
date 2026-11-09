The `clientraw` platform is WD Clientraw parser which can read data from your online weather station such a Davis Vantage PRO 2 (tested) and other generating clientraw.txt files

## UI setup

After installation, restart Home Assistant and open **Settings > Devices & services > Add integration > Clientraw**. Enter the full HTTP(S) URL of `clientraw.txt`, a station name (default: `clientraw`), and a polling interval (1-59 minutes; default: 15).

The next step shows all monitored conditions as checkboxes, prefilled from usable readings in the file. Detection is only a helper: check or uncheck any condition, including conditions with no current data. Zero is a valid reading, but can also be a station's placeholder for unsupported hardware. Your saved selection does not change automatically. Selected conditions with missing or invalid readings remain unavailable until usable data appears.

Use **Configure** to edit the interval and conditions, optionally reviewing fresh detection suggestions. Use the entry's three-dot menu > **Reconfigure** to edit its URL or name without changing existing entity IDs. Multiple stations are supported with distinct URLs.

Each station's sensors are grouped under one device using the configured station name. Existing entities join the device on reload; changing the name or URL preserves device identity.

## Existing YAML installations

Existing Clientraw sensor YAML is automatically imported once, preserving its settings, entity IDs, and customizations. Import does not require the station to be online. After verifying the imported entry works, remove only its old `sensor: - platform: clientraw` block from `configuration.yaml` and restart; do not delete the whole file. Repairs provides a reminder and reports migration conflicts. Old YAML will not overwrite subsequent UI changes. YAML is retained only as a migration bridge.

## Supported monitored conditions
  - **dewpoint**: Dewpoint (°C or °F)
  - **heat_index**: Heat index (°C or °F)
  - **temp**: Temperature (°C or °F)
  - **temp_indoor**: Temperature (°C or °F)
  - **temp_day_max**: Today MAX temperature (°C or °F)
  - **temp_day_min**: Today MIN temperature (°C or °F)
  - **humidex**: Humidex (°C or °F)
  - **wind_degrees**: Where the wind is coming from in degrees, with true north at 0° and progressing clockwise.
  - **wind_dir**: Wind Direction as string ie.: N, NW, etc.
  - **wind_gust_hour**: Wind Gust last hour (km/h or mph)
  - **wind_gust_day**: Wind Gust last day (km/h or mph)
  - **wind_speed**: Current Wind Speed (km/h or mph)
  - **wind_speed_average**: Last 60 Sec Avg Wind Speed (km/h or mph)
  - **wind_speed_avg_10min**: 10 Min Avg Wind Speed (km/h or mph)
  - **symbol**: Symbol
  - **daily_rain**: Daily Rain (mm or in)
  - **yesterday_rain**: Yesterday Rain (mm or in)
  - **monthly_rain**: Monthly Rain (mm or in)
  - **yearly_rain**: Yearly Rain (mm or in)
  - **rain_rate**: Rain rate (mm or in)
  - **pressure**: Pressure (hPa or inHg)
  - **humidity**: Relative humidity (%)
  - **humidity_indoor**: Relative humidity (%)
  - **humidity_max**: Max relative humidity (%)
  - **humidity_min**: Min relative humidity (%)
  - **cloud_height**: Cloud Height (m or ft)
  - **forecast**: string based output ie.: night showers
  - **station**: station name without the trailing update time
  - **date**: current date
  - **last_updated**: date and station-field time combined into a timestamp using Home Assistant's configured timezone; unavailable if either is missing or invalid
  - **wind_chill**: Wind Chill (°C or °F)
  - **wind_chill_max**: Today MAX Wind Chill (°C or °F)
  - **wind_chill_min**: Today MIN Wind Chill (°C or °F)
  - **vp_solar**: Solar Irradiation (W/m² or BTU/(h×ft²))
  - **uv_index**: UV Index
  - **apparent_temp**: Apparent temperature (°C or °F)
  - **apparent_temp_min**: Min apparent temperature (°C or °F)
  - **apparent_temp_max**: Max apparent temperature (°C or °F)

Existing entries can enable **Last updated (last_updated)** in **Configure > Monitored conditions**. Date remains available for compatibility. Station now shows just the name, e.g. `TILSKI` instead of `TILSKI-15:12:24`.

For installation instructions and symbol codes, see the [README](README.md).
