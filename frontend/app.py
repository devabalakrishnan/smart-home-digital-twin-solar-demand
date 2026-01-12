import streamlit as st
import pandas as pd
import paho.mqtt.client as mqtt
import ssl
import time
import os
import random

# --- 1. HIVEMQ CONFIGURATION ---
MQTT_HOST = "cyanqueen-29ab69cf.a01.euc1.aws.hivemq.cloud"
MQTT_PORT = 8883
MQTT_USER = "hivemq.client.1766925863216"
MQTT_PASS = "6<9SwUoy#0D8*dl:CNir" 

# Persistent background connection with unique ID to prevent "Another client connected" error
if 'mqtt_client' not in st.session_state:
    unique_id = f"Twin_Broadcaster_{random.randint(1000, 9999)}"
    client = mqtt.Client(client_id=unique_id, transport="tcp")
    client.username_pw_set(MQTT_USER, MQTT_PASS)
    client.tls_set(cert_reqs=ssl.CERT_NONE)
    try:
        client.connect(MQTT_HOST, MQTT_PORT, 60)
        client.loop_start() 
        st.session_state.mqtt_client = client
        st.session_state.connected = True
    except Exception:
        st.session_state.connected = False

# --- 2. DATA LOADING & SIMULATION STATE ---
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
        return df, apps
    return None, []

df, app_list = load_data()
if 'current_hr' not in st.session_state:
    st.session_state.current_hr = 0

# --- 3. DASHBOARD UI ---
st.set_page_config(page_title="PPO Energy Twin", layout="wide")
st.title("🏡 Residential Digital Twin: Home Energy Hub")

if df is not None:
    idx = st.session_state.current_hr % len(df)
    row = df.iloc[idx]
    
    # CALCULATE METRICS
    net_load = row['total_demand'] - row['solar_gen']
    grid_status = "Buying 🔴" if net_load > 0 else "Selling 🟢"
    total_net_day = (df['total_demand'] - df['solar_gen']).sum()
    cost_opt = 15.5 # Example percentage based on PPO model
    current_savings = abs(net_load) * 0.15 if net_load < 0 else 0.01 # Mock saving

    # --- ROW 1: DEMAND, SOLAR, NET LOAD ---
    col1, col2, col3 = st.columns(3)
    with col1:
        st.metric("Demand (Current)", f"{row['total_demand']:.2f} kW")
        st.metric("Demand (Net Avg)", f"{df['total_demand'].mean():.2f} kW")
    with col2:
        st.metric("Solar (Current)", f"{row['solar_gen']:.2f} kW")
        st.metric("Solar (Net Avg)", f"{df['solar_gen'].mean():.2f} kW")
    with col3:
        st.metric("Net Load", f"{abs(net_load):.2f} kW", delta=grid_status)
        st.metric("Total Net (Day)", f"{total_net_day:.2f} kWh")

    st.divider()

    # --- ROW 2: COST OPTIMIZATION ---
    opt1, opt2 = st.columns(2)
    opt1.metric("Cost Optimization", f"{cost_opt}%", delta="Current Hour")
    opt2.metric("Cost Saving (Current)", f"${current_savings:.2f}", delta="Net Saving")

    st.divider()

    # --- DEVICE MANAGEMENT & SYNC ---
    st.subheader("Device Management")
    
    # MANUAL SLIDE TRIGGER: Signals only send when this is ON
    sync_on = st.toggle("🚀 Activate Cloud Sync (Send to HiveMQ)")

    status_data = []
    for app in app_list:
        status_val = "ON" if row[app] > 0 else "OFF"
        topic = f"home/appliances/{app.lower().replace(' ', '_')}/command"
        
        # SEND SIGNAL LOGIC
        send_status = "Sent ✅" if sync_on else "Waiting..."
        if sync_on and st.session_state.get('connected'):
            st.session_state.mqtt_client.publish(topic, status_val, qos=1)
            time.sleep(0.1) # Buffer pacing for ESP32 stability
        
        status_data.append({
            "Appliance": app,
            "Status": status_val,
            "HiveMQ Signal": send_status,
            "Topic": topic
        })

    # Display Appliance Table
    st.table(pd.DataFrame(status_data))

    # --- SIMULATION CONTROL ---
    if st.button("Advance to Next Hour ➡️"):
        st.session_state.current_hr += 1
        st.rerun()

    if sync_on:
        st.info("Continuous Sync Active. Broadcasting real-time state...")
        time.sleep(8)
        st.session_state.current_hr += 1
        st.rerun()
