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
    """Create a requests session with retry strategy for resilient API calls."""
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
    Only requests temperature_2m - weather_code is NOT supported for current endpoint.
    """
    url = f"{API_BASE}/forecast"
    params = {
        "latitude": lat,
        "longitude": lon,
        "current": "temperature_2m",  # FIXED: Removed unsupported weather_code
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


def safe_get_daily_data(daily_dict):
    """Safely extract daily weather data with validation."""
    if not daily_dict or "time" not in daily_dict:
        return None
    if "temperature_2m_max" not in daily_dict or "temperature_2m_min" not in daily_dict:
        return None
    return daily_dict


# Main
if __name__ == "__main__":
    today = date.today()
    current_year = today.year
    log_file = "daily_log.csv"
    success = False

    try:
        # Fetch and process current weather
        current_data = get_current_weather(LATITUDE, LONGITUDE)
        logger.info(f"Current data response keys: {current_data.keys()}")

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

        # Handle daily log CSV
        if os.path.isfile(log_file):
            try:
                prev = pd.read_csv(log_file, skipinitialspace=True)
                if not prev.empty and "time" in prev.columns:
                    last_time = prev["time"].iloc[-1]
                    if str(last_time) == str(current_time):
                        logger.info(f"Duplicate timestamp ({current_time}) - skipping append")
                    else:
                        log_df.to_csv(log_file, mode="a", header=False, index=False)
                        logger.info(f"Appended new reading to {log_file}")
                else:
                    log_df.to_csv(log_file, mode="a", header=False, index=False)
                    logger.info(f"Appended to {log_file}")
            except Exception as e:
                logger.error(f"Failed to read existing log file: {e}, creating new")
                log_df.to_csv(log_file, index=False)
        else:
            log_df.to_csv(log_file, index=False)
            logger.info(f"Created {log_file}")

        # Display tail of log
        try:
            tail = pd.read_csv(log_file, skipinitialspace=True).tail(5)
            print("daily_log.csv last 5 rows:")
            print(tail.to_string(index=False))
        except Exception as e:
            logger.warning(f"Unable to show tail of daily_log.csv: {e}")

        # Fetch historical data
        all_data = []
        for year in range(current_year - 5, current_year):
            start = date(year, CAMP_MONTH, CAMP_START_DAY)
            end = date(year, CAMP_MONTH, CAMP_END_DAY)
            try:
                data = get_historical_weather(LATITUDE, LONGITUDE, start, end)
                all_data.append(data)
                logger.info(f"Fetched data for {year}")
            except Exception as e:
                logger.error(f"Historical fetch failed for {year}: {e}")

        # Process historical data
        dfs = []
        for year_data in all_data:
            daily = year_data.get("daily", {})
            daily_data = safe_get_daily_data(daily)
            if daily_data:
                try:
                    df = pd.DataFrame({
                        "date": daily_data["time"],
                        "max_temp": daily_data["temperature_2m_max"],
                        "min_temp": daily_data["temperature_2m_min"],
                    })
                    dfs.append(df)
                except Exception as e:
                    logger.error(f"Failed to parse daily data: {e}")
        
        historical_df = pd.concat(dfs, ignore_index=True) if dfs else pd.DataFrame()

        # Fetch forecast data
        forecast_df = pd.DataFrame()
        try:
            forecast_data = get_forecast(LATITUDE, LONGITUDE)
            daily = forecast_data.get("daily", {})
            daily_data = safe_get_daily_data(daily)
            if daily_data:
                forecast_df = pd.DataFrame({
                    "date": daily_data["time"],
                    "max_temp": daily_data["temperature_2m_max"],
                    "min_temp": daily_data["temperature_2m_min"],
                })
        except Exception as e:
            logger.error(f"Forecast fetch failed: {e}")

        # Save CSV files
        if not historical_df.empty:
            try:
                historical_df.to_csv("historical_weather.csv", index=False)
                logger.info("Saved historical_weather.csv")
            except Exception as e:
                logger.error(f"Failed to write historical_weather.csv: {e}")
        else:
            logger.warning("Historical DataFrame is empty, skipping save")

        if not forecast_df.empty:
            try:
                forecast_df.to_csv("forecast_weather.csv", index=False)
                logger.info("Saved forecast_weather.csv")
            except Exception as e:
                logger.error(f"Failed to write forecast_weather.csv: {e}")
        else:
            logger.warning("Forecast DataFrame is empty, skipping save")

        # Generate dashboard
        try:
            generate_dashboard(log_df)
        except Exception as e:
            logger.error(f"Failed to generate dashboard: {e}")

        logger.info("Weather update completed successfully")
        print("✓ Weather update completed successfully")
        success = True

    except requests.exceptions.HTTPError as e:
        logger.error(f"HTTP Error - API request failed: {e}")
        print(f"HTTP Error: {e}")
        raise
    except requests.exceptions.RequestException as e:
        logger.error(f"Request failed: {e}")
        print(f"Request failed: {e}")
        raise
    except Exception as e:
        logger.error(f"Unhandled error: {e}", exc_info=True)
        print(f"Error: {e}")
        raise
