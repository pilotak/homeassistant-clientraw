# HomeAssistant component: `clientraw`
[![Validate](https://github.com/pilotak/homeassistant-clientraw/workflows/Validate/badge.svg)](https://github.com/pilotak/homeassistant-clientraw/actions)
[![hacs_badge](https://img.shields.io/badge/HACS-Default-orange.svg)](https://github.com/custom-components/hacs)

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
  - **wind_gust_hour**: Wind Gust in last hour (km/h or mph)
  - **wind_gust_day**: Wind Gust in last day (km/h or mph)
  - **wind_speed**: Wind Speed (km/h or mph)
  - **symbol**: Symbol
  - **daily_rain**: Daily Rain (mm or in)
  - **monthly_rain**: Daily Rain (mm or in)
  - **daily_rain**: Daily Rain (mm or in)
  - **yearly_rain**: Daily Rain (mm or in)
  - **rain_rate**: Daily Rain (mm or in)
  - **pressure**: Pressure (hPa or inHg)
  - **humidity**: Relative humidity (%)
  - **humidity_indoor**: Relative humidity (%)
  - **cloud_height**: Cloud Height (m or ft)
  - **forecast**: string based output ie.: night showers

## Install via [HACS](https://github.com/custom-components/hacs)
You can find this integration in a store.

## Install manually
You need to copy `clientraw` folder from this repo to the `custom_components` folder in the root of your configuration, file tree should look like this:
```
└── ...
└── configuration.yaml
└── custom_components
    └── clientraw
        └── __init__.py
        └── manifest.json
        └── sensor.py
```

>__Note__: if the `custom_components` directory does not exist, you need to create it.

## A full configuration example
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
      - symbol
      - rain_rate
      - daily_rain
      - monthly_rain
      - yearly_rain
      - pressure
      - humidity
      - humidity_indoor
      - cloud_height
      - forecast
```
Symbol codes:
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
