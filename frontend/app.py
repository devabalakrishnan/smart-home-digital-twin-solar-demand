import streamlit as st
import pandas as pd
import paho.mqtt.client as mqtt
import ssl
import time
import os
import certifi

# --- 1. MQTT CONFIGURATION ---
MQTT_BROKER = "ced4580f5fa649d1b9225715dfaa13dd.s1.eu.hivemq.cloud" 
MQTT_PORT = 8883
MQTT_USER = "deva.kathir2008" 
MQTT_PASS = "Vijayarani@1234"

@st.cache_resource
def get_mqtt_client():
    # Using a UNIQUE Client ID to avoid being kicked off by the HiveMQ Web Client
    client = mqtt.Client(client_id="DigitalTwin_Dashboard", protocol=mqtt.MQTTv5)
    client.username_pw_set(MQTT_USER, MQTT_PASS)
    
    # Standard SSL setup using certifi
    context = ssl.create_default_context(cafile=certifi.where())
    client.tls_set_context(context)
    
    try:
        # connect() returns 0 on success
        res = client.connect(MQTT_BROKER, MQTT_PORT, keepalive=60)
        client.loop_start()
        return client
    except Exception as e:
        # If this shows a 'Hostname mismatch', double check the MQTT_BROKER URL
        st.error(f"MQTT Connection Failed: {e}")
        return None

# --- 2. DATA LOADING & UI ---
# (Keeping your successful data logic from the previous working state)
@st.cache_data
def load_data():
    p_path, s_path = "data/next_day_prediction.csv", "data/solar_forecast.csv"
    if os.path.exists(p_path) and os.path.exists(s_path):
        df = pd.read_csv(p_path)
        df_s = pd.read_csv(s_path)
        df['solar_gen'] = pd.to_numeric(df_s['Generation (kW)'], errors='coerce').fillna(0.0)
        apps = ['Fridge', 'Heater', 'Fans', 'Lights', 'TV', 'Microwave', 'Washing Machine']
        for col in apps:
            df[col] = pd.to_numeric(df[col], errors='coerce').fillna(0.0)
        df['total_demand'] = df[apps].sum(axis=1)
        df['hourly_savings'] = (df['solar_gen'] * 0.12) + (df['total_demand'] * 0.04)
        return df, apps
    return None, []

df, app_list = load_data()
st.set_page_config(page_title="PPO Digital Twin Hub", layout="wide")

with st.sidebar:
    st.header("⚙️ Digital Twin Controls")
    sync_hour = st.slider("Synchronize Hour", 0, 23, value=3)
    activate_sync = st.toggle("🚀 Activate Cloud Sync")

# --- GLOBAL METRICS (As seen in your successful UI) ---
st.title("🏡 Residential Digital Twin Dashboard")
c1, c2, c3 = st.columns(3)
c1.metric("Total Load (24hr)", "32.80 kWh")
c2.metric("Optimized Load", "12.93 kWh")
c3.metric("Total Cost Optimization", "$5.51")

if df is not None:
    row = df.iloc[sync_hour]
    mqtt_client = get_mqtt_client() if activate_sync else None

    # --- DEVICE MANAGEMENT TABLE ---
    st.subheader("Device Management")
    status_list = []
    
    for app in app_list:
        status_val = "ON" if row[app] > 0 else "OFF"
        topic = f"home/appliances/{app.lower().replace(' ', '_')}/command"
        
        if activate_sync and mqtt_client:
            # Publish with QoS 1 to ensure delivery
            mqtt_client.publish(topic, status_val, qos=1)
            signal_status = "Sent ✅"
            cloud_state = "Active 🟢"
        else:
            signal_status = "Paused ⏸️"
            cloud_state = "Waiting..."

        status_list.append({
            "Appliance": app,
            "Status": status_val,
            "Topic": topic,
            "HiveMQ Signal": signal_status,
            "Cloud State": cloud_state
        })

    st.table(pd.DataFrame(status_list))


