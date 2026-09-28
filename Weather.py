import os
from datetime import date
import logging

import pandas as pd
import plotly.graph_objects as go
import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

LATITUDE = -25.6829
LONGITUDE = -54.4546
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
        allowed_methods=["HEAD", "GET", "OPTIONS"],
    )
    adapter = HTTPAdapter(max_retries=retry_strategy)
    session.mount("https://", adapter)
    session.mount("http://", adapter)
    return session


session = create_session_with_retries()


def get_current_weather(lat, lon):
    """
    Fetch current weather using Open-Meteo API v1.
    Uses 'current' parameter (not 'current_weather').
    """
    url = f"{API_BASE}/forecast"
    params = {
        "latitude": lat,
        "longitude": lon,
        "current": "temperature_2m",
        "timezone": "America/Argentina/Iguazu",
    }
    logger.info(f"Fetching current weather from {url} with params: {params}")
    r = session.get(url, params=params, timeout=10)
    r.raise_for_status()
    return r.json()


def get_historical_weather(lat, lon, start_date, end_date):
    """
    Fetch historical weather data from archive API.
    """
    url = f"{ARCHIVE_BASE}/archive"
    params = {
        "latitude": lat,
        "longitude": lon,
        "start_date": start_date.isoformat(),
        "end_date": end_date.isoformat(),
        "daily": "temperature_2m_max,temperature_2m_min",
        "timezone": "America/Argentina/Iguazu",
    }
    logger.info(f"Fetching historical weather for {start_date} to {end_date}")
    r = session.get(url, params=params, timeout=30)
    r.raise_for_status()
    return r.json()


def get_forecast(lat, lon, days=7):
    """
    Fetch weather forecast using Open-Meteo API v1.
    """
    url = f"{API_BASE}/forecast"
    params = {
        "latitude": lat,
        "longitude": lon,
        "daily": "temperature_2m_max,temperature_2m_min",
        "timezone": "America/Argentina/Iguazu",
        "forecast_days": days,
    }
    logger.info(f"Fetching forecast for {days} days")
    r = session.get(url, params=params, timeout=10)
    r.raise_for_status()
    return r.json()


def generate_dashboard(df, out="dashboard.html"):
    """
    Generate an HTML dashboard from temperature data.
    """
    if df.empty:
        logger.warning("DataFrame is empty, skipping dashboard generation")
        return
    
    df = df.copy()
    if "time" in df.columns:
        df["datetime"] = pd.to_datetime(df["time"])
    elif "date" in df.columns:
        df["datetime"] = pd.to_datetime(df["date"])
    else:
        raise ValueError("DataFrame needs 'time' or 'date' column")
    
    # Handle missing temp_f column
    if "temp_f" not in df.columns:
        if "temperature_2m" in df.columns:
            df["temp_f"] = round(df["temperature_2m"] * 9/5 + 32, 1)
        elif "max_temp" in df.columns:
            df["temp_f"] = round(df["max_temp"] * 9/5 + 32, 1)
        else:
            raise ValueError("DataFrame needs temperature column (temp_f, temperature_2m, or max_temp)")
    
    fig = go.Figure()
    fig.add_scatter(x=df["datetime"], y=df["temp_f"], mode="lines+markers", name="Temp (F)")
    fig.write_html(out, include_plotlyjs="cdn")
    print(f"Dashboard saved to {out}")


