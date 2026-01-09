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

# --- 2. DATA LOADING & CLEANING ---
@st.cache_data
def load_and_clean_data():
    path = "data/next_day_prediction.csv"
    if os.path.exists(path):
        df = pd.read_csv(path)
        df.columns = df.columns.str.strip()
        # Force all columns to float to avoid "float and str" errors
        for col in df.columns:
            df[col] = pd.to_numeric(df[col], errors='coerce').fillna(0.0)
        
        # Define appliance list for charts
        app_list = ['Fridge', 'Heater', 'Fans', 'Lights', 'TV', 'Microwave', 'Washing Machine']
        existing_apps = [c for c in app_list if c in df.columns]
        
        # Ensure calculated columns exist
        df['total_demand'] = df[existing_apps].sum(axis=1)
        if 'solar_gen' not in df.columns:
            df['solar_gen'] = 0.0
            
        return df, existing_apps
    return None, []

# --- 3. STATE INITIALIZATION ---
if 'current_hr' not in st.session_state:
    st.session_state.current_hr = 0
if 'auto_mode' not in st.session_state:
    st.session_state.auto_mode = False

df, apps = load_and_clean_data()

# --- 4. DASHBOARD UI ---
st.title("🏡 Autonomous Digital Twin Dashboard")

if df is not None:
    # Sidebar Controls
    st.sidebar.header("🤖 Control Center")
    st.session_state.auto_mode = st.sidebar.toggle("Enable AI Auto-Control", value=st.session_state.auto_mode)
    
    # DYNAMIC DATA SYNC: Update index and row immediately
    idx = st.session_state.current_hr % len(df)
    row = df.iloc[idx]
    
    # AI Logic: Decision based on current hour data
    ai_on = float(row['solar_gen']) > float(row['total_demand'])

    if st.session_state.auto_mode:
        st.sidebar.info(f"Auto-Syncing: Hour {idx}:00")
        st.sidebar.write(f"AI Decision: **{'HEATER ON' if ai_on else 'HEATER OFF'}**")
        
        # Push to Physical Layer
        send_mqtt_command(ai_on)
        
        # Advance time and rerun to refresh all values
        time.sleep(2)
        st.session_state.current_hr = (idx + 1) % len(df)
        st.rerun() 
    else:
        st.session_state.current_hr = st.sidebar.slider("Manual Hour Select", 0, len(df)-1, idx)
        row = df.iloc[st.session_state.current_hr]

    # --- 5. UPDATED METRICS ---
    # Global daily stats
    solar_util = np.minimum(df['solar_gen'], df['total_demand']).sum()
    co2 = solar_util * 0.4
    eff = (len(df[df['solar_gen'] > df['total_demand']]) / len(df)) * 100

    col1, col2, col3, col4 = st.columns(4)
    col1.metric("Demand", f"{row['total_demand']:.2f} kW")
    col2.metric("Solar", f"{row['solar_gen']:.2f} kW")
    col3.metric("Efficiency", f"{eff:.1f}%")
    col4.metric("CO2 Saved", f"{co2:.2f} kg")

    # --- 6. VISUALIZATION ---
    st.subheader(f"📊 Live Data at Hour {idx}:00")
    st.line_chart(df[['solar_gen', 'total_demand']])
    
    st.write("### Current Load Breakdown")
    st.bar_chart(row[apps])
else:
    st.error("🚨 Could not load data from /data/next_day_prediction.csv")
