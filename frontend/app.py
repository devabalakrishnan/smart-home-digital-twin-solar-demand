import streamlit as st
import pandas as pd
import paho.mqtt.client as mqtt
import ssl
import time
import os
import numpy as np

# --- 1. HIVEMQ CONFIGURATION ---
MQTT_HOST = "cyanqueen-29ab69cf.a01.euc1.aws.hivemq.cloud"
MQTT_PORT = 8883
MQTT_USER = "hivemq.client.1766925863216"
MQTT_PASS = "6<9SwUoy#0D8*dl:CNir"

# Use session_state to keep the connection alive
if 'mqtt_client' not in st.session_state:
    client = mqtt.Client(transport="tcp")
    client.username_pw_set(MQTT_USER, MQTT_PASS)
    client.tls_set(cert_reqs=ssl.CERT_NONE) 
    try:
        client.connect(MQTT_HOST, MQTT_PORT, 60)
        # loop_start() is critical; it runs networking in a separate thread
        client.loop_start() 
        st.session_state.mqtt_client = client
        st.session_state.connected = True
    except Exception as e:
        st.session_state.connected = False
        st.error(f"MQTT Connection Error: {e}")

# --- 2. DATA LOADING ---
@st.cache_data
def load_data():
    p_path, s_path = "data/next_day_prediction.csv", "data/solar_forecast.csv"
    if os.path.exists(p_path) and os.path.exists(s_path):
        df = pd.read_csv(p_path)
        df_s = pd.read_csv(s_path)
        df.columns = df.columns.str.strip()
        df_s.columns = df_s.columns.str.strip()
        df['solar_gen'] = pd.to_numeric(df_s['Generation (kW)'], errors='coerce').fillna(0.0)
        
        apps = ['Fridge', 'Heater', 'Fans', 'Lights', 'TV', 'Microwave', 'Washing Machine']
        for col in apps:
            if col in df.columns:
                df[col] = pd.to_numeric(df[col], errors='coerce').fillna(0.0)
        
        df['total_demand'] = df[[c for c in apps if c in df.columns]].sum(axis=1)
        return df, [c for c in apps if c in df.columns]
    return None, []

# --- 3. UI LAYOUT ---
st.set_page_config(page_title="PPO Digital Twin", layout="wide")
st.title("🏡 Residential Digital Twin: Reliable Cloud Sync")

if 'df' not in st.session_state:
    st.session_state.df, st.session_state.apps = load_data()
if 'current_hr' not in st.session_state:
    st.session_state.current_hr = 0

df, app_list = st.session_state.df, st.session_state.apps

if df is not None:
    idx = st.session_state.current_hr % len(df)
    row = df.iloc[idx]
    
    st.subheader(f"⏱️ Simulating Hour {idx}:00")
    c1, c2 = st.columns(2)
    c1.metric("Total Demand", f"{row['total_demand']:.2f} kW")
    c2.metric("Solar Gen", f"{row['solar_gen']:.2f} kW")

    st.divider()

    # --- 4. ASYNCHRONOUS BROADCAST (Fixed Error) ---
    if st.session_state.get('connected'):
        st.info("🛰️ Pushing appliance states to HiveMQ Cloud...")
        status_table = []
        
        for app in app_list:
            status = "ON" if row[app] > 0 else "OFF"
            topic = f"home/appliances/{app.lower().replace(' ', '_')}/command"
            
            # REMOVED wait_for_publish() to prevent the RuntimeError
            # This allows the app to stay smooth while the background loop sends data
            st.session_state.mqtt_client.publish(topic, status, qos=1)
            
            status_table.append({
                "Appliance": app, 
                "Status": status, 
                "Topic": topic,
                "Cloud State": "📡 Sent to Buffer"
            })
        
        st.table(pd.DataFrame(status_table))
        st.success("✅ Dashboard Updated. Messages are streaming in background.")
    else:
        st.error("❌ Disconnected from HiveMQ.")

    # --- RERUN TIMER ---
    time.sleep(8) # Increased time to let the cloud catch up
    st.session_state.current_hr += 1
    st.rerun()
