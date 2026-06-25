import requests
import pandas as pd
from datetime import date
import os

# My camping location
LATITUDE = -25.6829
LONGITUDE = -54.4546
LOCATION_NAME = "Iguazu National Park"

# Camping month and day range
CAMP_MONTH = 8
CAMP_START_DAY = 1
CAMP_END_DAY = 14

# get the current temperature right now   
def get_current_weather(lat, lon):        
    url = "https://api.open-meteo.com/v1/forecast"
    params = {
        "latitude": lat,
        "longitude": lon,
        "current": "temperature_2m",
        "timezone": "America/Los_Angeles"
    }
    response = requests.get(url, params=params)
    return response.json()

def get_historical_weather(lat, lon, start_date, end_date):
    url = "https://archive-api.open-meteo.com/v1/archive"
    params = {
        "latitude": lat,
        "longitude": lon,
        "start_date": start_date,
        "end_date": end_date,
        "daily": "temperature_2m_max,temperature_2m_min",
        "timezone": "America/Los_Angeles",
        "temperature_unit": "fahrenheit",
    }
    response = requests.get(url, params=params)
    return response.json()

def get_forecast(lat, lon):
    url = "https://api.open-meteo.com/v1/forecast"
    params = {
        "latitude": lat,
        "longitude": lon,
        "daily": "temperature_2m_max,temperature_2m_min",
        "timezone": "America/Los_Angeles",
        "forecast_days": 7,
        "temperature_unit": "fahrenheit",
    }
    response = requests.get(url, params=params)
    return response.json()

today = date.today()
current_year = today.year

current_data = get_current_weather(LATITUDE, LONGITUDE)
current_temp = current_data["current"]["temperature_2m"]
current_time = current_data["current"]["time"]
log_df = pd.DataFrame({
    "date": [str(today)],
    "time": [current_time],
    "temperature_2m": [current_temp]
})
log_file = "daily_log.csv"
log_df.to_csv(log_file, mode='a', header=not os.path.isfile(log_file), index=False)
print(f"Logged current temperature: {current_temp} degrees C at {current_time}")

# Collect historical data for the last 5 years
all_data = []

for year in range(current_year - 5, current_year):
    start = date(year, CAMP_MONTH, CAMP_START_DAY)
    end = date(year, CAMP_MONTH, CAMP_END_DAY)
    data = get_historical_weather(LATITUDE, LONGITUDE, start, end)
    all_data.append(data)
    print(f"Fetched data for {year}")

dfs = []
for year_data in all_data:
    df = pd.DataFrame({
        "date": year_data["daily"]["time"],
        "max_temp": year_data["daily"]["temperature_2m_max"],
        "min_temp": year_data["daily"]["temperature_2m_min"]
    })
    dfs.append(df)

historical_df = pd.concat(dfs, ignore_index=True)

# Get the 7-day forecast
forecast_data = get_forecast(LATITUDE, LONGITUDE)
forecast_df = pd.DataFrame({
    "date": forecast_data["daily"]["time"],
    "max_temp": forecast_data["daily"]["temperature_2m_max"],
    "min_temp": forecast_data["daily"]["temperature_2m_min"]
})

# Results
print(f"Weather analysis for {LOCATION_NAME}")
print("=" * 40)

print("\n--- Historical Averages (last 5 years, your camping dates) ---")
print(historical_df)
print(f"\nAverage High: {historical_df['max_temp'].mean():.1f}°F")
print(f"Average Low: {historical_df['min_temp'].mean():.1f}°F")

print("\n--- 7-Day Forecast ---")
print(forecast_df)

# Save to CSV
historical_df.to_csv("historical_weather.csv", index=False)
forecast_df.to_csv("forecast_weather.csv", index=False)
print("\nData saved to CSV files.")
