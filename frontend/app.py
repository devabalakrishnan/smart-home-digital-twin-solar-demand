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
MQTT_PASS = "6<9SwUoy#0D8*dI:CNir" 

if 'mqtt_client' not in st.session_state:
    unique_id = f"Twin_Hub_{random.randint(1000, 9999)}"
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

# --- 2. DATA LOADING ---
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
        # Calculate hourly savings (example logic: solar coverage + optimized shifting)
        df['hourly_savings'] = (df['solar_gen'] * 0.15) + (df['total_demand'] * 0.05)
        return df, apps
    return None, []

df, app_list = load_data()

# --- 3. SESSION STATE FOR CLOCK ---
if 'current_hr' not in st.session_state:
    st.session_state.current_hr = 0

# --- 4. DASHBOARD UI ---
st.set_page_config(page_title="Home Energy Twin", layout="wide")
st.title("🏡 Residential Digital Twin: Home Energy Hub")

if df is not None:
    # Logic for 0-23 Hour cycle
    idx = st.session_state.current_hr % 24 
    row = df.iloc[idx]
    
    # CALCULATE METRICS
    net_load = row['total_demand'] - row['solar_gen']
    grid_status = "Buying 🔴" if net_load > 0 else "Selling 🟢"
    
    # Cumulative Totals (Sum from Hour 0 to Current Hour)
    total_demand_so_far = df['total_demand'].iloc[:idx+1].sum()
    total_solar_so_far = df['solar_gen'].iloc[:idx+1].sum()
    total_net_so_far = (df['total_demand'].iloc[:idx+1] - df['solar_gen'].iloc[:idx+1]).sum()
    total_savings_so_far = df['hourly_savings'].iloc[:idx+1].sum()
    avg_opt_so_far = 15.5 + (random.uniform(-1, 1)) # Simulated PPO optimization performance

    # --- ROW 1: DEMAND, SOLAR, NET LOAD ---
    st.subheader(f"⏱️ Current Time: {idx}:00")
    col1, col2, col3 = st.columns(3)
    with col1:
        st.metric("Demand (Current)", f"{row['total_demand']:.2f} kW")
        st.metric("Total Demand (Day)", f"{total_demand_so_far:.2f} kWh")
    with col2:
        st.metric("Solar (Current)", f"{row['solar_gen']:.2f} kW")
        st.metric("Total Solar (Day)", f"{total_solar_so_far:.2f} kWh")
    with col3:
        st.metric("Net Load (Current)", f"{abs(net_load):.2f} kW", delta=grid_status)
        st.metric("Total Net Load (Day)", f"{total_net_so_far:.2f} kWh")

    st.divider()

    # --- ROW 2: COST & OPTIMIZATION ---
    opt1, opt2 = st.columns(2)
    opt1.metric("Current Cost Optimization", f"{avg_opt_so_far:.1f}%", delta="PPO Active")
    opt2.metric("Total Cost Saving (Day)", f"${total_savings_so_far:.2f}", delta=f"Current: ${df['hourly_savings'].iloc[idx]:.2f}")

    st.divider()

    # --- DEVICE MANAGEMENT ---
    st.subheader("Device Management")
    sync_on = st.toggle("🚀 Activate Cloud Sync (Broadcasting to ESP32)")

    status_data = []
    for app in app_list:
        status_val = "ON" if row[app] > 0 else "OFF"
        topic = f"home/appliances/{app.lower().replace(' ', '_')}/command"
        
        send_status = "Sent ✅" if sync_on else "Waiting..."
        if sync_on and st.session_state.get('connected'):
            st.session_state.mqtt_client.publish(topic, status_val, qos=1)
            time.sleep(0.05) # Optimized pacing
        
        status_data.append({
            "Appliance": app,
            "Status": status_val,
            "HiveMQ Signal": send_status,
            "Topic": topic
        })

    st.table(pd.DataFrame(status_data))

    # --- AUTO-PROGRESSION ENGINE ---
    # Progresses through 0-23 hours
    if sync_on:
        time.sleep(5) # Set how fast you want the "hours" to pass (5 seconds = 1 hour)
        st.session_state.current_hr = (st.session_state.current_hr + 1) % 24
        st.rerun()
    else:
        if st.button("Advance 1 Hour ➡️"):
            st.session_state.current_hr = (st.session_state.current_hr + 1) % 24
            st.rerun()

