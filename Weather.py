import os
os.environ['MPLBACKEND'] = 'Agg'
import matplotlib
import matplotlib.pyplot as plt
import matplotlib.dates as mdates
import requests
import pandas as pd
from datetime import date
import plotly.graph_objects as go

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
    }
    response = requests.get(url, params=params)
    return response.json()

def generate_dashboard(df):
    df = df.copy()
    df["datetime"] = pd.to_datetime(df["time"]) 
    max_idx = df["temp_f"].idxmax()
    min_idx = df["temp_f"].idxmin()

    fig = go.Figure()

    fig.add_scatter(
        x=df["datetime"], y=df["temp_f"],
        mode="lines+markers", name="Temp (F)"
    )
    fig.add_scatter(
        x=[df.loc[max_idx, "datetime"]], y=[df.loc[max_idx, "temp_f"]],
        mode="markers+text",
        marker=dict(color="red", size=14, symbol="star"),
        text=[f"Max: {round(df.loc[max_idx, 'temp_f'], 1)}F"],
        textposition="top right", name="Max"
    )
    fig.add_scatter(
        x=[df.loc[min_idx, "datetime"]], y=[df.loc[min_idx, "temp_f"]],
        mode="markers+text",
        marker=dict(color="royalblue", size=14, symbol="star"),
        text=[f"Min: {round(df.loc[min_idx, 'temp_f'], 1)}F"],
        textposition="bottom right", name="Min"
    )

    fig.write_html("dashboard.html", include_plotlyjs="cdn")
    print("Dashboard saved to dashboard.html")
    

today = date.today()
current_year = today.year

current_data = get_current_weather(LATITUDE, LONGITUDE)
current_temp = current_data["current"]["temperature_2m"]
current_time = current_data["current"]["time"]

temp_c = current_temp
temp_f = round(temp_c * 9/5 + 32, 1)

log_df = pd.DataFrame({
    "date": [str(today)],
    "time": [current_time],
    "temperature_2m": [temp_c],
    "temp_f": [temp_f]
})
log_file = "daily_log.csv"
log_df.to_csv(log_file, mode='a', header=not os.path.isfile(log_file), index=False)
print(f"Logged current temperature: {temp_c} degrees C / {temp_f} degrees F at {current_time}")

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
print(f"\nAverage High: {historical_df['max_temp'].mean():.1f}°C")
print(f"Average Low: {historical_df['min_temp'].mean():.1f}°C")

print("\n--- 7-Day Forecast ---")
print(forecast_df)

# Save to CSV
historical_df.to_csv("historical_weather.csv", index=False)
forecast_df.to_csv("forecast_weather.csv", index=False)
print("\nData saved to CSV files.")

generate_dashboard(log_df)
________________________
import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

# Create a session with retry strategy
session = requests.Session()
retry_strategy = Retry(
    total=3,  # Number of retries
    backoff_factor=1,  # Wait 1, 2, 4 seconds between retries
    status_forcelist=[429, 500, 502, 503, 504],  # Retry on these HTTP codes
    allowed_methods=["GET", "POST"]
)
adapter = HTTPAdapter(max_retries=retry_strategy)
session.mount("http://", adapter)
session.mount("https://", adapter)

# Set a timeout for requests
timeout_seconds = 10

# Use session for your API calls instead of requests.get()
response = session.get('https://api.open-meteo.com/...', timeout=timeout_seconds)
