import streamlit as st
import pandas as pd
import paho.mqtt.client as mqtt
import ssl
import time
import os
import numpy as np

# --- 1. MQTT SETTINGS ---
MQTT_HOST = "cyanqueen-29ab69cf.a01.euc1.aws.hivemq.cloud"
MQTT_PORT = 8883
MQTT_USER = "hivemq.client.1766925863216"
MQTT_PASS = "6<9SwUoy#0D8*dI:CNir"

def send_mqtt_command(is_on):
    client = mqtt.Client(transport="tcp") 
    client.username_pw_set(MQTT_USER, MQTT_PASS)
    client.tls_set(cert_reqs=ssl.CERT_NONE) 
    try:
        client.connect(MQTT_HOST, MQTT_PORT, 60)
        topic = "home/appliances/heater/command"
        payload = "ON" if is_on else "OFF"
        client.publish(topic, payload, qos=1)
        client.disconnect()
        return True
    except:
        return False

# --- 2. DATA LOADING ---
@st.cache_data
def load_data():
    path = "data/next_day_prediction.csv"
    if os.path.exists(path):
        df = pd.read_csv(path)
        df.columns = df.columns.str.strip()
        for col in df.columns:
            df[col] = pd.to_numeric(df[col], errors='coerce').fillna(0.0)
        
        app_list = ['Fridge', 'Heater', 'Fans', 'Lights', 'TV', 'Microwave', 'Washing Machine']
        existing_apps = [c for c in app_list if c in df.columns]
        df['total_demand'] = df[existing_apps].sum(axis=1)
        if 'solar_gen' not in df.columns:
            df['solar_gen'] = 0.0
        return df, existing_apps
    return None, []

df, app_cols = load_data()

# --- 3. SESSION STATE ---
if 'current_hr' not in st.session_state:
    st.session_state.current_hr = 0
if 'auto_mode' not in st.session_state:
    st.session_state.auto_mode = False

# --- 4. UI SETUP ---
st.title("🏡 Autonomous Digital Twin Dashboard")

# Define empty containers to prevent duplicates
metric_container = st.empty()
chart_container = st.empty()

# Sidebar
st.sidebar.header("🤖 Control Center")
st.session_state.auto_mode = st.sidebar.toggle("Enable AI Auto-Control", value=st.session_state.auto_mode)

# --- 5. LOGIC LOOP ---
idx = st.session_state.current_hr % len(df)
row = df.iloc[idx]

# Daily Stats
solar_util = np.minimum(df['solar_gen'], df['total_demand']).sum()
co2 = solar_util * 0.4
eff = (len(df[df['solar_gen'] > df['total_demand']]) / len(df)) * 100

# DRAW METRICS (Inside the empty container to prevent duplication)
with metric_container.container():
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Demand", f"{row['total_demand']:.2f} kW")
    c2.metric("Solar", f"{row['solar_gen']:.2f} kW")
    c3.metric("Efficiency", f"{eff:.1f}%")
    c4.metric("CO2 Saved", f"{co2:.2f} kg")

# DRAW CHARTS
with chart_container.container():
    st.subheader(f"📊 Energy Flow at Hour {idx}:00")
    st.line_chart(df[['solar_gen', 'total_demand']])
    st.bar_chart(row[app_cols])

# --- 6. AUTOMATION ---
if st.session_state.auto_mode:
    # Decision
    ai_on = float(row['solar_gen']) > float(row['total_demand'])
    st.sidebar.info(f"Synchronizing: Hour {idx}:00")
    st.sidebar.write(f"Signal: **{'ON' if ai_on else 'OFF'}**")
    
    # Execute
    send_mqtt_command(ai_on)
    
    # Wait and Refresh
    time.sleep(2)
    st.session_state.current_hr = (idx + 1) % len(df)
    st.rerun() # Forces a clean redraw of the containers
else:
    st.session_state.current_hr = st.sidebar.slider("Manual Hour Select", 0, len(df)-1, idx)
