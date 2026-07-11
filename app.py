from pathlib import Path

import streamlit as st
import pandas as pd
import plotly.graph_objects as go

BASE_DIR = Path(__file__).resolve().parent
DATA_FILE = BASE_DIR / "daily_log.csv"

st.set_page_config(page_title="My City Temperature Dashboard", layout="wide")
st.title("My City Temperature Dashboard")


def load_weather_data():
    if not DATA_FILE.exists():
        st.error(f"Weather data file not found: {DATA_FILE}")
        return pd.DataFrame(columns=["date", "time", "temperature_2m", "temp_f"])

    df = pd.read_csv(DATA_FILE, skipinitialspace=True)
    if df.empty:
        return df

    df["datetime"] = pd.to_datetime(df["time"])
    return df.sort_values("datetime").reset_index(drop=True)


df = load_weather_data()
if df.empty:
    st.info("No weather data has been logged yet.")
    st.stop()

max_idx = df["temp_f"].idxmax()
min_idx = df["temp_f"].idxmin()

col1, col2, col3 = st.columns(3)
col1.metric("Latest Reading", f"{round(df['temp_f'].iloc[-1], 1)}F")
col2.metric("All-Time Max", f"{round(df.loc[max_idx, 'temp_f'], 1)}F")
col3.metric("All-Time Min", f"{round(df.loc[min_idx, 'temp_f'], 1)}F")

st.divider()
st.subheader("Alert Thresholds")
tcol1, tcol2 = st.columns(2)
hot = tcol1.slider("Hot alert (F)", min_value=60, max_value=110, value=80)
cold = tcol2.slider("Cold alert (F)", min_value=20, max_value=65, value=45)

st.divider()

fig = go.Figure()

fig.add_scatter(
    x=df["datetime"], y=df["temp_f"],
    mode="lines+markers", name="Temp (F)",
    line=dict(color="steelblue", width=2), marker=dict(size=6)
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
fig.add_hline(y=hot, line_dash="dash", line_color="red", line_width=1.5,
              annotation_text=f"Hot: {hot}F", annotation_position="top right",
              annotation_font_color="red")
fig.add_hline(y=cold, line_dash="dash", line_color="royalblue", line_width=1.5,
              annotation_text=f"Cold: {cold}F", annotation_position="bottom right",
              annotation_font_color="royalblue")
fig.update_layout(
    yaxis_title="Temperature (F)", xaxis_title="Date / Time",
    hovermode="x unified", plot_bgcolor="white", paper_bgcolor="white"
)

st.plotly_chart(fig, use_container_width=True)

st.divider()
st.subheader("Incoming Data Log")

log = df[["datetime", "temperature_2m", "temp_f"]].copy()
log = log.sort_values("datetime", ascending=False)
log.columns = ["Date / Time", "Temp (C)", "Temp (F)"]
log["Temp (F)"] = log["Temp (F)"].round(1)
log["Temp (C)"] = log["Temp (C)"].round(1)
log["Date / Time"] = log["Date / Time"].dt.strftime("%b %d, %Y %H:%M")
st.dataframe(log, use_container_width=True, hide_index=True)