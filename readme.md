## Power Aware IOT
Simulating Frames traveling from the Sensor over the Network Layer and trying to reduce the amount of Frames passing through the Network using an Algorithm by marking them as Essential Frames.

## Installation
- Install Python version >= 3.10 from [python.org](https://www.python.org/downloads/)

- ```console
  pip install -r requirements.txt
  ```

### Ingredients
- `power_aware_iot.py` - Contains definition of Fixed Sized Frame, Algorithm to filter Essential Frames and other related functions.  

- `visualize.ipynb` - A Jupiter notebook to use API exposed by _power_aware_iot.py_ and visualize the amount of Essential Frames passing through after applying the Algorithm.  

- `get_historic_weather_data.py` - To pull some historic weather data to simulate the temperature and humidity data coming from the sensor.  

### Sources
- [World Weather Online](https://www.worldweatheronline.com/weather-api/api/historical-weather-api.aspx)
