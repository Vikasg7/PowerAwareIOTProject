from urllib.parse import urlencode
from urllib.request import urlopen
from datetime import datetime
import json
import csv

base_url = 'https://api.worldweatheronline.com/premium/v1/past-weather.ashx'
query_params = {
   'q': 'kolkata',
   'date': '2023-01-01',
   'enddate': '2023-01-31',
   'tp': '1',
   'format': 'json',
   'key': 'f50f8355f937443a81d125110231905'
}

# Encode the query parameters
encoded_params = urlencode(query_params)

# Construct the complete URL with query parameters
url = f"{base_url}?{encoded_params}"

# Send GET request
response = urlopen(url)

json_data = json.load(response)

outfile = open("input_data.csv", "w")
writer  = csv.writer(outfile, lineterminator="\n") 

daily_data = json_data["data"]["weather"]
for days_data in daily_data:
   date = datetime.strptime(days_data["date"], "%Y-%m-%d")
   for hours_data in days_data["hourly"]:
      hour = int(hours_data["time"]) // 100
      timestamp   = date.replace(hour=hour)
      temperature = float(hours_data["tempC"])
      humidity    = float(hours_data["humidity"])
      writer.writerow([timestamp, temperature, humidity])

print("Done!")