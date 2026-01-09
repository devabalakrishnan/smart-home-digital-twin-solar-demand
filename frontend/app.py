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

# --- 2. DATA LOADING (FORCED NUMERIC) ---
@st.cache_data
def load_data():
    path = "data/next_day_prediction.csv"
    if os.path.exists(path):
        df = pd.read_csv(path)
        df.columns = df.columns.str.strip()
        
        # FIX: Ensure all columns are numeric immediately
        for col in df.columns:
            df[col] = pd.to_numeric(df[col], errors='coerce').fillna(0.0)
        
        app_cols = ['Fridge', 'Heater', 'Fans', 'Lights', 'TV', 'Microwave', 'Washing Machine']
        existing_apps = [c for c in app_cols if c in df.columns]
        df['total_demand'] = df[existing_apps].sum(axis=1)
        
        if 'solar_gen' not in df.columns:
            df['solar_gen'] = 0.0
            
        return df, existing_apps
    return None, []

# Load data into session state
if 'df' not in st.session_state:
    st.session_state.df, st.session_state.apps = load_data()

# --- 3. SESSION STATE FOR AUTOMATION ---
if 'current_hr' not in st.session_state:
    st.session_state.current_hr = 0
if 'auto_mode' not in st.session_state:
    st.session_state.auto_mode = False

df = st.session_state.df
app_list = st.session_state.apps

# --- 4. UI AND DYNAMIC DATA SYNC ---
st.title("🏡 Autonomous Digital Twin Dashboard")

if df is not None:
    st.sidebar.header("🤖 Control Center")
    st.session_state.auto_mode = st.sidebar.toggle("Enable AI Auto-Control", value=st.session_state.auto_mode)
    
    # CRITICAL FIX: Re-calculate 'row' every time the script runs
    idx = st.session_state.current_hr % len(df)
    row = df.iloc[idx]
    
    # Logic for Efficiency and CO2 (Now recalculated with dynamic numeric values)
    solar_util = np.minimum(df['solar_gen'], df['total_demand']).sum()
    co2_saved = solar_util * 0.4
    efficiency = (len(df[df['solar_gen'] > df['total_demand']]) / len(df)) * 100

    if st.session_state.auto_mode:
        st.sidebar.info(f"Auto-Syncing Hour {idx}:00")
        
        # AI Decision
        ai_on = float(row['solar_gen']) > float(row['total_demand'])
        st.sidebar.write(f"Decision: **{'HEATER ON' if ai_on else 'HEATER OFF'}**")
        
        # Trigger MQTT
        send_mqtt_command(ai_on)
        
        # Advance hour and FORCED REFRESH
        time.sleep(2)
        st.session_state.current_hr = (idx + 1) % len(df)
        st.rerun() 
    else:
        st.session_state.current_hr = st.sidebar.slider("Select Hour", 0, len(df)-1, idx)
        row = df.iloc[st.session_state.current_hr]

    # --- 5. METRICS DISPLAY ---
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Demand", f"{row['total_demand']:.2f} kW")
    c2.metric("Solar", f"{row['solar_gen']:.2f} kW")
    c3.metric("Efficiency", f"{efficiency:.1f}%")
    c4.metric("CO2 Saved", f"{co2_saved:.2f} kg")

    # --- 6. CHARTS ---
    st.subheader(f"📊 Live Data at Hour {idx}:00")
    st.line_chart(df[['solar_gen', 'total_demand']])
    
    st.write("### Load Breakdown")
    st.bar_chart(row[app_list])

else:
    st.error("🚨 CSV file not found or data is corrupted.")
