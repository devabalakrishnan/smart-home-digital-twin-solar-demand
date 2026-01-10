import streamlit as st
import pandas as pd
import paho.mqtt.client as mqtt
import ssl
import time
import os
import numpy as np
import plotly.express as px

# --- 1. HIVEMQ CONFIGURATION ---
MQTT_HOST = "cyanqueen-29ab69cf.a01.euc1.aws.hivemq.cloud"
MQTT_PORT = 8883
MQTT_USER = "hivemq.client.1766925863216"
MQTT_PASS = "6<9SwUoy#0D8*dl:CNir"

# Use session_state to keep the connection alive between reruns
if 'mqtt_client' not in st.session_state:
    client = mqtt.Client(transport="tcp")
    client.username_pw_set(MQTT_USER, MQTT_PASS)
    client.tls_set(cert_reqs=ssl.CERT_NONE) 
    try:
        client.connect(MQTT_HOST, MQTT_PORT, 60)
        # Background loop handles SSL handshakes
        client.loop_start() 
        st.session_state.mqtt_client = client
        st.session_state.connected = True
    except Exception as e:
        st.session_state.connected = False
        st.error(f"Cloud Connection Failed: {e}")

# --- 2. DATA ENGINE ---
@st.cache_data
def load_and_prep_data():
    p_path, s_path = "data/next_day_prediction.csv", "data/solar_forecast.csv"
    if os.path.exists(p_path) and os.path.exists(s_path):
        df_p = pd.read_csv(p_path)
        df_s = pd.read_csv(s_path)
        df_p.columns = df_p.columns.str.strip()
        df_s.columns = df_s.columns.str.strip()
        
        # Sync solar data
        df_p['solar_gen'] = pd.to_numeric(df_s['Generation (kW)'], errors='coerce').fillna(0.0)
        
        apps = ['Fridge', 'Heater', 'Fans', 'Lights', 'TV', 'Microwave', 'Washing Machine']
        existing_apps = [c for c in apps if c in df_p.columns]
        for col in existing_apps:
            df_p[col] = pd.to_numeric(df_p[col], errors='coerce').fillna(0.0)
            
        df_p['total_demand'] = df_p[existing_apps].sum(axis=1)
        return df_p, existing_apps
    return None, []

# --- 3. UI INITIALIZATION ---
st.set_page_config(page_title="PPO Digital Twin", layout="wide")
st.title("🏡 Residential Digital Twin: Global Optimization")

if 'df' not in st.session_state:
    st.session_state.df, st.session_state.apps = load_and_prep_data()
if 'current_hr' not in st.session_state:
    st.session_state.current_hr = 0

df, app_list = st.session_state.df, st.session_state.apps

if df is not None:
    # --- METRICS ---
    idx = st.session_state.current_hr % len(df)
    row = df.iloc[idx]
    
    solar_offset = np.minimum(row['solar_gen'], row['total_demand'])
    savings = (solar_offset / row['total_demand'] * 100) if row['total_demand'] > 0 else 100

    c1, c2, c3 = st.columns(3)
    c1.metric("Current Demand", f"{row['total_demand']:.2f} kW")
    c2.metric("Solar Available", f"{row['solar_gen']:.2f} kW")
    c3.metric("Hourly Savings", f"{savings:.1f}%")

    st.divider()

    # --- THE BROADCAST LOOP ---
    st.subheader(f"🔌 Sending Appliance Commands to HiveMQ (Hour {idx}:00)")
    
    status_data = []
    if st.session_state.get('connected'):
        for app in app_list:
            is_on = row[app] > 0
            payload = "ON" if is_on else "OFF"
            topic = f"home/appliances/{app.lower().replace(' ', '_')}/command"
            
            # 1. Publish to the cloud
            st.session_state.mqtt_client.publish(topic, payload, qos=1)
            
            status_data.append({
                "Appliance": app,
                "Status": "🟢 ON" if is_on else "🔴 OFF",
                "MQTT Topic": topic
            })
        
        # 2. FORCE DATA OUT: This is the critical fix
        st.session_state.mqtt_client.loop(timeout=0.5) 
        
        st.table(pd.DataFrame(status_data))
        st.success(f"✅ All {len(app_list)} appliance states synced to HiveMQ.")
    else:
        st.error("MQTT Disconnected. Please restart the app.")

    # --- 4. RERUN CONTROL ---
    time.sleep(5) 
    st.session_state.current_hr = (idx + 1) % len(df)
    st.rerun()
