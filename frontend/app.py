import streamlit as st
import pandas as pd
import paho.mqtt.client as mqtt
import ssl
import time
import os
import numpy as np

# --- 1. MQTT CONFIGURATION ---
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

# --- 2. DATA LOADING (Force Refresh) ---
@st.cache_data
def load_data():
    path = "data/next_day_prediction.csv"
    if os.path.exists(path):
        df = pd.read_csv(path)
        df.columns = df.columns.str.strip()
        # Convert everything to float to ensure math works
        for col in df.columns:
            df[col] = pd.to_numeric(df[col], errors='coerce').fillna(0.0)
        
        app_cols = ['Fridge', 'Heater', 'Fans', 'Lights', 'TV', 'Microwave', 'Washing Machine']
        existing_apps = [c for c in app_cols if c in df.columns]
        df['total_demand'] = df[existing_apps].sum(axis=1)
        if 'solar_gen' not in df.columns:
            df['solar_gen'] = 0.0
        return df, existing_apps
    return None, []

# Load data
df, apps = load_data()

# --- 3. SESSION STATE ---
if 'current_hr' not in st.session_state:
    st.session_state.current_hr = 0
if 'auto_mode' not in st.session_state:
    st.session_state.auto_mode = False

# --- 4. DASHBOARD UI ---
st.title("🏡 Autonomous Digital Twin Dashboard")

if df is not None:
    st.sidebar.header("🤖 Control Center")
    st.session_state.auto_mode = st.sidebar.toggle("Enable AI Auto-Control", value=st.session_state.auto_mode)
    
    # --- DYNAMIC DATA SYNC: FETCH DATA BEFORE DISPLAY ---
    # This ensures that when the script reruns, it grabs the NEW values
    idx = st.session_state.current_hr % len(df)
    current_row = df.iloc[idx]
    
    # Global Metrics Calculation (recidivous every rerun)
    solar_util = np.minimum(df['solar_gen'], df['total_demand']).sum()
    co2 = solar_util * 0.4
    eff = (len(df[df['solar_gen'] > df['total_demand']]) / len(df)) * 100

    # DISPLAY METRICS
    c1, c2, c3, c4 = st.columns(4)
    # Forced update using the fresh current_row
    c1.metric("Demand", f"{current_row['total_demand']:.2f} kW")
    c2.metric("Solar", f"{current_row['solar_gen']:.2f} kW")
    c3.metric("Efficiency", f"{eff:.1f}%")
    c4.metric("CO2 Saved", f"{co2:.2f} kg")

    # --- 5. AUTOMATION LOGIC ---
    if st.session_state.auto_mode:
        st.sidebar.info(f"Synchronizing: Hour {idx}:00")
        
        # Decision logic based on the updated current_row
        ai_signal = float(current_row['solar_gen']) > float(current_row['total_demand'])
        st.sidebar.write(f"AI Decision: **{'HEATER ON' if ai_signal else 'HEATER OFF'}**")
        
        # Hardware Trigger
        send_mqtt_command(ai_signal)
        
        # Wait 2 seconds, increment time, then FORCE REFRESH
        time.sleep(2)
        st.session_state.current_hr = (idx + 1) % len(df)
        st.rerun() 
    else:
        st.session_state.current_hr = st.sidebar.slider("Select Hour", 0, len(df)-1, idx)

    # --- 6. VISUALIZATION ---
    st.subheader(f"📊 Energy Flow at Hour {idx}:00")
    st.line_chart(df[['solar_gen', 'total_demand']])
    st.bar_chart(current_row[apps])

else:
    st.error("🚨 Check data/next_day_prediction.csv path.")
