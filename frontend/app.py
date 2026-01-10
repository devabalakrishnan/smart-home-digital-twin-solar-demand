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

# PERSISTENT CLIENT
if 'mqtt_client' not in st.session_state:
    # Use a unique Client ID to avoid being kicked off by the broker
    client = mqtt.Client(client_id="DigitalTwin_Streamlit", transport="tcp")
    client.username_pw_set(MQTT_USER, MQTT_PASS)
    client.tls_set(cert_reqs=ssl.CERT_NONE)
    
    try:
        client.connect(MQTT_HOST, MQTT_PORT, 60)
        # loop_start creates a background thread to handle all messaging
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
        existing_apps = [c for c in apps if c in df.columns]
        for col in existing_apps:
            df[col] = pd.to_numeric(df[col], errors='coerce').fillna(0.0)
        
        df['total_demand'] = df[existing_apps].sum(axis=1)
        return df, existing_apps
    return None, []

# --- 3. UI LAYOUT ---
st.set_page_config(page_title="PPO Digital Twin", layout="wide")
st.title("🏡 Residential Digital Twin: Automatic Cloud Sync")

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

    # --- 4. THE AUTOMATIC SYNC ---
    if st.session_state.get('connected'):
        st.info("🛰️ Streaming appliance states to HiveMQ Cloud...")
        status_table = []
        
        for app in app_list:
            status = "ON" if row[app] > 0 else "OFF"
            topic = f"home/appliances/{app.lower().replace(' ', '_')}/command"
            
            # CRITICAL FIX: Publish WITHOUT waiting for confirmation.
            # This allows the app to send all 7 messages instantly without crashing.
            st.session_state.mqtt_client.publish(topic, status, qos=1)
            
            status_table.append({
                "Appliance": app, 
                "Status": status, 
                "Topic": topic,
                "Cloud Sync": "🟢 Active"
            })
        
        st.table(pd.DataFrame(status_table))
        st.success(f"✅ Data for Hour {idx} sent to HiveMQ.")
    else:
        st.error("❌ MQTT Disconnected. Check Internet.")

    # --- RERUN TIMER ---
    time.sleep(10) # 10 seconds allows the cloud broker to process the burst of 7 messages
    st.session_state.current_hr += 1
    st.rerun()
