import streamlit as st
import requests
import pandas as pd
import time
from datetime import datetime, timedelta
import altair as alt

# Config
TOKEN = "BBUS-vBdGKqnwoffdpbrrJd2FlWptMwyZRd"
DEVICE_LABEL = "esp32"
BASE_URL = f"https://industrial.api.ubidots.com/api/v1.6/devices/{DEVICE_LABEL}"
HEADERS = {"X-Auth-Token": TOKEN, "Content-Type": "application/json"}

st.set_page_config(page_title="StanceSense", page_icon="🦵", layout="centered")

# Functions time... yay...
def check_connection():
    """Checks if the ESP32 has sent data in the last 15 seconds."""
    try:
        response = requests.get(BASE_URL, headers=HEADERS, timeout=5)
        if response.status_code == 200:
            last_activity = response.json().get("last_activity", 0)
            current_time = int(time.time() * 1000)
            if (current_time - last_activity) < 15000:
                return True
        return False
    except:
        return False

def get_data(variable_label, start_timestamp, end_timestamp):
    """Fetches data from Ubidots within a specific time range."""
    # Change this line in your get_data function:
    url = f"{BASE_URL}/{variable_label}/values/?start={start_timestamp}&end={end_timestamp}&page_size=15000"
    response = requests.get(url, headers=HEADERS)
    
    if response.status_code == 200:
        results = response.json().get("results", [])
        if results:
            df = pd.DataFrame(results)
            df['timestamp'] = pd.to_datetime(df['timestamp'], unit='ms')
            df.set_index('timestamp', inplace=True)
            return df
    return pd.DataFrame()

def send_pain_log(value):
    """Sends the pain scale value back to Ubidots."""
    url = BASE_URL + "/"
    payload = {"pain-level": value}
    response = requests.post(url, headers=HEADERS, json=payload)
    return response.status_code == 200

# Interface
st.title("🦵 StanceSense")

# Connection Status
is_connected = check_connection()
if is_connected:
    st.markdown("""
    <div style='background-color: #d4edda; color: #155724; padding: 10px; border-radius: 20px; text-align: center; border: 1px solid #c3e6cb; margin-bottom: 20px;'>
        <strong>🟢 ESP32 is Connected</strong>
    </div>
    """, unsafe_allow_html=True)
else:
    st.markdown("""
    <div style='background-color: #f8d7da; color: #721c24; padding: 10px; border-radius: 20px; text-align: center; border: 1px solid #f5c6cb; margin-bottom: 20px;'>
        <strong>🔴 ESP32 is Offline</strong>
    </div>
    """, unsafe_allow_html=True)

# Make the tabs
tab1, tab2 = st.tabs(["📋 Summary", "📈 Stat Screen"])

# summary page
with tab1:
    st.header("Today's Overview")
    
    # Calculate "Today's" timestamps
    now = datetime.now()
    midnight = now.replace(hour=0, minute=0, second=0, microsecond=0)
    start_of_today_ms = int(midnight.timestamp() * 1000)
    current_time_ms = int(time.time() * 1000)
    
    with st.spinner("Loading today's data..."):
        today_hyper = get_data("hyperextension-count", start_of_today_ms, current_time_ms)
        today_knee = get_data("knee-angle", start_of_today_ms, current_time_ms)
    
    # Set up 3 columns instead of 2
    col1, col2, col3 = st.columns(3)
    
    with col1:
        if not today_hyper.empty:
            # Absolute latest hyperextension count
            latest_count = int(today_hyper['value'].iloc[0])
            st.metric("Hyperextensions Today", latest_count)
        else:
            st.metric("Hyperextensions Today", "0")
            
    with col2:
        if not today_knee.empty:
            # Absolute latest knee angle
            latest_angle = today_knee['value'].iloc[0]
            st.metric("Current Knee Angle", f"{latest_angle:.1f}°")
        else:
            st.metric("Current Knee Angle", "--°")

    with col3:
        if not today_knee.empty:
            # (Number of points * 5) = total seconds monitored
            total_seconds = len(today_knee) * 5
            minutes_monitored = total_seconds // 60
            st.metric("Time Monitored Today", f"{minutes_monitored} mins")
        else:
            st.metric("Time Monitored Today", "0 mins")
            
    st.divider()
    
    # Pain Logger
    st.subheader("Daily Log")
    pain_level = st.slider("How much knee pain did you experience today?", min_value=1, max_value=10, value=5)
    if st.button("Save Log", use_container_width=True):
        success = send_pain_log(pain_level)
        if success:
            st.success(f"Pain level {pain_level} saved successfully!")
        else:
            st.error("Failed to save log. Check connection.")

# Stat page
with tab2:
    st.header("Data Analysis")
    
    # Time Filter
    time_filter = st.radio("Select Time Range:", ["Last Hour", "Last Day", "Last Month"], horizontal=True)

    end_time_ms = int(time.time() * 1000)
    if time_filter == "Last Hour":
        start_time_ms = end_time_ms - (1 * 60 * 60 * 1000)
    elif time_filter == "Last Day":
        start_time_ms = end_time_ms - (24 * 60 * 60 * 1000)
    else: 
        start_time_ms = end_time_ms - (30 * 24 * 60 * 60 * 1000)

    with st.spinner("Fetching data..."):
        knee_data = get_data("knee-angle", start_time_ms, end_time_ms)

    # Display Chart with Red Dots for Hyperextension
    st.subheader("Knee Angle History")
    
    if not knee_data.empty:
        # Reverse the data so it reads left-to-right (oldest to newest)
        # and move the timestamp index into a regular column for Altair
        chart_df = knee_data[::-1].reset_index()
        chart_df.rename(columns={'value': 'Angle'}, inplace=True)

        # Draw the base line chart
        line_chart = alt.Chart(chart_df).mark_line(color="#FF4B4B").encode(
            x=alt.X('timestamp:T', title='Time'),
            y=alt.Y('Angle:Q', title='Knee Angle (°)')
        )

        # Draw red dots ONLY where the angle is <= -9.0
        red_dots = alt.Chart(chart_df).mark_circle(size=80, color="red").encode(
            x='timestamp:T',
            y='Angle:Q',
            tooltip=['timestamp:T', 'Angle:Q'] # Shows exact time/angle when you hover or tap
        ).transform_filter(
            alt.datum.Angle <= -9.0
        )

        # 3. Layer them together and display
        final_chart = alt.layer(line_chart, red_dots).interactive()
        st.altair_chart(final_chart, use_container_width=True)

    else:
        st.info("No data available for this time range.")
