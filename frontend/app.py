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

# Use session_state to maintain a single, stable connection
if 'mqtt_client' not in st.session_state:
    # Use a unique Client ID to prevent being disconnected by the broker
    client = mqtt.Client(client_id="Streamlit_Digital_Twin_Final", transport="tcp")
    client.username_pw_set(MQTT_USER, MQTT_PASS)
    client.tls_set(cert_reqs=ssl.CERT_NONE) # Mandatory for HiveMQ Cloud
    
    try:
        client.connect(MQTT_HOST, MQTT_PORT, 60)
        # loop_start() runs the networking in a separate thread to prevent UI freezing
        client.loop_start() 
        st.session_state.mqtt_client = client
        st.session_state.connected = True
    except Exception as e:
        st.session_state.connected = False
        st.error(f"MQTT Connection Error: {e}")

# --- 2. DATA ENGINE ---
@st.cache_data
def load_data():
    p_path, s_path = "data/next_day_prediction.csv", "data/solar_forecast.csv"
    if os.path.exists(p_path) and os.path.exists(s_path):
        df = pd.read_csv(p_path)
        df_s = pd.read_csv(s_path)
        df.columns = df.columns.str.strip()
        df_s.columns = df_s.columns.str.strip()
        
        # Merge solar generation data
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
    
    # Dashboard Metrics
    st.subheader(f"⏱️ Simulating Hour {idx}:00")
    c1, c2 = st.columns(2)
    c1.metric("Total Demand", f"{row['total_demand']:.2f} kW")
    c2.metric("Solar Gen", f"{row['solar_gen']:.2f} kW")
    st.divider()

    # --- 4. THE AUTOMATIC BROADCAST ---
    if st.session_state.get('connected'):
        st.info("🛰️ Sending appliance status to HiveMQ Cloud...")
        status_table = []
        
        for app in app_list:
            status = "ON" if row[app] > 0 else "OFF"
            # Format topic to match your HiveMQ subscription
            topic = f"home/appliances/{app.lower().replace(' ', '_')}/command"
            
            # CRITICAL: We do NOT use wait_for_publish() here. 
            # This prevents the RuntimeError and "Delay/Retry" freeze.
            st.session_state.mqtt_client.publish(topic, status, qos=1)
            
            status_table.append({
                "Appliance": app, 
                "Status": status, 
                "Topic": topic,
                "Cloud State": "🟢 Active"
            })
        
        st.table(pd.DataFrame(status_table))
        st.success(f"✅ Data for Hour {idx} successfully pushed to network buffer.")
    else:
        st.error("❌ Disconnected from HiveMQ. Please check your credentials.")

    # --- RERUN TIMER ---
    # Increased time to 8 seconds to give HiveMQ time to process the burst
    time.sleep(8) 
    st.session_state.current_hr += 1
    st.rerun()
