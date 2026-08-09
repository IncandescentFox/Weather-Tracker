import os
import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry
import pandas as pd
from datetime import date
import plotly.graph_objects as go

LATITUDE = -25.6829
LONGITUDE = -54.4546
LOCATION_NAME = "Iguazu National Park"
CAMP_MONTH = 8
CAMP_START_DAY = 1
CAMP_END_DAY = 14

API_BASE = "https://api.open-meteo.com/v1"
ARCHIVE_BASE = "https://archive-api.open-meteo.com/v1"

def create_session_with_retries(retries=3, backoff_factor=1):
    session = requests.Session()
    retry_strategy = Retry(
        total=retries,
        backoff_factor=backoff_factor,
        status_forcelist=[429, 500, 502, 503, 504],
        allowed_methods=["HEAD", "GET", "OPTIONS"]
    )
    adapter = HTTPAdapter(max_retries=retry_strategy)
    session.mount("https://", adapter)
    session.mount("http://", adapter)
    return session

session = create_session_with_retries()

def get_current_weather(lat, lon):
    url = f"{API_BASE}/forecast"
    params = {
        "latitude": lat,
        "longitude": lon,
        "current_weather": True,           # use API's current_weather flag
        "timezone": "America/Argentina/Iguazu"
    }
    r = session.get(url, params=params, timeout=10)
    r.raise_for_status()
    return r.json()

def get_historical_weather(lat, lon, start_date, end_date):
    url = f"{ARCHIVE_BASE}/archive"
    params = {
        "latitude": lat,
        "longitude": lon,
        "start_date": start_date.isoformat(),
        "end_date": end_date.isoformat(),
        "daily": "temperature_2m_max,temperature_2m_min",
        "timezone": "America/Argentina/Iguazu",
    }
    r = session.get(url, params=params, timeout=30)
    r.raise_for_status()
    return r.json()

def get_forecast(lat, lon, days=7):
    url = f"{API_BASE}/forecast"
    params = {
        "latitude": lat,
        "longitude": lon,
        "daily": "temperature_2m_max,temperature_2m_min",
        "timezone": "America/Argentina/Iguazu",
        "forecast_days": days,
    }
    r = session.get(url, params=params, timeout=10)
    r.raise_for_status()
    return r.json()

def generate_dashboard(df, out="dashboard.html"):
    df = df.copy()
    if "time" in df.columns:
        df["datetime"] = pd.to_datetime(df["time"])
    elif "date" in df.columns:
        df["datetime"] = pd.to_datetime(df["date"])
    else:
        raise ValueError("DataFrame needs 'time' or 'date' column")
    fig = go.Figure()
    fig.add_scatter(x=df["datetime"], y=df["temp_f"], mode="lines+markers", name="Temp (F)")
    fig.write_html(out, include_plotlyjs="cdn")
    print(f"Dashboard saved to {out}")

# Example usage (wrap network calls with try/except in production)
today = date.today()
current_year = today.year

try:
    current_data = get_current_weather(LATITUDE, LONGITUDE)
    # extract current temperature from API structure (current_weather)
    temp_c = current_data["current_weather"]["temperature"]
    temp_f = round(temp_c * 9/5 + 32, 1)
    current_time = current_data["current_weather"]["time"]

    log_df = pd.DataFrame({
        "date": [str(today)],
        "time": [current_time],
        "temperature_2m": [temp_c],
        "temp_f": [temp_f]
    })
    log_file = "daily_log.csv"
    log_df.to_csv(log_file, mode='a', header=not os.path.isfile(log_file), index=False)
    print(f"Logged current temperature: {temp_c} C / {temp_f} F at {current_time}")

    # historical fetching (ensure start/end are date objects)
    all_data = []
    for year in range(current_year - 5, current_year):
        start = date(year, CAMP_MONTH, CAMP_START_DAY)
        end = date(year, CAMP_MONTH, CAMP_END_DAY)
        data = get_historical_weather(LATITUDE, LONGITUDE, start, end)
        all_data.append(data)
        print(f"Fetched data for {year}")

    # assemble DataFrame safely (validate structure)
    dfs = []
    for year_data in all_data:
        daily = year_data.get("daily", {})
        if daily and "time" in daily:
            df = pd.DataFrame({
                "date": daily["time"],
                "max_temp": daily["temperature_2m_max"],
                "min_temp": daily["temperature_2m_min"]
            })
            dfs.append(df)
    historical_df = pd.concat(dfs, ignore_index=True) if dfs else pd.DataFrame()

    forecast_data = get_forecast(LATITUDE, LONGITUDE)
    forecast_df = pd.DataFrame({
        "date": forecast_data["daily"]["time"],
        "max_temp": forecast_data["daily"]["temperature_2m_max"],
        "min_temp": forecast_data["daily"]["temperature_2m_min"]
    })

    # Save CSVs
    historical_df.to_csv("historical_weather.csv", index=False)
    forecast_df.to_csv("forecast_weather.csv", index=False)

    # Create dashboard from a useful dataset (e.g., historical or last N logs)
    generate_dashboard(log_df)

except requests.exceptions.RequestException as e:
    print("API request failed:", e)