# Main
if __name__ == "__main__":
    today = date.today()
    current_year = today.year
    log_file = "daily_log.csv"

    try:
        current_data = get_current_weather(LATITUDE, LONGITUDE)
        logger.info(f"Current data response keys: {current_data.keys()}")

        # Validate response - check for 'current' key (not 'current_weather')
        if "current" not in current_data:
            raise RuntimeError(f"Unexpected API response, missing 'current' key. Got: {current_data.keys()}")

        current = current_data.get("current", {})
        if not current or "temperature_2m" not in current:
            raise RuntimeError(f"Invalid current data structure: {current}")

        temp_c = current["temperature_2m"]
        temp_f = round(temp_c * 9/5 + 32, 1)
        current_time = current.get("time", str(today))

        logger.info(f"Current temperature: {temp_c}°C / {temp_f}°F at {current_time}")

        log_df = pd.DataFrame({
            "date": [str(today)],
            "time": [current_time],
            "temperature_2m": [temp_c],
            "temp_f": [temp_f],
        })

        if os.path.isfile(log_file):
            try:
                prev = pd.read_csv(log_file, skipinitialspace=True)
                if not prev.empty and "time" in prev.columns:
                    last_time = prev["time"].iloc[-1]
                    if str(last_time) == str(current_time):
                        print(f"Duplicate timestamp detected ({current_time}) - not appending")
                    else:
                        log_df.to_csv(log_file, mode="a", header=False, index=False)
                        print(f"Appended new reading to {log_file}")
                else:
                    log_df.to_csv(log_file, mode="a", header=False, index=False)
                    print(f"Appended new reading to {log_file}")
            except Exception as e:
                logger.error(f"Failed to read existing log file: {e}")
                print("Failed to read existing log file, writing new one:", e)
                log_df.to_csv(log_file, index=False)
                print(f"Wrote new {log_file}")
        else:
            log_df.to_csv(log_file, index=False)
            print(f"Created {log_file} and wrote initial reading")

        try:
            tail = pd.read_csv(log_file, skipinitialspace=True).tail(5)
            print("daily_log.csv last 5 rows:")
            print(tail.to_string(index=False))
        except Exception as e:
            print("Unable to show tail of daily_log.csv:", e)

        all_data = []
        for year in range(current_year - 5, current_year):
            start = date(year, CAMP_MONTH, CAMP_START_DAY)
            end = date(year, CAMP_MONTH, CAMP_END_DAY)
            try:
                data = get_historical_weather(LATITUDE, LONGITUDE, start, end)
                all_data.append(data)
                print(f"Fetched data for {year}")
            except requests.exceptions.RequestException as e:
                logger.error(f"Historical fetch failed for {year}: {e}")
                print(f"Historical fetch failed for {year}:", e)
            except Exception as e:
                logger.error(f"Unexpected error fetching {year}: {e}")
                print(f"Unexpected error fetching {year}:", e)

        dfs = []
        for year_data in all_data:
            daily = year_data.get("daily", {})
            if daily and "time" in daily and "temperature_2m_max" in daily and "temperature_2m_min" in daily:
                try:
                    df = pd.DataFrame({
                        "date": daily["time"],
                        "max_temp": daily["temperature_2m_max"],
                        "min_temp": daily["temperature_2m_min"],
                    })
                    dfs.append(df)
                except Exception as e:
                    logger.error(f"Failed to parse daily data: {e}")
        
        historical_df = pd.concat(dfs, ignore_index=True) if dfs else pd.DataFrame()

        try:
            forecast_data = get_forecast(LATITUDE, LONGITUDE)
            daily = forecast_data.get("daily", {})
            if daily and "time" in daily and "temperature_2m_max" in daily and "temperature_2m_min" in daily:
                forecast_df = pd.DataFrame({
                    "date": daily["time"],
                    "max_temp": daily["temperature_2m_max"],
                    "min_temp": daily["temperature_2m_min"],
                })
            else:
                logger.error(f"Invalid forecast data structure: {daily}")
                forecast_df = pd.DataFrame()
        except requests.exceptions.RequestException as e:
            logger.error(f"Forecast fetch failed: {e}")
            print("Forecast fetch failed:", e)
            forecast_df = pd.DataFrame()
        except Exception as e:
            logger.error(f"Forecast processing error: {e}")
            print("Forecast processing error:", e)
            forecast_df = pd.DataFrame()

        try:
            if not historical_df.empty:
                historical_df.to_csv("historical_weather.csv", index=False)
                print("Saved historical_weather.csv")
            else:
                logger.warning("Historical DataFrame is empty, skipping save")
        except Exception as e:
            logger.error(f"Failed to write historical_weather.csv: {e}")
            print("Failed to write historical_weather.csv:", e)

        try:
            if not forecast_df.empty:
                forecast_df.to_csv("forecast_weather.csv", index=False)
                print("Saved forecast_weather.csv")
            else:
                logger.warning("Forecast DataFrame is empty, skipping save")
        except Exception as e:
            logger.error(f"Failed to write forecast_weather.csv: {e}")
            print("Failed to write forecast_weather.csv:", e)

        try:
            generate_dashboard(log_df)
        except Exception as e:
            logger.error(f"Failed to generate dashboard: {e}")
            print("Failed to generate dashboard:", e)

        print("Weather update completed successfully")

    except requests.exceptions.RequestException as e:
        logger.error(f"API request failed: {e}")
        print("API request failed:", e)
        raise
    except Exception as e:
        logger.error(f"Unhandled error in Weather.py: {e}")
        print("Unhandled error in Weather.py:", e)
        raise
