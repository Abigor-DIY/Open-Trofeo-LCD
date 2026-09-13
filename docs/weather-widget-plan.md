# Weather Widget Plan

## Provider

Use Open-Meteo as the default provider because it works without an API key and
supports the data needed for current conditions and a weekly forecast.

Initial request shape:

```text
https://api.open-meteo.com/v1/forecast
  ?latitude=<lat>
  &longitude=<lon>
  &current=temperature_2m,apparent_temperature,relative_humidity_2m,is_day,precipitation,weather_code,cloud_cover,wind_speed_10m
  &daily=weather_code,temperature_2m_max,temperature_2m_min,precipitation_sum,wind_speed_10m_max,sunrise,sunset
  &forecast_days=7
  &timezone=auto
```

## UI Configuration

- Manual latitude and longitude fields first.
- Optional city search later through Open-Meteo Geocoding.
- Unit selector: Celsius/km/h first, Fahrenheit/mph later.
- Refresh interval: 15 minutes minimum for current weather, daily forecast from
  the same cached response.

## Widget Presets

- `Weather Current Compact`: icon, temperature, condition, wind.
- `Weather Current Panel`: larger icon, temperature, feels-like, humidity, wind.
- `Weather Forecast 7D`: seven small day cards with icon, max/min temperature,
  precipitation.
- `Weather Hero`: large themed panel for dashboard-style themes.

## Renderer Data Keys

- `weather_temp_c`
- `weather_feels_like_c`
- `weather_humidity_percent`
- `weather_wind_kph`
- `weather_precip_mm`
- `weather_cloud_percent`
- `weather_code`
- `weather_condition`
- `weather_icon`
- `weather_is_day`
- `weather_daily`

`weather_daily` should be a list of seven normalized entries:

```json
{
  "date": "2026-05-15",
  "weekday": "Fri",
  "code": 2,
  "condition": "Partly cloudy",
  "icon": "partly-cloudy-day.svg",
  "temp_min_c": 10.2,
  "temp_max_c": 19.8,
  "precip_mm": 0.4,
  "wind_kph": 18.0
}
```

## Assets

Static SVG icons are bundled in `assets/weather/icons/meteocons/fill`. The
mapping from Open-Meteo WMO codes to icon filenames lives in
`assets/weather/open_meteo_icon_map.json`.
