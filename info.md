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
      - temp_indoor
      - temp_day_max
      - temp_day_min
      - humidex
      - wind_degrees
      - wind_dir
      - wind_gust_hour
      - wind_gust_day
      - wind_speed
      - wind_speed_avg_10min
      - symbol
      - rain_rate
      - daily_rain
      - yesterday_rain
      - monthly_rain
      - yearly_rain
      - pressure
      - humidity
      - humidity_indoor
      - cloud_height
      - forecast
```
