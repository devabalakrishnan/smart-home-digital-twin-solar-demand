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

# --- 2. DATA LOADING (Force Numeric & Column Check) ---
def load_data():
    path = "data/next_day_prediction.csv"
    if os.path.exists(path):
        df = pd.read_csv(path)
        df.columns = df.columns.str.strip() # Remove spaces
        
        # Convert all columns to numeric floats
        for col in df.columns:
            df[col] = pd.to_numeric(df[col], errors='coerce').fillna(0.0)
        
        app_cols = ['Fridge', 'Heater', 'Fans', 'Lights', 'TV', 'Microwave', 'Washing Machine']
        existing_apps = [c for c in app_cols if c in df.columns]
        df['total_demand'] = df[existing_apps].sum(axis=1)
        
        # Ensure solar_gen is valid
        if 'solar_gen' not in df.columns:
            st.error("⚠️ Column 'solar_gen' not found in CSV! Defaulting to 0.0")
            df['solar_gen'] = 0.0
            
        return df, existing_apps
    return None, []

# Load data every rerun to ensure fresh calculation
df, apps = load_data()

# --- 3. SESSION STATE ---
if 'current_hr' not in st.session_state:
    st.session_state.current_hr = 0
if 'auto_mode' not in st.session_state:
    st.session_state.auto_mode = False

# --- 4. DYNAMIC CALCULATION LAYER ---
if df is not None:
    # 1. Select current hour index
    idx = st.session_state.current_hr % len(df)
    row = df.iloc[idx]
    
    # 2. RE-CALCULATE Global Metrics every single time
    # Solar utilized is the minimum of what is produced vs what is needed
    solar_utilized_total = np.minimum(df['solar_gen'], df['total_demand']).sum()
    co2_val = solar_utilized_total * 0.4
    
    # Efficiency is the % of hours where Solar covers the Demand
    solar_hours = len(df[df['solar_gen'] > df['total_demand']])
    eff_val = (solar_hours / len(df)) * 100

    # --- 5. DASHBOARD UI ---
    st.title("🏡 Autonomous Digital Twin Dashboard")
    
    st.sidebar.header("🤖 Control Center")
    st.session_state.auto_mode = st.sidebar.toggle("Enable AI Auto-Control", value=st.session_state.auto_mode)

    # Metrics Display (Now using the fresh variables)
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Demand", f"{row['total_demand']:.2f} kW")
    c2.metric("Solar", f"{row['solar_gen']:.2f} kW")
    c3.metric("Efficiency", f"{eff_val:.1f}%")
    c4.metric("CO2 Saved", f"{co2_val:.2f} kg")

    # --- 6. AUTOMATION LOOP ---
    if st.session_state.auto_mode:
        st.sidebar.info(f"Syncing Hour {idx}:00")
        
        # Decision logic
        ai_signal = float(row['solar_gen']) > float(row['total_demand'])
        st.sidebar.write(f"AI Decision: **{'HEATER ON' if ai_signal else 'HEATER OFF'}**")
        
        send_mqtt_command(ai_signal) # Hardware Sync
        
        time.sleep(2)
        st.session_state.current_hr = (idx + 1) % len(df)
        st.rerun() # Forces the whole page to recalculate metrics
    else:
        st.session_state.current_hr = st.sidebar.slider("Select Hour", 0, len(df)-1, idx)

    # --- 7. CHARTS ---
    st.subheader(f"📊 Energy Flow at Hour {idx}:00")
    st.line_chart(df[['solar_gen', 'total_demand']])
    st.bar_chart(row[apps])

else:
    st.error("🚨 CSV file missing.")
