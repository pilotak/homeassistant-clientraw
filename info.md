The `clientraw` platform is WD Clientraw parser which can read data from your online weather station such a Davis Vantage PRO 2 (tested) and other generating clientraw.txt files

To add clientraw to your installation, add the following to your `configuration.yaml` file:

```yaml
# Example configuration.yaml entry
sensor:
  - platform: clientraw
    url: "http://example.com/clientraw.txt"
    monitored_conditions:
      - temp
      - humidity
```

Configuration variables:

- **url**: full path to clientraw.txt file
- **interval**: poll interval in minutes (1-59), 15 min is default
- **monitored_conditions** array: Conditions to display in the frontend.
  - **dewpoint**: Dewpoint (°C or °F)
  - **heat_index**: Heat index (°C or °F)
  - **temp**: Temperature (°C or °F)
  - **humidex**: Humidex (°C or °F)
  - **wind_degrees**: Where the wind is coming from in degrees, with true north at 0° and progressing clockwise.
  - **wind_dir**: Wind Direction as string ie.: N, NW, etc.
  - **wind_gust**: Wind Gust (km/h or mph)
  - **wind_speed**: Wind Speed (km/h or mph)
  - **symbol**: Symbol
  - **daily_rain**: Daily Rain (mm or in)
  - **pressure**: Pressure (hPa or inHg)
  - **humidity**: Relative humidity (%)
  - **cloud_height**: Cloud Height (m or ft)
  - **forecast**: string based output ie.: night showers

A full configuration example can be found below:

```yaml
# Example configuration.yaml entry
sensor:
  - platform: clientraw
    url: "http://example.com/clientraw.txt"
    interval: 10
    monitored_conditions:
      - dewpoint
      - heat_index
      - temp
      - humidex
      - wind_degrees
      - wind_dir
      - wind_gust
      - wind_speed
      - symbol
      - rain_rate
      - pressure
      - humidity
      - cloud_height
      - forecast
```