/**
 * WMO Weather Code → Weather Icons CSS class name
 * Uses classes from weather-icons (erikflowers/weather-icons v1.3)
 * Reference: https://erikflowers.github.io/weather-icons/
 */
export const weatherIconMap = {
  // Clear sky / Mainly clear
  0:  'wi-day-sunny',
  1:  'wi-day-sunny-overcast',
  // Partly / Overcast cloudy
  2:  'wi-day-cloudy',
  3:  'wi-cloudy',
  // Fog
  45: 'wi-fog',
  48: 'wi-fog',
  // Drizzle
  51: 'wi-sprinkle',
  53: 'wi-sprinkle',
  55: 'wi-sprinkle',
  // Freezing drizzle
  56: 'wi-hail',
  57: 'wi-hail',
  // Rain
  61: 'wi-rain',
  63: 'wi-rain',
  65: 'wi-rain',
  // Freezing rain
  66: 'wi-hail',
  67: 'wi-hail',
  // Snow
  71: 'wi-snow',
  73: 'wi-snow',
  75: 'wi-snow',
  77: 'wi-snow-wind',
  // Rain showers
  80: 'wi-showers',
  81: 'wi-showers',
  82: 'wi-showers',
  // Snow showers
  85: 'wi-snow',
  86: 'wi-snow',
  // Thunderstorm
  95: 'wi-thunderstorm',
  96: 'wi-thunderstorm',
  99: 'wi-thunderstorm',
};

export default weatherIconMap;
