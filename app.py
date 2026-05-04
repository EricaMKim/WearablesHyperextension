import streamlit as st
import requests
import pandas as pd
import time
from datetime import datetime, timedelta

# Config
TOKEN = "BBUS-vBdGKqnwoffdpbrrJd2FlWptMwyZRd"
DEVICE_LABEL = "esp32"
BASE_URL = f"https://industrial.api.ubidots.com/api/v1.6/devices/{DEVICE_LABEL}"
HEADERS = {"X-Auth-Token": TOKEN}

st.set_page_config(page_title="StanceSense", page_icon="🦵", layout="centered")


def check_connection():
    """Checks if the ESP32 has sent data in the last 15 seconds."""
    try:
        response = requests.get(BASE_URL, headers=HEADERS, timeout=5)
        if response.status_code == 200:
            last_activity = response.json().get("last_activity", 0)
            current_time = int(time.time() * 1000)
            # If activity was within the last 15 seconds (15000 ms), it's online
            if (current_time - last_activity) < 15000:
                return True
        return False
    except:
        return False

def get_data(variable_label, start_timestamp, end_timestamp):
    """Fetches data from Ubidots within a specific time range."""
    url = f"{BASE_URL}/{variable_label}/values/?start={start_timestamp}&end={end_timestamp}&page_size=2000"
    response = requests.get(url, headers=HEADERS)
    
    if response.status_code == 200:
        results = response.json().get("results", [])
        if results:
            # Convert JSON to a Pandas DataFrame
            df = pd.DataFrame(results)
            # Convert Ubidots timestamps (ms) to readable datetime objects
            df['timestamp'] = pd.to_datetime(df['timestamp'], unit='ms')
            # Set the timestamp as the index for Streamlit charting
            df.set_index('timestamp', inplace=True)
            return df
    return pd.DataFrame() # Return empty if no data

# Interface
st.title("🦵 StanceSense Dashboard")

# 1. Connection Status
is_connected = check_connection()
if is_connected:
    st.success("🟢 ESP32 is Connected and Transmitting")
else:
    st.error("🔴 ESP32 is Offline (No data in the last 15s)")

st.divider()

# Time Filter
time_filter = st.radio("Select Time Range:", ["Last Hour", "Last Day", "Last Month"], horizontal=True)

# Calculate timestamps based on selection (Ubidots uses milliseconds)
end_time_ms = int(time.time() * 1000)

if time_filter == "Last Hour":
    start_time_ms = end_time_ms - (1 * 60 * 60 * 1000)
elif time_filter == "Last Day":
    start_time_ms = end_time_ms - (24 * 60 * 60 * 1000)
else: # Last Month
    start_time_ms = end_time_ms - (30 * 24 * 60 * 60 * 1000)

# Fetch Data
with st.spinner("Fetching data from Ubidots..."):
    knee_data = get_data("knee-angle", start_time_ms, end_time_ms)
    hyper_data = get_data("hyperextension-count", start_time_ms, end_time_ms)

# Show Metrics
col1, col2 = st.columns(2)

with col1:
    if not knee_data.empty:
        latest_angle = knee_data['value'].iloc[0] # First item is the most recent
        st.metric("Current Knee Angle", f"{latest_angle:.1f}°")
    else:
        st.metric("Current Knee Angle", "--°")

with col2:
    if not hyper_data.empty:
        # Since your Arduino code keeps a running total, we just grab the latest value
        latest_count = int(hyper_data['value'].iloc[0]) 
        st.metric("Total Hyperextensions", latest_count)
    else:
        st.metric("Total Hyperextensions", "--")

# Show Display Chart
st.subheader("Knee Angle History")
if not knee_data.empty:
    # Streamlit line_chart expects the data to be in chronological order
    st.line_chart(knee_data['value'][::-1], color="#FF4B4B") 
else:
    st.info("No data available for this time range.")
